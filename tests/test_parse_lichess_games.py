"""Tests for openings/parse_lichess_games.py.

A hand-made fixture PGN (tests/fixtures/sample.pgn) drives these tests. Its
Event headers use the exact text from docs/matches_openings.md: "Rated Blitz
game" and "Rated Rapid game". All expected counts, order, tie-breaks, and ID
strings below are worked out by hand from the fixture and the spec, never by
running the code under test.

Tests run the parser with P=4 and K=2000 unless noted, so lines stay short
enough to count by hand.
"""

import json
import os
import tempfile
import unittest
from compression import zstd

from openings import parse_lichess_games as P

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample.pgn")


def eligible_lines_by_hand():
    """The P=4, K=2000 counts of the fixture, worked out by hand.

    Walking the fixture game by game and applying the eligibility and move
    rules from docs/matches_openings.md:

    - game 1  Blitz 2100/2050  -> "e4 e5 Nf3 Nc6"
    - game 2  Rapid 2200/2000  -> "e4 e5 Nf3 Nc6"  (comments skipped)
    - game 3  Blitz 2500/2500  -> "e4 e5 Nf3 Nc6"  (variation and $1 skipped)
    - game 4  Rapid 2300/2300  -> "d4 d5 c4 e6"
    - game 5  Blitz 2400/2400  -> "d4 d5 c4 e6"
    - game 6  Blitz 2000/2000  -> "c4 e5 Nc3 Nf6"  (exactly K is eligible)
    - game 7  Rapid 2100/2100  -> "d4 Nf6 c4 g6"
    - game 8  Blitz 1900/2600  -> excluded (White below K)
    - game 9  Blitz   ?/2200   -> excluded (WhiteElo is '?')
    - game 10 Blitz missing WhiteElo -> excluded
    - game 11 Blitz tournament -> excluded (Event is not "Rated Blitz game")
    - game 12 Bullet           -> excluded (not Blitz or Rapid)
    - game 13 Blitz 2400/2400, 3 plies -> excluded (fewer than P plies)
    """
    return {
        "e4 e5 Nf3 Nc6": 3,
        "d4 d5 c4 e6": 2,
        "c4 e5 Nc3 Nf6": 1,
        "d4 Nf6 c4 g6": 1,
    }


class ExtractMovesTests(unittest.TestCase):
    """Move-text parsing rules, checked on hand-written inputs."""

    def test_skips_comments_nags_variations_numbers_results(self):
        # Expected tokens written out by hand from the spec rules.
        text = "1. e4 { [%eval 0.2] } e5 (1... c5 2. Nf3) 2. Nf3 $1 Nc6 1-0"
        self.assertEqual(
            P.extract_moves(text, 4), ["e4", "e5", "Nf3", "Nc6"]
        )

    def test_strips_san_suffixes(self):
        # Check, mate, and annotation marks are stripped; "+", "#", "!", "?".
        text = "1. e4 e5 2. Qh5 Nc6 3. Bc4+ Nf6?? 4. Qxf7# 1-0"
        self.assertEqual(
            P.extract_moves(text, 5), ["e4", "e5", "Qh5", "Nc6", "Bc4"]
        )

    def test_stops_at_limit(self):
        text = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6"
        self.assertEqual(P.extract_moves(text, 2), ["e4", "e5"])

    def test_returns_fewer_when_game_too_short(self):
        text = "1. e4 e5 2. Nf3 1-0"
        self.assertEqual(P.extract_moves(text, 4), ["e4", "e5", "Nf3"])

    def test_glued_move_number(self):
        # Some exports write "1.e4" with no space; the number must be dropped.
        text = "1.e4 e5 2.Nf3 Nc6"
        self.assertEqual(
            P.extract_moves(text, 4), ["e4", "e5", "Nf3", "Nc6"]
        )


class EligibilityTests(unittest.TestCase):
    def test_event_eligible(self):
        self.assertTrue(P.event_eligible("Rated Blitz game"))
        self.assertTrue(P.event_eligible("Rated Rapid game"))
        self.assertFalse(P.event_eligible("Rated Bullet game"))
        self.assertFalse(
            P.event_eligible("Rated Blitz tournament https://lichess.org/x")
        )

    def test_parse_elo_missing_or_question_mark(self):
        self.assertIsNone(P.parse_elo(None))
        self.assertIsNone(P.parse_elo("?"))
        self.assertEqual(P.parse_elo("2000"), 2000)


class ListIdTests(unittest.TestCase):
    def test_default_frequency_id(self):
        # Hand-written from the "List IDs" section of docs/matches_openings.md.
        self.assertEqual(
            P.list_id("2026-09", 2000, 16, 1024),
            "freq-2026-09-k2000-p16-f1024",
        )


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = os.path.join(self.tmp.name, "data")
        self.out_dir = os.path.join(self.tmp.name, "openings")
        os.makedirs(self.data_dir)
        os.makedirs(self.out_dir)
        # Compress the fixture into a .zst source the parser can read.
        self.month = "2099-01"
        self.src = os.path.join(
            self.data_dir, f"lichess_db_standard_rated_{self.month}.pgn.zst"
        )
        with open(FIXTURE, "rb") as fobj:
            raw = fobj.read()
        with open(self.src, "wb") as fobj:
            fobj.write(zstd.compress(raw))

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, k=2000, p=4, f=3):
        return P.build(self.month, k, p, f, self.data_dir, self.out_dir)

    def test_frequency_order_and_tiebreak(self):
        # Expected output lines, in order, worked out by hand:
        #   count 3: "e4 e5 Nf3 Nc6"
        #   count 2: "d4 d5 c4 e6"
        #   count 1 tie: "c4 e5 Nc3 Nf6" < "d4 Nf6 c4 g6" by ascending key,
        #     so the c4 line is kept and the d4 Nf6 line is dropped at F=3.
        lid = self.build(f=3)
        pgn = os.path.join(self.out_dir, lid + ".pgn")
        with open(pgn, "r", encoding="utf-8") as fobj:
            lines = fobj.read().splitlines()
        self.assertEqual(
            lines,
            ["e4 e5 Nf3 Nc6", "d4 d5 c4 e6", "c4 e5 Nc3 Nf6"],
        )

    def test_output_format_one_game_per_line_p_moves_only(self):
        # Documented layout: one game per line, only the first P moves, no
        # comments, results, or move numbers. Hand-written expected lines.
        lid = self.build(p=4, f=3)
        with open(os.path.join(self.out_dir, lid + ".pgn"), encoding="utf-8") as fobj:
            content = fobj.read()
        self.assertEqual(
            content,
            "e4 e5 Nf3 Nc6\n" "d4 d5 c4 e6\n" "c4 e5 Nc3 Nf6\n",
        )
        for line in content.splitlines():
            self.assertEqual(len(line.split(" ")), 4)

    def test_metadata_counts(self):
        # games_kept and distinct_lines_seen from the hand count; fth_line_count
        # is the count of the F=3rd line, which is 1.
        by_hand = eligible_lines_by_hand()
        lid = self.build(f=3)
        with open(os.path.join(self.out_dir, lid + ".json"), encoding="utf-8") as fobj:
            meta = json.load(fobj)
        self.assertEqual(meta["games_kept"], sum(by_hand.values()))
        self.assertEqual(meta["distinct_lines_seen"], len(by_hand))
        self.assertEqual(meta["fth_line_count"], 1)
        self.assertEqual(meta["list_id"], "freq-2099-01-k2000-p4-f3")

    def test_refuses_to_overwrite(self):
        lid = self.build(f=3)
        # A second build with the same parameters must fail, not overwrite.
        with self.assertRaises(FileExistsError):
            self.build(f=3)
        # The first output is untouched.
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, lid + ".pgn")))

    def test_fails_when_too_few_lines_qualify(self):
        # Only 4 distinct lines qualify; F=5 cannot be met.
        with self.assertRaises(ValueError):
            self.build(f=5)

    def test_temp_database_removed_after_success(self):
        lid = self.build(f=3)
        self.assertFalse(
            os.path.exists(os.path.join(self.data_dir, lid + ".sqlite"))
        )


if __name__ == "__main__":
    unittest.main()
