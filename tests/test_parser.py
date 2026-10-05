"""Unit tests for timestamp parsing and JSON validation."""

import json
import tempfile
import unittest
from pathlib import Path

from video_trimmer.parser import (
    ClipSpec,
    format_bytes,
    format_duration,
    format_timestamp,
    load_clips_from_json,
    parse_timestamp,
)


class TestParser(unittest.TestCase):
    def test_parse_numeric_timestamps(self):
        self.assertEqual(parse_timestamp(0), 0.0)
        self.assertEqual(parse_timestamp(15), 15.0)
        self.assertEqual(parse_timestamp(12.75), 12.75)
        self.assertEqual(parse_timestamp("42"), 42.0)
        self.assertEqual(parse_timestamp("100.5"), 100.5)

    def test_parse_clock_formats(self):
        # MM:SS
        self.assertEqual(parse_timestamp("01:23"), 83.0)
        self.assertEqual(parse_timestamp("00:30.500"), 30.5)
        self.assertEqual(parse_timestamp("00:30,500"), 30.5)

        # HH:MM:SS
        self.assertEqual(parse_timestamp("01:00:00"), 3600.0)
        self.assertEqual(parse_timestamp("00:02:15.250"), 135.25)
        self.assertEqual(parse_timestamp("02:10:05.100"), 7805.1)

    def test_parse_invalid_timestamps(self):
        with self.assertRaises(ValueError):
            parse_timestamp("-5")
        with self.assertRaises(ValueError):
            parse_timestamp("invalid")
        with self.assertRaises(ValueError):
            parse_timestamp("01:65")  # seconds >= 60

    def test_formatting_functions(self):
        self.assertEqual(format_timestamp(0.0), "00:00:00.000")
        self.assertEqual(format_timestamp(65.5), "00:01:05.500")
        self.assertEqual(format_timestamp(3661.0), "01:01:01.000")

        self.assertEqual(format_bytes(500), "500.00 B")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")

        self.assertIn("15.00s", format_duration(15.0))
        self.assertIn("1m", format_duration(65.0))

    def test_load_clips_from_list(self):
        sample = [
            {"title": "Intro", "start": "00:05", "end": "00:20"},
            {"title": "Part 2", "start": 30.0, "end": 45.0, "output_name": "part2.mp4"},
        ]
        clips, video_hint = load_clips_from_json(sample)
        self.assertIsNone(video_hint)
        self.assertEqual(len(clips), 2)
        self.assertEqual(clips[0].title, "Intro")
        self.assertEqual(clips[0].start_seconds, 5.0)
        self.assertEqual(clips[0].end_seconds, 20.0)
        self.assertEqual(clips[0].duration_seconds, 15.0)
        self.assertEqual(clips[1].output_filename, "part2.mp4")

    def test_load_clips_with_duration_field(self):
        sample = [
            {"title": "Segment", "start": "00:10", "duration": "00:05"}
        ]
        clips, _ = load_clips_from_json(sample)
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].start_seconds, 10.0)
        self.assertEqual(clips[0].end_seconds, 15.0)
        self.assertEqual(clips[0].duration_seconds, 5.0)

    def test_load_clips_validation_errors(self):
        # Start >= end
        bad_times = [{"title": "Backwards", "start": 20, "end": 10}]
        with self.assertRaises(ValueError):
            load_clips_from_json(bad_times)

        # Exceeds video duration
        valid_clip = [{"title": "Too Long", "start": 100, "end": 110}]
        with self.assertRaises(ValueError):
            load_clips_from_json(valid_clip, video_duration=50.0)


if __name__ == "__main__":
    unittest.main()
