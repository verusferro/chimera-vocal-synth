"""Render the mesh with its parts colour coded (head, neck, chest, arm). Run: python covers/heads/v1/parts_render.py"""
import numpy as np, an8, segment, render as R
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
m=an8.parse(segment.f)['obj1']; P=m['P'].copy(); P[:,0]*=-1; P[:,2]*=-1
key={}; idx=np.zeros(len(P),int)
for i,p in enumerate(P): idx[i]=key.setdefault(tuple(np.round(p,4)),len(key))
n=len(key); r=[];c=[]
for fc in m['F']:
    for a,b in zip(fc,fc[1:]+fc[:1]): r.append(idx[a]);c.append(idx[b])
nc,lab=connected_components(coo_matrix((np.ones(len(r)),(r,c)),shape=(n,n)),directed=False)
# component id -> role by bbox
def role(q):
    lo,hi=q.min(0),q.max(0)
    cy=(lo[1]+hi[1])/2
    if lo[1]>1.39 and hi[1]>1.55: return 'head'
    if lo[1]>1.39: return 'neck'
    if lo[1]>1.28 and hi[1]<1.45 and abs(lo[0])<0.05 and hi[0]<0.05: return 'neck'
    if lo[1]>1.0 and cy>1.0 and abs((lo[0]+hi[0])/2)>0.12 and lo[1]>1.0 and hi[1]<1.4: return 'arm'
    if cy>0.86 and hi[1]<1.40 and abs(lo[0])>-1 and (hi[0]-lo[0])>0.2: return 'chest'
    if hi[1]<1.1 and abs((lo[0]+hi[0])/2)>0.12: return 'arm'
    return 'other'
cols={'head':(250,200,60),'neck':(80,220,140),'chest':(90,150,255),'arm':(255,110,150),'other':(120,120,130)}
pts=P
roles={}
for k in range(nc):
    mem=np.where(lab==k)[0]
    if len(mem)==0: continue
    q=np.array([P[i] for i in range(len(P)) if lab[idx[i]]==k])
    roles[k]=role(q) if len(q) else 'other'
tris=[]
for fc in m['F']:
    k=lab[idx[fc[0]]]; col=cols[roles[k]]
    for j in range(1,len(fc)-1): tris.append((P[[fc[0],fc[j],fc[j+1]]],col,roles[k]))
O=R.ROOT+'render/'
for nm,az,el in [('front',0,0),('sideL',90,0),('back',180,0),('q35',35,10)]:
    R.render(tris,az,el,(0,1.37,0),0.80,O+f'parts_{nm}.png',size=700,wire=True)
