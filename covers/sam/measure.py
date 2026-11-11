#!/usr/bin/env python3
"""Smoke check: per-note pitch error (cents), gaps and click candidates.
  python covers/sam/measure.py smoke.wav smoke.timing.json"""
import json, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, pyworld as pw, soundfile as sf

y, sr = sf.read(sys.argv[1]); T = json.load(open(sys.argv[2]))
f0, t = pw.harvest(y.astype("f8"), sr, f0_floor=70, f0_ceil=500, frame_period=5)
midi = np.where(f0 > 0, 69 + 12 * np.log2(np.maximum(f0, 1) / 440), np.nan)
ph = T["phonemes"]
print(f"duration {len(y)/sr:.2f}s peak {np.abs(y).max():.2f}")
print("note  text      target  win(s)        n   median_err_c  mad_c")
bad = 0
for n in T["notes"]:
    nuc = [p for p in ph if p["role"] == "nucleus" and p["start"] <= n["t"] + 1e-3 and p["end"] > n["t"]]
    lo = n["t"] + 0.03
    hi = min(n["end"], nuc[0]["end"] if nuc else n["end"]) - 0.01  # stay inside the vowel (coda consonants are noisy)
    if nuc and nuc[0]["note"] != n["i"]:  # melisma note: vowel runs through, but a coda begins at the group end
        hi = n["end"] - 0.01
    m = (t >= lo) & (t <= hi) & ~np.isnan(midi)
    if m.sum() < 3:
        print(f"{n['i']:>3}  {n['text']:<8} no voiced frames in window"); continue
    tt = t[m]; tgt = n["midi"] + np.interp(tt - n["t"], *zip(*n["bend"])) / 100 if n.get("bend") else n["midi"]
    err = (midi[m] - tgt) * 100
    print(f"{n['i']:>3}  {n['text']:<8} {n['midi']:>5.1f}  {lo:5.2f}-{hi:5.2f}  {m.sum():>3}  {np.median(err):+8.1f}     {np.median(abs(err - np.median(err))):.1f}")
    bad += abs(np.median(err)) > 25
print("notes with |median error| > 25 cents:", bad)
# gaps: 10 ms RMS below -50 dBFS between the first and last sound, longer than 25 ms, not at a declared phrase end
h = int(sr * 0.01); r = np.sqrt(np.convolve(y ** 2, np.ones(h) / h, "same"))[::h]
db = 20 * np.log10(r + 1e-9); loud = np.nonzero(db > -40)[0]
silent = db < -50; gaps = []; i = 0
while i < len(silent):
    if silent[i]:
        j = i
        while j < len(silent) and silent[j]: j += 1
        if j - i >= 3 and loud[0] < i and j < loud[-1]: gaps.append((i * 0.01, j * 0.01))
        i = j
    else: i += 1
rests = [(p["end"], q["sound_start"]) for p, q in zip(ph, ph[1:]) if p["role"] == "tail" and q["sound_start"]]
ctx = lambda a: next((p["alias"] for p in ph if p["start"] <= a + 0.02 < p["end"]), "?")
print("silent gaps >=30 ms (s, phoneme at gap):", [(round(a, 2), round(b, 2), ctx(a)) for a, b in gaps])
print("  declared rests (tail end -> next onset):", [(round(a, 2), round(b, 2)) for a, b in rests])
# clicks: spike in 2nd difference relative to its 5 ms local RMS
d2 = np.diff(y, 2); w = int(sr * 0.005); loc = np.sqrt(np.convolve(d2 ** 2, np.ones(w) / w, "same")) + 1e-6
z = np.abs(d2) / loc; idx = np.nonzero((z > 12) & (np.abs(d2) > 0.01))[0]
print("click candidates (|d2| > 12x local rms and > 0.01):", len(idx), [round(i / sr, 3) for i in idx[:20]])
