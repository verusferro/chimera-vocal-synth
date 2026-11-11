"""One song, start to end, from a small config: GAME notes + HubertFA words -> CHIMERA melody files
-> CHIMERA renders -> mix with the instrumental -> a duet show.

  COVERS_WORK=covers/work/<song> python covers/song/cover.py [--show]

WORK/cover.json:
  {"id": "despicable-me", "title": "...", "bpm": 85, "t0": 0.32,
   "voices": [{"name": "Gru", "body": "male", "lines": [[1, 40]], "shift": 0, "gain": 1.0,
               "look": "niko", "enter": 0}],
   "hand": {"12": [[start_s, length_s, "C4", "word"], ...]}}
`lines` are 1-based inclusive ranges of lyrics.txt lines (omit = every line); `shift` moves the
voice by semitones (octaves keep it in key); `look`, `enter`: see docs/ui-changes.md. `hand`
replaces a line's notes ("" token = the word's next syllable). It reads WORK/game/vocals.txt (GAME,
--pitch-format number), WORK/hfa/words.json, WORK/stems/*(vocals)* and *(other)*, WORK/video.mp4.
--show prints every line's syllables on their notes. Writes WORK/build/ and public/shows/<id>/.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

import librosa
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import align  # noqa: E402
from paths import REPO, SHOWS, WORK  # noqa: E402

SR = 44100
NAMES = {n: i for i, n in enumerate(align.NAMES)}


def hand(rows):
    midi = lambda nm: 12 * (int(nm[-1]) + 1) + NAMES[nm[:-1]]  # noqa: E731
    return [[(t - align.T0) / align.BEAT, (t + d - align.T0) / align.BEAT, midi(n), tok or None, tok or "-"] for t, d, n, tok in rows]


def trim_tail(ev):
    """a line's held last syllable keeps only the notes near its pitch within a beat: the rest is
    ad-libs and backing voices that the vocal stem still holds"""
    last = max(i for i, e in enumerate(ev) if e[3] and e[3] != "-")
    keep = ev[: last + 1]
    for e in ev[last + 1:]:
        if e[0] - ev[last][0] >= 1.0 or abs(e[2] - ev[last][2]) > 2:
            break
        keep.append(e)
    return keep


def melodies(cfg):
    notes = align.load_notes(f"{WORK}/game/vocals.txt")
    res = align.build(notes, json.load(open(f"{WORK}/hfa/words.json")))
    res.update({int(ln): hand(rows) for ln, rows in cfg.get("hand", {}).items()})
    res = {ln: ev if str(ln) in cfg.get("hand", {}) else trim_tail(ev) for ln, ev in res.items()}
    out = []
    for v in cfg["voices"]:
        mine = [ln for ln in sorted(res) if "lines" not in v or any(a <= ln <= b for a, b in v["lines"])]
        if "--show" in sys.argv:
            print(f"== {v['name']}")
            for ln in mine:
                align.show(ln, res[ln])
        ev = sorted((list(e) for ln in mine for e in res[ln]), key=lambda e: e[0])
        for a, b in zip(ev, ev[1:]):  # lines that run into each other: the earlier note gives way
            if b[0] < a[1]:
                a[1] = b[0]
        ev = align.fit([e for e in ev if e[1] > e[0]])
        ev = [[e[0], e[1], e[2] + v.get("shift", 0), *e[3:]] for e in ev]
        out.append(align.melody(ev))
        lo, hi = min(e[2] for e in ev), max(e[2] for e in ev)
        print(f"{v['name']}: {len(ev)} notes, {align.name(lo)}..{align.name(hi)}")
    return out


def active_rms(y):
    f = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    return float(np.sqrt(np.mean(np.square(f[f > 0.1 * f.max()]))))


def main():
    cfg = json.load(open(f"{WORK}/cover.json"))
    align.BPM, align.T0 = float(cfg["bpm"]), float(cfg.get("t0", 0))
    align.BEAT = 60.0 / align.BPM
    build, show = f"{WORK}/build", f"{SHOWS}/{cfg['id']}"
    os.makedirs(build, exist_ok=True)
    os.makedirs(show, exist_ok=True)
    jobs = []
    for i, (v, m) in enumerate(zip(cfg["voices"], melodies(cfg))):
        json.dump(m, open(f"{show}/v{i}.json", "w"))
        jobs.append(subprocess.Popen(["./target/release/chimera", "render", "notes", f"{show}/v{i}.json", f"{build}/v{i}", v.get("body", "male"),
                                      "--tele", f"{show}/v{i}.tele"], cwd=REPO, stdout=subprocess.DEVNULL))
    if any(p.wait() for p in jobs):
        sys.exit("render failed")

    stem = lambda kind: glob.glob(f"{WORK}/stems/*({kind})*")[0]  # noqa: E731
    backing, _ = librosa.load(stem("other"), sr=SR, mono=False)
    n = backing.shape[1]
    voices = np.zeros((2, n), np.float32)
    for i, v in enumerate(cfg["voices"]):
        y, _ = librosa.load(f"{build}/v{i}.wav", sr=SR)
        t = np.zeros(n, np.float32)
        t[: min(n, len(y))] = y[:n]
        # one voice in the middle; two apart a little, as singers stand
        pan = 0.0 if len(cfg["voices"]) == 1 else (-0.25 if i % 2 == 0 else 0.25)
        voices += np.stack([(1 - pan) * t, (1 + pan) * t]) * v.get("gain", 1.0) / active_rms(t)
    # the voices as loud as the original's vocal stem, over the original's own instrumental
    rms = lambda y: float(np.sqrt(np.mean(np.square(y))))  # noqa: E731
    voices *= rms(librosa.load(stem("vocals"), sr=SR, mono=False)[0]) / rms(voices)
    k = min(1.0, 0.95 / float(np.max(np.abs(voices + backing))))
    for name, y in (("mix", voices + backing), ("backing", backing)):
        sf.write(f"{build}/{name}.wav", (y * k).T, SR)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{build}/{name}.wav", "-c:a", "libmp3lame", "-q:a", "2", f"{show}/{name}.mp3"], check=True)
    if os.path.exists(f"{WORK}/video.mp4"):
        shutil.copy(f"{WORK}/video.mp4", f"{show}/video.mp4")

    def ver(f):
        return f"{f}?v={hashlib.md5(open(f'{show}/{f}', 'rb').read()).hexdigest()[:8]}"
    out = {"title": cfg["title"], "audio": ver("mix.mp3"), "backing": ver("backing.mp3"), "bpm": align.BPM, "downbeat": align.T0,
           "voices": [{"name": v["name"], "tele": ver(f"v{i}.tele"), "melody": ver(f"v{i}.json"),
                       **({"look": v["look"]} if "look" in v else {}), **({"enter": v["enter"]} if "enter" in v else {})}
                      for i, v in enumerate(cfg["voices"])]}
    if os.path.exists(f"{show}/video.mp4"):
        out["video"] = ver("video.mp4")
    json.dump(out, open(f"{show}/show.json", "w"), indent=1)
    print(f"{show}: scale {k:.2f}")


if __name__ == "__main__":
    main()
