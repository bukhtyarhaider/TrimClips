#!/usr/bin/env python3
"""Main entry point for Video Clip Trimmer."""

import sys
from pathlib import Path

# Ensure package is importable when running `python main.py` directly
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from video_trimmer.cli import run_cli

if __name__ == "__main__":
    sys.exit(run_cli())
