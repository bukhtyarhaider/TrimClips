"""Console formatting utilities for pre-trim summaries and progress reports."""

import sys
from typing import List

from .inspector import TrimPlanSummary


def print_banner(title: str, width: int = 78) -> None:
    """Print a clean styled section banner."""
    print("=" * width)
    print(f"  {title.upper()}")
    print("=" * width)


def print_trim_plan_summary(plan: TrimPlanSummary, output_dir: str) -> None:
    """Print detailed pre-trim information about source video and clips."""
    v = plan.video_info

    print()
    print_banner("Video Clip Trimmer - Pre-Trim Summary")
    print(f" Source Video:   {v.file_path.name}")
    print(f" Full Path:      {v.file_path}")
    print(f" File Size:      {v.file_size_str} ({v.file_size_bytes:,} bytes)")
    print(f" Total Duration: {v.duration_str} ({v.duration_seconds:.2f} seconds)")
    print(f" Resolution:     {v.resolution_str} @ {v.fps:.2f} fps")
    print(f" Codecs:         Video: {v.video_codec} | Audio: {v.audio_codec or 'None'}")
    print(f" Bitrate:        {v.bitrate_kbps_str}")
    print(f" Output Folder:  {output_dir}")
    print("-" * 78)

    print()
    print("Planned Clips to Trim:")
    print("-" * 78)

    # Format table header
    # # | Title | Start | End | Length | Est. Size
    hdr_fmt = "{:<3} | {:<20} | {:<12} | {:<12} | {:<10} | {:<10}"
    row_fmt = "{:<3} | {:<20} | {:<12} | {:<12} | {:<10} | {:<10}"

    print(hdr_fmt.format("#", "Clip Title", "Start", "End", "Duration", "Est. Size"))
    print("-" * 78)

    for est in plan.clip_estimates:
        clip = est.clip
        # Truncate title if too long
        title = clip.title if len(clip.title) <= 20 else clip.title[:17] + "..."
        print(
            row_fmt.format(
                clip.index,
                title,
                clip.start_str,
                clip.end_str,
                est.clip.duration_str,
                est.estimated_size_str,
            )
        )

    print("-" * 78)

    print()
    print("Trim Analytics & Aggregate Stats:")
    print(f" • Total Clips to Generate:     {plan.total_clips}")
    print(f" • Total Combined Trim Length:  {plan.total_trimmed_duration_str} ({plan.total_trimmed_duration:.2f}s)")
    print(f" • Total Estimated Output Size: ~{plan.total_estimated_bytes_str}")
    print(f" • Footage Retained:            {plan.pct_of_original_retained:.1f}% of original video")
    print(f" • Footage Discarded/Skipped:   {plan.duration_removed_str} ({plan.duration_removed:.2f}s)")
    print("=" * 78)
    print()


def ask_user_confirmation(prompt: str = "Proceed with trimming clips? [Y/n]: ") -> bool:
    """Ask user for interactive confirmation in terminal."""
    try:
        response = input(prompt).strip().lower()
        if response in ("", "y", "yes"):
            return True
        return False
    except (KeyboardInterrupt, EOFError):
        print("\nAborted by user.")
        return False
