import os, sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hfa import *  # run with vendor/HubertFA/.venv/bin/python
ws=json.load(open(f'{WORK}/hfa/words.json'))
y=stem(); on=librosa.onset.onset_detect(y=y,sr=SR,hop_length=441,units='time',backtrack=False)
rms=librosa.feature.rms(y=y,frame_length=1764,hop_length=441)[0]; db=20*np.log10(rms+1e-9)
for w in ws:
    if (w['line'],w['word']) in [(1,'night'),(12,'fun'),(40,'day'),(45,'switch'),(36,'wheel')]:
        t=w['start']; o=on[np.argmin(abs(on-t))]
        e=lambda x: db[int(x*100)]
        print(f"L{w['line']} {w['word']} start {t:.2f} end {w['end']:.2f}; nearest onset {o:.2f} (d={o-t:+.2f}); dB at -0.15/0/+0.15/end: {e(t-.15):.0f}/{e(t):.0f}/{e(t+.15):.0f}/{e(w['end']):.0f}")
