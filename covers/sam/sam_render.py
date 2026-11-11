#!/usr/bin/env python3
"""Headless renderer for the S.A.M. English ARPAsing UTAU bank (oto diphones + WORLD).

  python covers/sam/sam_render.py NOTES.json OUT.wav [--timing OUT.timing.json] [--bpm 120]

NOTES.json: array of {t, dur, midi, syl:{onset:[{ipa}],nucleus:{ipa},coda:[{ipa}],melisma?,phraseEnd?}}
(the syllabifier format).  Optional extras: syl.arpa = ["t","ao",...] overrides IPA (onset+nucleus+coda order
is then taken from syl.onset/nucleus/coda lengths), note.bend = [[sec_from_note_start, cents],...].

Method = OpenUtau ArpasingPhonemizer layout (first vowel on the beat, leading consonants before it, coda
consonants at the end, aliases "prev cur", "- c" at phrase start, "x -" at phrase end) + UTAU oto semantics
(offset/consonant/cutoff/preutt/overlap) but joined in the WORLD parameter domain (log-spectrum, aperiodicity
crossfades, one global flat f0 contour) so there are no waveform phase clicks.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import VENDOR, WORK  # noqa: E402
import numpy as np, pyworld as pw, soundfile as sf

BANK = os.environ.get("SAM_BANK", f"{VENDOR}/sam-bank")  # the Samparsing folder of the Samouthuel pack
CACHE = f"{WORK}/sam-cache"  # WORLD analysis of every bank wav, built on first use
SR, FP = 44100, 5.0 / 1000  # output rate, WORLD frame period (s)
CONS_TICKS, PPQ = 60, 480   # OpenUtau PhonemeBasedPhonemizer.ConsonantLength
PHRASE_GAP = 0.12           # rest longer than this ends the phrase even without phraseEnd
HOLD = 0.08                 # seconds of vowel tail ping-ponged when a phoneme must be stretched
VOWELS = set("aa ae ah ao aw ax ay eh er ey ih iy ow oy uh uw".split())
FALLBACK = {"aa": "ah ae", "ae": "ah aa", "ah": "aa ae", "ao": "ow", "ow": "ao", "eh": "ae", "ih": "iy",
            "iy": "ih", "uh": "uw", "uw": "uh", "aw": "ao", "ax": "ah"}
IPA = {  # IPA (as emitted by the chimera syllabifier) -> bank ARPAbet
    "ɪ": "ih", "ə": "ax", "i": "iy", "eɪ": "ey", "oʊ": "ow", "ɛ": "eh", "u": "uw", "ɔ": "ao", "aɪ": "ay",
    "æ": "ae", "ɑ": "aa", "ɚ": "er", "ɝ": "er", "ʊ": "uh", "aʊ": "aw", "ɔɪ": "oy", "ʌ": "ah", "ɐ": "ah",
    "ɜ": "er", "ɒ": "aa", "əʊ": "ow", "e": "ey", "o": "ow", "a": "aa", "ɨ": "ih", "ᵻ": "ih", "ɵ": "ow",
    "t": "t", "n": "n", "s": "s", "ɹ": "r", "r": "r", "l": "l", "ɫ": "l", "d": "d", "ð": "dh", "m": "m",
    "f": "f", "j": "y", "v": "v", "b": "b", "g": "g", "ɡ": "g", "w": "w", "z": "z", "ŋ": "ng", "h": "hh",
    "k": "k", "p": "p", "ʃ": "sh", "tʃ": "ch", "dʒ": "jh", "θ": "th", "ʒ": "zh", "ɾ": "d", "ʔ": None,
}


def arpa(ipa):
    k = ipa.replace("ː", "").replace("ˈ", "").replace("ˌ", "").replace("\u0361", "").replace("\u0329", "")
    if k not in IPA:
        sys.exit(f"unknown IPA symbol {ipa!r}; add it to IPA in sam_render.py")
    return IPA[k]


# ---------------------------------------------------------------- bank
def load_oto():
    oto = {}
    for sub in ("G#2 BASE", "G#2 Extras"):  # Extras last: its "x -" fade-out endings override Base duplicates
        d = os.path.join(BANK, sub)
        for line in open(os.path.join(d, "oto.ini"), encoding="cp932").read().splitlines():
            if "=" not in line:
                continue
            f, rest = line.split("=", 1)
            a, *v = rest.split(",")
            a = a[:-3] if a.endswith("G#2") else a  # prefix.map: every pitch -> suffix G#2
            v = [float(x) / 1000 if x else 0.0 for x in (v + [""] * 5)[:5]]
            oto[a] = (os.path.join(d, f), *v)  # file, offset, consonant, cutoff, preutt, overlap (seconds)
    return oto


def bridge(x, sr, f0, max_gap=25, db=3):
    """harvest drops f0 during fast diphthong->nasal glides although the sound is clearly voiced: interpolate gaps
    <=125 ms that sit between voiced frames and whose spectrum is low-band dominated (0-1 kHz vs 3-8 kHz)."""
    c = (np.arange(len(f0)) * FP * sr).astype(int)
    seg = np.stack([np.pad(x, (551, 551))[i:i + 1102] for i in c]) * np.hanning(1102)
    P = np.abs(np.fft.rfft(seg, 2048)) ** 2
    r = 10 * np.log10((P[:, :46].sum(1) + 1e-12) / (P[:, 140:372].sum(1) + 1e-12))
    f0, i = f0.copy(), 0
    while i < len(f0):
        if f0[i] > 0:
            i += 1; continue
        j = i
        while j < len(f0) and f0[j] == 0: j += 1
        if 0 < i and j < len(f0) and j - i <= max_gap and (r[i:j] > db).all():
            f0[i:j] = np.interp(np.arange(i, j), [i - 1, j], [f0[i - 1], f0[j]])
        i = j
    return f0


_an = {}
def analyze(path):
    """WORLD analysis of a bank wav, cached on disk: (log spectral envelope, aperiodicity, voiced mask)."""
    if path in _an:
        return _an[path]
    cp = os.path.join(CACHE, os.path.relpath(path, BANK).replace("/", "__").replace(" ", "_") + ".npz")
    if os.path.exists(cp):
        z = np.load(cp)
        r = (z["ls"], z["ap"], z["vo"], z["n"])
    else:
        x, sr = sf.read(path)
        assert sr == SR, (path, sr)
        x = np.ascontiguousarray(x if x.ndim == 1 else x[:, 0])
        # harvest, not dio: some bank vowels sit an octave up (~213 Hz) and dio drops them as unvoiced
        f0, t = pw.harvest(x, sr, f0_floor=60, f0_ceil=600, frame_period=FP * 1000)
        f0 = bridge(x, sr, f0)
        sp = pw.cheaptrick(x, f0, t, sr)
        ap = pw.d4c(x, f0, t, sr)
        r = (np.log(np.maximum(sp, 1e-16)).astype(np.float32), ap.astype(np.float32), f0 > 0, np.array(len(x) / sr))
        os.makedirs(CACHE, exist_ok=True)
        np.savez(cp, ls=r[0], ap=r[1], vo=r[2], n=r[3])
    _an[path] = r
    return r


def pick_alias(oto, prev, cur):
    """OpenUtau LatinDiphonePhonemizer.GetPhonemeOrFallback; None = no sample (caller skips it)."""
    if cur == "-":
        return f"{prev} -" if f"{prev} -" in oto else None
    for p in [prev] + (["ah"] if prev == "ax" else []):
        for c in [cur] + FALLBACK.get(cur, "").split():
            if f"{p} {c}" in oto:
                return f"{p} {c}"
    for c in [cur] + FALLBACK.get(cur, "").split():  # no diphone (e.g. most C-C pairs): restart on the new phone
        if f"- {c}" in oto:
            return f"- {c}"
    sys.exit(f"no alias for {prev} {cur}")


# ---------------------------------------------------------------- phoneme layout
def layout(notes, bpm):
    """notes -> (groups, phones). One group per syllable (melisma notes merged into the previous one)."""
    cons = CONS_TICKS / PPQ * 60 / bpm
    notes = sorted(notes, key=lambda n: n["t"])
    groups = []
    for i, n in enumerate(notes):
        s = n["syl"]
        if s.get("melisma") and groups:
            g = groups[-1]; g["notes"].append(i); g["end"] = n["t"] + n["dur"]
            continue
        a = s.get("arpa")
        on, nu, co = s.get("onset", []), s.get("nucleus"), s.get("coda", [])
        if a:
            on, nu, co = a[:len(on)], a[len(on)], a[len(on) + 1:]
        else:
            on = [arpa(p["ipa"]) for p in on]; nu = arpa(nu["ipa"]) if nu else "ax"; co = [arpa(p["ipa"]) for p in co]
        groups.append(dict(text=s.get("text", ""), on=[p for p in on if p], nu=nu, co=[p for p in co if p],
                           ipa=s, t=n["t"], end=n["t"] + n["dur"], notes=[i], brk=bool(s.get("phraseEnd"))))
    for k, g in enumerate(groups):  # phrase break: flagged, or a real rest follows
        nxt = groups[k + 1]["t"] if k + 1 < len(groups) else None
        g["brk"] = g["brk"] or nxt is None or nxt - g["end"] > PHRASE_GAP
    phones = []
    for k, g in enumerate(groups):
        ph = lambda sym, t, role: phones.append(dict(sym=sym, t=t, role=role, g=k, text=g["text"]))
        for j, c in enumerate(g["on"]):
            ph(c, g["t"] - (len(g["on"]) - j) * cons, "onset")
        ph(g["nu"], g["t"], "nucleus")
        tail = g["co"] + (["-"] if g["brk"] else [])
        cc = min(cons, (g["end"] - g["t"]) / 2 / max(len(tail), 1))
        for j, c in enumerate(tail):
            ph(c, g["end"] - (len(tail) - j) * cc, "tail" if c == "-" else "coda")
    # a coda that runs into the next syllable's onset (or a too-short vowel) -> lay the cluster out back to back
    for k in range(len(groups) - 1):
        a, b = groups[k], groups[k + 1]
        if a["brk"]:
            continue
        co = [p for p in phones if p["g"] == k and p["role"] == "coda"]
        on = [p for p in phones if p["g"] == k + 1 and p["role"] == "onset"]
        cl = co + on
        if not cl:
            continue
        w = min(cons, (b["t"] - a["t"]) / 2 / len(cl))
        if w < cons or (co and on and co[-1]["t"] + 0.02 > on[0]["t"]):
            for j, p in enumerate(cl):
                p["t"] = b["t"] - (len(cl) - j) * w
    return groups, phones


# ---------------------------------------------------------------- pitch
def contour(notes, glide=0.04):
    """Flat per-note pitch with a short linear glide between notes; optional per-note bend [[sec, cents], ...]."""
    pts, prev = [], None
    for n in sorted(notes, key=lambda n: n["t"]):
        m = float(n["midi"])
        if prev is not None and prev != m:
            pts.append((n["t"] - glide / 2, prev)); pts.append((n["t"] + glide / 2, m))
        elif prev is None:
            pts.append((n["t"] - 10, m)); pts.append((n["t"], m))
        for tt, c in n.get("bend", []):
            pts.append((n["t"] + tt, m + c / 100))
        prev = pts[-1][1] if n.get("bend") else m
        pts.append((n["t"] + n["dur"] - 1e-3, prev))
    pts.sort(key=lambda p: p[0])
    xs, ys = zip(*pts)
    return lambda t: 440 * 2 ** ((np.interp(t, xs, ys) - 69) / 12)


# ---------------------------------------------------------------- render
def tmap(x, P2, P, C, L, D):
    """Output time x (s from segment start) -> source time (s from oto offset)."""
    y1, y2 = P, min(max(C, P), L); x1 = P2; x2 = x1 + (y2 - y1)
    if D < x2:  # too short even for the fixed part: squeeze it
        f = D / max(x2, 1e-6)
        return np.interp(x, [0, x1 * f, D], [0, y1, y2])
    t_out, t_src = D - x2, L - y2
    if t_out <= t_src * 2.0:  # compress (at most 2x) like UTAU; beyond that truncate
        sp = max(t_out / t_src, 0.5) if t_src > 0 else 1
        return np.interp(x, [0, x1, x2, x2 + t_src * sp], [0, y1, y2, L])
    h = min(HOLD, t_src); xp = x2 + t_src - h  # stretch: play normally, then ping-pong the last `h` seconds
    y = np.interp(x, [0, x1, x2, xp], [0, y1, y2, L - h])
    u = np.mod(x - xp, 2 * h) if h > 0 else 0 * x
    return np.where(x > xp, L - h + np.where(u <= h, u, 2 * h - u), y)


def render(notes, bpm, wav_path, timing_path):
    oto = load_oto()
    groups, phones = layout(notes, bpm)
    f0fn = contour(notes)
    # alias selection
    segs, prev = [], "-"
    for p in phones:
        al = pick_alias(oto, prev, p["sym"])
        prev = "-" if p["sym"] == "-" else p["sym"]
        p["alias"] = al
        if al:
            file, off, C, cut, P, O = oto[al]
            nat = analyze(file)[3] - off
            L = nat - cut if cut > 0 else (-cut if cut < 0 else nat)  # UTAU cutoff: >0 trims from file end, <0 = length from offset
            segs.append(dict(p=p, file=file, off=off, C=C, P=P, O=O, L=L, t=p["t"]))
    # UTAU preutt/overlap scaling when the previous phoneme is shorter than the preutterance
    for i, s in enumerate(segs):
        gap = s["t"] - segs[i - 1]["t"] if i else 1e9
        k = min(1.0, 0.9 * gap / s["P"]) if s["P"] > 0 else 1.0
        s["P2"], s["O2"] = s["P"] * k, s["O"] * k
        s["s"] = s["t"] - s["P2"]; s["ramp"] = max(s["O2"], 0.01)
    for i, s in enumerate(segs):
        last = (i + 1 == len(segs) or s["p"]["role"] == "tail"
                or (groups[s["p"]["g"]]["brk"] and segs[i + 1]["p"]["g"] != s["p"]["g"]))
        s["last"] = last
        if last:
            if s["p"]["role"] == "tail":
                s["e"] = s["s"] + s["P2"] + (s["L"] - s["P"]); s["fade"] = 0.01
            else:  # no end sample (hh/r/w/y): hold to the note end, 40 ms fade
                s["e"] = groups[s["p"]["g"]]["end"] + 0.04; s["fade"] = 0.04
        else:
            s["e"] = segs[i + 1]["s"] + segs[i + 1]["ramp"]
        s["e"] = max(s["e"], s["s"] + 0.01)
        s["D"] = s["e"] - s["s"]
    # chunks = phrases (split after every last segment)
    chunks, cur = [], []
    for s in segs:
        cur.append(s)
        if s["last"]:
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    t_end = max(s["e"] for s in segs) + 0.1
    out = np.zeros(int(t_end * SR) + SR)
    for ch in chunks:
        fa, fb = int(np.floor(ch[0]["s"] / FP)), int(np.ceil(max(s["e"] for s in ch) / FP)) + 1
        T, F = fb - fa, analyze(ch[0]["file"])[0].shape[1]
        A_ls, A_ap = np.zeros((T, F)), np.zeros((T, F)); A_v, W = np.zeros(T), np.zeros(T)
        tau = (np.arange(fa, fb)) * FP
        for i, s in enumerate(ch):
            ls, ap, vo, _ = analyze(s["file"])
            m = (tau >= s["s"]) & (tau < s["e"])
            if not m.any(): continue
            x = tau[m] - s["s"]
            y = np.minimum(tmap(x, s["P2"], s["P"], s["C"], s["L"], s["D"]), s["L"])
            fi = np.clip((s["off"] + y) / FP, 0, len(ls) - 1.001); i0 = fi.astype(int); fr = (fi - i0)[:, None]
            w = np.clip(x / s["ramp"], 0, 1)
            if i + 1 < len(ch):
                w = w * (1 - np.clip((tau[m] - ch[i + 1]["s"]) / ch[i + 1]["ramp"], 0, 1))
            else:
                w = w * np.clip((s["e"] - tau[m]) / s["fade"], 0, 1) if "fade" in s else w
            if i == 0: w = np.maximum(w, 0)  # first phoneme fades in over its ramp
            idx = np.nonzero(m)[0]
            A_ls[idx] += w[:, None] * ((1 - fr) * ls[i0] + fr * ls[i0 + 1])
            A_ap[idx] += w[:, None] * ((1 - fr) * ap[i0] + fr * ap[i0 + 1])
            A_v[idx] += w * vo[np.rint(fi).astype(int)]; W[idx] += w
        nz = W > 1e-6
        Wd = np.where(nz, W, 1)
        sp = np.exp(A_ls / Wd[:, None]) * (np.minimum(W, 1) ** 2)[:, None]
        ap = np.clip(A_ap / Wd[:, None], 0, 1)
        sp[~nz] = 0; ap[~nz] = 1
        sp = np.maximum(sp, 1e-16)  # exact zeros make WORLD's synthesizer emit NaN
        f0 = np.where(nz & (A_v / Wd > 0.5), f0fn(tau), 0.0)
        y = pw.synthesize(np.ascontiguousarray(f0), np.ascontiguousarray(sp), np.ascontiguousarray(ap), SR, FP * 1000)
        a = int(round(fa * FP * SR)); b = min(a + len(y), len(out))
        if a < 0: sys.exit("phrase starts before t=0; shift the notes later")
        out[a:b] += y[:b - a]
    out *= 0.9 / max(np.abs(out).max(), 1e-9)
    sf.write(wav_path, out[:int(t_end * SR)], SR, subtype="PCM_16")
    # timing json
    ph_out = []
    sq = {id(s["p"]): s for s in segs}
    for i, p in enumerate(phones):
        s = sq.get(id(p))
        if p["role"] == "tail":
            end = s["e"] if s else p["t"]
        elif i + 1 < len(phones) and not (groups[p["g"]]["brk"] and phones[i + 1]["g"] != p["g"]):
            end = phones[i + 1]["t"]
        else:
            end = groups[p["g"]]["end"]
        ph_out.append(dict(arpa=p["sym"], alias=p["alias"], role=p["role"], start=round(p["t"], 4), end=round(end, 4),
                           sound_start=round(s["s"], 4) if s else None, syl=p["text"], note=groups[p["g"]]["notes"][0]))
    json.dump(dict(sr=SR, bpm=bpm, duration=round(t_end, 3), consonant_len=round(CONS_TICKS / PPQ * 60 / bpm, 4),
                   notes=[dict(i=i, t=n["t"], end=round(n["t"] + n["dur"], 4), midi=n["midi"], bend=n.get("bend"),
                               text=n["syl"].get("text", "")) for i, n in enumerate(sorted(notes, key=lambda n: n["t"]))],
                   phonemes=ph_out), open(timing_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("notes"); ap.add_argument("wav"); ap.add_argument("--timing"); ap.add_argument("--bpm", type=float, default=120)
    a = ap.parse_args()
    render(json.load(open(a.notes)), a.bpm, a.wav, a.timing or os.path.splitext(a.wav)[0] + ".timing.json")
