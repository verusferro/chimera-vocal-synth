"""ARTIST BLOCK: GAME notes + HubertFA words -> one CHIMERA melody file per singer (Caine and the
six guests; the lines all six sing go to each of them) and the sung/spoken spans, with
covers/song/align.py's syllable-to-note matching.

  python covers/sam/make_ab.py [--show]

Writes $WORK/ab/build/<singer>.json and spans.json ([{voice, kind, line, start, end, text}],
seconds), which the build script uses to send sung notes to the S.A.M. bank and spoken lines to
S.A.M. TTS. Every sung line moves by whole octaves to Caine's range (the female roles go an
octave down), then the whole song moves TRANSPOSE semitones (the build shifts the instrumental
by the same amount).

The singers are human and the verses half rapped, so GAME's notes wander: a sung note's pitch is
the median RMVPE pitch at its start, moved by octaves next to its line's median, then snapped to
the key (E flat minor; E minor from the outro on).
"""
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "song"))
sys.path.insert(0, os.path.dirname(HERE))
import align  # noqa: E402
from paths import WORK  # noqa: E402

AB = f"{WORK}/ab"

align.BPM = 120.0
align.BEAT = 60.0 / align.BPM
align.T0 = 0.022
# the octave every sung line moves to (its median nearest this; Caine's lines sit about A#3)
CENTER = 57  # MIDI
# the whole song, down a fifth to A flat minor: Caine at about 156 Hz (the original key was too
# high for S.A.M., an octave down too low); build_ab.py reads it to shift the instrumental
TRANSPOSE = -7
NAMES = {n: i for i, n in enumerate(align.NAMES)}
OUTRO = 202.0  # s: the key goes up to E minor
MINOR = (0, 2, 3, 5, 7, 8, 10)  # natural minor, from the tonic

# Lines set by hand: (start s, length s, note, token; "" = the word's next syllable). The bridge is
# six voices at once, where neither GAME nor pYIN finds a line, so its notes follow the few pitches
# pYIN did hold (B flat 3 to B 3 at 155-157 s, E flat 3 to A flat 3 at 158-160 s, E to F sharp 5 in
# the second half, an octave down here) on a plain rhythm: a guess, not a transcription. The
# laughs and "Oh." have no aligned words.
HAND = {
    47: [(103.3, 0.2, "C4", "ha"), (103.55, 0.2, "C4", "ha"), (103.8, 0.3, "C4", "ha")],
    66: [(137.4, 0.45, "C4", "Oh")],
    71: [(154.0, 0.5, "A#3", "No"), (154.5, 1.5, "A#3", "more"), (156.0, 1.5, "B3", "crying"), (157.5, 0.5, "A#3", "")],
    72: [(158.0, 0.5, "D#3", "No"), (158.5, 0.75, "G#3", "use"), (159.25, 1.0, "G#3", "trying"), (160.25, 1.25, "F#3", "")],
    73: [(162.0, 0.5, "D#4", "Digital"), (162.5, 0.5, "D#4", ""), (163.0, 0.75, "C#4", ""), (163.75, 1.0, "F4", "landscape"), (164.75, 1.0, "D#4", "")],
    74: [(166.0, 0.5, "D#4", "Animated"), (166.5, 0.5, "F#4", ""), (167.0, 0.5, "F4", ""), (167.5, 0.5, "D#4", ""),
         (168.0, 1.0, "F#4", "hellscape"), (169.0, 2.0, "F4", "")],
    75: [(168.0, 0.25, "C4", "a"), (168.3, 0.5, "C4", "ha")],
}


def hand(rows):
    def midi(nm):
        return 12 * (int(nm[-1]) + 1) + NAMES[nm[:-1]]
    return [[(t - align.T0) / align.BEAT, (t + d - align.T0) / align.BEAT, midi(n), tok or None, tok or "-"] for t, d, n, tok in rows]


def snap(m, tonic):
    """float MIDI -> the nearest note of the key"""
    best = None
    for o in range(-1, 2):
        for d in MINOR:
            c = 12 * (round(m) // 12 + o) + (tonic + d) % 12
            if best is None or abs(c - m) < abs(best - m):
                best = c
    return best


def refine(ev, f0, rate):
    """the line's sung pitches: RMVPE at each note's first 0.3 s, octave-fixed, in the key"""
    t = [align.T0 + e[0] * align.BEAT for e in ev]
    raw = []
    for e, t0 in zip(ev, t):
        a, b = int(t0 * rate), int(min(align.T0 + e[1] * align.BEAT, t0 + 0.3) * rate)
        v = f0[a:max(b, a + 1)]
        v = v[~np.isnan(v)]
        raw.append(12 * np.log2(np.median(v) / 440) + 69 if len(v) else float(e[2]))
    med = float(np.median(raw))
    out = []
    for e, t0, m in zip(ev, t, raw):
        if abs(m - med) > 7:
            m += 12 * round((med - m) / 12)
        out.append([e[0], e[1], snap(m, 4 if t0 >= OUTRO else 3), e[3], e[4]])
    return out


def game_notes(path):
    """GAME's 'start end E3-2' lines -> (start, end, midi)"""
    out = []
    for line in open(path):
        a = line.split()
        if len(a) < 3 or float(a[1]) - float(a[0]) < align.MIN_NOTE:
            continue
        nm = a[2]
        i = next(k for k in range(len(nm)) if nm[k] in "+-" and k > 1 and nm[k - 1].isdigit())
        pc, octv = nm[: i - 1], int(nm[i - 1])
        out.append((float(a[0]), float(a[1]), round(12 * (octv + 1) + NAMES[pc] + float(nm[i:]) / 100)))
    return out


def main():
    notes = game_notes(f"{AB}/song/game/vocals.txt")
    words = json.load(open(f"{AB}/song/aligned_words.json"))
    lines = {l["i"]: l for l in json.load(open(f"{AB}/song/lines_timed.json"))}
    words = [w for w in words if w["line"] in lines]
    from cover import rmvpe_hz  # the shared stem pitch (pYIN dropped most held notes here)
    f0 = rmvpe_hz(f"{AB}/song/vocals.wav", f"{AB}/research/f0_rmvpe.npy")
    f0, rate = np.where(f0 > 0, f0, np.nan), 100.0
    res = align.build(notes, words)
    res.update({ln: hand(rows) for ln, rows in HAND.items()})
    voices = {}  # singer -> lines' events, in order of first appearance (Caine first)
    spans = []
    for ln, ev in sorted(res.items()):
        l = lines[ln]
        if l["kind"] == "SUNG" and ln not in HAND:
            ev = refine(ev, f0, rate)
        if l["kind"] == "SUNG":
            shift = 12 * round((CENTER - float(np.median([e[2] for e in ev]))) / 12) + TRANSPOSE
            ev = [[e[0], e[1], e[2] + shift, e[3], e[4]] for e in ev]
        if "--show" in sys.argv:
            align.show(ln, ev)
        # one head per singer: "All six (Pomni, …)" goes to each of them, "Ragatha + others" to Ragatha
        m = re.match(r"All six \((.*)\)", l["who"])
        for who in m.group(1).split(", ") if m else [l["who"].split(" + ")[0]]:
            voices.setdefault(who, []).append(ev)
            spans.append({"voice": who, "kind": l["kind"], "line": ln, "who": l["who"], "text": l["text"],
                          "start": align.T0 + ev[0][0] * align.BEAT, "end": align.T0 + ev[-1][1] * align.BEAT})
    os.makedirs(f"{AB}/build", exist_ok=True)
    for name, ls in voices.items():
        ev = sorted((list(e) for l in ls for e in l), key=lambda e: e[0])
        # lines that run into each other: the earlier note gives way
        for a, b in zip(ev, ev[1:]):
            if b[0] < a[1]:
                a[1] = b[0]
        ev = align.fit([e for e in ev if e[1] > e[0]])
        json.dump(align.melody(ev), open(f"{AB}/build/{name}.json", "w"))
        lo, hi = min(e[2] for e in ev), max(e[2] for e in ev)
        print(f"build/{name}.json: {len(ev)} notes, {align.name(lo)}..{align.name(hi)}")
    json.dump(spans, open(f"{AB}/build/spans.json", "w"), indent=1)


if __name__ == "__main__":
    main()
