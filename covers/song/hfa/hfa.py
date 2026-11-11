"""Helpers: cut stem chunks -> HubertFA (onnx, en) -> words on full-song clock. Run with the HubertFA venv python (vendor/HubertFA/.venv/bin/python); final.py and spot.py import this."""
import glob, json, os, re, shutil, subprocess, sys, textgrid, soundfile as sf, librosa, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # covers/, for paths.py
from paths import WORK, VENDOR
STEM = glob.glob(f'{WORK}/stems/*(vocals)*')[0]
LINES = [l.strip() for l in open(f'{WORK}/lyrics.txt') if l.strip()]
SR = 44100
_y = None
def stem():
    global _y
    if _y is None: _y = librosa.load(STEM, sr=SR, mono=True)[0]
    return _y
# words the aligner's dictionary lacks, respelled for the alignment only (one word for one word):
# WORK/hfa/respell.json, e.g. {"rumba": "rumble"}; the shown and sung words stay as written
RESPELL = json.load(open(f'{WORK}/hfa/respell.json')) if os.path.exists(f'{WORK}/hfa/respell.json') else {}
def lab(line):
    t = re.sub(r"[^a-z' ]", ' ', line.lower().replace("pain's", 'pains'))
    return ' '.join(RESPELL.get(w, w) for w in t.split())
def toks(line):  # original-case tokens aligned 1:1 with lab(line) tokens
    return [re.sub(r"[^A-Za-z']", '', w) for w in re.sub(r"[^A-Za-z' ]", ' ', line).split()]
def make_segments(segs, folder):
    """segs: list of (name, t0, t1, [line indices]) -> wav+lab in folder"""
    shutil.rmtree(folder, ignore_errors=True); os.makedirs(folder)
    y = stem()
    for name, t0, t1, ls in segs:
        sf.write(f'{folder}/{name}.wav', y[int(t0*SR):int(t1*SR)], SR)
        open(f'{folder}/{name}.lab', 'w').write(' '.join(lab(LINES[i]) for i in ls))
def run(folder, threads='0-2'):
    env = dict(os.environ, OMP_NUM_THREADS='3')
    subprocess.run(['taskset', '-c', threads, sys.executable, 'onnx_infer.py', '-m',
        'models/1218_hfa_model_new_dict/model.onnx', '-wf', folder, '-l', 'en'], cwd=f'{VENDOR}/HubertFA', env=env, check=True)
def read(folder, segs):
    """-> list of words {word,start,end,phones,line,seg} full-song seconds"""
    out = []
    for name, t0, t1, ls in segs:
        tg = textgrid.TextGrid.fromFile(f'{folder}/TextGrid/{name}.TextGrid')
        wt = next(t for t in tg if t.name == 'words'); pt = next(t for t in tg if t.name == 'phones')
        ws = [i for i in wt if i.mark not in ('SP', 'AP', 'EP', '')]
        orig = [(li, w) for li in ls for w in toks(LINES[li])]
        assert len(ws) == len(orig), (name, len(ws), len(orig))
        for iv, (li, w) in zip(ws, orig):
            ph = [{'ph': p.mark, 'start': round(t0+p.minTime, 3), 'end': round(t0+p.maxTime, 3)}
                  for p in pt if p.minTime >= iv.minTime-1e-6 and p.maxTime <= iv.maxTime+1e-6 and p.mark not in ('SP',)]
            out.append({'word': w, 'start': round(t0+iv.minTime, 3), 'end': round(t0+iv.maxTime, 3), 'phones': ph, 'line': li, 'seg': name})
    return out
