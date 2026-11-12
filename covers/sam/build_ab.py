"""Build the ARTIST BLOCK show: V1 (S.A.M.) sings, CHIMERA's heads only move.

  python covers/sam/build_ab.py               then open http://127.0.0.1:5317/?show=artist-block

1. make_ab.py: one melody per singer (Caine and the six guests) and their spans.
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
# S.A.M. sits under the band more than a human voice does: this much louder than the original's
# vocal stem against its instrumental
LIFT_DB = 2.0
# the guests' heads (CHIMERA's own; only Caine wears V1): the body each actor's voice suggests
FEMALE = {"Pomni", "Ragatha", "Gangle", "Zooble"}


def run(*cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def say(text, length):
    """S.A.M. saying `text`, its silence trimmed, fitted to `length` s: at most 2.5x faster (a word
    squeezed harder only runs a little long) and at most 1.25x slower (stretched further, S.A.M.'s
    voice turns to a buzz: a word given more time than that ends early instead)"""
    words = re.sub(r"\(.*?\)\s*", "", text).upper()
    words = re.sub(r"[^A-Z0-9 .,?!'-]", "", words).strip(" -") or "HA"
    raw = f"{BUILD}/tts.wav"
    run(f"{VENDOR}/sam-tts/sam", "-wav", raw, words, stdout=subprocess.DEVNULL)
    y, sr = sf.read(raw, dtype="float32")
    y = librosa.effects.trim(y - float(np.median(y)), top_db=35)[0]
    tempo, chain = min(max(len(y) / sr / max(length, 0.05), 0.8), 2.5), []
    while tempo > 2.0:
        chain.append("atempo=2.0")
        tempo /= 2.0
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
    VOICES = list(dict.fromkeys(s["voice"] for s in spans))  # the singers, Caine first
    words = json.load(open(f"{AB}/song/aligned_words.json"))
    renders = [subprocess.Popen(["./target/release/chimera", "render", "notes", f"{BUILD}/{v}.json", f"{BUILD}/chimera-{v}", "female" if v in FEMALE else "male",
                                 "--tele", f"{SHOW}/{v}.tele", "--syllables", f"{BUILD}/{v}.syl.json"], cwd=REPO, stdout=subprocess.DEVNULL)
               for v in VOICES]
    if any(p.wait() for p in renders):
        sys.exit("chimera render failed")

    # the sung syllables, to the bank; a line several sing (the bridge) sounds once, from its first
    # singer (S.A.M. has one voice: six equal copies would only be louder), the other heads mime it
    owner = {}
    for s in spans:
        owner.setdefault(s["line"], s["voice"])
    mine = lambda v, kind: [s for s in spans if s["voice"] == v and s["kind"] == kind and owner[s["line"]] == v]  # noqa: E731
    sams = []
    for v in VOICES:
        sung = [(s["start"] - 0.01, s["end"]) for s in mine(v, "SUNG")]
        syl = [n for n in json.load(open(f"{BUILD}/{v}.syl.json")) if any(a <= n["t"] < b for a, b in sung)]
        if os.path.exists(f"{BUILD}/sam-{v}.wav"):
            os.remove(f"{BUILD}/sam-{v}.wav")
        if not syl:  # only spoken lines
            continue
        json.dump(syl, open(f"{BUILD}/{v}.sung.json", "w"))
        sams.append(subprocess.Popen([sys.executable, f"{HERE}/sam_render.py", f"{BUILD}/{v}.sung.json", f"{BUILD}/sam-{v}.wav", "--bpm", "120"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if any(p.wait() for p in sams):
        sys.exit("sam_render failed")

    # the instrumental, moved with the melody (Rubber Band, through ffmpeg)
    sys.path.insert(0, HERE)
    from make_ab import HAND, TRANSPOSE
    inst = f"{BUILD}/instrumental{TRANSPOSE:+d}.wav"
    if not os.path.exists(inst):
        run("ffmpeg", "-v", "error", "-y", "-i", f"{AB}/song/instrumental_official.wav", "-af",
            f"rubberband=pitch={2 ** (TRANSPOSE / 12):.6f}:pitchq=quality:transients=crisp", "-ar", str(SR), inst)
    backing, _ = librosa.load(inst, sr=SR, mono=False)
    n = backing.shape[1]
    tracks = {}
    for v in VOICES:
        t = np.zeros(n, np.float32)
        if os.path.exists(f"{BUILD}/sam-{v}.wav"):
            place(t, librosa.load(f"{BUILD}/sam-{v}.wav", sr=SR)[0], 0.0)
        for s in mine(v, "SPOKEN"):
            # a hand-set line is spoken where its head speaks it (its words' times are the aligner's
            # guess, which can sit on another singer's held note)
            ws = [] if s["line"] in HAND else [w for w in words if w["line"] == s["line"]]
            for w in ws or [{"word": s["text"], "start": s["start"], "end": s["end"]}]:
                place(t, 0.8 * say(w["word"], w["end"] - w["start"]), w["start"])
        tracks[v] = t

    # the original's balance: its vocal stem against its instrumental, by RMS
    rms = lambda y: float(np.sqrt(np.mean(np.square(y))))  # noqa: E731
    ov, _ = librosa.load(f"{AB}/song/vocals.wav", sr=SR)
    oi, _ = librosa.load(f"{AB}/song/instrumental.wav", sr=SR)
    # the singers spread a little across the stereo field, as they would stand
    pans = np.linspace(-0.3, 0.3, len(VOICES))
    voices = sum(np.stack([(1 - p) * tracks[v], (1 + p) * tracks[v]]) for v, p in zip(VOICES, pans))
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
    def on(v):
        """when a guest's head is on screen: 0.3 s around each of its lines, breaks under 4 s joined"""
        out = []
        for s in sorted((s for s in spans if s["voice"] == v), key=lambda s: s["start"]):
            a, b = s["start"] - 0.3, s["end"] + 0.3
            if out and a - out[-1][1] < 4.0:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b])
        return [[round(a, 2), round(b, 2)] for a, b in out]
    show = {
        "title": "ARTIST BLOCK (St4tic) - V1 / S.A.M. cover",
        "audio": ver("mix.mp3"), "backing": ver("backing.mp3"), "video": ver("video.mp4"),
        "bpm": 120, "downbeat": 0.022,
        # one head per singer: V1 plays Caine, the guests keep CHIMERA's own head, face him (left) and
        # are on screen only while they sing
        "voices": [{"name": "V1 as Caine", "tele": ver(f"{v}.tele"), "melody": ver(f"{v}.json"), "look": "v1", "facing": 1} if not i else
                   {"name": v, "tele": ver(f"{v}.tele"), "melody": ver(f"{v}.json"), "on": on(v), "facing": -1}
                   for i, v in enumerate(VOICES)],
    }
    json.dump(show, open(f"{SHOW}/show.json", "w"), indent=1)
    print(f"{SHOW}: voices peak {np.max(np.abs(voices * k)):.2f}, scale {k:.2f}")


if __name__ == "__main__":
    main()
