"""Measure the V1 head, lens and chest lights. Run: python covers/heads/v1/measure.py"""
import sys, math, json
import numpy as np, segment, render as R
comps=segment.comps()
head=comps[0]
print('HEAD verts',len(head),'bbox',head.min(0).round(4),head.max(0).round(4),'size',(head.max(0)-head.min(0)).round(4))
# lens: yellow/orange faces
tris=R.load(wings=False,arm=False)
ly=[t for t in tris if t[0][:,1].min()>1.40 and t[1][0]>150 and t[1][2]<90 and t[1][1]>60]
print('lens faces',len(ly))
if ly:
    V=np.concatenate([t[0] for t in ly]); print('lens verts bbox',V.min(0).round(4),V.max(0).round(4),'centroid',V.mean(0).round(4))
    N=np.mean([np.cross(t[0][1]-t[0][0],t[0][2]-t[0][0])/np.linalg.norm(np.cross(t[0][1]-t[0][0],t[0][2]-t[0][0])) for t in ly],0)
    print('lens normal (avg, unflipped)',N.round(3))
# PCA of head
c=head.mean(0); u,s,vt=np.linalg.svd(head-c); print('PCA axes',vt.round(3),'std',s/np.sqrt(len(head)))
# slice profile of head: for y bands, x extent, z extent
print('HEAD y-band profile: y_lo y_hi  x[min,max]  z[min,max]')
for y0 in np.arange(1.395,1.598,0.02):
    b=head[(head[:,1]>=y0)&(head[:,1]<y0+0.02)]
    if len(b): print(round(y0,3),round(y0+0.02,3),b[:,0].min().round(3),b[:,0].max().round(3),b[:,2].min().round(3),b[:,2].max().round(3),len(b))

print('\n--- head local frame (pitch) ---')
shell=head[head[:,1]>1.47]
c=shell.mean(0); u,s,vt=np.linalg.svd(shell-c)
ax=vt[0]*np.sign(vt[0][2]); print('shell long axis',ax.round(3),'pitch deg',math.degrees(math.atan2(-ax[1],ax[2])).__round__(1),'(neg = front low)')
th=math.atan2(ax[1],ax[2])   # rotate about X so long axis -> z
cs,sn=math.cos(-th),math.sin(-th)
def loc(P): 
    Q=P.copy(); Q[:,1]=P[:,1]*cs - P[:,2]*sn; Q[:,2]=P[:,1]*sn + P[:,2]*cs; return Q
L=loc(head); Ls=loc(shell)
print('shell local bbox min',Ls.min(0).round(4),'max',Ls.max(0).round(4),'size',(Ls.max(0)-Ls.min(0)).round(4))
print('all-head local bbox size',(L.max(0)-L.min(0)).round(4))
# torso & others by named components
names=['head shell','rear neck joint','neck rod','torso core','chest-front lower block?','R shoulder/upper arm','R forearm','pelvis']
for i,q in enumerate(comps[:9]): print(i,len(q),'min',q.min(0).round(3),'max',q.max(0).round(3))
# yellow chest lights
ty=[t for t in tris if 1.0<t[0][:,1].mean()<1.45 and t[1][0]>180 and t[1][1]>140 and t[1][2]<100]
print('chest-light faces',len(ty))
if ty:
    V=np.concatenate([t[0] for t in ty]); print('chest light bbox',V.min(0).round(3),V.max(0).round(3))
