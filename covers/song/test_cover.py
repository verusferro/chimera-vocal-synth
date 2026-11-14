"""Run: python -m unittest discover -s covers/song -p test_cover.py"""
import unittest
from unittest.mock import patch

import numpy as np

import cover


class SyllableTiming(unittest.TestCase):
    def test_repeated_word_keeps_its_own_end_and_leaves_the_gap_silent(self):
        words = [
            {"word": "hey", "line": 1, "start": 0.0, "end": 1.0,
             "phones": [{"ph": "ey", "start": 0.0}]},
            {"word": "hey", "line": 1, "start": 4.0, "end": 8.0,
             "phones": [{"ph": "ey", "start": 4.0}]},
        ]
        mid = np.full(850, np.nan)
        mid[:100] = 48.0
        mid[400:800] = 52.0
        with patch.multiple(cover.align, BPM=60.0, BEAT=1.0, T0=0.0, GRID=0.125):
            events = cover.f0_lines(words, mid, lambda ln: 0)[1]
        self.assertEqual([e[:4] for e in events], [
            [0.0, 1.0, 48, "hey"],
            [4.0, 5.5, 52, "hey"],
        ])


class Hold(unittest.TestCase):
    def test_a_note_holds_while_the_stem_does_up_to_the_next_singers_note(self):
        mid = np.full(500, np.nan)
        mid[:300] = 60.2  # the singer holds C4 to 3 s, then stops
        with patch.multiple(cover.align, BPM=60.0, BEAT=1.0, T0=0.0, GRID=0.125):
            alone = cover.hold([[0.0, 1.0, 60, "la", "la"]], mid, [0.0])
            cut = cover.hold([[0.0, 1.0, 60, "la", "la"]], mid, [0.0, 2.0])
            other_pitch = cover.hold([[0.0, 1.0, 64, "la", "la"]], mid, [0.0])
        self.assertEqual(alone[0][1], 3.0)
        self.assertEqual(cut[0][1], 2.0)  # another voice's note at 2 s
        self.assertEqual(other_pitch[0][1], 1.0)  # the stem holds another pitch: no hold


class Fold(unittest.TestCase):
    def test_octave_errors_fold_but_real_leaps_and_high_lines_stay(self):
        notes = lambda ps: [[i, i + 1, p, None, "x"] for i, p in enumerate(ps)]  # noqa: E731
        fold = lambda ps: [e[2] for e in cover.fold(notes(ps), 7)]  # noqa: E731
        self.assertEqual(fold([53, 54, 78, 53]), [53, 54, 54, 53])  # two octaves up: back
        self.assertEqual(fold([58, 57, 50]), [58, 57, 50])  # a sung fall of a fifth
        # a high line's low note 9 off: folding it up would take it away from the line, so it stays
        self.assertEqual(fold([63, 70, 66, 72, 63, 57]), [63, 70, 66, 72, 63, 57])


class TrimTail(unittest.TestCase):
    def test_the_last_words_later_syllables_stay_and_a_stray_note_goes(self):
        ev = [[0, 1, 53, "me", "me"], [1, 2, 56, "away", "away.1"], [2, 4, 60, None, "away.2"], [4, 5, 70, "-", "-"]]
        self.assertEqual([e[4] for e in cover.trim_tail(ev)], ["me", "away.1", "away.2"])


if __name__ == "__main__":
    unittest.main()
