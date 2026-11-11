"""Assemble the melody files of "Switch Off The Game" for `chimera render notes`.

  python covers/song/make_song.py   writes covers/work/song/lead.json (and second.json once its notes exist)

Lead: the lines come from align.py (GAME notes + HubertFA words), then:
 - FIX: lines where the transcription slipped (a note cut at a line boundary, two equal notes
   heard as one, a pickup not heard), rewritten by the verse's own pattern, which every other
   line of the song confirms;
 - the last chorus (lines 41-48) is the first chorus's notes 144 beats later with its own words:
   there the stem holds two voices at once and the transcription mixes them;
 - the outro repeats "so live your life again" every 16 beats.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))  # covers/, for paths.py
import align
from align import NAMES
from paths import WORK as ROOT

BREATH = 0.25  # beats taken off a line's last note (when it is at least a beat long)


def midi(nm):
    return NAMES.index(nm[:-1]) + 12 * (int(nm[-1]) + 1)


def line(start, spec):
    """"word:F3 _:G3:1 ..." from `start`: half a beat each unless a length is given; "_" is a
    further syllable of the word before, "-" a melisma"""
    ev, b = [], start
    for item in spec.split():
        tok, nm, *ln = item.split(":")
        d = float(ln[0]) if ln else 0.5
        ev.append([b, b + d, midi(nm), None if tok == "_" else tok, tok])
        b += d
    return ev


FIX = {
    1: line(63, "In:F3 the:F3 night:G3 I:G3 boot:D#4 and:D4 read:C4"),
    2: line(66.5, "a:C4 shadow:A#3 _:A3 loads:F3 into:F3 _:D#4 the:D4 scene:A#3:1"),
    3: line(71, "teary:F3 _:F3 eyed:G3 assuming:G3 _:D#4 _:D4 grief:C4:1"),
    5: line(79, "Don't:F3 be:F3 scared:G3 to:G3 leave:D#4 the:D4 dream:C4:1"),
    6: line(83, "you've:A#3 still:A3 got:F3 the:F3 memories:D#4 _:D4 _:A#3:1"),
    7: line(87, "Not:F3 the:F3 same:G3 but:G3 if:D#4 you:D4 need:C4:1"),
    9: line(111, "Look:F3 I:F3 know:G3 just:G3 what:D#4 they:D4 meant:C4 to:C4 you:A#3"),
    20: line(157.5, "don't:C4 fear:D4 you've:C4 done:A#3 them:A3 wrong:G3:1"),
    24: line(173.5, "so:C4 live:D4 your:C4 life:A#3 again:A3 _:G3:4"),
    25: line(207, "Niko:F3 _:F3 left:G3 so:G3 long:D#4 ago:D4 _:C4"),
    26: line(210.5, "you:C4 saved:A#3 the:A3 day:F3 I:F3 sent:D#4 them:D4 home:A#3:1"),
    28: line(219, "separated:A#3 _:A3 _:F3 _:F3 but:G3 you:A3 know:A#3:1"),
    33: line(255, "What:F3 you:F3 had:G3 with:G3 them:D#4 was:D4 real:C4:1"),
}
# the last chorus's words on the first chorus's notes (same syllable counts)
CHORUS2 = {17: "Although _ I may be gone", 18: "I'm here to sing along _", 19: "So keep it strong", 20: "don't fear you've done me wrong",
           21: "Oh switch off the game", 22: "recordings _ _ aren't _ the same", 23: "I'll be okay _", 24: "so live your life again _"}
OUTRO = [333.5, 349.5, 365.5, 381.5]


def shifted(ev, by, words=None):
    toks = words.split() if words else None
    if toks and len(toks) != len(ev):
        sys.exit(f"{len(ev)} notes for: {words}")
    return [[e[0] + by, e[1] + by, e[2], (None if toks[i] == "_" else toks[i]) if toks else e[3], e[4]] for i, e in enumerate(ev)]


def lead():
    notes = align.load_notes(f"{ROOT}/game/full/vocals.txt")
    words = [w for w in json.load(open(f"{ROOT}/hfa/words.json")) if w["line"] <= 40]
    lines = align.build(notes, words)
    lines.update(FIX)
    for ln in range(17, 25):  # the last chorus: the lead keeps the first chorus's words ("they")
        lines[ln + 24] = shifted(lines[ln], 144)
    refrain = lines[24]
    for i, at in enumerate(OUTRO):
        lines[49 + i] = shifted(refrain, at - refrain[0][0])
    return held(lines)


def held(lines):
    """After the second voice comes in, the "-gain" of each "so live your life again" is held
    until the next one starts (the original's long note); the song's last one is not."""
    for ln in range(48, 48 + len(OUTRO)):
        lines[ln][-1][1] = lines[ln + 1][0][0] - 0.25
    return lines


# The second voice, Niko (from the lead/backing split of the vocal stem, GAME notes): in the last
# chorus and the outro it sings in the lead's rhythm, a harmony above it, with the words about
# itself ("Although I may be gone ... I'll be okay").
HARMONY = {17: "A#4 A#4 D#5 D5 D#5 A4", 18: "C5 A#4 A4 G4 F4 D4", 19: "G4 A#4 C5 A4", 20: "G4 A#4 A4 D#5 D5 A#4",
           21: "A#4 D#5 D5 D#5 A4", 22: "C5 A#4 A4 G4 G4 F4 D4", 23: "G4 A#4 C5 A4", 24: "G4 A#4 A4 D#5 D5 G4"}


def second(L):
    def harm(ln, by):
        ps = HARMONY[ln].split()
        if len(ps) != len(L[ln]):
            sys.exit(f"line {ln}: {len(L[ln])} notes, {len(ps)} harmony pitches")
        return shifted([[e[0], e[1], midi(p), e[3], e[4]] for e, p in zip(L[ln], ps)], by, CHORUS2[ln])
    lines = {ln + 24: harm(ln, 144) for ln in range(17, 25)}
    for i, at in enumerate(OUTRO):
        lines[49 + i] = harm(24, at - L[24][0][0])
    return held(lines)

def flatten(lines):
    ev = []
    for ln in sorted(lines):
        cur = [list(e) for e in lines[ln]]
        last = cur[-1]
        if last[1] - last[0] >= 1:
            last[1] -= BREATH
        ev.extend(cur)
    for a, b in zip(ev, ev[1:]):
        if b[0] < a[1]:  # a line's pickup inside the last note of the line before
            a[1] = b[0]
    return ev


def write(name, lines, transpose=0):
    ev = [[e[0], e[1], e[2] + transpose, e[3], e[4]] for e in flatten(lines)]
    m = align.melody(ev)
    os.makedirs(f"{ROOT}/song", exist_ok=True)
    json.dump(m, open(f"{ROOT}/song/{name}.json", "w"))
    lo, hi = min(e[2] for e in ev), max(e[2] for e in ev)
    print(f"song/{name}.json: {len(ev)} notes, {align.name(lo)}..{align.name(hi)}, ends at {ev[-1][1] * align.BEAT:.1f} s")


if __name__ == "__main__":
    L = lead()
    if "--show" in sys.argv:
        for ln in sorted(L):
            align.show(ln, L[ln])
    write("lead", L)
    write("second", second(L))
