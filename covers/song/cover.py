"""One song, start to end, from a small config: GAME notes + HubertFA words -> CHIMERA melody files
-> CHIMERA renders -> mix with the instrumental -> a duet show.

  COVERS_WORK=covers/work/<song> python covers/song/cover.py [--show]

WORK/cover.json:
  {"id": "despicable-me", "title": "...", "bpm": 85, "t0": 0.32, "grid": 0.25,
   "voices": [{"name": "Gru", "body": "male", "lines": [[1, 40]], "shift": 0, "gain": 1.0,
               "look": "niko", "enter": 0, "leave": false}],
   "hand": {"12": [[start_s, length_s, "C4", "word"], ...]}}
`lines` are 1-based inclusive ranges of lyrics.txt lines (omit = every line); `shift` moves the
voice by semitones (octaves keep it in key); `look`: see docs/ui-changes.md; `enter` (s): the head
comes on then and stays; `leave`: the head is on only while it sings (0.3 s around its lines). `hand`
replaces a line's notes ("" token = the word's next syllable). It reads WORK/game/vocals.txt (GAME,
--pitch-format number), WORK/hfa/words.json, WORK/stems/*(vocals)* and *(other)*, WORK/video.mp4.
--show prints every line's syllables on their notes. Writes WORK/build/ and public/shows/<id>/.
`grid` (beats, default 0.25): use 0.125 for a song whose tempo drifts; the grid then only rounds.
`"notes": "f0"`: take each syllable's pitch from the vocal stem's f0 instead of GAME's notes
(better for rapped or half-spoken songs, where GAME finds few notes).
"""
import bisect
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
GAP_S = 4.0  # s: a leaving head stays on through a shorter break between its lines
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


def rmvpe_hz(wav, cache):
    """RMVPE pitch of a vocal stem (Hz, 0 where unvoiced; 10 ms frames), cached. RMVPE (the RVC
    project's pitch net, rmvpe-onnx) holds the voice through held notes and backing sound where
    WORLD's harvest and pYIN drop out or jump"""
    if not os.path.exists(cache):
        from rmvpe_onnx import RMVPE
        y, _ = librosa.load(wav, sr=16000)
        _, f0, conf, _ = RMVPE().predict(audio=y, sr=16000)
        np.save(cache, np.where(conf >= 0.03, f0, 0.0))
    return np.load(cache)


def stem_midi():
    """the vocal stem's pitch (RMVPE, 10 ms frames) as float MIDI, NaN where unvoiced"""
    f0 = rmvpe_hz(glob.glob(f"{WORK}/stems/*(vocals)*")[0], f"{WORK}/build/f0_rmvpe.npy")
    return np.where(f0 > 0, 12 * np.log2(np.maximum(f0, 1e-9) / 440) + 69, np.nan)


def frame(b):
    return int((align.T0 + b * align.BEAT) * 100)


def pc_dist(a, b):
    """semitones between two pitches, octaves aside"""
    return np.abs((a - b + 6) % 12 - 6)


def repitch(ev, mid, tune):
    """a note's pitch from the stem where the stem holds one steady pitch over the note's middle
    (GAME's notes and the f0 onsets catch scoops, slides and stray backing voices); the note keeps
    its octave (the line folds). `tune`: the song's offset from A440 in semitones"""
    for e in ev:
        a, b = frame(e[0]), frame(e[1])
        x = mid[a + (b - a) // 4: b - (b - a) // 4 + 1]
        v = x[~np.isnan(x)]
        if len(v) < 3 or len(v) < 0.6 * len(x) or np.std(v) > 0.7:
            continue
        p = round(float(np.median(v)) - tune)
        e[2] = p + 12 * round((e[2] - p) / 12)
    return ev


def hold(ev, mid, starts):
    """a note before a rest holds on while the stem's voice goes on at its pitch (the aligner and
    the word fixes end words early; the stem says how long the singer held), up to the next note
    of any voice (`starts`, sorted: the stem holds all the singers)"""
    for i, e in enumerate(ev):
        j = bisect.bisect_right(starts, e[1] - 1e-9)
        nxt = min(ev[i + 1][0] if i + 1 < len(ev) else e[1] + 8, starts[j] if j < len(starts) else e[1] + 8)
        if nxt - e[1] < align.GRID:
            continue
        k, stop, gap = frame(e[1]), min(frame(nxt) - 5, len(mid)), 0
        while k < stop and gap < 4:  # a few unvoiced frames (a consonant, a breath of noise) pass
            gap = gap + 1 if np.isnan(mid[k]) or pc_dist(mid[k], e[2]) > 1.5 else 0
            k += 1
        e[1] = max(e[1], min(nxt, align.q((k - gap) / 100)))
    return ev


def f0_lines(words, mid, voice):
    """notes from the words alone, for half-spoken songs where GAME finds few notes: one note per
    syllable, from its vowel onset to the next syllable (or its word's end, then a rest), pitched at
    the stem's median f0 over its first 0.25 s, octave-folded next to its line's median"""
    res = {}
    for ln in sorted({w["line"] for w in words}):
        lw = [w for w in words if w["line"] == ln]
        syl = align.syllables(lw)
        ends = []
        for i, s in enumerate(syl):
            w_end = next(w["end"] for w in lw if w["word"] == s["word"] and w["start"] <= s["t"] <= w["end"] + 1e-6)
            nxt = syl[i + 1]["t"] if i + 1 < len(syl) else w_end
            # a word the aligner stretched over an ad-lib holds at most 1.5 s
            ends.append(min(nxt if nxt - w_end < align.REST else w_end, s["t"] + 1.5))
        raw = []
        for s, e in zip(syl, ends):
            v = mid[int(s["t"] * 100): max(int(min(s["t"] + 0.25, e) * 100), int(s["t"] * 100) + 1)]
            v = v[~np.isnan(v)]
            raw.append(float(np.median(v)) if len(v) else None)
        known = [m for m in raw if m is not None]
        med = float(np.median(known)) if known else 48.0
        ev = []
        for s, e, m in zip(syl, ends, raw):
            m = med if m is None else m - 12 * round((m - med) / 12)
            b0, b1 = align.q(s["t"]), align.q(e)
            if ev and b0 < ev[-1][1]:
                b0 = ev[-1][1]
            ev.append([b0, max(b1, b0 + align.GRID), round(m), s["word"] if s["first"] else None, s["label"]])
        res[ln] = ev
    # a line the stem's backing voices dominate (an octave up, say) comes back to its singer's
    # octave (`voice(line)`: who sings it); a line only a few semitones off its singer's median is
    # that singer's own high or low line
    for who in {voice(ln) for ln in res}:
        lines = [ln for ln in res if voice(ln) == who]
        song = float(np.median([e[2] for ln in lines for e in res[ln]]))
        for ln in lines:
            d = song - float(np.median([e[2] for e in res[ln]]))
            k = 12 * round(d / 12) if abs(d) >= 10 else 0
            res[ln] = [[e[0], e[1], e[2] + k, *e[3:]] for e in res[ln]]
    return res


def melodies(cfg):
    words = json.load(open(f"{WORK}/hfa/words.json"))
    mid = stem_midi()
    sung = mid[~np.isnan(mid)]
    tune = float(np.angle(np.mean(np.exp(2j * np.pi * sung))) / (2 * np.pi))  # the song's offset from A440, semitones
    def voice(ln):
        return next((i for i, v in enumerate(cfg["voices"]) if "lines" not in v or any(a <= ln <= b for a, b in v["lines"])), None)
    if cfg.get("notes") == "f0":
        res = f0_lines(words, mid, voice)
    else:
        res = align.build(align.load_notes(f"{WORK}/game/vocals.txt"), words)
    res = {ln: trim_tail(repitch(ev, mid, tune)) for ln, ev in res.items()}
    res.update({int(ln): hand(rows) for ln, rows in cfg.get("hand", {}).items()})
    starts = sorted(e[0] for ev in res.values() for e in ev)
    out = []
    for i, v in enumerate(cfg["voices"]):
        mine = [ln for ln in sorted(res) if voice(ln) == i]
        if "--show" in sys.argv:
            print(f"== {v['name']}")
            for ln in mine:
                align.show(ln, res[ln])
        ev = sorted((list(e) for ln in mine for e in res[ln]), key=lambda e: e[0])
        for a, b in zip(ev, ev[1:]):  # lines that run into each other: the earlier note gives way
            if b[0] < a[1]:
                a[1] = b[0]
        ev = align.fit(hold([e for e in ev if e[1] > e[0]], mid, starts))
        ev = [[e[0], e[1], e[2] + v.get("shift", 0), *e[3:]] for e in ev]
        out.append(align.melody(ev))
        lo, hi = min(e[2] for e in ev), max(e[2] for e in ev)
        print(f"{v['name']}: {len(ev)} notes, {align.name(lo)}..{align.name(hi)}")
    return out


def active_rms(y):
    f = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    return float(np.sqrt(np.mean(np.square(f[f > 0.1 * f.max()]))))

def on_screen(v):
    """a voice's `on` for show.json: with `leave`, its lines' spans (0.3 s around, as a head
    enters; spans less than GAP_S apart joined so a head doesn't flicker); with `enter`, from then on"""
    if v.get("leave"):
        words = json.load(open(f"{WORK}/hfa/words.json"))
        spans = sorted((min(w["start"] for w in ws) - 0.3, max(w["end"] for w in ws) + 0.3)
                       for ln in sorted({w["line"] for w in words}) if any(a <= ln <= b for a, b in v["lines"])
                       for ws in [[w for w in words if w["line"] == ln]])
        out = []
        for a, b in spans:
            if out and a - out[-1][1] < GAP_S:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b])
        return [[round(a, 2), round(b, 2)] for a, b in out]
    return [[v["enter"], None]] if "enter" in v else None



def main():
    cfg = json.load(open(f"{WORK}/cover.json"))
    align.BPM, align.T0 = float(cfg["bpm"]), float(cfg.get("t0", 0))
    align.BEAT, align.GRID = 60.0 / align.BPM, float(cfg.get("grid", 0.25))
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
    for name, y in (("mix", voices), ("backing", backing)):
        sf.write(f"{build}/{name}.wav", (y * k).T, SR)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{build}/{name}.wav", "-c:a", "libmp3lame", "-q:a", "2", f"{show}/{name}.mp3"], check=True)
    if os.path.exists(f"{WORK}/video.mp4"):
        shutil.copy(f"{WORK}/video.mp4", f"{show}/video.mp4")

    def ver(f):
        return f"{f}?v={hashlib.md5(open(f'{show}/{f}', 'rb').read()).hexdigest()[:8]}"
    out = {"title": cfg["title"], "audio": ver("mix.mp3"), "backing": ver("backing.mp3"), "bpm": align.BPM, "downbeat": align.T0,
           "voices": [{"name": v["name"], "tele": ver(f"v{i}.tele"), "melody": ver(f"v{i}.json"),
                       **({"look": v["look"]} if "look" in v else {}), **({"on": on} if (on := on_screen(v)) else {})}
                      for i, v in enumerate(cfg["voices"])]}
    if os.path.exists(f"{show}/video.mp4"):
        out["video"] = ver("video.mp4")
    json.dump(out, open(f"{show}/show.json", "w"), indent=1)
    print(f"{show}: scale {k:.2f}")


if __name__ == "__main__":
    main()
