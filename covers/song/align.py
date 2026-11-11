"""HubertFA words (with phones) + GAME notes -> a CHIMERA melody file, one syllable per note.

  python covers/song/align.py NOTES.txt WORDS.json     print every line's syllables on their notes (make_song.py builds the files)

The notes are the truth for time and pitch (the original is a synth voice: exact, on the grid).
The words only say which syllable goes on which note: syllables (at their vowel's onset) and notes
(at their onset) are matched in order, by a dynamic program that may leave a note without a
syllable (a melisma, written "-") or a syllable without a note (it then splits the note it is in).
Times go on the song's grid: 96 BPM, sixteenths, beat 0 at T0.

`extra` (see build) appends hand-written phrases and copies of earlier lines.
"""
import json
import sys

BPM = 96.0
BEAT = 60.0 / BPM
GRID = 0.25  # beats
T0 = 0.0
REST = 0.2  # s of silence after a note that makes a rest (a breath)
MIN_NOTE = 0.09  # s: shorter GAME notes are slides between pitches, not notes
MELISMA, ORPHAN = 0.15, 0.3  # costs (s) of a note without a syllable, and of a syllable without a note
VOWELS = set("aa ae ah ao aw ax ay eh er ey ih iy ow oy uh uw".split())
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def name(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def q(t):
    return round((t - T0) / BEAT / GRID) * GRID


def load_notes(path, shift=0.0):
    notes = []
    for line in open(path):
        a = line.split()
        if len(a) >= 3 and float(a[1]) - float(a[0]) >= MIN_NOTE:
            notes.append((float(a[0]) + shift, float(a[1]) + shift, round(float(a[2]))))
    return notes


def syllables(words):
    """[{word, first (of its word), t (vowel onset), line}]"""
    out = []
    for w in words:
        vs = [p["start"] for p in w["phones"] if p["ph"] in VOWELS] or [w["start"]]
        for i, t in enumerate(vs):
            out.append({"word": w["word"], "first": i == 0, "t": t, "line": w.get("line"), "label": w["word"] if len(vs) == 1 else f"{w['word']}.{i + 1}"})
    return out


def match(syl, notes):
    """for each syllable, the indexes of its notes (the first is its own; [] = none of its own)"""
    S, N = len(syl), len(notes)
    INF = 1e9
    D = [[INF] * (N + 1) for _ in range(S + 1)]
    back = [[0] * (N + 1) for _ in range(S + 1)]
    D[0][0] = 0.0
    for i in range(S + 1):
        for j in range(N + 1):
            if i and j:
                c = D[i - 1][j - 1] + abs(syl[i - 1]["t"] - notes[j - 1][0])
                if c < D[i][j]:
                    D[i][j], back[i][j] = c, 1
            if j and D[i][j - 1] + MELISMA < D[i][j]:
                D[i][j], back[i][j] = D[i][j - 1] + MELISMA, 2
            if i and D[i - 1][j] + ORPHAN < D[i][j]:
                D[i][j], back[i][j] = D[i - 1][j] + ORPHAN, 3
    own = [[] for _ in range(S)]
    i, j = S, N
    while i or j:
        b = back[i][j]
        if b == 1:
            own[i - 1].insert(0, j - 1)
            i, j = i - 1, j - 1
        elif b == 2:
            if i:
                own[i - 1].append(j - 1)  # sorted below
            j -= 1
        else:
            i -= 1
    # a melisma note recorded before its syllable's own note was matched belongs to the syllable
    # before; the DP visits them in reverse, so sort and fix ownership by time
    for k in range(S):
        own[k].sort()
    return own


def build_line(notes, words, t_next):
    """one lyric line -> [start beat, end beat, midi, token, label]; the notes are those from just
    before the line's first vowel to the next line (t_next: its first vowel, or None)"""
    syl = syllables(words)
    t_lo = syl[0]["t"] - 0.25
    t_hi = t_next - 0.12 if t_next is not None else max(w["end"] for w in words) + 6.0
    mine = [n for n in notes if t_lo <= n[0] < t_hi]
    # after the line's last word, only notes that go on holding its last pitch belong to it
    w_end = max(w["end"] for w in words)
    while len(mine) > 1 and mine[-1][0] > w_end - 0.05 and not (mine[-1][2] == mine[-2][2] and mine[-1][0] - mine[-2][1] < REST):
        mine.pop()
    own = match(syl, mine)
    ev = []  # [start s, end s, midi, token, label]
    for s, idx in zip(syl, own):
        tok = s["word"] if s["first"] else None  # the engine splits a word into its syllables itself
        if not idx:  # no note of its own: it splits the note sounding at its vowel
            host = next((e for e in ev if e[0] <= s["t"] < e[1]), ev[-1] if ev else None)
            if host is None:
                ev.append([s["t"], s["t"] + BEAT / 2, mine[0][2] if mine else 60, tok, s["label"] + "?"])
                continue
            cut = s["t"] if host[0] + 0.1 < s["t"] < host[1] - 0.1 else (host[0] + host[1]) / 2
            ev.append([cut, host[1], host[2], tok, s["label"] + "?"])
            host[1] = cut
            continue
        for k, j in enumerate(idx):
            n = mine[j]
            if k and n[2] == ev[-1][2] and n[0] - ev[-1][1] < REST:  # the same pitch held on: one note
                ev[-1][1] = n[1]
            else:
                ev.append([n[0], n[1], n[2], tok if k == 0 else "-", s["label"] if k == 0 else "-"])
    out = []
    for k, e in enumerate(ev):
        nxt = ev[k + 1][0] if k + 1 < len(ev) else None
        # a note lasts to the next one, unless silence follows it
        t_end = e[1] if nxt is None or nxt - e[1] > REST else nxt
        b0, b1 = q(e[0]), q(t_end)
        if out and b0 < out[-1][1]:
            b0 = out[-1][1]
        if b1 <= b0:
            if e[3] == "-":  # a melisma note squeezed out by the grid
                continue
            b1 = b0 + GRID
        out.append([b0, b1, e[2], e[3], e[4]])
    return out


def build(notes, words, report=False):
    """all the lines in `words` -> {line: events}"""
    lines = sorted({w["line"] for w in words})
    by = {ln: [w for w in words if w["line"] == ln] for ln in lines}
    first = {ln: syllables(by[ln])[0]["t"] for ln in lines}
    res = {}
    for i, ln in enumerate(lines):
        nxt = first[lines[i + 1]] if i + 1 < len(lines) and first[lines[i + 1]] - by[ln][-1]["end"] < 1.5 else None
        res[ln] = build_line(notes, by[ln], nxt)
        if report:
            show(ln, res[ln])
    return res


def show(ln, ev):
    print(f"[{ln}] beat {ev[0][0]:g}: " + " ".join(f"{e[4]}={name(e[2])}:{e[1] - e[0]:g}" for e in ev))


def melody(events):
    """events (start beat, end beat, midi, token or None) in time order -> the melody file"""
    notes, lyr, pos = [], [], 0.0
    for b0, b1, m, tok, *_ in events:
        if b0 < pos - 1e-9:
            sys.exit(f"events overlap at beat {b0}")
        if b0 > pos:
            notes.append([0, b0 - pos])
        notes.append([m, b1 - b0])
        if tok:
            lyr.append(tok)
        pos = b1
    return {"bpm": BPM, "t0": T0, "lyrics": " ".join(lyr), "notes": notes}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    notes = load_notes(args[0])
    words = json.load(open(args[1]))
    build(notes, words, report=True)
