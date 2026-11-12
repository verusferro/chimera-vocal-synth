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


def fix(words, wh, win=None, voiced=None):
    """`win(line)`: the (start, end) s of the region the aligner had for that line, or None; a
    Whisper word outside it is a match to the same words sung elsewhere (a repeated line).
    `voiced`: the stem sounding or not, per 10 ms (None: not known)"""
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower())  # noqa: E731
    pairs = []
    sm = difflib.SequenceMatcher(None, [norm(w["word"]) for w in words], [norm(x["w"]) for x in wh], autojunk=False)
    for blk in sm.get_matching_blocks():
        pairs += [(blk.a + k, wh[blk.b + k]) for k in range(blk.size)]
    if win:
        pairs = [(i, x) for i, x in pairs if (r := win(words[i]["line"])) is None or r[0] <= x["s"] <= r[1]]
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
    # two matches that leave the lyric words between them no room (Whisper heard other words there,
    # or the same words sung later): the one further from the aligner's time is no anchor
    while True:
        idx = sorted(pairs)
        tight = next(((a, b) for a, b in zip(idx, idx[1:]) if b - a > 1 and pairs[b]["s"] - pairs[a]["e"] < 0.12 * (b - a - 1)), None)
        if tight is None:
            break
        del pairs[max(tight, key=lambda i: abs(words[i]["start"] - pairs[i]["s"]))]
    moved = 0

    def heard_until(t0, t1):
        """where the stem stops sounding after t0 (gaps under 0.1 s pass), at most t1"""
        if voiced is None:
            return t1
        k, end, gap = int(t0 * 100), int(t1 * 100), 0
        while k < min(end, len(voiced)) and gap < 10:
            gap = 0 if voiced[k] else gap + 1
            k += 1
        return (k - gap) / 100

    for i, x in pairs.items():
        w = words[i]
        # Whisper later than the aligner, but under 0.8 s, with the stem sounding all the way
        # between: Whisper heard the word late on a held first vowel ("Aaartist"); the aligner's
        # start stays (seconds apart is the aligner's error on a busy stem: that still moves)
        if voiced is not None and 0 < x["s"] - w["start"] < 0.8 and heard_until(w["start"], x["s"]) >= x["s"] - 0.02:
            continue
        if abs(w["start"] - x["s"]) > OFF:
            # Whisper's word ends are rough and short on a held note: the word keeps the aligner's
            # length while the stem still sounds
            end = max(x["e"], x["s"] + 0.08, heard_until(x["s"], x["s"] + w["end"] - w["start"]))
            move(w, x["s"], end)
            moved += 1
    anchors = sorted(pairs)
    spread = 0
    for a, b in zip(anchors, anchors[1:]):
        lo, hi = words[a]["end"], words[b]["start"]
        gap = words[a + 1: b]
        if gap and hi > lo and any(w["start"] < lo or w["end"] > hi for w in gap):
            # the unmatched words follow the matched one in the aligner's proportions (a held word
            # stays the longest), squeezed into the room there is, never longer than the aligner had
            d = [max(w["end"] - w["start"], 0.05) for w in gap]
            k = min(1.0, (hi - lo) / sum(d))
            t = lo
            for w, dw in zip(gap, d):
                move(w, t, t + dw * k)
                t += dw * k
            spread += len(gap)
    for i, w in enumerate(words):
        # an unmatched word held over 1.2 s while the stem is mostly silent there: the aligner put
        # its start in a pause or an ad-lib (a word the stem sounds through is a held note: kept)
        if i not in pairs and w["end"] - w["start"] > 1.2 and (voiced is None or heard_until(w["start"], w["end"]) - w["start"] < 0.8 * (w["end"] - w["start"])):
            move(w, w["end"] - 0.6, w["end"])
        if i and w["start"] < words[i - 1]["start"]:
            move(w, words[i - 1]["start"] + 0.02, max(w["end"], words[i - 1]["start"] + 0.1))
    for w, nxt in zip(words, words[1:]):  # no word runs into the next one
        if w["end"] > nxt["start"]:
            move(w, w["start"], max(nxt["start"], w["start"] + 0.02))
    if voiced is not None:
        for i, w in enumerate(words):
            nxt = words[i + 1]["start"] if i + 1 < len(words) else w["end"] + 1.0
            # the stem still sounding after the word, up to the next one (at most 1 s more), is the
            # word held on: its last phone takes it. (Its start is left alone: a sound before a
            # word is as often a laugh or an effect as the word's own first vowel)
            e = heard_until(w["end"], min(nxt, w["end"] + 1.0))
            if e > w["end"] + 0.05:
                w["end"] = w["phones"][-1]["end"] = round(e, 3)
    return moved, spread, len(pairs)


def main():
    src = f"{H}/words_aligner.json"
    if not os.path.exists(src):
        shutil.copy(f"{H}/words.json", src)
    words = json.load(open(src))
    win = None
    if os.path.exists(f"{H}/regions.json"):  # [name, start, end, first line, last line + 1], 0-based lines
        regions = json.load(open(f"{H}/regions.json"))
        win = lambda ln: next(((a, b) for _, a, b, l0, l1 in regions if l0 < ln <= l1), None)  # noqa: E731
    moved, spread, matched = fix(words, whisper_words(), win, stem_sounding())
    json.dump(words, open(f"{H}/words.json", "w"), indent=1)
    print(f"{len(words)} words, {matched} matched to Whisper; moved {moved}, spread {spread}")


def stem_sounding():
    """the vocal stem sounding (RMS within 35 dB of its loudest), per 10 ms"""
    import librosa
    import numpy as np
    y, _ = librosa.load(glob.glob(f"{WORK}/stems/*(vocals)*")[0], sr=16000)
    db = librosa.amplitude_to_db(librosa.feature.rms(y=y, frame_length=640, hop_length=160)[0], ref=np.max)
    return db > -35


if __name__ == "__main__":
    main()
