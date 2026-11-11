"""GAME notes (txt: onset s, offset s, midi) -> phrases on the song's 96 BPM grid -> CHIMERA melody JSON.

  python covers/song/melody.py phrases NOTES.txt [t_from t_to]     list the sung phrases (for matching to lyric lines)
  python covers/song/melody.py build NOTES.txt PLAN.json OUT.json   write the melody file

PLAN.json: {"transpose": 0, "phrases": [{"at": <phrase start s, as listed>, "lyrics": "one syl per note, - = melisma"}, ...]}
A phrase is matched to the listed phrase starting nearest `at`. Phrases not in the plan are not sung.
"""
import json
import sys

BPM = 96.0
BEAT = 60.0 / BPM
GRID = 0.25  # beats: a sixteenth note
T0 = 0.0  # the song's grid starts at sample 0 (measured: beats land at 0.02 s + n * 0.625)
GAP = 0.18  # s of silence that ends a phrase
MIN_NOTE = 0.07  # s: shorter notes are transcription noise, merged into the note before


def load(path, t_from=0.0, t_to=1e9):
    notes = []
    for line in open(path):
        a = line.split()
        if len(a) >= 3 and t_from <= float(a[0]) < t_to:
            notes.append([float(a[0]), float(a[1]), float(a[2])])
    # merge slivers into the previous note
    out = []
    for n in notes:
        if out and n[1] - n[0] < MIN_NOTE and n[0] - out[-1][1] < 0.03:
            out[-1][1] = n[1]
        else:
            out.append(n)
    return out


def phrases(notes):
    ph = []
    for n in notes:
        if ph and n[0] - ph[-1][-1][1] < GAP:
            ph[-1].append(n)
        else:
            ph.append([n])
    return ph


def beats(t):
    """time -> beats from T0, on the grid"""
    return round((t - T0) / BEAT / GRID) * GRID


NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def name(m):
    m = round(m)
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def quantized(ph):
    """a phrase's notes as (start beat, length beats, midi); each note lasts to the next one's start"""
    starts = [beats(n[0]) for n in ph]
    end = max(beats(ph[-1][1]), starts[-1] + GRID)
    out = []
    for i, n in enumerate(ph):
        nxt = starts[i + 1] if i + 1 < len(ph) else end
        if nxt <= starts[i]:  # two notes on one grid step: the second is an ornament, drop it
            continue
        out.append((starts[i], nxt - starts[i], round(n[2])))
    return out


def cmd_phrases(path, t_from=0.0, t_to=1e9):
    for ph in phrases(load(path, float(t_from), float(t_to))):
        q = quantized(ph)
        print(f"{ph[0][0]:7.2f}-{ph[-1][1]:7.2f}  bar {q[0][0] / 4 + 1:6.2f}  n={len(q):2d}  " + " ".join(f"{name(m)}:{l:g}" for _, l, m in q))


def cmd_build(path, plan_path, out_path):
    plan = json.load(open(plan_path))
    tr = plan.get("transpose", 0)
    all_ph = phrases(load(path))
    notes, lyrics, pos, errors = [], [], 0.0, []
    for item in plan["phrases"]:
        ph = min(all_ph, key=lambda p: abs(p[0][0] - item["at"]))
        q = quantized(ph)
        if "drop" in item:  # indexes of notes to leave out (their time goes to the note before)
            for i in sorted(item["drop"], reverse=True):
                s, l, m = q.pop(i)
                if i > 0:
                    q[i - 1] = (q[i - 1][0], q[i - 1][1] + l, q[i - 1][2])
        syl = item["lyrics"].split()
        n_syl = item.get("count", len(syl))
        if n_syl != len(q):
            errors.append(f"at {item['at']}: {len(q)} notes, {n_syl} syllables: {item['lyrics']}")
            continue
        if q[0][0] < pos:
            errors.append(f"at {item['at']}: overlaps the phrase before")
            continue
        if q[0][0] > pos:
            notes.append([0, q[0][0] - pos])
        for s, l, m in q:
            notes.append([m + tr, l])
        pos = q[-1][0] + q[-1][1]
        lyrics.append(item["lyrics"])
    if errors:
        sys.exit("\n".join(errors))
    json.dump({"bpm": BPM, "t0": T0, "lyrics": " ".join(lyrics), "notes": notes}, open(out_path, "w"))
    print(f"{out_path}: {sum(1 for n in notes if n[0] > 0)} notes, ends at {pos * BEAT:.1f} s")


if __name__ == "__main__":
    {"phrases": cmd_phrases, "build": cmd_build}[sys.argv[1]](*sys.argv[2:])
