"""Fix the aligner's gross word-time errors with Whisper's word timestamps.

  COVERS_WORK=covers/work/<song> python covers/song/fix_words.py

HubertFA (hfa/final.py) is exact where it is right, but in a busy stem (a choir, ad-libs, a
line missing from lyrics.txt) it can stretch one word over seconds and push the next ones late.
Whisper hears the same stem on its own and gives rough (about 0.1 s) word times. The lyrics and
Whisper's words are matched in order (difflib); a matched word that the aligner put more than
OFF seconds from Whisper's time takes Whisper's time, and words between two matched words that
fell outside them are spread evenly between them. Everything else keeps the aligner's times.

Reads WORK/hfa/words.json (the first run copies it to words_aligner.json and always reads that),
and WORK/hfa/whisper_words.json (made here on the first run: faster-whisper medium.en on the vocal
stem). Writes WORK/hfa/words.json.
"""
import difflib
import glob
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import WORK  # noqa: E402

OFF = 0.35  # s
H = f"{WORK}/hfa"


def whisper_words():
    path = f"{H}/whisper_words.json"
    if not os.path.exists(path):
        import librosa
        from faster_whisper import WhisperModel
        y, _ = librosa.load(glob.glob(f"{WORK}/stems/*(vocals)*")[0], sr=16000)
        m = WhisperModel("medium.en", device="cpu", compute_type="int8")
        segs, _ = m.transcribe(y, word_timestamps=True, condition_on_previous_text=False)
        json.dump([{"w": x.word, "s": round(x.start, 3), "e": round(x.end, 3)} for s in segs for x in s.words], open(path, "w"))
    return json.load(open(path))


def move(w, t0, t1):
    """the word to [t0, t1], its phones scaled along"""
    a, b = w["start"], max(w["end"], w["start"] + 1e-3)
    f = lambda t: round(t0 + (t - a) * (t1 - t0) / (b - a), 3)  # noqa: E731
    w["phones"] = [p | {"start": f(p["start"]), "end": f(p["end"])} for p in w["phones"]]
    w["start"], w["end"] = round(t0, 3), round(t1, 3)


def fix(words, wh):
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower())  # noqa: E731
    pairs = []
    sm = difflib.SequenceMatcher(None, [norm(w["word"]) for w in words], [norm(x["w"]) for x in wh], autojunk=False)
    for blk in sm.get_matching_blocks():
        pairs += [(blk.a + k, wh[blk.b + k]) for k in range(blk.size)]
    # keep only matches whose times rise with the lyrics (a short word like "your" can match a
    # Whisper word from the line before): the longest rising run
    best, prev = [1] * len(pairs), [-1] * len(pairs)
    for j in range(len(pairs)):
        for i in range(j):
            if pairs[i][1]["s"] < pairs[j][1]["s"] and best[i] + 1 > best[j]:
                best[j], prev[j] = best[i] + 1, i
    j, keep = (max(range(len(pairs)), key=best.__getitem__) if pairs else -1), []
    while j >= 0:
        keep.append(pairs[j])
        j = prev[j]
    pairs = dict(reversed(keep))
    # a match that leaves the lyric words before it no room (Whisper heard other words there) is
    # no anchor
    idx = sorted(pairs)
    for a, b in zip(idx, idx[1:]):
        if a in pairs and b - a > 1 and pairs[b]["s"] - pairs[a]["e"] < 0.12 * (b - a - 1):
            del pairs[b]
    moved = 0
    for i, x in pairs.items():
        w = words[i]
        if abs(w["start"] - x["s"]) > OFF:
            move(w, x["s"], max(x["e"], x["s"] + 0.08))
            moved += 1
    anchors = sorted(pairs)
    spread = 0
    for a, b in zip(anchors, anchors[1:]):
        lo, hi = words[a]["end"], words[b]["start"]
        gap = words[a + 1: b]
        if gap and hi > lo and any(w["start"] < lo or w["end"] > hi for w in gap):
            # the unmatched words follow the matched one at a sung pace (at most 0.4 s each)
            step = min((hi - lo) / len(gap), 0.4)
            for k, w in enumerate(gap):
                move(w, lo + k * step, lo + (k + 1) * step)
            spread += len(gap)
    for i, w in enumerate(words):
        # an unmatched word held over 1.2 s: the aligner put its start in a pause or an ad-lib
        if i not in pairs and w["end"] - w["start"] > 1.2:
            move(w, w["end"] - 0.6, w["end"])
        if i and w["start"] < words[i - 1]["start"]:
            move(w, words[i - 1]["start"] + 0.02, max(w["end"], words[i - 1]["start"] + 0.1))
    for w, nxt in zip(words, words[1:]):  # no word runs into the next one
        if w["end"] > nxt["start"]:
            move(w, w["start"], max(nxt["start"], w["start"] + 0.02))
    return moved, spread, len(pairs)


def main():
    src = f"{H}/words_aligner.json"
    if not os.path.exists(src):
        shutil.copy(f"{H}/words.json", src)
    words = json.load(open(src))
    moved, spread, matched = fix(words, whisper_words())
    json.dump(words, open(f"{H}/words.json", "w"), indent=1)
    print(f"{len(words)} words, {matched} matched to Whisper; moved {moved}, spread {spread}")


if __name__ == "__main__":
    main()
