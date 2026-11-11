"""Print the head's size by height band, in head widths, and save its vertices. Run: python covers/heads/v1/dump.py"""
import sys,json,math
import numpy as np, segment, an8
c=segment.comps(); head=c[0]
W=0.171
shell=head[head[:,1]>1.47]
th=math.atan2(-0.097,0.995)
def loc(P):
    cs,sn=math.cos(-th),math.sin(-th); Q=P.copy(); Q[:,1]=P[:,1]*cs-P[:,2]*sn; Q[:,2]=P[:,1]*sn+P[:,2]*cs; return Q
L=loc(head); y0=L[:,1].min(); H=L[:,1].max()-y0
print('local-frame head (all incl chin): height',round(H,4),'z',L[:,2].min().round(4),L[:,2].max().round(4))
print('u = fraction of local height above lowest point; x half-width; z range (z0=back)')
z0=L[:,2].min()
for u in np.arange(0,1.0,0.1):
    b=L[(L[:,1]>=y0+u*H)&(L[:,1]<y0+(u+0.1)*H)]
    if len(b): print(f' u={u:.1f}-{u+0.1:.1f}: halfx {np.abs(b[:,0]).max():.3f} ({np.abs(b[:,0]).max()/W*2:.2f} W)  z {b[:,2].min()-z0:.3f}..{b[:,2].max()-z0:.3f}  n={len(b)}')
json.dump({'head_vertices_world_xyz':np.round(head,4).tolist(),'frame':'x right(viewer at +z), y up, z front; metres; feet y=0'},open(an8.V1REF+'/head_vertices.json','w'))
