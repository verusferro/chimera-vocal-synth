"""Median pitch of a monophonic stem per eighth note on the song grid.  python covers/song/f0_grid.py FILE OFFSET_S BEAT0 BEAT1"""
import sys, numpy as np, librosa
path, off, b0, b1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
BEAT=0.625; sr=16000
y, _ = librosa.load(path, sr=sr, mono=True)
f, vf, vp = librosa.pyin(y, fmin=150, fmax=1100, sr=sr, frame_length=1024, hop_length=160)
rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=160)[0]
ref = np.percentile(rms, 95)
N=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
row=[]
for k in np.arange(b0, b1, 0.5):
    a, b = int((k*BEAT-off+0.05)*sr/160), int(((k+0.5)*BEAT-off-0.03)*sr/160)
    if a < 0 or b > len(f): continue
    seg, lvl = f[a:b], rms[a:b].mean()/ref
    ok = seg[~np.isnan(seg)]
    if len(ok) < 0.5*len(seg) or lvl < 0.08: row.append(f"{k:g}:--")
    else:
        m = 69+12*np.log2(np.median(ok)/440); r=int(round(m))
        row.append(f"{k:g}:{N[r%12]}{r//12-1}({lvl:.1f})")
    if len(row)==8: print('  '.join(row)); row=[]
if row: print('  '.join(row))
