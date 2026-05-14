"""
R2V FFmpeg Assembly Service
===========================

Service for assembling video frames and audio into final MP4 output.
Handles Module 4: Video assembly with FFmpeg.

This module provides:
- Frame sequence to video encoding
- Audio/video synchronization
- Subtitle burning (optional)
- VTT generation for web players

Author: Open TutorAI Core Team
License: MIT
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass

from open_tutorai.r2v_config.r2v_config import get_r2v_config, FFmpegConfig

log = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class AssemblyResult:
    """Result of video assembly operation."""
    success: bool
    video_path: Optional[Path] = None
    vtt_path: Optional[Path] = None
    duration_sec: float = 0.0
    file_size: int = 0
    error: Optional[str] = None


@dataclass
class SubtitleSegment:
    """A single subtitle segment for VTT generation."""
    start_sec: float
    end_sec: float
    text: str


# =============================================================================
# VTT GENERATION
# =============================================================================

def generate_vtt(
    segments: list[SubtitleSegment],
    output_path: Path,
) -> Path:
    """
    Generate a WebVTT subtitle file from narration segments.
    
    Args:
        segments: List of subtitle segments
        output_path: Path to save the VTT file
        
    Returns:
        Path to the generated VTT file
    """
    def format_time(seconds: float) -> str:
        """Format seconds as VTT timestamp (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
    lines = ["WEBVTT", "", ""]
    
    for i, segment in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_time(segment.start_sec)} --> {format_time(segment.end_sec)}")
        lines.append(segment.text)
        lines.append("")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    
    log.info("[FFmpeg] Generated VTT | segments=%d | path=%s", len(segments), output_path)
    return output_path


def extract_subtitles_from_storyboard(storyboard: dict[str, Any]) -> list[SubtitleSegment]:
    """
    Extract subtitle segments from a storyboard JSON.
    
    Args:
        storyboard: Storyboard JSON from Module 2
        
    Returns:
        List of SubtitleSegment objects
    """
    segments = []
    
    for scene in storyboard.get("scenes", []):
        narration = scene.get("narration", {})
        for seg in narration.get("segments", []):
            segments.append(SubtitleSegment(
                start_sec=float(seg.get("t_start", 0)),
                end_sec=float(seg.get("t_end", 0)),
                text=seg.get("text", ""),
            ))
    
    # Sort by start time
    segments.sort(key=lambda s: s.start_sec)
    return segments


# =============================================================================
# FFMPEG WRAPPER
# =============================================================================

class FFmpegAssembler:
    """
    FFmpeg-based video assembler for the R2V pipeline.
    
    Handles the final assembly step (Module 4):
    - Combines video frames into video stream
    - Adds audio track
    - Burns subtitles (optional)
    - Generates web-ready MP4
    """
    
    def __init__(self, config: Optional[FFmpegConfig] = None):
        """
        Initialize the FFmpeg assembler.
        
        Args:
            config: FFmpeg configuration. If None, uses global config.
        """
        self.config = config or get_r2v_config().ffmpeg
    
    async def check_ffmpeg(self) -> bool:
        """
        Check if FFmpeg is available on the system.
        
        Returns:
            True if FFmpeg is available, False otherwise
        """
        try:
            process = await asyncio.create_subprocess_exec(
                self.config.path, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except FileNotFoundError:
            log.error("[FFmpeg] FFmpeg not found at: %s", self.config.path)
            return False
    
    async def assemble_video(
        self,
        video_input: Path,
        audio_input: Optional[Path],
        output_path: Path,
        storyboard: Optional[dict[str, Any]] = None,
        duration_sec: Optional[float] = None,
    ) -> AssemblyResult:
        """
        Assemble final video from video and audio inputs.
        
        Args:
            video_input: Path to video file or frame sequence pattern
            audio_input: Path to audio file (optional)
            output_path: Path for output MP4
            storyboard: Optional storyboard for subtitle generation
            duration_sec: Target duration (for validation)
            
        Returns:
            AssemblyResult with status and output paths
        """
        log.info(
            "[FFmpeg] Starting assembly | video=%s | audio=%s | output=%s",
            video_input, audio_input, output_path
        )
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build FFmpeg command
        cmd = [self.config.path]
        
        # Input video
        cmd.extend(["-i", str(video_input)])
        
        # Input audio (if provided)
        if audio_input and audio_input.exists():
            cmd.extend(["-i", str(audio_input)])
        
        # Video encoding settings
        cmd.extend([
            "-c:v", self.config.video_codec,
            "-b:v", self.config.video_bitrate,
            "-r", str(self.config.fps),
        ])
        
        # Audio encoding settings
        if audio_input and audio_input.exists():
            cmd.extend([
                "-c:a", self.config.audio_codec,
                "-b:a", self.config.audio_bitrate,
            ])
        else:
            # No audio - create silent track for valid MP4
            cmd.extend(["-an"])
        
        # Output settings for web streaming
        cmd.extend([
            "-movflags", "+faststart",  # Enable progressive download
            "-pix_fmt", "yuv420p",      # Compatibility
            "-y",                        # Overwrite output
            str(output_path),
        ])
        
        log.debug("[FFmpeg] Command: %s", " ".join(cmd))
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                log.error("[FFmpeg] Assembly failed: %s", error_msg)
                return AssemblyResult(
                    success=False,
                    error=f"FFmpeg error: {error_msg[:500]}",
                )
            
            # Generate VTT if storyboard is provided
            vtt_path = None
            if storyboard and self.config.generate_vtt:
                subtitles = extract_subtitles_from_storyboard(storyboard)
                if subtitles:
                    vtt_path = output_path.with_suffix(".vtt")
                    generate_vtt(subtitles, vtt_path)
            
            # Get file stats
            file_size = output_path.stat().st_size if output_path.exists() else 0
            
            log.info(
                "[FFmpeg] Assembly complete | output=%s | size=%d bytes",
                output_path, file_size
            )
            
            return AssemblyResult(
                success=True,
                video_path=output_path,
                vtt_path=vtt_path,
                duration_sec=duration_sec or 0.0,
                file_size=file_size,
            )
            
        except Exception as e:
            log.exception("[FFmpeg] Assembly error: %s", e)
            return AssemblyResult(
                success=False,
                error=str(e),
            )
    
    async def create_video_from_frames(
        self,
        frames_dir: Path,
        frame_pattern: str,
        output_path: Path,
        fps: Optional[int] = None,
    ) -> AssemblyResult:
        """
        Create video from a sequence of image frames.
        
        Args:
            frames_dir: Directory containing frame images
            frame_pattern: Pattern for frame files (e.g., "frame_%04d.png")
            output_path: Path for output video
            fps: Frames per second (default from config)
            
        Returns:
            AssemblyResult with status
        """
        fps = fps or self.config.fps
        frame_input = frames_dir / frame_pattern
        
        cmd = [
            self.config.path,
            "-framerate", str(fps),
            "-i", str(frame_input),
            "-c:v", self.config.video_codec,
            "-b:v", self.config.video_bitrate,
            "-pix_fmt", "yuv420p",
            "-y",
            str(output_path),
        ]
        
        log.info("[FFmpeg] Creating video from frames | pattern=%s | fps=%d", frame_pattern, fps)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                return AssemblyResult(success=False, error=error_msg[:500])
            
            return AssemblyResult(
                success=True,
                video_path=output_path,
                file_size=output_path.stat().st_size if output_path.exists() else 0,
            )
            
        except Exception as e:
            return AssemblyResult(success=False, error=str(e))
    
    async def merge_audio_video(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> AssemblyResult:
        """
        Merge separate audio and video files into a single MP4.
        
        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            output_path: Path for merged output
            
        Returns:
            AssemblyResult with status
        """
        cmd = [
            self.config.path,
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",  # Don't re-encode video
            "-c:a", self.config.audio_codec,
            "-b:a", self.config.audio_bitrate,
            "-movflags", "+faststart",
            "-y",
            str(output_path),
        ]
        
        log.info("[FFmpeg] Merging audio/video | output=%s", output_path)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                return AssemblyResult(success=False, error=error_msg[:500])
            
            return AssemblyResult(
                success=True,
                video_path=output_path,
                file_size=output_path.stat().st_size if output_path.exists() else 0,
            )
            
        except Exception as e:
            return AssemblyResult(success=False, error=str(e))
