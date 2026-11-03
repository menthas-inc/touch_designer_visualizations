import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "td"))
import clip_stats  # noqa: E402


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class ClipStatsTest(unittest.TestCase):
    def test_black_then_white_buckets(self):
        with tempfile.TemporaryDirectory() as d:
            clip = os.path.join(d, "bw.mp4")
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=160x90:r=10:d=10",
                 "-f", "lavfi", "-i", "color=white:s=160x90:r=10:d=10",
                 "-filter_complex", "[0][1]concat=n=2:v=1:a=0", "-pix_fmt", "yuv420p", clip],
                check=True)
            s = clip_stats.stats_for(clip)
            self.assertAlmostEqual(s["length"], 20.0, delta=0.5)
            self.assertAlmostEqual(s["fps"], 10.0, delta=0.01)
            self.assertEqual(len(s["buckets"]), 2)
            self.assertLess(s["buckets"][0]["high"], 0.1)
            self.assertGreater(s["buckets"][1]["mean"], 0.85)
            self.assertLess(s["motion"], 0.05)  # one cut in 200 frames


if __name__ == "__main__":
    unittest.main()
