"""FFmpeg video trimming execution engine."""

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import time
from typing import Callable, List, Optional, Union

from .inspector import VideoInfo, find_binary
from .parser import ClipSpec, format_bytes, format_duration


@dataclass
class TrimResult:
    """Outcome of trimming a single clip."""
    clip: ClipSpec
    output_path: Path
    file_size_bytes: int
    duration_seconds: float
    elapsed_seconds: float
    success: bool
    error_message: Optional[str] = None

    @property
    def file_size_str(self) -> str:
        return format_bytes(self.file_size_bytes)


def sanitize_filename(name: str) -> str:
    """Sanitize string to create safe filenames across platforms."""
    # Replace non-alphanumeric (except . - _) with underscore
    clean = re.sub(r"[^\w\-.]+", "_", name.strip())
    # Collapse consecutive underscores
    clean = re.sub(r"_+", "_", clean).strip("._")
    return clean or "clip"


def get_default_clip_filename(
    source_stem: str,
    clip: ClipSpec,
    extension: str = ".mp4"
) -> str:
    """Generate a clean, informative filename for a clip."""
    if clip.output_filename:
        out = clip.output_filename
        if not out.lower().endswith(extension.lower()):
            out += extension
        return sanitize_filename(Path(out).stem) + extension

    safe_title = sanitize_filename(clip.title)
    return f"{source_stem}_clip_{clip.index:03d}_{safe_title}{extension}"


def trim_single_clip(
    source_video: Union[str, Path],
    clip: ClipSpec,
    output_path: Union[str, Path],
    mode: str = "accurate",
    ffmpeg_path: Optional[str] = None,
    overwrite: bool = True,
    crf: int = 18,
    preset: str = "veryfast",
) -> TrimResult:
    """Trim a single clip from source video using ffmpeg.

    Args:
        source_video: Path to input video file.
        clip: ClipSpec definition with start and end timestamps.
        output_path: Destination file path.
        mode: 'accurate' (re-encode with libx264/aac, frame-accurate) or
              'fast' (stream copy `-c copy`, lossless & instant).
        ffmpeg_path: Optional custom path to ffmpeg binary.
        overwrite: Whether to overwrite existing destination file.
        crf: Constant Rate Factor for quality (default 18 for high quality).
        preset: FFmpeg encoding speed preset (default 'veryfast').
    """
    src = Path(source_video).resolve()
    dst = Path(output_path).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = find_binary("ffmpeg", ffmpeg_path)
    start_time = time.time()

    # Base flags
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    if overwrite:
        cmd.append("-y")
    else:
        cmd.append("-n")

    duration = clip.duration_seconds

    if mode == "fast":
        # Fast stream copy (-c copy)
        # Fast seek before input, accurate duration
        cmd.extend([
            "-ss", f"{clip.start_seconds:.3f}",
            "-i", str(src),
            "-t", f"{duration:.3f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(dst)
        ])
    else:
        # Accurate re-encode mode: frame-accurate cuts
        # Seek with -ss before -i for fast jumping, and re-encode audio/video
        cmd.extend([
            "-ss", f"{clip.start_seconds:.3f}",
            "-i", str(src),
            "-t", f"{duration:.3f}",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            str(dst)
        ])

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        elapsed = time.time() - start_time
        file_size = dst.stat().st_size if dst.exists() else 0
        return TrimResult(
            clip=clip,
            output_path=dst,
            file_size_bytes=file_size,
            duration_seconds=duration,
            elapsed_seconds=elapsed,
            success=True,
        )
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        err_msg = e.stderr.strip() or f"FFmpeg exited with code {e.returncode}"
        return TrimResult(
            clip=clip,
            output_path=dst,
            file_size_bytes=0,
            duration_seconds=duration,
            elapsed_seconds=elapsed,
            success=False,
            error_message=err_msg,
        )


def trim_all_clips(
    source_video: Union[str, Path],
    clips: List[ClipSpec],
    output_dir: Union[str, Path],
    mode: str = "accurate",
    ffmpeg_path: Optional[str] = None,
    overwrite: bool = True,
    progress_callback: Optional[Callable[[int, int, ClipSpec, Optional[TrimResult]], None]] = None,
) -> List[TrimResult]:
    """Trim all specified clips and save to output directory."""
    src = Path(source_video).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    source_stem = src.stem
    extension = src.suffix or ".mp4"
    results: List[TrimResult] = []

    total = len(clips)
    for idx, clip in enumerate(clips, start=1):
        filename = get_default_clip_filename(source_stem, clip, extension)
        dst = out_dir / filename

        # If not overwriting and file exists, find an available unique name
        if not overwrite and dst.exists():
            counter = 1
            while dst.exists():
                dst = out_dir / f"{dst.stem}_{counter}{dst.suffix}"
                counter += 1

        if progress_callback:
            progress_callback(idx, total, clip, None)

        res = trim_single_clip(
            source_video=src,
            clip=clip,
            output_path=dst,
            mode=mode,
            ffmpeg_path=ffmpeg_path,
            overwrite=overwrite,
        )
        results.append(res)

        if progress_callback:
            progress_callback(idx, total, clip, res)

    return results
