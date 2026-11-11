"""Parse meshes out of an Anim8or .an8 (text) file. Reference only."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from paths import WORK
# reference data: the GameBanana 5430 pack, downloaded by you (see covers/docs/wireframe-heads.md)
V1REF = f"{WORK}/v1-ref"
PACK = f"{V1REF}/model/gb5430/v1_v2_255/v1_v2_"
AN8 = f"{PACK}/v1_v2.an8"
TEXDIR = f"{PACK}/textures/v1"
import re, numpy as np
def parse(path, obj="v1-ultrakill"):
    t=open(path,encoding='latin1').read()
    i=t.index('object { "%s"'%obj); j=t.index('\nobject {',i+10) if '\nobject {' in t[i+10:] else t.index('\nfigure {',i)
    seg=t[i:j]
    meshes={}
    for m in re.finditer(r'mesh \{\s*name \{ "([^"]+)" \}',seg):
        s=m.start(); e=seg.find('\n  mesh {',s+10); body=seg[s:(e if e>0 else len(seg))]
        pts=re.search(r'points \{(.*?)\n    \}',body,re.S).group(1)
        P=np.array([[float(x) for x in g] for g in re.findall(r'\(([-\d.e]+) ([-\d.e]+) ([-\d.e]+)\)',pts)])
        tc=re.search(r'texcoords \{(.*?)\n    \}',body,re.S)
        UV=np.array([[float(x) for x in g] for g in re.findall(r'\(([-\d.e]+) ([-\d.e]+)\)',tc.group(1))]) if tc else None
        fs=re.search(r'faces \{(.*?)\n    \}',body,re.S).group(1)
        F=[];FT=[];MI=[]
        for l in fs.strip().splitlines():
            h=re.match(r'\s*(\d+) (\d+) (\d+) (-?\d+) \((.*)\)',l)
            if not h: continue
            vs=re.findall(r'\((\d+) (\d+)\)',h.group(5))
            F.append([int(a) for a,b in vs]); FT.append([int(b) for a,b in vs])
        base=re.search(r'origin \{ \(([-\d. ]+)\) \}\s*orientation \{ \(([-\d. ]+)\) \}',body)
        meshes[m.group(1)]=dict(P=P,UV=UV,F=F,FT=FT,
            origin=[float(x) for x in base.group(1).split()] if base else None,
            orient=[float(x) for x in base.group(2).split()] if base else None)
    return meshes
if __name__=="__main__":
    import sys
    ms=parse(sys.argv[1])
    for k,v in ms.items(): print(k,len(v['P']),len(v['F']),v['origin'],v['orient'],v['P'].min(0).round(3),v['P'].max(0).round(3))
