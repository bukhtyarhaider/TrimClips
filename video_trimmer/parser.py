"""Timestamp and JSON parsing utilities for video clip trimming."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class ClipSpec:
    """Specification for a single clip to be extracted."""
    index: int
    title: str
    start_seconds: float
    end_seconds: float
    output_filename: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)

    @property
    def start_str(self) -> str:
        return format_timestamp(self.start_seconds)

    @property
    def end_str(self) -> str:
        return format_timestamp(self.end_seconds)

    @property
    def duration_str(self) -> str:
        return format_duration(self.duration_seconds)


def parse_timestamp(value: Union[int, float, str]) -> float:
    """Parse various timestamp representations into total seconds.

    Supports:
        - Numbers (int/float): 12, 12.5 -> 12.0, 12.5
        - Numeric strings: "12", "12.5" -> 12.0, 12.5
        - "MM:SS" or "MM:SS.mmm": "01:23.500" -> 83.5
        - "HH:MM:SS" or "HH:MM:SS.mmm": "01:02:03.456" -> 3723.456
    """
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError(f"Timestamp cannot be negative: {value}")
        return float(value)

    if not isinstance(value, str):
        raise TypeError(f"Invalid timestamp type {type(value).__name__}: {value}")

    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        raise ValueError("Timestamp string cannot be empty")

    # Pure numeric string
    try:
        val = float(cleaned)
        if val < 0:
            raise ValueError(f"Timestamp cannot be negative: {value}")
        return val
    except ValueError:
        pass

    # Clock format HH:MM:SS[.mmm] or MM:SS[.mmm]
    parts = cleaned.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0.0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(
            f"Unrecognized timestamp format: '{value}'. Expected seconds or [HH:]MM:SS[.mmm]"
        )

    try:
        h = float(hours)
        m = float(minutes)
        s = float(seconds)
    except ValueError as e:
        raise ValueError(f"Invalid numeric value in timestamp '{value}': {e}") from e

    if h < 0 or m < 0 or s < 0:
        raise ValueError(f"Timestamp components cannot be negative: '{value}'")
    if m >= 60 and len(parts) == 3:
        raise ValueError(f"Minutes component must be < 60 in HH:MM:SS format: '{value}'")
    if s >= 60:
        raise ValueError(f"Seconds component must be < 60 in clock format: '{value}'")

    return (h * 3600.0) + (m * 60.0) + s


def format_timestamp(seconds: float, include_millis: bool = True) -> str:
    """Format seconds into HH:MM:SS.mmm string."""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    remainder = seconds % 3600
    minutes = int(remainder // 60)
    secs = remainder % 60

    if include_millis:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    return f"{hours:02d}:{minutes:02d}:{int(secs):02d}"


def format_duration(seconds: float) -> str:
    """Format duration into a friendly human-readable format."""
    if seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.2f}s"
    
    minutes = int(seconds // 60)
    remaining_secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {remaining_secs:05.2f}s"
    
    hours = int(minutes // 60)
    rem_mins = minutes % 60
    return f"{hours}h {rem_mins}m {remaining_secs:05.2f}s"


def format_bytes(size_bytes: float) -> str:
    """Format bytes into readable units (KB, MB, GB)."""
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    size = float(size_bytes)
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    return f"{size:.2f} {units[unit_idx]}"


def load_clips_from_json(
    json_path_or_content: Union[str, Path, dict, list],
    video_duration: Optional[float] = None,
    default_stem: str = "clip",
) -> Tuple[List[ClipSpec], Optional[str]]:
    """Load and validate clips from a JSON file path, string, or Python object.

    Returns:
        Tuple of (list of validated ClipSpecs, optional video path specified in JSON)
    """
    raw_data: Any
    if isinstance(json_path_or_content, (str, Path)):
        p = Path(json_path_or_content)
        if p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        else:
            # Try parsing directly as JSON string
            raw_data = json.loads(str(json_path_or_content))
    else:
        raw_data = json_path_or_content

    video_hint: Optional[str] = None
    clips_list: list

    if isinstance(raw_data, list):
        clips_list = raw_data
    elif isinstance(raw_data, dict):
        video_hint = raw_data.get("video") or raw_data.get("source_video") or raw_data.get("file")
        if "clips" in raw_data and isinstance(raw_data["clips"], list):
            clips_list = raw_data["clips"]
        elif "timestamps" in raw_data and isinstance(raw_data["timestamps"], list):
            clips_list = raw_data["timestamps"]
        else:
            raise ValueError(
                "JSON object must contain a 'clips' or 'timestamps' array, or be an array of clip objects."
            )
    else:
        raise ValueError(f"Expected JSON array or object, got {type(raw_data).__name__}")

    if not clips_list:
        raise ValueError("No clips found in the provided JSON input.")

    parsed_clips: List[ClipSpec] = []
    for idx, item in enumerate(clips_list, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Clip #{idx} must be a JSON object, got {type(item).__name__}")

        # Start field resolution
        start_val = None
        for key in ("start", "start_time", "from", "begin", "start_seconds"):
            if key in item and item[key] is not None:
                start_val = item[key]
                break
        if start_val is None:
            raise ValueError(f"Clip #{idx} missing 'start' timestamp.")

        # End field resolution
        end_val = None
        for key in ("end", "end_time", "to", "finish", "end_seconds"):
            if key in item and item[key] is not None:
                end_val = item[key]
                break

        # Duration field alternative if end is not provided
        duration_val = None
        for key in ("duration", "length", "duration_seconds"):
            if key in item and item[key] is not None:
                duration_val = item[key]
                break

        start_sec = parse_timestamp(start_val)

        if end_val is not None:
            end_sec = parse_timestamp(end_val)
        elif duration_val is not None:
            dur_sec = parse_timestamp(duration_val)
            end_sec = start_sec + dur_sec
        else:
            raise ValueError(f"Clip #{idx} must specify either 'end' or 'duration'.")

        if end_sec <= start_sec:
            raise ValueError(
                f"Clip #{idx}: End time ({end_sec}s) must be strictly greater than start time ({start_sec}s)."
            )

        if video_duration is not None and start_sec >= video_duration:
            raise ValueError(
                f"Clip #{idx}: Start time ({format_timestamp(start_sec)}) exceeds video length ({format_timestamp(video_duration)})."
            )

        if video_duration is not None and end_sec > video_duration:
            # Allow trimming up to video duration with a cap or warning
            end_sec = video_duration

        title = (
            item.get("title")
            or item.get("name")
            or item.get("label")
            or item.get("description")
            or f"Clip {idx}"
        )

        output_filename = (
            item.get("output_name")
            or item.get("output_filename")
            or item.get("filename")
            or item.get("output")
        )

        # Retain extra keys
        known_keys = {
            "start", "start_time", "from", "begin", "start_seconds",
            "end", "end_time", "to", "finish", "end_seconds",
            "duration", "length", "duration_seconds",
            "title", "name", "label", "description",
            "output_name", "output_filename", "filename", "output"
        }
        extra = {k: v for k, v in item.items() if k not in known_keys}

        parsed_clips.append(
            ClipSpec(
                index=idx,
                title=str(title),
                start_seconds=start_sec,
                end_seconds=end_sec,
                output_filename=str(output_filename) if output_filename else None,
                custom_metadata=extra,
            )
        )

    return parsed_clips, video_hint
