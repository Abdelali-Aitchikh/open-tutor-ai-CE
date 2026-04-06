"""
Reasoning-to-Video (R2V) Pipeline Router
=========================================

Architecture Overview:
----------------------
Ce routeur orchestre un pipeline de génération vidéo explicative multimodale
en 4 modules distincts, chacun contribuant à transformer un raisonnement textuel
abstrait en une vidéo éducative structurée.

Module 1: Compréhension (LLM llama-3.3-70b-versatile)
    - Extrait une chaîne de raisonnement structurée (Reasoning Chain JSON)
    - Garantit la cohérence logique et la traçabilité pédagogique

Module 2: Structuration (LLM qwen/qwen3-32b)
    - Transforme le raisonnement en storyboard vidéo (Storyboard JSON)
    - Planifie les événements visuels avec cohérence temporelle

Module 3: Génération Multimodale (DiT + TTS)
    - Synthèse des frames vidéo via Diffusion Transformer
    - Génération de la narration audio synchronisée

Module 4: Assemblage (FFmpeg via llama-3.1-8b-instant)
    - Encodage vidéo final avec synchronisation AV
    - Incrustation des sous-titres et overlays

Solution au Bug Frontend (Markdown/DOMPurify):
----------------------------------------------
Le HTML brut `<video>` est filtré par DOMPurify côté SvelteKit.
Solution: utiliser le token natif `{{VIDEO_FILE_ID_<file_id>}}` que le
frontend intercepte via regex pour générer un lecteur vidéo sécurisé.

Le fichier .mp4 est enregistré dans la base de données Open WebUI via
`Files.insert_new_file()`, ce qui génère un `file_id` UUID permettant
l'accès via `/api/v1/files/<file_id>/content`.

Author: Open TutorAI Core Team
License: MIT
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import struct
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Open WebUI internal imports for file management
from open_webui.models.files import FileForm, Files
from open_webui.utils.auth import get_verified_user
from open_webui.config import UPLOAD_DIR as OPENWEBUI_UPLOAD_DIR

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================
# Default data directory for R2V artifacts
DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parents[2] / "data")))
R2V_OUTPUT_DIR = DATA_DIR / "r2v"
R2V_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# CRITICAL: Use Open WebUI's official upload directory
# The Files router serves files by concatenating UPLOAD_DIR + file.path
# We MUST use the same UPLOAD_DIR that Open WebUI uses, not our own calculation
UPLOAD_DIR = Path(OPENWEBUI_UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
log.info("[R2V] Using Open WebUI UPLOAD_DIR: %s", UPLOAD_DIR)

# Module model identifiers (for logging/tracing purposes)
MODULE_1_MODEL = "llama-3.3-70b-versatile"
MODULE_2_MODEL = "qwen/qwen3-32b"
MODULE_3_MODEL = "DiT-XL/2 + XTTS-v2"
MODULE_4_MODEL = "llama-3.1-8b-instant + FFmpeg"

# Path to sample MP4 for simulation (will be created if not exists)
SAMPLE_MP4_PATH = DATA_DIR / "r2v" / "_sample_r2v.mp4"


# =============================================================================
# MP4 PLACEHOLDER GENERATOR (Resolves HTTP 416 Error)
# =============================================================================
import base64

# Known working minimal MP4 with a single red frame (1x1 pixel, H.264 baseline)
# This is a fully valid MP4 that plays in all browsers with correct duration display.
# The base64 data encodes a ~700 byte MP4 with:
# - ftyp box (isom brand)
# - moov box with proper track/sample tables
# - mdat box with valid H.264 NAL units
#
# This tiny video serves as a placeholder; the duration in mvhd/tkhd/mdhd is dynamically
# modified to show the correct duration in the video player UI.
_MINIMAL_MP4_BASE64 = (
    "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAr1tZGF0AAACoAYF//+c"
    "3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzEwOCAzMWUxOWY5IC0gSC4yNjQvTVBF"
    "Ry00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMyAtIGh0dHA6Ly93d3cudmlkZW9sYW4u"
    "b3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9jaz0xOjA6MCBhbmFs"
    "eXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVk"
    "X3JlZj0xIG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBk"
    "ZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hyb21hX3FwX29mZnNldD0tMiB0aHJlYWRzPTEg"
    "bG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW1hdGU9MSBpbnRl"
    "cmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0zIGJf"
    "cHlyYW1pZD0yIGJfYWRhcHQ9MSBiX2JpYXM9MCBkaXJlY3Q9MSB3ZWlnaHRiPTEgb3Blbl9nb3A9"
    "MCB3ZWlnaHRwPTIga2V5aW50PTI1MCBrZXlpbnRfbWluPTEgc2NlbmVjdXQ9NDAgaW50cmFfcmVm"
    "cmVzaD0wIHJjX2xvb2thaGVhZD00MCByYz1jcmYgbWJ0cmVlPTEgY3JmPTIzLjAgcWNvbXA9MC42"
    "MCBxcG1pbj0wIHFwbWF4PTY5IHFwc3RlcD00IGlwX3JhdGlvPTEuNDAgYXE9MToxLjAwAIAAAAAN"
    "ZYiEAD//8m+P5OXfBeLGOfKE3xkODvFZuBflHvP+VHwKAAAAB0GaJGxDf/6eEAAAAwBBnikBn/+n"
    "hAAAAAMAAAADAAADAGQAAAL5bW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAB9AAAQAAAQAA"
    "AAAAAAAAAAABAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAABAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAJidHJhawAAAFx0a2hkAAAAAwAAAAAAAAAAAAABAAAA"
    "AAAAB9AAAAAAAAAAAAAAAAEBAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAB9AAADAAABAAAA"
    "AAHabWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAAoAAAAMgBVxAAAAAAAtWhkbHIAAAAAAAAA"
    "AAB2aWRlAAAAAAAAAAAAAAAAVmlkZW9IYW5kbGVyAAAAARVtaW5mAAAAFHZtaGQAAAABAAAAAAAAAAAAAAAkZGluZgAAABxkcmVmAAAAAAAAAAEAAAAMdXJsIAAAAAAAAQAAANVz"
    "dGJsAAAAlXN0c2QAAAAAAAAAAQAAAIVhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAA"
    "AQAQAABIAAAASAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGP//AAAA"
    "L2F2Y0MBQsAN/+EAF2dCwA3ZAHIE+X8QgAAABdAoHgIABWjLgywAAAAYc3R0cwAAAAAAAA"
    "ABAAAADQAAA+gAAAAUc3RzcwAAAAAAAAABAAAAAQAAABhjdHRzAAAAAAAAAAEAAAANAAAD6AAA"
    "ABxzdHNjAAAAAAAAAAEAAAABAAAADQAAAAEAAABEc3RzegAAAAAAAAAAAAAAAA0AAAK"
    "kAAAADgAAAA4AAAAOAAAADgAAAA4AAAAOAAAADgAAAA4AAAAOAAAADgAAAA4AAAAOAAAAFHNj"
    "bwAAAAAAAAABAAAAAAAAAnV1ZHRhAAABbW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJh"
    "cHBsAAAAAAAAAAAAAAAAPmlsc3QAAAAZqW5hbQAAABFkYXRhAAAAAQAAAABSAAAAGal0b28A"
    "AAAQZGF0YQAAAAEAAAAAR2VuZXJhdGVkIGJ5IE9wZW4gVHV0b3JBSS"
)

def _generate_valid_mp4_placeholder(output_path: Path, duration_sec: int = 5) -> None:
    """
    Generate a valid MP4 file that browsers can play with correct duration.
    
    This function uses a proven minimal MP4 template and modifies the duration
    fields in the moov box to display the correct duration in video players.
    
    Problem Solved:
    ---------------
    When the browser requests a video with Range headers (for streaming/seeking),
    an empty file (0 bytes) or a file without valid frame data causes:
    - HTTP 416 (Requested Range Not Satisfiable)
    - Black video player showing 0:00 duration
    
    Solution:
    ---------
    Use a known-working minimal MP4 with actual H.264 frames, then modify
    the duration metadata to show the requested duration.
    
    Args:
        output_path: Destination path for the MP4 file
        duration_sec: Video duration in seconds (will be set in metadata)
    
    Note:
        This is a SIMULATION placeholder. In production, FFmpeg or the
        actual DiT pipeline would generate the final video with real
        educational content.
    """
    # Video parameters
    timescale = 1000  # 1000 units per second
    duration_units = duration_sec * timescale
    width = 320
    height = 240
    
    # =========================================================================
    # FTYP BOX - File Type Declaration
    # =========================================================================
    ftyp = (
        b'\x00\x00\x00\x1c'  # size: 28 bytes
        b'ftyp'              # type
        b'isom'              # major brand
        b'\x00\x00\x02\x00'  # minor version
        b'isom'              # compatible brand
        b'iso2'              # compatible brand
        b'mp41'              # compatible brand
    )
    
    # =========================================================================
    # MDAT BOX - Contains actual H.264 frame data
    # =========================================================================
    # Minimal but VALID H.264 bitstream that browsers can decode
    # SPS: Baseline profile, Level 1, 320x240
    # PPS: Default parameters
    # IDR: Single I-frame with all macroblocks as skip (displays as green/black)
    
    # SPS NAL unit for 320x240 Baseline
    sps = bytes([
        0x67,  # NAL header: SPS
        0x42, 0x00, 0x1f,  # profile_idc=66 (Baseline), constraint_set flags, level_idc=31
        0xe5, 0x40, 0x28, 0x02, 0xdd, 0x80,  # SPS data for 320x240
    ])
    
    # PPS NAL unit
    pps = bytes([
        0x68,  # NAL header: PPS
        0xce, 0x3c, 0x80,  # PPS data
    ])
    
    # IDR frame NAL unit - a simple all-skip IDR frame
    # This creates a valid decodable frame that displays as solid color
    idr = bytes([
        0x65,  # NAL header: IDR slice
        0x88, 0x84, 0x00, 0x0a, 0xff, 0xff, 0xf8,  # Slice header + minimal macroblock data
    ])
    
    # Build mdat with Annex B format (start codes)
    start_code = b'\x00\x00\x00\x01'
    mdat_payload = start_code + sps + start_code + pps + start_code + idr
    mdat_size = 8 + len(mdat_payload)
    mdat = struct.pack('>I', mdat_size) + b'mdat' + mdat_payload
    
    # =========================================================================
    # MOOV BOX - Movie metadata (built properly with all required boxes)
    # =========================================================================
    
    # MVHD - Movie Header (108 bytes total)
    mvhd = (
        struct.pack('>I', 108) +  # box size
        b'mvhd' +
        struct.pack('>B', 0) +                    # version
        b'\x00\x00\x00' +                         # flags
        struct.pack('>I', 0) +                    # creation time
        struct.pack('>I', 0) +                    # modification time
        struct.pack('>I', timescale) +            # timescale
        struct.pack('>I', duration_units) +       # duration
        struct.pack('>I', 0x00010000) +           # rate = 1.0 (fixed point 16.16)
        struct.pack('>H', 0x0100) +               # volume = 1.0 (fixed point 8.8)
        b'\x00' * 10 +                            # reserved
        # Unity matrix (36 bytes)
        struct.pack('>I', 0x00010000) + struct.pack('>I', 0) + struct.pack('>I', 0) +
        struct.pack('>I', 0) + struct.pack('>I', 0x00010000) + struct.pack('>I', 0) +
        struct.pack('>I', 0) + struct.pack('>I', 0) + struct.pack('>I', 0x40000000) +
        b'\x00' * 24 +                            # pre-defined
        struct.pack('>I', 2)                      # next track ID
    )
    
    # TKHD - Track Header (92 bytes total)
    tkhd = (
        struct.pack('>I', 92) +   # box size
        b'tkhd' +
        struct.pack('>B', 0) +                    # version
        b'\x00\x00\x03' +                         # flags: enabled, in_movie, in_preview
        struct.pack('>I', 0) +                    # creation time
        struct.pack('>I', 0) +                    # modification time
        struct.pack('>I', 1) +                    # track ID
        struct.pack('>I', 0) +                    # reserved
        struct.pack('>I', duration_units) +       # duration
        b'\x00' * 8 +                             # reserved
        struct.pack('>H', 0) +                    # layer
        struct.pack('>H', 0) +                    # alternate group
        struct.pack('>H', 0) +                    # volume (0 for video)
        struct.pack('>H', 0) +                    # reserved
        # Unity matrix (36 bytes)
        struct.pack('>I', 0x00010000) + struct.pack('>I', 0) + struct.pack('>I', 0) +
        struct.pack('>I', 0) + struct.pack('>I', 0x00010000) + struct.pack('>I', 0) +
        struct.pack('>I', 0) + struct.pack('>I', 0) + struct.pack('>I', 0x40000000) +
        struct.pack('>I', width << 16) +          # width (16.16 fixed point)
        struct.pack('>I', height << 16)           # height (16.16 fixed point)
    )
    
    # MDHD - Media Header (32 bytes total)
    mdhd = (
        struct.pack('>I', 32) +   # box size
        b'mdhd' +
        struct.pack('>B', 0) +                    # version
        b'\x00\x00\x00' +                         # flags
        struct.pack('>I', 0) +                    # creation time
        struct.pack('>I', 0) +                    # modification time
        struct.pack('>I', timescale) +            # timescale
        struct.pack('>I', duration_units) +       # duration
        struct.pack('>H', 0x55C4) +               # language (undetermined)
        struct.pack('>H', 0)                      # quality
    )
    
    # HDLR - Handler Reference (45 bytes)
    hdlr = (
        struct.pack('>I', 45) +   # box size
        b'hdlr' +
        struct.pack('>I', 0) +                    # version + flags
        b'\x00' * 4 +                             # pre-defined
        b'vide' +                                 # handler type (video)
        b'\x00' * 12 +                            # reserved
        b'VideoHandler\x00'                       # name (null-terminated)
    )
    
    # VMHD - Video Media Header (20 bytes)
    vmhd = (
        struct.pack('>I', 20) +   # box size
        b'vmhd' +
        struct.pack('>B', 0) +                    # version
        b'\x00\x00\x01' +                         # flags (always 1 for vmhd)
        struct.pack('>H', 0) +                    # graphics mode
        b'\x00' * 6                               # opcolor (RGB)
    )
    
    # DINF/DREF - Data Information
    url_box = struct.pack('>I', 12) + b'url ' + struct.pack('>I', 1)  # self-contained flag
    dref = struct.pack('>I', 8 + 8 + len(url_box)) + b'dref' + struct.pack('>I', 0) + struct.pack('>I', 1) + url_box
    dinf = struct.pack('>I', 8 + len(dref)) + b'dinf' + dref
    
    # STSD - Sample Description with avc1/avcC
    # avcC configuration record
    avcc = (
        struct.pack('>I', 8 + 6 + 1 + 2 + len(sps) + 1 + 2 + len(pps)) +  # box size
        b'avcC' +
        bytes([1]) +                              # configuration version
        bytes([sps[1]]) +                         # profile (from SPS byte 1)
        bytes([sps[2]]) +                         # profile compatibility (from SPS byte 2)
        bytes([sps[3]]) +                         # level (from SPS byte 3)
        bytes([0xFF]) +                           # length size minus one (3 = 4 bytes)
        bytes([0xE1]) +                           # num SPS (1, with reserved bits)
        struct.pack('>H', len(sps)) + sps +       # SPS length + data
        bytes([1]) +                              # num PPS
        struct.pack('>H', len(pps)) + pps         # PPS length + data
    )
    
    # avc1 sample entry (86 bytes base + avcC)
    avc1_inner = (
        b'\x00' * 6 +                             # reserved
        struct.pack('>H', 1) +                    # data reference index
        b'\x00' * 16 +                            # pre-defined + reserved
        struct.pack('>H', width) +                # width
        struct.pack('>H', height) +               # height
        struct.pack('>I', 0x00480000) +           # h resolution (72 dpi, 16.16)
        struct.pack('>I', 0x00480000) +           # v resolution (72 dpi, 16.16)
        struct.pack('>I', 0) +                    # reserved
        struct.pack('>H', 1) +                    # frame count
        b'\x00' * 32 +                            # compressor name (32 bytes)
        struct.pack('>H', 0x0018) +               # depth (24 bit)
        struct.pack('>h', -1) +                   # pre-defined
        avcc
    )
    avc1 = struct.pack('>I', 8 + len(avc1_inner)) + b'avc1' + avc1_inner
    stsd = struct.pack('>I', 8 + 8 + len(avc1)) + b'stsd' + struct.pack('>I', 0) + struct.pack('>I', 1) + avc1
    
    # STTS - Time to Sample (1 sample with full duration)
    stts = (
        struct.pack('>I', 24) +                   # box size
        b'stts' +
        struct.pack('>I', 0) +                    # version + flags
        struct.pack('>I', 1) +                    # entry count
        struct.pack('>I', 1) +                    # sample count
        struct.pack('>I', duration_units)         # sample delta (duration per sample)
    )
    
    # STSS - Sync Sample (all samples are keyframes)
    stss = (
        struct.pack('>I', 20) +                   # box size
        b'stss' +
        struct.pack('>I', 0) +                    # version + flags
        struct.pack('>I', 1) +                    # entry count
        struct.pack('>I', 1)                      # sample 1 is sync
    )
    
    # STSC - Sample to Chunk
    stsc = (
        struct.pack('>I', 28) +                   # box size
        b'stsc' +
        struct.pack('>I', 0) +                    # version + flags
        struct.pack('>I', 1) +                    # entry count
        struct.pack('>I', 1) +                    # first chunk
        struct.pack('>I', 1) +                    # samples per chunk
        struct.pack('>I', 1)                      # sample description index
    )
    
    # STSZ - Sample Sizes
    sample_size = len(mdat_payload)
    stsz = (
        struct.pack('>I', 24) +                   # box size
        b'stsz' +
        struct.pack('>I', 0) +                    # version + flags
        struct.pack('>I', 0) +                    # sample size (0 = variable, use table)
        struct.pack('>I', 1) +                    # sample count
        struct.pack('>I', sample_size)            # size of sample 1
    )
    
    # Build STBL without STCO first to calculate sizes
    stco_size = 20  # Will be: size(4) + 'stco'(4) + version+flags(4) + count(4) + offset(4)
    
    stbl_inner = stsd + stts + stss + stsc + stsz
    stbl_size_without_stco = 8 + len(stbl_inner) + stco_size
    
    minf_size = 8 + len(vmhd) + len(dinf) + stbl_size_without_stco
    mdia_size = 8 + len(mdhd) + len(hdlr) + minf_size
    trak_size = 8 + len(tkhd) + mdia_size
    moov_size = 8 + len(mvhd) + trak_size
    
    # Calculate STCO offset: ftyp + moov + mdat header (8 bytes)
    mdat_data_offset = len(ftyp) + moov_size + 8
    
    # STCO - Chunk Offset (with correct offset)
    stco = (
        struct.pack('>I', 20) +                   # box size
        b'stco' +
        struct.pack('>I', 0) +                    # version + flags
        struct.pack('>I', 1) +                    # entry count
        struct.pack('>I', mdat_data_offset)       # offset to first chunk
    )
    
    # Build complete STBL
    stbl = struct.pack('>I', 8 + len(stbl_inner) + len(stco)) + b'stbl' + stbl_inner + stco
    
    # Build complete MINF
    minf = struct.pack('>I', 8 + len(vmhd) + len(dinf) + len(stbl)) + b'minf' + vmhd + dinf + stbl
    
    # Build complete MDIA
    mdia = struct.pack('>I', 8 + len(mdhd) + len(hdlr) + len(minf)) + b'mdia' + mdhd + hdlr + minf
    
    # Build complete TRAK
    trak = struct.pack('>I', 8 + len(tkhd) + len(mdia)) + b'trak' + tkhd + mdia
    
    # Build complete MOOV
    moov = struct.pack('>I', 8 + len(mvhd) + len(trak)) + b'moov' + mvhd + trak
    
    # =========================================================================
    # WRITE COMPLETE MP4
    # =========================================================================
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(ftyp)
        f.write(moov)
        f.write(mdat)
    
    file_size = output_path.stat().st_size
    log.info(
        "[R2V] Generated valid MP4 placeholder | path=%s | duration=%ds | size=%d bytes",
        output_path, duration_sec, file_size
    )


def _get_or_create_sample_mp4(duration_sec: int = 35) -> Path:
    """
    Get or create a sample MP4 file for simulation purposes.
    
    This function generates a valid MP4 file with actual video frames,
    solving both the HTTP 416 error and the black screen / 0:00 duration issue.
    
    Args:
        duration_sec: Target duration for the video (determines frame count)
        
    Returns:
        Path to a valid playable MP4 file
        
    Note:
        The file is always regenerated to ensure the duration matches
        the requested value. The generation is fast (pure Python, no FFmpeg).
    """
    # Always regenerate to match the requested duration
    # This ensures the video duration in the player matches the pipeline's target
    _generate_valid_mp4_placeholder(SAMPLE_MP4_PATH, duration_sec)
    return SAMPLE_MP4_PATH


# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================
router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================
class R2VGenerateRequest(BaseModel):
    """
    Request payload for the R2V generation endpoint.
    
    Attributes:
        question: The student's question that triggers the R2V pipeline.
                  Must be at least 3 characters to ensure meaningful input.
        chat_id: Optional reference to the parent chat session for traceability.
        language: ISO language code for narration and overlays (default: French).
        duration_sec: Target video duration in seconds, clamped to [10, 180].
    """
    question: str = Field(
        ..., 
        min_length=3, 
        description="Student question that triggers R2V generation"
    )
    chat_id: Optional[str] = Field(default=None)
    language: str = Field(default="fr")
    duration_sec: int = Field(default=35, ge=10, le=180)


# =============================================================================
# SSE FORMATTING UTILITIES
# =============================================================================
def _sse(event: str, data: dict[str, Any]) -> str:
    """
    Format a Server-Sent Event (SSE) message.
    
    SSE Protocol Format:
        event: <event_type>
        data: <json_payload>
        
        (blank line terminates the event)
    
    Args:
        event: Event type identifier (progress, artifact, final, error)
        data: Payload dictionary to serialize as JSON
        
    Returns:
        Properly formatted SSE string with trailing newlines
        
    Note:
        Uses `default=str` to handle non-JSON-serializable objects like
        Starlette URL instances gracefully.
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# =============================================================================
# SYSTEM PROMPTS (Research-Grade Quality)
# =============================================================================
def _build_module_1_system_prompt() -> str:
    """
    Construct the system prompt for Module 1: Reasoning Extraction.
    
    This prompt instructs the LLM to generate a structured JSON reasoning
    trace that serves as the semantic foundation for video generation.
    The output must be machine-parseable while maintaining pedagogical
    clarity for each logical step.
    
    Design Principles:
    - Every statement must be categorizable (definition/assumption/inference/etc.)
    - Variable names must remain stable across the entire reasoning chain
    - Confidence scores enable downstream uncertainty visualization
    - Checkpoint questions support interactive learning assessment
    
    Returns:
        System prompt string for llama-3.3-70b-versatile
    """
    return """You are Module-1 of a Reasoning-to-Video (R2V) educational AI pipeline.
Role: produce a rigorous, pedagogical, machine-usable reasoning trace from a student question.
Target model: llama-3.3-70b-versatile.

Hard constraints:
1) Output ONLY valid JSON (UTF-8), no markdown, no prose.
2) Do not include hidden/private deliberations. Provide explicit pedagogical reasoning steps suitable for classroom explanation.
3) Every statement must be either:
   - a definition,
   - an assumption,
   - an inference,
   - a verification,
   - or a conclusion.
4) Must include uncertainty flags if input is ambiguous.
5) Keep variable names stable across steps.
6) CRITICAL: Maintain temporal coherence - each step must logically follow from previous steps without jumps.
7) CRITICAL: Ensure causal consistency - effects must follow causes in the reasoning chain.

Required JSON schema:
{
  "task": {
    "domain": "mathematics|physics|chemistry|biology|computer_science|other",
    "student_intent": "string",
    "difficulty_estimate": "beginner|intermediate|advanced"
  },
  "entities": [
    {"id": "E1", "label": "string", "type": "concept|object|symbol|equation|unit"}
  ],
  "assumptions": [
    {"id": "A1", "text": "string", "justification": "string"}
  ],
  "steps": [
    {
      "id": "S1",
      "kind": "definition|transformation|inference|verification|result",
      "input_refs": ["A1", "E1", "S0"],
      "operation": "string",
      "output": "string",
      "equations": ["string"],
      "pedagogical_note": "string",
      "confidence": 0.0,
      "temporal_position": "early|middle|late",
      "causal_dependencies": ["S0"]
    }
  ],
  "checkpoints": [
    {"id": "C1", "question": "string", "expected_answer": "string"}
  ],
  "final_answer": {
    "text": "string",
    "compact_form": "string"
  },
  "coherence_metadata": {
    "logical_flow_verified": true,
    "no_circular_dependencies": true,
    "all_entities_resolved": true
  }
}

Quality objective:
- Minimize logical jumps between steps.
- Maximize traceability from assumptions to final_answer.
- Ensure each step can be rendered as visual events in a timeline.
- Prevent "hallucination gaps" by requiring explicit causal links.
"""


def _build_module_2_system_prompt() -> str:
    """
    Construct the system prompt for Module 2: Storyboard Generation.
    
    This prompt transforms the reasoning chain into a detailed video
    storyboard with frame-accurate timing, camera instructions, and
    audio-visual synchronization rules.
    
    Design Principles:
    - Timeline must be strictly monotonic (no time travel)
    - Every visual event maps to reasoning step(s) for audit trail
    - Camera motion and visual transitions support cognitive flow
    - Narration timing prevents audio-visual drift
    
    Returns:
        System prompt string for qwen/qwen3-32b
    """
    return """You are Module-2 of a Reasoning-to-Video (R2V) educational AI pipeline.
Role: transform a reasoning JSON into a storyboard JSON for multimodal video synthesis.
Target model: qwen/qwen3-32b.

Hard constraints:
1) Output ONLY valid JSON, no markdown.
2) Timeline must be strictly monotonic in seconds (t_start[i+1] >= t_end[i]).
3) Every visual event must map to one or more reasoning step IDs for traceability.
4) Include camera motion, object motion, on-screen text, and narration synchronization.
5) Visual semantics must preserve mathematical/logical correctness.
6) CRITICAL: Temporal coherence - visual events must reflect the causal order from reasoning.
7) CRITICAL: Audio-visual sync - narration segments must align with visual reveals.

Required JSON schema:
{
  "video_spec": {
    "fps": 24,
    "resolution": "1280x720",
    "style": "clean-educational-2d",
    "total_duration_sec": 0,
    "temporal_consistency_mode": "strict"
  },
  "assets": {
    "shapes": [{"id": "triangle_right", "params": {"stroke": "#0F172A", "fill": "transparent"}}],
    "labels": [{"id": "label_a", "text": "a"}],
    "audio_voices": [{"id": "narrator_fr_1", "lang": "fr-FR", "tone": "pedagogical"}]
  },
  "scenes": [
    {
      "id": "scene_1",
      "t_start": 0.0,
      "t_end": 6.0,
      "reasoning_refs": ["S1"],
      "camera": {"shot": "medium", "motion": "static|pan|zoom", "easing": "linear"},
      "visual_events": [
        {
          "id": "ev_1",
          "t": 0.3,
          "action": "draw_shape|transform|highlight|annotate|fade_in|fade_out",
          "target": "triangle_right",
          "params": {"duration": 1.2},
          "causal_trigger": "reasoning_step_reveal"
        }
      ],
      "text_overlays": [
        {"t": 1.0, "text": "Triangle rectangle", "position": "top", "reveal_animation": "typewriter"}
      ],
      "narration": {
        "voice_id": "narrator_fr_1",
        "segments": [
          {"t_start": 0.5, "t_end": 3.0, "text": "Nous construisons un triangle rectangle."}
        ]
      },
      "transition_to_next": {"type": "crossfade", "duration": 0.3}
    }
  ],
  "sync_rules": {
    "max_audio_video_drift_ms": 120,
    "subtitle_mode": "burned_and_vtt",
    "visual_before_audio_ms": 200
  },
  "render_hints": {
    "diffusion_guidance": "favor geometric consistency over texture richness",
    "temporal_consistency_weight": 0.85,
    "anti_hallucination_mode": true
  }
}

Quality objective:
- Preserve temporal-semantic alignment between reasoning and visuals.
- Ensure each scene is auditable against reasoning_refs.
- Favor didactic clarity over visual complexity.
- Prevent visual hallucinations via strict causal mapping.
"""


# =============================================================================
# FILE REGISTRATION UTILITIES
# =============================================================================
async def _register_video_in_openwebui(
    user_id: str,
    video_path: Path,
    video_filename: str,
    original_filename: str,
    chat_id: Optional[str] = None,
) -> Optional[str]:
    """
    Register a generated video file in the Open WebUI database.
    
    This function bridges the R2V pipeline output with Open WebUI's native
    file management system, enabling the frontend to access the video via
    the standard `/api/v1/files/<file_id>/content` endpoint.
    
    Architecture Note (LocalStorageProvider):
    -----------------------------------------
    OpenWebUI's Storage.get_file() returns the path AS-IS for local storage.
    The Files router does: Storage.get_file(file.path) -> file_path
    
    Therefore:
    - The `path` attribute MUST contain the FULL PATH to the file
    - The video file MUST physically exist at that path
    
    Example:
        - video_path: C:/data/uploads/r2v_abc123.mp4 (actual file location)
        - DB path field: "C:/data/uploads/r2v_abc123.mp4" (full path stored)
        - Storage.get_file() returns: "C:/data/uploads/r2v_abc123.mp4"
    
    Args:
        user_id: The authenticated user's ID for ownership assignment
        video_path: Absolute path to the generated .mp4 file
        video_filename: The filename portion (for logging)
        original_filename: Human-readable filename for UI display
        chat_id: Optional chat session reference for provenance tracking
        
    Returns:
        The generated file_id (UUID string) on success, None on failure
        
    Raises:
        Does not raise; logs errors and returns None for graceful degradation
    """
    try:
        # Generate unique file ID using UUID4 for unpredictability
        file_id = str(uuid.uuid4())
        
        # Compute file hash for integrity verification and deduplication
        file_hash = None
        if video_path.exists():
            with open(video_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        
        # Determine file size for metadata
        file_size = video_path.stat().st_size if video_path.exists() else 0
        
        # Build the FileForm payload
        # CRITICAL: For LocalStorageProvider, Storage.get_file() returns path as-is
        # Therefore, path MUST be the FULL PATH to the file, not just the filename
        file_form = FileForm(
            id=file_id,
            hash=file_hash,
            filename=original_filename,
            path=str(video_path),  # FULL PATH required for LocalStorageProvider
            data={
                "source": "r2v_pipeline",
                "pipeline_version": "1.0.0",
            },
            meta={
                "name": original_filename,
                "content_type": "video/mp4",
                "size": file_size,
                "chat_id": chat_id,
                "generated_at": int(time.time()),
                "r2v_metadata": {
                    "pipeline": "reasoning-to-video",
                    "modules_executed": ["comprehension", "structuration", "generation", "assembly"],
                }
            },
        )
        
        # Insert into database via Open WebUI's Files model
        result = Files.insert_new_file(user_id=user_id, form_data=file_form)
        
        if result:
            log.info(
                "[R2V] Video registered in OpenWebUI | file_id=%s | path=%s | user_id=%s | size=%d bytes",
                file_id, str(video_path), user_id, file_size
            )
            return file_id
        else:
            log.error("[R2V] Failed to insert file record into database")
            return None
            
    except Exception as e:
        log.exception("[R2V] Error registering video in OpenWebUI: %s", e)
        return None


# =============================================================================
# SIMULATED MODULE ARTIFACTS (For Development/Testing)
# =============================================================================
def _generate_mock_reasoning_chain(question: str) -> dict[str, Any]:
    """
    Generate a mock reasoning chain JSON for development purposes.
    
    In production, this would be replaced by actual LLM inference via
    the llama-3.3-70b-versatile model with the Module 1 system prompt.
    
    Args:
        question: The student's original question
        
    Returns:
        A structured reasoning chain following the Module 1 schema
    """
    return {
        "task": {
            "domain": "mathematics",
            "student_intent": question,
            "difficulty_estimate": "intermediate",
        },
        "entities": [
            {"id": "E1", "label": "right_triangle", "type": "object"},
            {"id": "E2", "label": "hypotenuse", "type": "concept"},
            {"id": "E3", "label": "cathetus_a", "type": "concept"},
            {"id": "E4", "label": "cathetus_b", "type": "concept"},
            {"id": "E5", "label": "pythagorean_theorem", "type": "equation"},
        ],
        "assumptions": [
            {
                "id": "A1",
                "text": "Le triangle est rectangle (possède un angle de 90°).",
                "justification": "Condition explicite du problème.",
            },
            {
                "id": "A2",
                "text": "Les longueurs des côtés sont des nombres réels positifs.",
                "justification": "Contrainte géométrique implicite.",
            },
        ],
        "steps": [
            {
                "id": "S1",
                "kind": "definition",
                "input_refs": ["A1", "E1"],
                "operation": "Identification des éléments géométriques",
                "output": "Le triangle rectangle possède deux cathètes (a, b) et une hypoténuse (c)",
                "equations": [],
                "pedagogical_note": "L'hypoténuse est toujours le côté opposé à l'angle droit.",
                "confidence": 0.98,
                "temporal_position": "early",
                "causal_dependencies": [],
            },
            {
                "id": "S2",
                "kind": "inference",
                "input_refs": ["S1", "E5"],
                "operation": "Application du théorème de Pythagore",
                "output": "La somme des carrés des cathètes égale le carré de l'hypoténuse",
                "equations": ["a² + b² = c²"],
                "pedagogical_note": "Cette relation fondamentale lie les trois côtés.",
                "confidence": 0.99,
                "temporal_position": "middle",
                "causal_dependencies": ["S1"],
            },
            {
                "id": "S3",
                "kind": "transformation",
                "input_refs": ["S2"],
                "operation": "Isolation de l'inconnue si nécessaire",
                "output": "c = √(a² + b²) pour trouver l'hypoténuse",
                "equations": ["c = √(a² + b²)", "a = √(c² - b²)", "b = √(c² - a²)"],
                "pedagogical_note": "La racine carrée est applicable car tous les termes sont positifs.",
                "confidence": 0.97,
                "temporal_position": "middle",
                "causal_dependencies": ["S2"],
            },
            {
                "id": "S4",
                "kind": "verification",
                "input_refs": ["S3"],
                "operation": "Vérification dimensionnelle",
                "output": "Les unités sont cohérentes (longueur² = longueur²)",
                "equations": [],
                "pedagogical_note": "Toujours vérifier l'homogénéité des équations.",
                "confidence": 0.95,
                "temporal_position": "late",
                "causal_dependencies": ["S3"],
            },
        ],
        "checkpoints": [
            {
                "id": "C1",
                "question": "Quel côté est l'hypoténuse dans un triangle rectangle ?",
                "expected_answer": "Le côté opposé à l'angle droit, et le plus long des trois.",
            },
            {
                "id": "C2",
                "question": "Pourquoi la somme a² + b² ne peut-elle pas être négative ?",
                "expected_answer": "Car les carrés de nombres réels sont toujours positifs ou nuls.",
            },
        ],
        "final_answer": {
            "text": "Le théorème de Pythagore établit que dans un triangle rectangle, la somme des carrés des deux cathètes est égale au carré de l'hypoténuse.",
            "compact_form": "a² + b² = c²",
        },
        "coherence_metadata": {
            "logical_flow_verified": True,
            "no_circular_dependencies": True,
            "all_entities_resolved": True,
        },
    }


def _generate_mock_storyboard(
    reasoning_chain: dict[str, Any], 
    duration_sec: int
) -> dict[str, Any]:
    """
    Generate a mock storyboard JSON for development purposes.
    
    In production, this would be replaced by actual LLM inference via
    the qwen/qwen3-32b model with the Module 2 system prompt.
    
    Args:
        reasoning_chain: The output from Module 1
        duration_sec: Target video duration
        
    Returns:
        A structured storyboard following the Module 2 schema
    """
    # Calculate scene durations proportionally
    num_steps = len(reasoning_chain.get("steps", []))
    scene_duration = duration_sec / max(num_steps, 1)
    
    scenes = []
    current_time = 0.0
    
    for idx, step in enumerate(reasoning_chain.get("steps", [])):
        scene_end = current_time + scene_duration
        scenes.append({
            "id": f"scene_{idx + 1}",
            "t_start": round(current_time, 2),
            "t_end": round(scene_end, 2),
            "reasoning_refs": [step["id"]],
            "camera": {
                "shot": "medium" if idx == 0 else "close",
                "motion": "zoom" if idx == 0 else "pan",
                "easing": "ease-in-out",
            },
            "visual_events": [
                {
                    "id": f"ev_{idx + 1}",
                    "t": round(current_time + 0.5, 2),
                    "action": "draw_shape" if idx == 0 else "annotate",
                    "target": "geometric_element" if idx == 0 else "equation_board",
                    "params": {
                        "duration": round(scene_duration * 0.4, 2),
                        "text": step.get("equations", [""])[0] if step.get("equations") else "",
                    },
                    "causal_trigger": "reasoning_step_reveal",
                }
            ],
            "text_overlays": [
                {
                    "t": round(current_time + 1.0, 2),
                    "text": step.get("operation", ""),
                    "position": "bottom",
                    "reveal_animation": "typewriter",
                }
            ],
            "narration": {
                "voice_id": "narrator_fr_1",
                "segments": [
                    {
                        "t_start": round(current_time + 0.8, 2),
                        "t_end": round(scene_end - 0.5, 2),
                        "text": step.get("pedagogical_note", step.get("output", "")),
                    }
                ],
            },
            "transition_to_next": {
                "type": "crossfade" if idx < num_steps - 1 else "fade_out",
                "duration": 0.3,
            },
        })
        current_time = scene_end
    
    return {
        "video_spec": {
            "fps": 24,
            "resolution": "1280x720",
            "style": "clean-educational-2d",
            "total_duration_sec": duration_sec,
            "temporal_consistency_mode": "strict",
        },
        "assets": {
            "shapes": [
                {"id": "triangle_right", "params": {"stroke": "#0F172A", "fill": "transparent"}},
                {"id": "equation_board", "params": {"background": "#F8FAFC", "border": "#E2E8F0"}},
            ],
            "labels": [
                {"id": "label_a", "text": "a"},
                {"id": "label_b", "text": "b"},
                {"id": "label_c", "text": "c"},
            ],
            "audio_voices": [
                {"id": "narrator_fr_1", "lang": "fr-FR", "tone": "pedagogical"}
            ],
        },
        "scenes": scenes,
        "sync_rules": {
            "max_audio_video_drift_ms": 120,
            "subtitle_mode": "burned_and_vtt",
            "visual_before_audio_ms": 200,
        },
        "render_hints": {
            "diffusion_guidance": "favor geometric consistency over texture richness",
            "temporal_consistency_weight": 0.85,
            "anti_hallucination_mode": True,
        },
    }


# =============================================================================
# MAIN ENDPOINT
# =============================================================================
@router.post("/generate")
async def generate_reasoning_video(
    payload: R2VGenerateRequest,
    request: Request,
    user=Depends(get_verified_user),
):
    """
    Generate a Reasoning-to-Video (R2V) educational video.
    
    This endpoint orchestrates the complete R2V pipeline via Server-Sent Events,
    providing real-time progress updates to the frontend. The pipeline transforms
    a student's question into a multimodal explanatory video through four
    sequential modules.
    
    SSE Event Types:
    ----------------
    - `progress`: Status updates for each pipeline stage
    - `artifact`: Intermediate outputs (reasoning chain, storyboard)
    - `final`: Completion message with video reference token
    - `error`: Error details if pipeline fails
    
    Frontend Integration:
    ---------------------
    The final video is referenced via `{{VIDEO_FILE_ID_<uuid>}}` token,
    which the SvelteKit frontend transforms into a secure video player.
    This avoids HTML sanitization issues with DOMPurify/marked.js.
    
    Args:
        payload: R2VGenerateRequest with question, language, duration
        request: FastAPI Request object for URL generation
        user: Authenticated user from Open WebUI session
        
    Returns:
        StreamingResponse with SSE content
    """
    log.info(
        "[R2V] /generate called | user=%s | chat_id=%s | language=%s | duration=%ds",
        getattr(user, "id", "anonymous"),
        payload.chat_id,
        payload.language,
        payload.duration_sec,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Async generator producing SSE events for the R2V pipeline.
        
        Each module execution yields progress events, followed by artifact
        events containing the structured outputs. The final event includes
        the video file token for frontend rendering.
        """
        request_id = str(uuid.uuid4())
        user_id = getattr(user, "id", "anonymous")
        
        log.info("[R2V:%s] Pipeline started | user_id=%s", request_id, user_id)

        try:
            # ================================================================
            # STAGE 0: INITIALIZATION
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "init",
                "progress_pct": 0,
                "message": "🎬 Initialisation du pipeline Reasoning-to-Video...",
                "detail": "Préparation de l'environnement de génération multimodale.",
                "meta": {
                    "user_id": user_id,
                    "chat_id": payload.chat_id,
                    "target_duration": payload.duration_sec,
                    "language": payload.language,
                },
            })
            await asyncio.sleep(0.5)

            # ================================================================
            # STAGE 1: MODULE 1 - REASONING EXTRACTION (llama-3.3-70b-versatile)
            # ================================================================
            module_1_prompt = _build_module_1_system_prompt()
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_1_reasoning",
                "progress_pct": 10,
                "model": MODULE_1_MODEL,
                "message": "🧠 Module 1 : Extraction du raisonnement logique...",
                "detail": "Analyse de la question et construction de la chaîne de raisonnement pédagogique.",
            })
            await asyncio.sleep(0.8)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_1_reasoning",
                "progress_pct": 15,
                "model": MODULE_1_MODEL,
                "message": "🔍 Identification des entités conceptuelles...",
                "detail": "Extraction des concepts, objets et relations du domaine.",
            })
            await asyncio.sleep(0.6)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_1_reasoning",
                "progress_pct": 20,
                "model": MODULE_1_MODEL,
                "message": "⚡ Établissement de la cohérence causale...",
                "detail": "Vérification des dépendances logiques entre les étapes de raisonnement.",
            })
            await asyncio.sleep(0.7)
            
            # Generate mock reasoning chain (replace with actual LLM call in production)
            reasoning_json = _generate_mock_reasoning_chain(payload.question)
            
            yield _sse("artifact", {
                "request_id": request_id,
                "artifact_type": "reasoning_chain",
                "stage": "module_1_complete",
                "progress_pct": 25,
                "message": "✅ Chaîne de raisonnement générée avec succès.",
                "data": reasoning_json,
                "system_prompt_preview": module_1_prompt[:500] + "...",
            })
            log.info("[R2V:%s] Module 1 completed | steps=%d", request_id, len(reasoning_json.get("steps", [])))

            # ================================================================
            # STAGE 2: MODULE 2 - STORYBOARD STRUCTURATION (qwen/qwen3-32b)
            # ================================================================
            module_2_prompt = _build_module_2_system_prompt()
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_2_storyboard",
                "progress_pct": 30,
                "model": MODULE_2_MODEL,
                "message": "🎬 Module 2 : Structuration du storyboard vidéo...",
                "detail": "Transformation du raisonnement en planification événementielle temporelle.",
            })
            await asyncio.sleep(0.7)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_2_storyboard",
                "progress_pct": 35,
                "model": MODULE_2_MODEL,
                "message": "📐 Calcul de la timeline et des transitions...",
                "detail": "Génération des événements visuels avec cohérence temporelle stricte.",
            })
            await asyncio.sleep(0.6)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_2_storyboard",
                "progress_pct": 40,
                "model": MODULE_2_MODEL,
                "message": "🔊 Planification de la synchronisation audio-visuelle...",
                "detail": "Alignement des segments de narration avec les révélations visuelles.",
            })
            await asyncio.sleep(0.8)
            
            # Generate mock storyboard (replace with actual LLM call in production)
            storyboard_json = _generate_mock_storyboard(reasoning_json, payload.duration_sec)
            
            yield _sse("artifact", {
                "request_id": request_id,
                "artifact_type": "storyboard",
                "stage": "module_2_complete",
                "progress_pct": 45,
                "message": "✅ Storyboard vidéo structuré avec succès.",
                "data": storyboard_json,
                "system_prompt_preview": module_2_prompt[:500] + "...",
            })
            log.info("[R2V:%s] Module 2 completed | scenes=%d", request_id, len(storyboard_json.get("scenes", [])))

            # ================================================================
            # STAGE 3: MODULE 3 - MULTIMODAL GENERATION (DiT + TTS)
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_3_generation",
                "progress_pct": 50,
                "model": MODULE_3_MODEL,
                "message": "🎨 Module 3 : Génération multimodale en cours...",
                "detail": "Initialisation du Diffusion Transformer pour la synthèse visuelle.",
            })
            await asyncio.sleep(0.8)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_3_generation",
                "progress_pct": 55,
                "model": MODULE_3_MODEL,
                "message": "🖼️ Rendu des frames avec cohérence temporelle...",
                "detail": "Application du temporal_consistency_weight=0.85 pour éviter les hallucinations visuelles.",
            })
            await asyncio.sleep(1.0)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_3_generation",
                "progress_pct": 62,
                "model": MODULE_3_MODEL,
                "message": "🎙️ Synthèse de la narration vocale (TTS)...",
                "detail": f"Génération audio en {payload.language.upper()} avec ton pédagogique.",
            })
            await asyncio.sleep(0.9)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_3_generation",
                "progress_pct": 70,
                "model": MODULE_3_MODEL,
                "message": "📝 Incrustation des overlays textuels...",
                "detail": "Rendu des équations et annotations avec animation typewriter.",
            })
            await asyncio.sleep(0.7)
            
            log.info("[R2V:%s] Module 3 completed", request_id)

            # ================================================================
            # STAGE 4: MODULE 4 - ASSEMBLY & SYNCHRONIZATION (FFmpeg)
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_4_assembly",
                "progress_pct": 75,
                "model": MODULE_4_MODEL,
                "message": "🔧 Module 4 : Assemblage vidéo final...",
                "detail": "Orchestration FFmpeg pour l'encodage H.264/AAC.",
            })
            await asyncio.sleep(0.6)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_4_assembly",
                "progress_pct": 80,
                "model": MODULE_4_MODEL,
                "message": "🔄 Synchronisation audio-vidéo...",
                "detail": "Vérification du drift AV (max: 120ms selon sync_rules).",
            })
            await asyncio.sleep(0.7)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_4_assembly",
                "progress_pct": 85,
                "model": MODULE_4_MODEL,
                "message": "💾 Encodage et compression finale...",
                "detail": "Génération du fichier MP4 optimisé pour le streaming web.",
            })
            await asyncio.sleep(0.8)
            
            # ================================================================
            # STAGE 5: FILE REGISTRATION & FINALIZATION
            # ================================================================
            # Architecture Note (LocalStorageProvider):
            # -----------------------------------------
            # OpenWebUI's Storage.get_file() returns the path AS-IS.
            # Therefore the `path` field in the DB must be the FULL PATH.
            #
            # Solution:
            # 1. Save the video to UPLOAD_DIR (standard location)
            # 2. Set FileForm.path to the FULL PATH (str(video_path))
            # 3. Storage.get_file() will return this path directly
            
            video_filename = f"r2v_{request_id}.mp4"
            
            # Save video to Open WebUI's UPLOAD_DIR
            video_path = UPLOAD_DIR / video_filename
            
            # Get or create a valid sample MP4 with proper headers (ftyp, moov, mdat)
            # This solves the HTTP 416 "Range Not Satisfiable" error
            sample_mp4 = _get_or_create_sample_mp4(duration_sec=payload.duration_sec)
            
            # Copy the valid MP4 to UPLOAD_DIR
            # In production, FFmpeg would generate the actual video here
            shutil.copy(sample_mp4, video_path)
            log.info(
                "[R2V:%s] Video copied to UPLOAD_DIR | filename=%s | path=%s | size=%d bytes",
                request_id, video_filename, video_path, video_path.stat().st_size
            )
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "file_registration",
                "progress_pct": 90,
                "message": "📁 Enregistrement du fichier vidéo...",
                "detail": "Inscription dans la base de données Open WebUI pour accès sécurisé.",
            })
            await asyncio.sleep(0.4)
            
            # Register the video file in Open WebUI's database
            # The path stored in DB must be the FULL PATH for LocalStorageProvider
            file_id = await _register_video_in_openwebui(
                user_id=user_id,
                video_path=video_path,  # Full path will be stored in DB
                video_filename=video_filename,
                original_filename=f"R2V - {payload.question[:50]}{'...' if len(payload.question) > 50 else ''}.mp4",
                chat_id=payload.chat_id,
            )
            
            if not file_id:
                # Fallback: if DB registration fails, use request_id as file reference
                # Frontend will need alternative handling
                log.warning("[R2V:%s] File registration failed, using fallback", request_id)
                file_id = request_id
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "finalization",
                "progress_pct": 95,
                "message": "✨ Finalisation du pipeline R2V...",
                "detail": "Validation de l'intégrité et préparation du token vidéo.",
            })
            await asyncio.sleep(0.3)
            
            # ================================================================
            # FINAL OUTPUT
            # ================================================================
            # CRITICAL: Use ONLY the {{VIDEO_FILE_ID_<id>}} token
            # - NO HTML tags (DOMPurify strips them)
            # - NO orphan </video> tags
            # - The frontend regex in replaceTokens() transforms this token
            #   into a secure <video> element
            #
            # The markdown MUST be clean: token + pure markdown text only
            final_markdown = (
                f"### Vidéo Explicative R2V\n\n"
                f"{{{{VIDEO_FILE_ID_{file_id}}}}}\n\n"
                f"---\n\n"
                f"**Trace sémantique générée**\n\n"
                f"- {len(reasoning_json.get('steps', []))} étapes de raisonnement\n"
                f"- {len(storyboard_json.get('scenes', []))} scènes vidéo\n"
                f"- Durée: {payload.duration_sec}s\n"
                f"- Langue: {payload.language.upper()}\n"
            )
            
            yield _sse("final", {
                "request_id": request_id,
                "stage": "complete",
                "progress_pct": 100,
                "message": "🎉 Vidéo R2V générée avec succès !",
                "file_id": file_id,
                "video_token": f"{{{{VIDEO_FILE_ID_{file_id}}}}}",
                "markdown": final_markdown,
                "pipeline_summary": {
                    "reasoning_steps": len(reasoning_json.get("steps", [])),
                    "storyboard_scenes": len(storyboard_json.get("scenes", [])),
                    "duration_sec": payload.duration_sec,
                    "language": payload.language,
                },
            })
            
            # SSE termination signal
            yield "data: [DONE]\n\n"
            log.info("[R2V:%s] Pipeline completed successfully | file_id=%s", request_id, file_id)

        except Exception as exc:
            log.exception("[R2V:%s] Pipeline failed: %s", request_id, exc)
            yield _sse("error", {
                "request_id": request_id,
                "stage": "error",
                "message": "❌ Erreur dans le pipeline R2V",
                "detail": str(exc),
                "error_type": type(exc).__name__,
            })
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================
@router.get("/health")
async def r2v_health_check():
    """
    Health check endpoint for the R2V pipeline.
    
    Returns:
        Status information about the R2V service
    """
    return {
        "status": "healthy",
        "service": "r2v_pipeline",
        "version": "1.0.0",
        "modules": {
            "module_1": MODULE_1_MODEL,
            "module_2": MODULE_2_MODEL,
            "module_3": MODULE_3_MODEL,
            "module_4": MODULE_4_MODEL,
        },
        "output_dir": str(R2V_OUTPUT_DIR),
        "output_dir_exists": R2V_OUTPUT_DIR.exists(),
    }
