"""The V1 (S.A.M.) version of a cover.py show: V1 sings, CHIMERA's heads only move.

  COVERS_WORK=<abs work dir> python covers/song/cover.py      # the regular show first
  COVERS_WORK=<abs work dir> python covers/sam/v1_cover.py    # then public/shows/<id>-v1/

It takes the regular show's melodies (public/shows/<id>/v<i>.json), so every fix there (hand lines,
repitch, holds) carries over. WORK/cover.json gets a "v1" block:
  "v1": {"title": "...", "transpose": -5, "spoken": [[1, 5]], "voice": 0}
`transpose` moves the whole song, instrumental too (S.A.M. sits best at 140 to 160 Hz, see
docs/sam-singing.md); `spoken` (1-based inclusive line ranges) are said by the S.A.M. TTS word by
word on the aligner's times, the rest is sung by the bank; `voice` is the head that wears V1.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

import librosa
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, f"{os.path.dirname(HERE)}/song")
import build_ab  # noqa: E402
import cover  # noqa: E402
from build_ab import LIFT_DB, place, run, say  # noqa: E402
from paths import REPO, SHOWS, WORK  # noqa: E402

SR = 44100


def main():
    cfg = json.load(open(f"{WORK}/cover.json"))
    v1 = cfg["v1"]
    T = int(v1.get("transpose", 0))
    src, show, build = f"{SHOWS}/{cfg['id']}", f"{SHOWS}/{cfg['id']}-v1", f"{WORK}/build-v1"
    os.makedirs(show, exist_ok=True)
    os.makedirs(build, exist_ok=True)
    build_ab.BUILD = build  # say()'s scratch files
    words = json.load(open(f"{WORK}/hfa/words.json"))
    voices = cfg["voices"]

    def voice(ln):
        return next((i for i, v in enumerate(voices) if "lines" not in v or any(a <= ln <= b for a, b in v["lines"])), None)
    spoken = {w["line"] for w in words if any(a <= w["line"] <= b for a, b in v1.get("spoken", []))}
    talk = [(min(w["start"] for w in ws), max(w["end"] for w in ws)) for ln in spoken for ws in [[w for w in words if w["line"] == ln]]]

    jobs = []
    for i, v in enumerate(voices):
        m = json.load(open(f"{src}/v{i}.json"))
        m["notes"] = [[n + T if n > 0 else 0, b] for n, b in m["notes"]]
        json.dump(m, open(f"{show}/v{i}.json", "w"))
        jobs.append(subprocess.Popen(["./target/release/chimera", "render", "notes", f"{show}/v{i}.json", f"{build}/chimera-v{i}", v.get("body", "male"),
                                      "--tele", f"{show}/v{i}.tele", "--syllables", f"{build}/v{i}.syl.json"], cwd=REPO, stdout=subprocess.DEVNULL))
    if any(p.wait() for p in jobs):
        sys.exit("chimera render failed")
    # the sung syllables to the bank, on CHIMERA's beats (so the mouths match the sound)
    jobs = []
    for i in range(len(voices)):
        syl = [n for n in json.load(open(f"{build}/v{i}.syl.json")) if not any(a - 0.01 <= n["t"] < b for a, b in talk)]
        if os.path.exists(f"{build}/sam-v{i}.wav"):
            os.remove(f"{build}/sam-v{i}.wav")
        if syl:
            json.dump(syl, open(f"{build}/v{i}.sung.json", "w"))
            jobs.append(subprocess.Popen([sys.executable, f"{HERE}/sam_render.py", f"{build}/v{i}.sung.json", f"{build}/sam-v{i}.wav", "--bpm", str(cfg["bpm"])],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if any(p.wait() for p in jobs):
        sys.exit("sam_render failed")

    vocal, other = (cover.glob.glob(f"{WORK}/stems/*({k})*")[0] for k in ("vocals", "other"))
    inst = f"{build}/other{T:+d}.wav"
    if not os.path.exists(inst):
        run("ffmpeg", "-v", "error", "-y", "-i", other, "-af",
            f"rubberband=pitch={2 ** (T / 12):.6f}:pitchq=quality:transients=crisp", "-ar", str(SR), inst)
    backing, _ = librosa.load(inst, sr=SR, mono=False)
    n = backing.shape[1]
    mix = np.zeros((2, n), np.float32)
    pans = [0.0] if len(voices) == 1 else np.linspace(-0.25, 0.25, len(voices))
    for i, p in enumerate(pans):
        t = np.zeros(n, np.float32)
        if os.path.exists(f"{build}/sam-v{i}.wav"):
            place(t, librosa.load(f"{build}/sam-v{i}.wav", sr=SR)[0], 0.0)
        for w in words:
            if w["line"] in spoken and voice(w["line"]) == i:
                place(t, 0.8 * say(w["word"], w["end"] - w["start"]), w["start"])
        mix += np.stack([(1 - p) * t, (1 + p) * t])
    # the original's balance (its vocal stem against its instrumental), S.A.M. a little louder
    rms = lambda y: float(np.sqrt(np.mean(np.square(y))))  # noqa: E731
    mix *= rms(librosa.load(vocal, sr=SR)[0]) / rms(librosa.load(other, sr=SR)[0]) * rms(backing) / rms(mix) * 10 ** (LIFT_DB / 20)
    k = min(1.0, 0.95 / float(np.max(np.abs(mix + backing))))
    for name, y in (("mix", mix), ("backing", backing)):
        sf.write(f"{build}/{name}.wav", (y * k).T, SR)
        run("ffmpeg", "-v", "error", "-y", "-i", f"{build}/{name}.wav", "-c:a", "libmp3lame", "-q:a", "2", f"{show}/{name}.mp3")
    shutil.copy(f"{WORK}/video.mp4", f"{show}/video.mp4")

    def ver(f):
        return f"{f}?v={hashlib.md5(open(f'{show}/{f}', 'rb').read()).hexdigest()[:8]}"
    me = v1.get("voice", 0)
    out = {"title": v1["title"], "audio": ver("mix.mp3"), "backing": ver("backing.mp3"), "video": ver("video.mp4"),
           "bpm": float(cfg["bpm"]), "downbeat": float(cfg.get("t0", 0)), **({"spell": cfg["spell"]} if "spell" in cfg else {}),
           "voices": [{"name": f"V1 as {v['name']}" if i == me else v["name"], "tele": ver(f"v{i}.tele"), "melody": ver(f"v{i}.json"),
                       **({"look": "v1"} if i == me else {"look": v["look"]} if "look" in v else {}),
                       **({"on": on} if (on := cover.on_screen(v)) else {})}
                      for i, v in enumerate(voices)]}
    json.dump(out, open(f"{show}/show.json", "w"), indent=1)
    print(f"{show}: voices peak {np.max(np.abs(mix * k)):.2f}, scale {k:.2f}")


if __name__ == "__main__":
    main()
