"""Integration test generating a test video and testing end-to-end clip extraction."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from video_trimmer.cutter import trim_all_clips
from video_trimmer.inspector import build_trim_plan, find_binary, inspect_video
from video_trimmer.parser import load_clips_from_json


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_path = Path(self.temp_dir.name)
        self.video_path = self.work_path / "test_pattern.mp4"
        self.output_dir = self.work_path / "output_clips"

        # Generate a 6-second synthetic test video with audio
        ffmpeg = find_binary("ffmpeg")
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=6:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=6",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(self.video_path)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_inspection_and_trimming(self):
        # 1. Inspect
        video_info = inspect_video(self.video_path)
        self.assertAlmostEqual(video_info.duration_seconds, 6.0, delta=0.5)
        self.assertEqual(video_info.width, 640)
        self.assertEqual(video_info.height, 360)

        # 2. Clips definition
        clips_data = [
            {"title": "Clip One", "start": "00:01", "end": "00:03"},
            {"title": "Clip Two", "start": 3.5, "end": 5.5, "output_name": "custom_clip_two.mp4"}
        ]
        clips, _ = load_clips_from_json(clips_data, video_duration=video_info.duration_seconds)
        self.assertEqual(len(clips), 2)

        # 3. Plan calculation
        plan = build_trim_plan(video_info, clips)
        self.assertEqual(plan.total_clips, 2)
        self.assertAlmostEqual(plan.total_trimmed_duration, 4.0, delta=0.1)
        self.assertGreater(plan.total_estimated_bytes, 0)

        # 4. Accurate trim execution
        results = trim_all_clips(
            source_video=self.video_path,
            clips=clips,
            output_dir=self.output_dir,
            mode="accurate",
        )
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertTrue(r.success)
            self.assertTrue(r.output_path.exists())
            self.assertGreater(r.file_size_bytes, 0)

        # Verify custom filename
        custom_file = self.output_dir / "custom_clip_two.mp4"
        self.assertTrue(custom_file.exists())


if __name__ == "__main__":
    unittest.main()
