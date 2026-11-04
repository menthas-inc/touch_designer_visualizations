import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "td"))
import sequencer as sq  # noqa: E402

BRIGHT = {"mean": 0.4, "high": 0.9}
DARK = {"mean": 0.1, "high": 0.3}


def clip(length, fps=30.0, motion=0.05, buckets=None):
    n = max(1, int(-(-length // 10)))
    return {"length": length, "fps": fps, "motion": motion,
            "buckets": buckets or [{"mean": 0.1, "high": 0.3}] * n}


class ChooseTest(unittest.TestCase):
    def test_bright_gets_a_darkener_dark_never_does(self):
        rng = random.Random(1)
        for _ in range(200):
            b = sq.enabled(sq.choose(BRIGHT, rng))
            self.assertTrue(b & set(sq.DARK), b)
            self.assertTrue("framing" in b)
            d = sq.enabled(sq.choose(DARK, rng))
            self.assertFalse(d & set(sq.DARK), d)
            self.assertTrue(len(d & set(sq.TREAT)) <= 2)

    def test_dark_is_mostly_plain_even_when_the_other_group_is(self):
        rng = random.Random(2)
        other = {n: {"Enable": int(n == "framing")} for n in sq.CORPUS}
        plain = sum(sq.enabled(sq.choose(DARK, rng, avoid=[other])) == {"framing"} for _ in range(1000))
        self.assertTrue(740 < plain < 860, plain)

    def test_darkness_default_matches_and_upper_levels_cut_lower(self):
        levels = list(sq.DARKNESS.values())
        self.assertEqual(levels[1][:3], (0.18, sq.DEFAULTS["bright_mean"], sq.DEFAULTS["bright_high"]))
        self.assertIsNone(levels[0][4]); self.assertIsNone(levels[1][4])
        self.assertGreater(min(levels[2][4]), max(levels[3][4]))
        rng = random.Random(9)
        for _ in range(50):
            sel = sq.choose(DARK, rng, bias=levels[3][3], cut=levels[3][4])
            h = sel["highlights"]
            self.assertEqual((h["Enable"], h["Amount"]), (1, 1.0))
            self.assertTrue(0.3 <= h["Cut"] <= 0.5, h)

    def test_bias_pushes_darkeners_to_the_dark_end_and_leaves_hue(self):
        rng = random.Random(3)
        for _ in range(100):
            sel = sq.choose(BRIGHT, rng, bias=1.0)
            for n in sq.enabled(sel) & set(sq.DARK):
                for k, v in sel[n].items():
                    if k not in ("Enable", "Hue"):
                        self.assertEqual(v, sq.CORPUS[n]["params"][k][1], (n, k))
        hues = {sq.params_for("tint", rng, 1.0)["Hue"] for _ in range(20)}
        self.assertGreater(len(hues), 1)
        self.assertFalse(sq.is_bright(BRIGHT, *list(sq.DARKNESS["none"])[1:3]))

    def test_missing_clip_is_bright(self):
        self.assertTrue(sq.is_bright(sq.window_stats(None, 0, 30)))

    def test_never_equals_avoid_unless_plain(self):
        rng = random.Random(2)
        plain = {"framing"}
        for stats in (BRIGHT, DARK):
            for _ in range(200):
                a = sq.choose(stats, rng)
                c = sq.choose(stats, rng, avoid=[a])
                b = sq.choose(stats, rng, avoid=[a, c])
                if sq.enabled(b) != plain:
                    self.assertNotEqual(sq.enabled(a), sq.enabled(b))
                    self.assertNotEqual(sq.enabled(c), sq.enabled(b))


class ProgressTest(unittest.TestCase):
    def test_half_way_at_the_knee_then_half_speed(self):
        self.assertEqual(sq.progress(0.0), 0.0)
        self.assertAlmostEqual(sq.progress(sq.KNEE), 0.5)
        self.assertAlmostEqual(sq.progress(sq.KNEE / 2), 0.25)
        self.assertAlmostEqual(sq.progress((1 + sq.KNEE) / 2), 0.75)
        self.assertEqual(sq.progress(1.0), 1.0)
        self.assertEqual(sq.progress(1.3), 1.0)


class PlaylistDropTest(unittest.TestCase):
    def test_a_clip_dropped_from_the_table_is_never_played_again(self):
        state = {}
        pl = sq.Playlist(["a.mp4", "b.mp4", "c.mp4"], random.Random(1), state)
        pl.next()
        pl = sq.Playlist(["a.mp4", "c.mp4"], random.Random(1), state)
        for _ in range(10):
            self.assertNotEqual(pl.next(), "b.mp4")


class PanTest(unittest.TestCase):
    def test_within_reach_and_apart_from_the_other(self):
        rng = random.Random(7)
        for _ in range(300):
            other = rng.uniform(-sq.PAN_REACH, sq.PAN_REACH)
            pan = sq.pick_pan(rng, other)
            self.assertLessEqual(abs(pan), sq.PAN_REACH)
            self.assertGreaterEqual(abs(pan - other), sq.PAN_APART - 1e-9)
        self.assertLessEqual(abs(sq.pick_pan(rng, None)), sq.PAN_REACH)


class SpiceTest(unittest.TestCase):
    def test_env_starts_and_ends_at_zero_pulses_and_never_takes_over(self):
        for pulses in (2, 3, 4):
            ys = [sq.spice_env(i / 1000, pulses) for i in range(1001)]
            self.assertEqual(ys[0], 0.0)
            self.assertAlmostEqual(ys[-1], 0.0)
            self.assertLessEqual(max(ys), 0.9)
            peaks = sum(ys[i - 1] < ys[i] >= ys[i + 1] for i in range(1, 1000))
            self.assertEqual(peaks, pulses, (pulses, peaks))


class HoldTest(unittest.TestCase):
    def test_held_selection_is_one_effect_over_neutral_framing(self):
        sel = sq.held_selection("crush", {"Gamma": 2.0, "Black": 0.1})
        self.assertEqual(sq.enabled(sel), {"framing", "crush"})
        self.assertEqual(sel["framing"]["Zoom"], 1.0)
        self.assertEqual(sel["crush"]["Gamma"], 2.0)
        sel = sq.held_selection("framing", {"Zoom": 1.3, "Tx": 0, "Ty": 0, "Flipx": 1, "Flipy": 0})
        self.assertEqual(sq.enabled(sel), {"framing"})
        self.assertEqual(sel["framing"]["Flipx"], 1)

    def test_framing_rotates_only_to_flips_and_tilts(self):
        rng = random.Random(5)
        for _ in range(100):
            r = sq.params_for("framing", rng)["Rotate"]
            self.assertTrue(r in (0, 180) or abs(r) <= 12 or 168 <= r <= 192, r)


class PlanTest(unittest.TestCase):
    def test_long_clip_gets_a_window_of_at_most_cap(self):
        rng = random.Random(4)
        for _ in range(100):
            p = sq.plan_segment(clip(180.0), rng)
            self.assertLessEqual(p["length"], 120.0)
            self.assertLessEqual(p["start"] + p["length"] * p["speed"], 180.0 + 0.01)
            self.assertIsNone(p["turn"])
            self.assertGreaterEqual(p["length"] - p["tease"] - p["xfade"], sq.FLOOR - 0.01)
            self.assertTrue(p["tease"] == 0 or 1 <= p["tease"] <= 6)
            self.assertTrue(7.5 <= p["xfade"] <= 22.5)

    def test_lead_shortens_the_play_not_the_window(self):
        rng = random.Random(8)
        p = sq.plan_segment(clip(30.0), rng, lead=9.0)
        self.assertEqual(p["window"], 100.0)  # 30 s at 0.6 is 50 s forward, 50 s back
        self.assertEqual(p["length"], 91.0)
        self.assertGreaterEqual(p["length"] - p["tease"] - p["xfade"], sq.FLOOR - 0.01)

    def test_short_clip_plays_whole_and_clamps(self):
        rng = random.Random(5)
        for _ in range(100):
            p = sq.plan_segment(clip(9.0), rng)
            self.assertEqual(p["start"], 0.0)
            self.assertEqual(p["turn"], 15.0)  # 9 s at 0.6, then again
            self.assertEqual(p["length"], 30.0)
            self.assertTrue(p["tease"] == 0 or p["tease"] >= 1.0)
            self.assertGreaterEqual(p["length"] - p["tease"] - p["xfade"], sq.FLOOR - 0.01)
        p = sq.plan_segment(clip(4.0), rng)  # the shortest clip in the table
        self.assertGreaterEqual(p["xfade"], 0.3)

    def test_speed_from_fps_and_motion(self):
        rng = random.Random(6)
        self.assertEqual(sq.plan_segment(clip(30, fps=24, motion=0.5), rng)["speed"], 0.6)
        self.assertEqual(sq.plan_segment(clip(30, fps=30, motion=0.2), rng)["speed"], 0.4)
        self.assertEqual(sq.plan_segment(clip(30, fps=30, motion=0.01), rng)["speed"], 0.6)

    def test_window_stats_reads_the_buckets_under_the_window(self):
        c = clip(40, buckets=[{"mean": 0.1, "high": 0.2}, {"mean": 0.1, "high": 0.2},
                              {"mean": 0.5, "high": 0.9}, {"mean": 0.1, "high": 0.2}])
        self.assertAlmostEqual(sq.window_stats(c, 0, 20)["high"], 0.2)
        self.assertAlmostEqual(sq.window_stats(c, 15, 10)["high"], 0.9)
        self.assertAlmostEqual(sq.window_stats(c, 35, 5)["high"], 0.2)


class PlaylistTest(unittest.TestCase):
    def test_short_twice_long_once_no_adjacent_repeat(self):
        paths = ["VJ_Visuals/a.mp4", "VJ_Visuals/b.mp4", "VJ_Visuals/Long/c.mp4"]
        state = {}
        pl = sq.Playlist(paths, random.Random(7), state)
        seen = [pl.next() for _ in range(5 * 20)]
        self.assertEqual(state["last"], seen[-1])
        self.assertEqual(seen.count("VJ_Visuals/Long/c.mp4"), 20)
        self.assertEqual(seen.count("VJ_Visuals/a.mp4"), 40)
        for x, y in zip(seen, seen[1:]):
            self.assertNotEqual(x, y)


if __name__ == "__main__":
    unittest.main()
