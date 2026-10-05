"""Command line interface for video clip trimmer."""

import argparse
from pathlib import Path
import sys
import time
from typing import Optional

from .cutter import trim_all_clips
from .formatter import ask_user_confirmation, print_banner, print_trim_plan_summary
from .inspector import build_trim_plan, find_binary, inspect_video
from .parser import format_bytes, format_duration, load_clips_from_json


def create_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="video-trimmer",
        description="Trim multiple clips from a video using JSON timestamp specifications.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview duration and size stats without trimming:
  python main.py -v my_video.mp4 -j timestamps.json --preview-only

  # Trim clips using accurate frame-by-frame mode (prompts for confirmation):
  python main.py -v my_video.mp4 -j timestamps.json

  # Fast stream copy without re-encoding (instant cut) into custom folder:
  python main.py -v my_video.mp4 -j timestamps.json -m fast -o ./highlights -y

  # JSON format example (timestamps.json):
  [
    {"title": "Intro", "start": "00:00:05", "end": "00:00:25"},
    {"title": "Key Moment", "start": "01:30.500", "end": "02:15.000", "output_name": "highlight.mp4"},
    {"title": "Outro", "start": 300, "duration": 15}
  ]
        """,
    )

    parser.add_argument(
        "-v", "--video",
        dest="video_path",
        help="Path to source video file (optional if defined inside the JSON object).",
    )
    parser.add_argument(
        "-j", "--json",
        dest="json_path",
        required=True,
        help="Path to JSON file with clip timestamps (or raw JSON string).",
    )
    parser.add_argument(
        "-o", "--output-dir",
        dest="output_dir",
        default="trimmed_clips",
        help="Directory to save trimmed clips (default: './trimmed_clips').",
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["accurate", "fast"],
        default="accurate",
        help="Trimming mode: 'accurate' (default, frame-accurate re-encode) or 'fast' (stream copy, instant).",
    )
    parser.add_argument(
        "--preview-only", "--dry-run",
        dest="preview_only",
        action="store_true",
        help="Show pre-trim duration, size estimates, and table, then exit without cutting.",
    )
    parser.add_argument(
        "-y", "--yes",
        dest="auto_confirm",
        action="store_true",
        help="Automatically proceed with trimming without interactive prompt.",
    )
    parser.add_argument(
        "--no-overwrite",
        dest="overwrite",
        action="store_false",
        default=True,
        help="Do not overwrite existing clip files; auto-append numbering suffix.",
    )
    parser.add_argument(
        "--ffmpeg-path",
        help="Explicit path to ffmpeg binary.",
    )
    parser.add_argument(
        "--ffprobe-path",
        help="Explicit path to ffprobe binary.",
    )

    return parser


def run_cli(args: Optional[list] = None) -> int:
    """Main CLI entrypoint."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    try:
        # 1. Locate binaries early to give fast, actionable feedback
        ffmpeg_bin = find_binary("ffmpeg", parsed_args.ffmpeg_path)
        ffprobe_bin = find_binary("ffprobe", parsed_args.ffprobe_path)

        # 2. Check JSON file existence
        json_target = parsed_args.json_path
        clips, video_hint = load_clips_from_json(json_target)

        # 3. Resolve video path
        video_path_str = parsed_args.video_path or video_hint
        if not video_path_str:
            print("Error: Source video file not specified.", file=sys.stderr)
            print("Please provide it via -v / --video or specify 'video' in your JSON file.", file=sys.stderr)
            return 1

        video_path = Path(video_path_str)
        if not video_path.is_file():
            print(f"Error: Video file not found at: {video_path}", file=sys.stderr)
            return 1

        # 4. Inspect video and calculate analytics
        video_info = inspect_video(video_path, ffprobe_path=ffprobe_bin)

        # Re-validate clips against actual duration
        validated_clips, _ = load_clips_from_json(json_target, video_duration=video_info.duration_seconds)

        # 5. Build pre-trim summary
        summary = build_trim_plan(video_info, validated_clips)

        # 6. Display pre-trim analysis
        out_dir = Path(parsed_args.output_dir).resolve()
        print_trim_plan_summary(summary, str(out_dir))

        # If preview only, stop here
        if parsed_args.preview_only:
            print("[Info] --preview-only mode active. No clips were cut.")
            return 0

        # 7. Ask for user confirmation if not bypassed
        if not parsed_args.auto_confirm:
            if not ask_user_confirmation(f"Proceed with trimming {len(validated_clips)} clips? [Y/n]: "):
                print("[Info] Trimming canceled by user.")
                return 0

        # 8. Execute trimming
        print_banner(f"Trimming Clips (Mode: {parsed_args.mode.upper()})")

        start_time = time.time()
        success_count = 0
        fail_count = 0

        def on_progress(current: int, total: int, clip, res):
            if res is None:
                print(f"[{current}/{total}] Cutting '{clip.title}' ({clip.start_str} -> {clip.end_str})...", end="", flush=True)
            else:
                if res.success:
                    print(f" Done! -> {res.output_path.name} ({res.file_size_str}, took {res.elapsed_seconds:.2f}s)")
                else:
                    print(f" FAILED! Reason: {res.error_message}")

        results = trim_all_clips(
            source_video=video_path,
            clips=validated_clips,
            output_dir=out_dir,
            mode=parsed_args.mode,
            ffmpeg_path=ffmpeg_bin,
            overwrite=parsed_args.overwrite,
            progress_callback=on_progress,
        )

        total_elapsed = time.time() - start_time
        for r in results:
            if r.success:
                success_count += 1
            else:
                fail_count += 1

        print("-" * 78)
        print(f"Completed in {total_elapsed:.2f}s! Successfully trimmed {success_count}/{len(results)} clips.")
        if fail_count > 0:
            print(f"Warning: {fail_count} clips failed. Check error logs above.", file=sys.stderr)
        print(f"Output files saved in: {out_dir}")
        print("=" * 78)

        return 0 if fail_count == 0 else 2

    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[Interrupted] Process terminated by user.", file=sys.stderr)
        return 130
