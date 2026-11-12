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

    def test_a_moved_held_word_keeps_its_length_while_the_stem_sounds(self):
        # the aligner had "peel" late but held 2 s; Whisper puts it at 20.5 with a 0.3 s word; the
        # stem sounds to 22.3: the word lasts to there, not to Whisper's end
        words = [word("black", 20.0, 20.4), word("peel", 21.2, 23.2)]
        wh = [{"w": " black", "s": 20.0, "e": 20.4}, {"w": " peel", "s": 20.5, "e": 20.8}]
        voiced = [False] * 2000 + [True] * 230 + [False] * 300  # sounding 20.0-22.3 s
        fix(words, wh, voiced=voiced)
        self.assertEqual(words[1]["start"], 20.5)
        self.assertAlmostEqual(words[1]["end"], 22.3, places=2)

    def test_whisper_late_on_a_held_vowel_and_a_held_last_word(self):
        # the stem sounds 137.4-139.6 (a laugh, then "aaartist block"); the aligner has "artist" at
        # 138.0, Whisper at 138.36 (late, on the held vowel): the aligner's start stays, a sound
        # before the word is not taken (the laugh), and the held end of "block" is the word's
        words = [word("artist", 138.0, 138.8), word("block", 138.9, 139.44), word("my", 140.5, 140.8)]
        wh = [{"w": " artist", "s": 138.36, "e": 138.8}, {"w": " block", "s": 138.9, "e": 139.4}, {"w": " my", "s": 140.5, "e": 140.8}]
        voiced = [False] * 13740 + [True] * 220 + [False] * 90 + [True] * 30 + [False] * 300
        fix(words, wh, voiced=voiced)
        self.assertEqual(words[0]["start"], 138.0)
        self.assertEqual(words[1]["end"], 139.6)
        self.assertEqual(words[2]["start"], 140.5)


if __name__ == "__main__":
    unittest.main()
