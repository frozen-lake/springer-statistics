"""Tests for openings/shuffle_openings_list.py.

Shuffle output is not checked against hand-worked values. Per the spec, the
tests check properties: the output has M lines, each line comes from the
frequency list with no repeats, the same seed gives the same output, and a
different seed gives a different output. The list ID strings are hand-written
from the "List IDs" section of docs/matches_openings.md.
"""

import json
import os
import tempfile
import unittest

from openings import shuffle_openings_list as S


class ListIdTests(unittest.TestCase):
    def test_shuffled_id(self):
        # Hand-written from docs/matches_openings.md "List IDs" section.
        self.assertEqual(
            S.list_id("freq-2026-09-k2000-p16-f1024", 42, 512),
            "shuf-freq-2026-09-k2000-p16-f1024-seed42-m512",
        )


class ShuffleLinesTests(unittest.TestCase):
    def test_does_not_modify_input(self):
        lines = [f"line{i}" for i in range(10)]
        original = list(lines)
        S.shuffle_lines(lines, 1, 5)
        self.assertEqual(lines, original)

    def test_uses_only_first_m_lines(self):
        # Expected set written by hand: the first 5 of line0..line9 in
        # frequency order are line0..line4.
        lines = [f"line{i}" for i in range(10)]
        out = S.shuffle_lines(lines, 3, 5)
        self.assertEqual(sorted(out), ["line0", "line1", "line2", "line3", "line4"])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out_dir = os.path.join(self.tmp.name, "openings")
        os.makedirs(self.out_dir)
        self.freq_id = "freq-2099-01-k2000-p4-f8"
        self.freq_lines = [f"m{i} a b c" for i in range(8)]
        with open(
            os.path.join(self.out_dir, self.freq_id + ".pgn"), "w", encoding="utf-8"
        ) as fobj:
            for line in self.freq_lines:
                fobj.write(line + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, lid):
        with open(os.path.join(self.out_dir, lid + ".pgn"), encoding="utf-8") as fobj:
            return fobj.read().splitlines()

    def test_m_lines_from_freq_no_repeats(self):
        lid = S.build(self.freq_id, 42, 5, self.out_dir)
        out = self.read(lid)
        self.assertEqual(len(out), 5)
        self.assertEqual(len(set(out)), 5)  # no repeats
        for line in out:
            self.assertIn(line, self.freq_lines)

    def test_same_seed_same_output(self):
        lid1 = S.build(self.freq_id, 7, 5, self.out_dir)
        out1 = self.read(lid1)
        # Build again into a fresh dir to avoid the overwrite guard.
        out_dir2 = os.path.join(self.tmp.name, "openings2")
        os.makedirs(out_dir2)
        with open(
            os.path.join(out_dir2, self.freq_id + ".pgn"), "w", encoding="utf-8"
        ) as fobj:
            for line in self.freq_lines:
                fobj.write(line + "\n")
        lid2 = S.build(self.freq_id, 7, 5, out_dir2)
        with open(os.path.join(out_dir2, lid2 + ".pgn"), encoding="utf-8") as fobj:
            out2 = fobj.read().splitlines()
        self.assertEqual(out1, out2)

    def test_different_seed_different_output(self):
        a = S.shuffle_lines(self.freq_lines, 1, 8)
        b = S.shuffle_lines(self.freq_lines, 2, 8)
        self.assertNotEqual(a, b)

    def test_refuses_to_overwrite(self):
        S.build(self.freq_id, 42, 5, self.out_dir)
        with self.assertRaises(FileExistsError):
            S.build(self.freq_id, 42, 5, self.out_dir)

    def test_fails_when_m_larger_than_freq_list(self):
        with self.assertRaises(ValueError):
            S.build(self.freq_id, 42, 9, self.out_dir)

    def test_metadata(self):
        lid = S.build(self.freq_id, 42, 5, self.out_dir)
        with open(os.path.join(self.out_dir, lid + ".json"), encoding="utf-8") as fobj:
            meta = json.load(fobj)
        self.assertEqual(meta["frequency_list_id"], self.freq_id)
        self.assertEqual(meta["seed"], 42)
        self.assertEqual(meta["m"], 5)
        self.assertEqual(
            meta["list_id"], "shuf-freq-2099-01-k2000-p4-f8-seed42-m5"
        )


class MainCliValidationTests(unittest.TestCase):
    """--m is rejected before any work starts."""

    def test_rejects_zero_m(self):
        with self.assertRaises(SystemExit):
            S.main(["--freq", "freq-x", "--seed", "1", "--m", "0"])

    def test_rejects_negative_m(self):
        with self.assertRaises(SystemExit):
            S.main(["--freq", "freq-x", "--seed", "1", "--m", "-1"])


if __name__ == "__main__":
    unittest.main()
