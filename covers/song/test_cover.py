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


if __name__ == "__main__":
    unittest.main()
