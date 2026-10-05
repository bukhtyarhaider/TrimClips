"""Video inspector and pre-trim analytics calculation."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import List, Optional, Tuple, Union

from .parser import ClipSpec, format_bytes, format_duration, format_timestamp


@dataclass
class VideoInfo:
    """Metadata extracted from the source video."""
    file_path: Path
    file_size_bytes: int
    duration_seconds: float
    bitrate_bps: int
    video_codec: str
    audio_codec: Optional[str]
    width: int
    height: int
    fps: float

    @property
    def resolution_str(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "Unknown"

    @property
    def duration_str(self) -> str:
        return format_timestamp(self.duration_seconds)

    @property
    def file_size_str(self) -> str:
        return format_bytes(self.file_size_bytes)

    @property
    def bitrate_kbps_str(self) -> str:
        if self.bitrate_bps > 0:
            return f"{self.bitrate_bps / 1000.0:.0f} kbps"
        return "Unknown"


@dataclass
class ClipEstimate:
    """Calculated duration and size estimates for a planned clip."""
    clip: ClipSpec
    duration_seconds: float
    estimated_bytes: float
    pct_of_original_duration: float

    @property
    def estimated_size_str(self) -> str:
        return format_bytes(self.estimated_bytes)


@dataclass
class TrimPlanSummary:
    """Overall pre-trim analysis summarizing input video and planned clips."""
    video_info: VideoInfo
    clip_estimates: List[ClipEstimate]
    total_clips: int
    total_trimmed_duration: float
    total_estimated_bytes: float
    pct_of_original_retained: float
    duration_removed: float

    @property
    def total_trimmed_duration_str(self) -> str:
        return format_duration(self.total_trimmed_duration)

    @property
    def total_estimated_bytes_str(self) -> str:
        return format_bytes(self.total_estimated_bytes)

    @property
    def duration_removed_str(self) -> str:
        return format_duration(self.duration_removed)


def find_binary(binary_name: str, custom_path: Optional[str] = None) -> str:
    """Locate binary path searching standard directories and PATH."""
    if custom_path:
        p = Path(custom_path)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p.resolve())
        raise FileNotFoundError(f"Specified {binary_name} binary not found at '{custom_path}'")

    # Standard PATH search
    found = shutil.which(binary_name)
    if found:
        return found

    # Common macOS and Linux locations
    candidate_dirs = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/opt/local/bin",
    ]
    for d in candidate_dirs:
        cand = Path(d) / binary_name
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)

    raise FileNotFoundError(
        f"'{binary_name}' was not found in PATH or standard directories ({', '.join(candidate_dirs)}).\n"
        f"Please install ffmpeg (e.g., 'brew install ffmpeg') or specify its path."
    )


def inspect_video(video_path: Union[str, Path], ffprobe_path: Optional[str] = None) -> VideoInfo:
    """Inspect video file using ffprobe and return parsed metadata."""
    path = Path(video_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Input video file not found: {path}")

    ffprobe = find_binary("ffprobe", ffprobe_path)

    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries",
        "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,bit_rate",
        "-of", "json",
        str(path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed to inspect {path}: {e.stderr.strip()}") from e

    data = json.loads(proc.stdout)
    format_info = data.get("format", {})
    streams = data.get("streams", [])

    file_size_bytes = int(format_info.get("size") or path.stat().st_size)
    duration_str = format_info.get("duration")

    duration_seconds = float(duration_str) if duration_str else 0.0

    bitrate_str = format_info.get("bit_rate")
    bitrate_bps = int(bitrate_str) if bitrate_str else 0

    video_codec = "unknown"
    audio_codec = None
    width = 0
    height = 0
    fps = 0.0

    for s in streams:
        c_type = s.get("codec_type")
        if c_type == "video" and video_codec == "unknown":
            video_codec = s.get("codec_name", "unknown")
            width = int(s.get("width") or 0)
            height = int(s.get("height") or 0)
            r_fps = s.get("r_frame_rate", "0/0")
            if "/" in r_fps:
                num, den = r_fps.split("/")
                try:
                    num_f, den_f = float(num), float(den)
                    if den_f > 0:
                        fps = num_f / den_f
                except ValueError:
                    fps = 0.0
            if duration_seconds == 0.0 and s.get("duration"):
                try:
                    duration_seconds = float(s["duration"])
                except ValueError:
                    pass
        elif c_type == "audio" and audio_codec is None:
            audio_codec = s.get("codec_name")

    if bitrate_bps == 0 and duration_seconds > 0 and file_size_bytes > 0:
        bitrate_bps = int((file_size_bytes * 8) / duration_seconds)

    return VideoInfo(
        file_path=path,
        file_size_bytes=file_size_bytes,
        duration_seconds=duration_seconds,
        bitrate_bps=bitrate_bps,
        video_codec=video_codec,
        audio_codec=audio_codec,
        width=width,
        height=height,
        fps=fps,
    )




def build_trim_plan(video_info: VideoInfo, clips: List[ClipSpec]) -> TrimPlanSummary:
    """Build pre-trim analysis with size and duration estimates for each clip."""
    clip_estimates: List[ClipEstimate] = []
    total_trimmed_duration = 0.0
    total_estimated_bytes = 0.0

    bytes_per_second = (
        (video_info.bitrate_bps / 8.0)
        if video_info.bitrate_bps > 0
        else (video_info.file_size_bytes / video_info.duration_seconds if video_info.duration_seconds > 0 else 0.0)
    )

    for clip in clips:
        dur = clip.duration_seconds
        total_trimmed_duration += dur

        est_bytes = dur * bytes_per_second
        total_estimated_bytes += est_bytes

        pct = (dur / video_info.duration_seconds * 100.0) if video_info.duration_seconds > 0 else 0.0

        clip_estimates.append(
            ClipEstimate(
                clip=clip,
                duration_seconds=dur,
                estimated_bytes=est_bytes,
                pct_of_original_duration=pct,
            )
        )

    pct_retained = (
        (total_trimmed_duration / video_info.duration_seconds * 100.0)
        if video_info.duration_seconds > 0
        else 0.0
    )
    duration_removed = max(0.0, video_info.duration_seconds - total_trimmed_duration)

    return TrimPlanSummary(
        video_info=video_info,
        clip_estimates=clip_estimates,
        total_clips=len(clips),
        total_trimmed_duration=total_trimmed_duration,
        total_estimated_bytes=total_estimated_bytes,
        pct_of_original_retained=pct_retained,
        duration_removed=duration_removed,
    )
