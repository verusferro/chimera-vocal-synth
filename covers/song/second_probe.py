"""Which pitch sounds besides the lead's? Harmonic salience of the vocal stem per eighth note.  python covers/song/second_probe.py BEAT0 BEAT1"""
import json, os, sys, numpy as np, librosa
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import WORK
y, sr = librosa.load(WORK+'/stems/song_(vocals)_bs_roformer_vocals_resurrection_unwa.wav', sr=22050, mono=True)
BEAT=0.625
S = np.abs(librosa.stft(y, n_fft=4096, hop_length=512))
freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
def sal(t0, t1):
    a, b = int(t0*sr/512), max(int(t0*sr/512)+1, int(t1*sr/512))
    spec = S[:, a:b].mean(1)
    out = {}
    for m in range(50, 86):
        f = 440*2**((m-69)/12); s = 0
        for h in range(1, 7):
            k = int(round(h*f/(sr/4096)))
            if k+1 < len(spec): s += spec[k-1:k+2].max()/h**0.5
        out[m] = s
    return out
mel = json.load(open(WORK+'/song/lead.json'))
lead = {}; b = 0.0
for m, l in mel['notes']:
    if m > 0:
        for k in np.arange(b, b+l, 0.5): lead[round(k*2)/2] = m
    b += l
N=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']; nm=lambda m: f"{N[m%12]}{m//12-1}"
b0, b1 = float(sys.argv[1]), float(sys.argv[2])
row=[]
for k in np.arange(b0, b1, 0.5):
    s = sal(k*BEAT+0.04, (k+0.5)*BEAT-0.02); L = lead.get(k)
    tot = max(s.values())
    cand = {m:v for m,v in s.items() if L is None or (m-L) % 12 not in (0,) and abs(m-L) not in (7,19)}
    # drop pitches explained as the lead's overtones (octave, twelfth) and neighbours of the lead
    cand = {m:v for m,v in cand.items() if L is None or abs(m-L) > 1}
    m2 = max(cand, key=cand.get)
    row.append(f"{k:g}:{nm(L) if L else '--'}+{nm(m2)}({cand[m2]/tot:.2f})")
    if len(row)==8: print('  '.join(row)); row=[]
if row: print('  '.join(row))
