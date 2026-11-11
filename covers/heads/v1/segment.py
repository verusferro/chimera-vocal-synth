"""Split the V1 body mesh into connected components (head, neck rod, torso ...). Run: python covers/heads/v1/segment.py"""
import an8, numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
f=an8.AN8
def comps(obj='v1-ultrakill',name='obj1'):
    m=an8.parse(f,obj)[name]; P=m['P'].copy(); P[:,0]*=-1; P[:,2]*=-1
    key={}; idx=np.zeros(len(P),int)
    for i,p in enumerate(P): idx[i]=key.setdefault(tuple(np.round(p,4)),len(key))
    n=len(key); r=[];c=[]
    for fc in m['F']:
        for a,b in zip(fc,fc[1:]+fc[:1]): r.append(idx[a]);c.append(idx[b])
    nc,lab=connected_components(coo_matrix((np.ones(len(r)),(r,c)),shape=(n,n)),directed=False)
    Pw=np.zeros((n,3))
    for i,p in enumerate(P): Pw[idx[i]]=p
    used=sorted(set(idx[v] for fc in m['F'] for v in fc))
    out=[]
    for k in range(nc):
        mem=[i for i in used if lab[i]==k]
        if mem: out.append(Pw[mem])
    return sorted(out,key=lambda q:-q[:,1].max())
if __name__=="__main__":
    for q in comps(): print(len(q),'min',q.min(0).round(3),'max',q.max(0).round(3),'size',(q.max(0)-q.min(0)).round(3))
