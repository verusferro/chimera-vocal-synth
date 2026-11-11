"""Switch Off The Game with V1 (S.A.M.) singing the World Machine's part; Niko stays Niko.

  python covers/sam/build_switch_v1.py     then open http://127.0.0.1:5317/?show=switch-off-v1

The melodies are $WORK/song/{lead,second}.json (song/make_song.py). The song and Niko stay at their
original pitch; V1 sings the World Machine's part an octave down (in key, but lower than she
sang it). The lead's syllables go to the S.A.M. bank on CHIMERA's beats (CHIMERA only moves the
head); Niko is CHIMERA's child voice as on the Niko site. The Niko site's own show
(shows/switch-off) is not touched.
"""
import hashlib
import json
import os
import subprocess
import sys

import librosa
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from paths import REPO, SHOWS, WORK  # noqa: E402

SONG = f"{WORK}/song"
BUILD = f"{WORK}/switch-v1"
SHOW = f"{SHOWS}/switch-off-v1"
STEMS = f"{WORK}/stems/song_(%s)_bs_roformer_vocals_resurrection_unwa.wav"
SR = 44100
# the World Machine's part sits about A#3 (233 Hz): an octave down keeps V1 in the song's key
V1_SHIFT = -12
LIFT_DB = 2.0  # S.A.M. against the band, over the original's vocal-to-backing balance
NIKO = 1.1  # Niko's level against V1's (RMS while singing)


def run(*cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def active_rms(y):
    frames = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    return float(np.sqrt(np.mean(np.square(frames[frames > 0.1 * frames.max()]))))


def main():
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(SHOW, exist_ok=True)
    for v, shift in (("lead", V1_SHIFT), ("second", 0)):
        m = json.load(open(f"{SONG}/{v}.json"))
        m["notes"] = [[n + shift if n > 0 else n, b] for n, b in m["notes"]]
        json.dump(m, open(f"{BUILD}/{v}.json", "w"))
    jobs = [subprocess.Popen(["./target/release/chimera", "render", "notes", f"{BUILD}/lead.json", f"{BUILD}/chimera-lead", "male",
                              "--tele", f"{SHOW}/lead.tele", "--syllables", f"{BUILD}/lead.syl.json"], cwd=REPO, stdout=subprocess.DEVNULL),
            subprocess.Popen(["./target/release/chimera", "render", "notes", f"{BUILD}/second.json", f"{BUILD}/second", "child",
                              "--tele", f"{SHOW}/second.tele"], cwd=REPO, stdout=subprocess.DEVNULL)]
    inst = STEMS % "other"
    if any(p.wait() for p in jobs):
        sys.exit("render failed")
    run(sys.executable, f"{HERE}/sam_render.py", f"{BUILD}/lead.syl.json", f"{BUILD}/sam-lead.wav", "--bpm", "96",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    backing, _ = librosa.load(inst, sr=SR, mono=False)
    n = backing.shape[1]

    def track(path):
        y, _ = librosa.load(path, sr=SR)
        t = np.zeros(n, np.float32)
        t[: min(n, len(y))] = y[:n]
        return t
    lead, niko = track(f"{BUILD}/sam-lead.wav"), track(f"{BUILD}/second.wav")
    niko *= NIKO * active_rms(lead) / active_rms(niko)
    voices = np.stack([0.95 * lead + 0.75 * niko, 0.8 * lead + 0.95 * niko])
    rms = lambda y: float(np.sqrt(np.mean(np.square(y))))  # noqa: E731
    ov, _ = librosa.load(STEMS % "vocals", sr=SR)
    oi, _ = librosa.load(STEMS % "other", sr=SR)
    voices *= rms(ov) / rms(oi) * rms(backing) / rms(voices) * 10 ** (LIFT_DB / 20)
    k = 0.95 / float(np.max(np.abs(voices + backing)))
    for name, y in (("mix", voices * k), ("backing", backing * k)):
        sf.write(f"{BUILD}/{name}.wav", y.T, SR)
        run("ffmpeg", "-v", "error", "-y", "-i", f"{BUILD}/{name}.wav", "-c:a", "libmp3lame", "-q:a", "2", f"{SHOW}/{name}.mp3")
    for v in ("lead", "second"):
        run("cp", f"{BUILD}/{v}.json", f"{SHOW}/{v}.json")
    run("cp", f"{SHOWS}/switch-off/video.mp4", f"{SHOW}/video.mp4")

    def ver(f):
        return f"{f}?v={hashlib.md5(open(f'{SHOW}/{f}', 'rb').read()).hexdigest()[:8]}"
    show = {
        "title": "Switch Off The Game (Musiclide) - V1 / S.A.M. and Niko",
        "audio": ver("mix.mp3"), "backing": ver("backing.mp3"), "video": ver("video.mp4"),
        "bpm": 96, "downbeat": 0,
        "voices": [
            {"name": "V1", "tele": ver("lead.tele"), "melody": ver("lead.json"), "look": "v1"},
            {"name": "Niko", "tele": ver("second.tele"), "melody": ver("second.json"), "look": "niko", "enter": 179},
        ],
    }
    json.dump(show, open(f"{SHOW}/show.json", "w"), indent=1)
    print(f"{SHOW}: voices peak {np.max(np.abs(voices * k)):.2f}, scale {k:.2f}")


if __name__ == "__main__":
    main()
