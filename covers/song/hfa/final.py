"""Run with vendor/HubertFA/.venv/bin/python.  Two-pass HubertFA: coarse region alignment -> per-line-group cut points -> 5-15 s segment alignment -> words.json"""
import os, sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hfa import *  # also gives WORK and VENDOR
H = f'{WORK}/hfa'
# 1) coarse regions, by hand from the stem's voice activity: WORK/hfa/regions.json holds
#    [[name, start_s, end_s, first_line, last_line + 1], ...] (lines 0-based, in lyrics.txt order)
regions = [(n, a, b, range(l0, l1)) for n, a, b, l0, l1 in json.load(open(f'{H}/regions.json'))]
make_segments(regions, f'{H}/pass1'); run(f'{H}/pass1')
w1 = read(f'{H}/pass1', regions)
# 2) line boundaries from pass 1, snapped to lowest-energy frame within +-0.2 s
y = stem(); rms = librosa.feature.rms(y=y, frame_length=1764, hop_length=441)[0]
def snap(t):
    i0, i1 = int((t-0.2)*100), int((t+0.2)*100)
    return (i0 + int(np.argmin(rms[i0:i1])))/100
segs, table = [], []
for rn, r0, r1, rl in regions:
    rl = list(rl); ln = {l: [w for w in w1 if w['line']==l] for l in rl}
    # cut before each line l>first = snap(mid(end of l-1, start of l))
    cut = {l: snap((ln[l-1][-1]['end']+ln[l][0]['start'])/2) for l in rl[1:]}
    cut[rl[0]] = max(r0, ln[rl[0]][0]['start']-0.25); end = min(r1, ln[rl[-1]][-1]['end']+0.6)
    groups, cur = [], []
    for l in rl:                               # greedy: close a group once it spans >= 6 s
        cur.append(l)
        nxt = cut.get(l+1, end)
        if nxt - cut[cur[0]] >= 6: groups.append(cur); cur = []
    if cur: groups[-1].extend(cur) if groups and (end-cut[cur[0]] < 4) else groups.append(cur)
    for g in groups:
        t0 = cut[g[0]]; t1 = cut.get(g[-1]+1, end)
        segs.append((f'seg{len(segs)+1:02d}', round(t0,2), round(t1,2), g))
make_segments(segs, f'{H}/segments'); run(f'{H}/segments')
w2 = read(f'{H}/segments', segs)
json.dump([{k: w[k] for k in ('word','start','end','phones')} | {'line': w['line']+1, 'seg': w['seg']} for w in w2], open(f'{H}/words.json','w'), indent=1)
# 3) table + agreement check vs pass 1
p1 = {(w['line'], i): w for l in range(len(LINES)) for i, w in enumerate([x for x in w1 if x['line']==l])}
p2 = {(w['line'], i): w for l in range(len(LINES)) for i, w in enumerate([x for x in w2 if x['line']==l])}
rows = []
for n, t0, t1, g in segs:
    keys = [k for k in p2 if k[0] in g]
    d = max(abs(p2[k]['start']-p1[k]['start']) for k in keys) if keys and all(k in p1 for k in keys) else None
    mx = max(p2[k]['end']-p2[k]['start'] for k in keys)
    rows.append({'seg': n, 'start': t0, 'end': t1, 'dur': round(t1-t0,2), 'lines': [l+1 for l in g],
                 'max_pass1_vs_pass2_start_diff_s': None if d is None else round(d,2), 'longest_word_s': round(mx,2)})
json.dump(rows, open(f'{H}/segments.json','w'), indent=1)
for r in rows: print(r)
print(len(w2), 'words')
