"""Run: python -m unittest discover -s covers/song -p 'test_*.py'"""
import unittest

from fix_words import fix


def word(w, s, e):
    return {"word": w, "start": s, "end": e, "phones": [{"ph": "ah", "start": s, "end": e}]}


class WhisperGuidedFix(unittest.TestCase):
    def test_late_words_move_to_whisper_and_unheard_words_follow_in_order(self):
        # the aligner held "spoil" for 6 s and put the rest late; Whisper missed "with your"
        words = [word("gonna", 78.1, 78.3), word("spoil", 78.6, 85.0), word("everybody", 85.9, 86.4),
                 word("with", 86.4, 86.5), word("your", 86.5, 86.6), word("bad", 86.6, 86.8)]
        wh = [{"w": " gonna", "s": 78.1, "e": 78.3}, {"w": " spoil", "s": 78.4, "e": 78.7},
              {"w": " everybody,", "s": 78.8, "e": 79.4}, {"w": " bad", "s": 80.2, "e": 80.5}]
        fix(words, wh)
        starts = [w["start"] for w in words]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual([words[i]["start"] for i in (1, 2, 5)], [78.6, 78.8, 80.2])  # 78.6: within 0.35 s
        self.assertLessEqual(words[1]["end"], 78.8)  # "spoil" no longer runs over "everybody"
        self.assertTrue(all(79.4 <= words[i]["start"] < 80.2 for i in (3, 4)))
        self.assertEqual(words[2]["phones"][0]["start"], 78.8)  # phones move with their word

    def test_a_match_outside_the_lines_region_is_no_anchor(self):
        # the line is sung at 171 s; Whisper heard the same words again only at 187 s (a repeat)
        words = [dict(word("day", 171.0, 171.3), line=54), dict(word("dreams", 171.3, 171.8), line=54)]
        wh = [{"w": " day", "s": 186.5, "e": 186.7}, {"w": " dreams", "s": 186.7, "e": 186.9}]
        fix(words, wh, lambda ln: (170.3, 179.0))
        self.assertEqual([w["start"] for w in words], [171.0, 171.3])

    def test_an_anchor_that_crushes_the_lines_after_it_is_dropped(self):
        # "day" matched a later repeat (16 s off) and would squeeze 3 words into 0.1 s before "end"
        words = [word("day", 170.4, 170.8), word("a", 171.0, 171.2), word("b", 172.0, 172.2),
                 word("c", 180.0, 180.2), word("end", 186.8, 187.2)]
        wh = [{"w": " day", "s": 186.5, "e": 186.6}, {"w": " end", "s": 186.7, "e": 187.1}]
        fix(words, wh)
        self.assertEqual([w["start"] for w in words][:4], [170.4, 171.0, 172.0, 180.0])


if __name__ == "__main__":
    unittest.main()
