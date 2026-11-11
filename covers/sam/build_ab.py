"""Build the ARTIST BLOCK show: V1 (S.A.M.) sings, CHIMERA's heads only move.

  python covers/sam/build_ab.py               then open http://127.0.0.1:5317/?show=artist-block

1. make_ab.py: the two melodies (lead = Caine's lines, second = everyone else's) and their spans.
2. CHIMERA renders each melody for its telemetry (the heads' mouths) and its syllables; its own
   sound is thrown away.
3. The sung syllables go to the S.A.M. UTAU bank (sam_render.py), on the same beats.
4. Spoken lines: S.A.M. text-to-speech (vendor/sam-tts/sam), one word at a time, each stretched onto
   the original word's place (HubertFA times), so the speech keeps the actors' pace and pauses.
5. Voices and the official instrumental, at the original's vocal-to-backing balance, and the show.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

import librosa
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from paths import REPO, SHOWS, VENDOR, WORK  # noqa: E402

AB = f"{WORK}/ab"  # ARTIST BLOCK data: song/ (stems, notes, words), research/, build/
BUILD = f"{AB}/build"
SHOW = f"{SHOWS}/artist-block"
SR = 44100
VOICES = ("lead", "second")
# S.A.M. sits under the band more than a human voice does: this much louder than the original's
# vocal stem against its instrumental
LIFT_DB = 2.0


def run(*cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def say(text, length):
    """S.A.M. saying `text`, its silence trimmed, stretched to `length` s (at most 2.5x faster:
    a word squeezed harder only runs a little long)"""
    words = re.sub(r"\(.*?\)\s*", "", text).upper()
    words = re.sub(r"[^A-Z0-9 .,?!'-]", "", words).strip(" -") or "HA"
    raw = f"{BUILD}/tts.wav"
    run(f"{VENDOR}/sam-tts/sam", "-wav", raw, words, stdout=subprocess.DEVNULL)
    y, sr = sf.read(raw, dtype="float32")
    y = librosa.effects.trim(y - float(np.median(y)), top_db=35)[0]
    tempo, chain = min(len(y) / sr / max(length, 0.05), 2.5), []
    while tempo > 2.0:
        chain.append("atempo=2.0")
        tempo /= 2.0
    while tempo < 0.5:
        chain.append("atempo=0.5")
        tempo /= 0.5
    chain.append(f"atempo={tempo:.5f}")
    sf.write(raw, y, sr)
    out = f"{BUILD}/tts_fit.wav"
    run("ffmpeg", "-v", "error", "-y", "-i", raw, "-af", ",".join(chain), "-ar", str(SR), "-ac", "1", out)
    y, _ = sf.read(out, dtype="float32")
    fade = min(len(y) // 4, int(0.005 * SR))
    if fade:
        y[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        y[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return y


def place(track, y, t):
    a = int(t * SR)
    b = min(len(track), a + len(y))
    track[a:b] += y[: b - a]


def main():
    os.makedirs(SHOW, exist_ok=True)
    run(sys.executable, f"{HERE}/make_ab.py")
    spans = json.load(open(f"{BUILD}/spans.json"))
    words = json.load(open(f"{AB}/song/aligned_words.json"))
    renders = [subprocess.Popen(["./target/release/chimera", "render", "notes", f"{BUILD}/{v}.json", f"{BUILD}/chimera-{v}", "male",
                                 "--tele", f"{SHOW}/{v}.tele", "--syllables", f"{BUILD}/{v}.syl.json"], cwd=REPO, stdout=subprocess.DEVNULL)
               for v in VOICES]
    if any(p.wait() for p in renders):
        sys.exit("chimera render failed")

    # the sung syllables, to the bank
    sams = []
    for v in VOICES:
        sung = [(s["start"] - 0.01, s["end"]) for s in spans if s["voice"] == v and s["kind"] == "SUNG"]
        syl = [n for n in json.load(open(f"{BUILD}/{v}.syl.json")) if any(a <= n["t"] < b for a, b in sung)]
        json.dump(syl, open(f"{BUILD}/{v}.sung.json", "w"))
        sams.append(subprocess.Popen([sys.executable, f"{HERE}/sam_render.py", f"{BUILD}/{v}.sung.json", f"{BUILD}/sam-{v}.wav", "--bpm", "120"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if any(p.wait() for p in sams):
        sys.exit("sam_render failed")

    # the instrumental, moved with the melody (Rubber Band, through ffmpeg)
    sys.path.insert(0, HERE)
    from make_ab import TRANSPOSE
    inst = f"{BUILD}/instrumental{TRANSPOSE:+d}.wav"
    if not os.path.exists(inst):
        run("ffmpeg", "-v", "error", "-y", "-i", f"{AB}/song/instrumental_official.wav", "-af",
            f"rubberband=pitch={2 ** (TRANSPOSE / 12):.6f}:pitchq=quality:transients=crisp", "-ar", str(SR), inst)
    backing, _ = librosa.load(inst, sr=SR, mono=False)
    n = backing.shape[1]
    tracks = {}
    for v in VOICES:
        t = np.zeros(n, np.float32)
        y, _ = librosa.load(f"{BUILD}/sam-{v}.wav", sr=SR)
        place(t, y, 0.0)
        for s in spans:
            if s["voice"] != v or s["kind"] != "SPOKEN":
                continue
            ws = [w for w in words if w["line"] == s["line"]]
            for w in ws or [{"word": s["text"], "start": s["start"], "end": s["end"]}]:
                place(t, 0.8 * say(w["word"], w["end"] - w["start"]), w["start"])
        tracks[v] = t

    # the original's balance: its vocal stem against its instrumental, by RMS
    rms = lambda y: float(np.sqrt(np.mean(np.square(y))))  # noqa: E731
    ov, _ = librosa.load(f"{AB}/song/vocals.wav", sr=SR)
    oi, _ = librosa.load(f"{AB}/song/instrumental.wav", sr=SR)
    voices = np.stack([0.95 * tracks["lead"] + 0.75 * tracks["second"], 0.8 * tracks["lead"] + 0.95 * tracks["second"]])
    voices *= rms(ov) / rms(oi) * rms(backing) / rms(voices) * 10 ** (LIFT_DB / 20)
    # the page plays both at full volume at first: together they must not clip
    k = 0.95 / float(np.max(np.abs(voices + backing)))
    for name, y in (("mix", voices * k), ("backing", backing * k)):
        sf.write(f"{BUILD}/{name}.wav", y.T, SR)
        run("ffmpeg", "-v", "error", "-y", "-i", f"{BUILD}/{name}.wav", "-c:a", "libmp3lame", "-q:a", "2", f"{SHOW}/{name}.mp3")
    for v in VOICES:
        run("cp", f"{BUILD}/{v}.json", f"{SHOW}/{v}.json")
    run("cp", f"{AB}/song/video.mp4", f"{SHOW}/video.mp4")

    # each address carries its content's hash, so a CDN or browser cache can't serve old files
    def ver(f):
        return f"{f}?v={hashlib.md5(open(f'{SHOW}/{f}', 'rb').read()).hexdigest()[:8]}"
    first_guest = min(s["start"] for s in spans if s["voice"] == "second")
    show = {
        "title": "ARTIST BLOCK (St4tic) - V1 / S.A.M. cover",
        "audio": ver("mix.mp3"), "backing": ver("backing.mp3"), "video": ver("video.mp4"),
        "bpm": 120, "downbeat": 0.022,
        "voices": [
            {"name": "V1 as Caine", "tele": ver("lead.tele"), "melody": ver("lead.json"), "look": "v1"},
            {"name": "V1 as the cast", "tele": ver("second.tele"), "melody": ver("second.json"), "look": "v1", "enter": round(first_guest - 0.3, 2)},
        ],
    }
    json.dump(show, open(f"{SHOW}/show.json", "w"), indent=1)
    print(f"{SHOW}: voices peak {np.max(np.abs(voices * k)):.2f}, scale {k:.2f}")


if __name__ == "__main__":
    main()
