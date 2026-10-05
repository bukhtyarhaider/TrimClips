# Video Clip Trimmer

A modular, robust Python tool to inspect a video and trim multiple clips using exact timestamps specified in a JSON file.

Before performing any cutting, the tool analyzes the source video and displays a **Pre-Trim Summary** detailing video duration, resolution, codecs, individual clip lengths, estimated file sizes, and aggregate metrics (footage kept vs. discarded).

---

## Features

- **Pre-Trim Analytics & Size Estimation**: Displays video metadata (resolution, frame rate, bitrate, codecs, duration) and calculates individual clip durations and estimated output sizes before trimming.
- **Flexible JSON Formats**:
  - Seconds: `15`, `45.250`
  - Clock strings: `"01:23"`, `"00:01:23.500"`, `"01:15:30"`
  - `start` & `end` or `start` & `duration`
- **Two Trimming Modes**:
  - **Accurate** (default): Frame-accurate cutting using video/audio re-encoding (`libx264`/`aac`), ensuring no black frames or audio sync drift at cut points.
  - **Fast** (`-m fast` / `--copy`): Lossless stream copy (`-c copy`) for near-instant cutting without re-encoding.
- **Automated or Custom Output Naming**: Automatically generates clean filenames (`<video>_clip_001_<title>.mp4`) or respects custom filenames provided in the JSON (`output_name`).
- **Zero Mandatory External Python Dependencies**: Built with Python 3's standard library; requires only [FFmpeg](https://ffmpeg.org).
- **Python Library & CLI**: Can be run directly from the command line or imported into other Python projects.

---

## Requirements

1. **Python 3.8+**
2. **FFmpeg & FFprobe**:
   - macOS: `brew install ffmpeg` *(already installed at `/opt/homebrew/bin/ffmpeg`)*
   - Linux: `sudo apt update && sudo apt install -y ffmpeg`
   - Windows: `winget install Gyan.FFmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html)

No extra `pip` packages are required for normal execution. For testing, `pytest` is optional:
```bash
pip install -r requirements.txt
```

---

## Quick Start

### 1. Preview Durations and Estimated File Sizes (Dry Run)
Inspect the video and see the exact clip breakdown without trimming any files:

```bash
python main.py -v sample_video.mp4 -j sample_clips.json --preview-only
```

### 2. Trim Clips with Pre-Trim Confirmation
Preview the summary and confirm (`[Y/n]`) before trimming:

```bash
python main.py -v sample_video.mp4 -j sample_clips.json
```

### 3. Fast Stream Copy Mode (Instant & Lossless)
Skip re-encoding for maximum speed and auto-confirm with `-y`:

```bash
python main.py -v sample_video.mp4 -j sample_clips.json -m fast -o ./output_clips -y
```

---

## JSON Format

You can provide your clips in two formats:

### Option A: Array of Clip Objects (Recommended)
Save as `clips.json`:

```json
[
  {
    "title": "Intro and Hook",
    "start": "00:00:05.500",
    "end": "00:00:25.000",
    "output_name": "clip_01_intro.mp4"
  },
  {
    "title": "Core Discussion",
    "start": "01:15",
    "end": "02:45.500"
  },
  {
    "title": "Key Insight",
    "start": 180.25,
    "end": 210.0,
    "output_name": "insight.mp4"
  },
  {
    "title": "Closing Remarks",
    "start": "04:10",
    "duration": "00:20"
  }
]
```

### Option B: Object with Video Reference and Clips
You can also embed the source video path directly in the JSON so you don't have to specify `-v` in the CLI:

```json
{
  "video": "interviews/session_01.mp4",
  "clips": [
    {
      "title": "Segment 1",
      "start": "00:00:10",
      "end": "00:00:40"
    },
    {
      "title": "Segment 2",
      "start": "01:00",
      "end": "01:30"
    }
  ]
}
```

Then run:
```bash
python main.py -j clips.json
```

### Supported JSON Fields per Clip

| Field | Aliases | Description |
|---|---|---|
| `start` | `start_time`, `from`, `begin` | Start timestamp (string `"00:01:23"` or seconds `83.0`) |
| `end` | `end_time`, `to`, `finish` | End timestamp (string or seconds). Must be `> start` |
| `duration` | `length` | Alternative to `end`: clip duration from `start` |
| `title` | `name`, `label` | Label or title for the clip |
| `output_name` | `output_filename`, `filename` | Optional custom file name for the trimmed clip |

---

## Example Pre-Trim Output

When you run the tool, it prints an overview and table before cutting:

```text
==============================================================================
  VIDEO CLIP TRIMMER - PRE-TRIM SUMMARY
==============================================================================
 Source Video:   interview.mp4
 Full Path:      /path/to/interview.mp4
 File Size:      142.50 MB (149,422,080 bytes)
 Total Duration: 00:15:20.000 (920.00 seconds)
 Resolution:     1920x1080 @ 30.00 fps
 Codecs:         Video: h264 | Audio: aac
 Bitrate:        1300 kbps
 Output Folder:  /path/to/output_clips
------------------------------------------------------------------------------

Planned Clips to Trim:
------------------------------------------------------------------------------
#   | Clip Title           | Start        | End          | Duration   | Est. Size 
------------------------------------------------------------------------------
1   | Intro and Hook       | 00:00:05.500 | 00:00:25.000 | 19.50s     | 3.17 MB   
2   | Core Discussion      | 00:01:15.000 | 00:02:45.500 | 1m 30.50s  | 14.71 MB  
3   | Key Insight          | 00:03:00.250 | 00:03:30.000 | 29.75s     | 4.83 MB   
------------------------------------------------------------------------------

Trim Analytics & Aggregate Stats:
 • Total Clips to Generate:     3
 • Total Combined Trim Length:  2m 19.75s (139.75s)
 • Total Estimated Output Size: ~22.71 MB
 • Footage Retained:            15.2% of original video
 • Footage Discarded/Skipped:   13m 00.25s (780.25s)
==============================================================================

Proceed with trimming 3 clips? [Y/n]: 
```

---

## CLI Options Reference

```text
usage: video-trimmer [-h] [-v VIDEO_PATH] -j JSON_PATH [-o OUTPUT_DIR]
                     [-m {accurate,fast}] [--preview-only] [-y]
                     [--no-overwrite] [--ffmpeg-path FFMPEG_PATH]
                     [--ffprobe-path FFPROBE_PATH]

arguments:
  -v, --video VIDEO_PATH      Path to input video file
  -j, --json JSON_PATH        Path to JSON file with clip timestamps (or JSON string)
  -o, --output-dir OUTPUT_DIR Destination folder for clips (default: './trimmed_clips')
  -m, --mode {accurate,fast}  'accurate' (re-encode, frame-accurate) or 'fast' (stream copy)
  --preview-only, --dry-run   Show pre-trim duration & size estimates without cutting
  -y, --yes                   Auto-confirm trimming without interactive prompt
  --no-overwrite              Append number suffix to prevent overwriting existing files
  --ffmpeg-path PATH          Custom path to ffmpeg executable
  --ffprobe-path PATH         Custom path to ffprobe executable
```

---

## Python API Usage

You can also use `video_trimmer` programmatically in your own Python scripts:

```python
from pathlib import Path
from video_trimmer.inspector import inspect_video, build_trim_plan
from video_trimmer.parser import load_clips_from_json
from video_trimmer.cutter import trim_all_clips

# 1. Inspect source video
video_info = inspect_video("my_video.mp4")
print(f"Duration: {video_info.duration_seconds}s, Size: {video_info.file_size_str}")

# 2. Parse JSON clip specs
clips, _ = load_clips_from_json("clips.json", video_duration=video_info.duration_seconds)

# 3. Compute analytics
plan = build_trim_plan(video_info, clips)
print(f"Total Trim Duration: {plan.total_trimmed_duration_str}")
print(f"Estimated Output Size: {plan.total_estimated_bytes_str}")

# 4. Perform trims
results = trim_all_clips(
    source_video="my_video.mp4",
    clips=clips,
    output_dir="./output_clips",
    mode="accurate",  # or 'fast'
)

for r in results:
    if r.success:
        print(f"Trimmed {r.clip.title} -> {r.output_path} ({r.file_size_str})")
```

---

## Running the Tests

To run the automated test suite (including synthetic video generation and extraction tests):

```bash
python -m unittest discover -s tests
```
