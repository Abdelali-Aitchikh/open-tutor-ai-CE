"""
R2V GPU Server Service
======================

Service for communicating with the local GPU server for video generation.
Handles Module 3 (DiT + TTS generation) and retrieves generated assets.

The GPU server is expected to expose the following endpoints:
- POST /api/v1/generate: Start video generation from storyboard
- GET /api/v1/status/{job_id}: Check generation status
- GET /api/v1/result/{job_id}: Download generated assets

Author: Open TutorAI Core Team
License: MIT
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from enum import Enum

import aiohttp

from open_tutorai.r2v_config.r2v_config import get_r2v_config, GPUServerConfig

log = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

class GenerationStatus(Enum):
    """Status of a video generation job."""
    PENDING = "pending"
    PROCESSING = "processing"
    GENERATING_FRAMES = "generating_frames"
    GENERATING_AUDIO = "generating_audio"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GenerationJob:
    """Represents a video generation job on the GPU server."""
    job_id: str
    status: GenerationStatus
    progress: float  # 0.0 to 1.0
    message: str
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationJob":
        """Create a GenerationJob from API response dictionary."""
        return cls(
            job_id=data.get("job_id", ""),
            status=GenerationStatus(data.get("status", "pending")),
            progress=float(data.get("progress", 0.0)),
            message=data.get("message", ""),
            video_path=Path(data["video_path"]) if data.get("video_path") else None,
            audio_path=Path(data["audio_path"]) if data.get("audio_path") else None,
            error=data.get("error"),
        )


# =============================================================================
# GPU SERVER CLIENT
# =============================================================================

class GPUServerClient:
    """
    Async client for communicating with the local GPU server.
    
    The GPU server handles the heavy lifting of video generation:
    - DiT (Diffusion Transformer) for frame synthesis
    - TTS (Text-to-Speech) for narration audio
    - Optional: FFmpeg assembly (if not done by main backend)
    """
    
    def __init__(self, config: Optional[GPUServerConfig] = None):
        """
        Initialize the GPU server client.
        
        Args:
            config: GPU server configuration. If None, uses global config.
        """
        self.config = config or get_r2v_config().gpu_server
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def base_url(self) -> str:
        """Get the base URL for the GPU server."""
        return self.config.url.rstrip("/")
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def health_check(self) -> dict[str, Any]:
        """
        Check if the GPU server is healthy and available.
        
        Returns:
            Health status dictionary
            
        Raises:
            aiohttp.ClientError: If server is unreachable
        """
        session = await self._ensure_session()
        url = f"{self.base_url}{self.config.health_endpoint}"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"status": "unhealthy", "code": response.status}
        except aiohttp.ClientError as e:
            log.error("[GPUServer] Health check failed: %s", str(e))
            return {"status": "unreachable", "error": str(e)}
    
    async def start_generation(
        self,
        storyboard: dict[str, Any],
        output_dir: Path,
        language: str = "fr",
    ) -> str:
        """
        Start a video generation job on the GPU server.
        
        Args:
            storyboard: Storyboard JSON from Module 2
            output_dir: Directory to save generated files
            language: Language code for TTS
            
        Returns:
            Job ID for tracking the generation
            
        Raises:
            aiohttp.ClientError: On HTTP errors
            ValueError: On API errors
        """
        session = await self._ensure_session()
        url = f"{self.base_url}{self.config.generate_endpoint}"
        
        payload = {
            "storyboard": storyboard,
            "output_dir": str(output_dir),
            "language": language,
            "settings": {
                "dit_model": self.config.dit_model,
                "temporal_consistency_weight": self.config.temporal_consistency_weight,
                "fps": storyboard.get("video_spec", {}).get("fps", 24),
                "resolution": storyboard.get("video_spec", {}).get("resolution", "1280x720"),
            }
        }
        
        log.info("[GPUServer] Starting generation job | url=%s", url)
        
        async with session.post(url, json=payload) as response:
            if response.status not in (200, 201, 202):
                error_text = await response.text()
                log.error("[GPUServer] Failed to start job: %s", error_text)
                raise ValueError(f"GPU server error {response.status}: {error_text[:200]}")
            
            result = await response.json()
            job_id = result.get("job_id")
            
            if not job_id:
                raise ValueError("GPU server did not return a job_id")
            
            log.info("[GPUServer] Job started | job_id=%s", job_id)
            return job_id
    
    async def get_status(self, job_id: str) -> GenerationJob:
        """
        Get the status of a generation job.
        
        Args:
            job_id: The job ID returned by start_generation
            
        Returns:
            GenerationJob with current status
        """
        session = await self._ensure_session()
        url = f"{self.base_url}{self.config.status_endpoint}/{job_id}"
        
        async with session.get(url) as response:
            if response.status != 200:
                error_text = await response.text()
                log.error("[GPUServer] Status check failed: %s", error_text)
                return GenerationJob(
                    job_id=job_id,
                    status=GenerationStatus.FAILED,
                    progress=0.0,
                    message="Failed to get status",
                    error=error_text,
                )
            
            result = await response.json()
            return GenerationJob.from_dict(result)
    
    async def download_result(
        self,
        job_id: str,
        destination: Path,
    ) -> Path:
        """
        Download the generated video file.
        
        Args:
            job_id: The job ID
            destination: Local path to save the video
            
        Returns:
            Path to the downloaded video
        """
        session = await self._ensure_session()
        url = f"{self.base_url}/api/v1/result/{job_id}/video"
        
        log.info("[GPUServer] Downloading result | job_id=%s | dest=%s", job_id, destination)
        
        async with session.get(url) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ValueError(f"Failed to download video: {error_text[:200]}")
            
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            with open(destination, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
        
        log.info("[GPUServer] Download complete | size=%d bytes", destination.stat().st_size)
        return destination
    
    async def wait_for_completion(
        self,
        job_id: str,
        poll_interval: float = 2.0,
        progress_callback: Optional[callable] = None,
    ) -> GenerationJob:
        """
        Wait for a generation job to complete, polling periodically.
        
        Args:
            job_id: The job ID to monitor
            poll_interval: Seconds between status checks
            progress_callback: Optional async callback(job: GenerationJob) for progress updates
            
        Returns:
            Final GenerationJob (completed or failed)
        """
        log.info("[GPUServer] Waiting for job completion | job_id=%s", job_id)
        
        while True:
            job = await self.get_status(job_id)
            
            if progress_callback:
                await progress_callback(job)
            
            if job.status == GenerationStatus.COMPLETED:
                log.info("[GPUServer] Job completed | job_id=%s", job_id)
                return job
            
            if job.status == GenerationStatus.FAILED:
                log.error("[GPUServer] Job failed | job_id=%s | error=%s", job_id, job.error)
                return job
            
            await asyncio.sleep(poll_interval)


# =============================================================================
# FALLBACK: LOCAL SIMULATION MODE
# =============================================================================

class SimulatedGPUServer:
    """
    Simulated GPU server for development/testing when no GPU server is available.
    
    Generates a placeholder video using the existing mock MP4 generator.
    """
    
    def __init__(self, output_dir: Path):
        """
        Initialize the simulated GPU server.
        
        Args:
            output_dir: Directory to save generated files
        """
        self.output_dir = output_dir
        self._job_counter = 0
        self._jobs: dict[str, GenerationJob] = {}
    
    async def health_check(self) -> dict[str, Any]:
        """Always returns healthy for simulation."""
        return {"status": "healthy", "mode": "simulation"}
    
    async def start_generation(
        self,
        storyboard: dict[str, Any],
        output_dir: Path,
        language: str = "fr",
    ) -> str:
        """
        Start a simulated generation job.
        
        Returns immediately with a job ID; actual "generation" happens in wait_for_completion.
        """
        self._job_counter += 1
        job_id = f"sim_{self._job_counter}"
        
        self._jobs[job_id] = GenerationJob(
            job_id=job_id,
            status=GenerationStatus.PENDING,
            progress=0.0,
            message="Simulation job started",
        )
        
        log.info("[SimulatedGPU] Job started | job_id=%s", job_id)
        return job_id
    
    async def get_status(self, job_id: str) -> GenerationJob:
        """Get status of a simulated job."""
        return self._jobs.get(job_id, GenerationJob(
            job_id=job_id,
            status=GenerationStatus.FAILED,
            progress=0.0,
            message="Job not found",
            error="Unknown job ID",
        ))
    
    async def simulate_generation(
        self,
        job_id: str,
        storyboard: dict[str, Any],
        duration_sec: int,
        progress_callback: Optional[callable] = None,
    ) -> GenerationJob:
        """
        Simulate the video generation process with progress updates.
        
        This mimics the timing of real generation while producing a placeholder video.
        """
        job = self._jobs.get(job_id)
        if not job:
            return GenerationJob(
                job_id=job_id,
                status=GenerationStatus.FAILED,
                progress=0.0,
                message="Job not found",
            )
        
        # Simulate frame generation (50% of time)
        stages = [
            (GenerationStatus.GENERATING_FRAMES, 0.0, 0.5, "Generating video frames..."),
            (GenerationStatus.GENERATING_AUDIO, 0.5, 0.8, "Synthesizing narration audio..."),
            (GenerationStatus.ASSEMBLING, 0.8, 1.0, "Assembling final video..."),
        ]
        
        for status, start_progress, end_progress, message in stages:
            job.status = status
            
            steps = 5
            for i in range(steps):
                job.progress = start_progress + (end_progress - start_progress) * (i / steps)
                job.message = message
                
                if progress_callback:
                    await progress_callback(job)
                
                await asyncio.sleep(0.3)  # Simulate processing time
        
        # Mark as completed
        job.status = GenerationStatus.COMPLETED
        job.progress = 1.0
        job.message = "Generation complete"
        
        if progress_callback:
            await progress_callback(job)
        
        return job


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

async def get_gpu_client(
    config: Optional[GPUServerConfig] = None,
) -> GPUServerClient | SimulatedGPUServer:
    """
    Get the appropriate GPU client based on configuration and availability.
    
    If the GPU server is unreachable and simulation mode is enabled,
    returns a SimulatedGPUServer instead.
    
    Args:
        config: Optional GPU server configuration
        
    Returns:
        GPUServerClient or SimulatedGPUServer
    """
    r2v_config = get_r2v_config()
    
    # If simulation mode is explicitly enabled, use simulated server
    if r2v_config.enable_simulation:
        log.info("[R2V] Using simulated GPU server (R2V_ENABLE_SIMULATION=true)")
        return SimulatedGPUServer(r2v_config.output_dir)
    
    # Try to connect to real GPU server
    client = GPUServerClient(config)
    health = await client.health_check()
    
    if health.get("status") == "healthy":
        log.info("[R2V] Connected to GPU server: %s", client.base_url)
        return client
    
    # Fallback to simulation if server is unreachable
    log.warning(
        "[R2V] GPU server unreachable at %s, falling back to simulation mode",
        client.base_url
    )
    await client.close()
    return SimulatedGPUServer(r2v_config.output_dir)
