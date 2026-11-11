"""Find the yellow (lens and chest light) faces by sampling the texture. Run: python covers/heads/v1/yellow.py"""
import an8, numpy as np
from PIL import Image
f=an8.AN8
TEX=np.array(Image.open(an8.TEXDIR+'/v1colour_tex.png').convert('RGB')).astype(int)
h,w,_=TEX.shape; print('tex',w,h)
m=an8.parse(f)['obj1']; P=m['P'].copy(); P[:,0]*=-1; P[:,2]*=-1; UV=m['UV']
bary=[(a/20,b/20,1-a/20-b/20) for a in range(21) for b in range(21-a)]
res={}
for fc,ft in zip(m['F'],m['FT']):
    tri=P[fc[:3]]; uv=UV[ft[:3]]
    cnt=0
    for (a,b,c) in bary:
        u,v=(a*uv[0]+b*uv[1]+c*uv[2]); px=TEX[min(int((1-(v%1))*h),h-1),min(int((u%1)*w),w-1)]
        if px[0]>170 and px[1]>110 and px[2]<110: cnt+=1   # yellow
    if cnt>=6: res.setdefault('yellow',[]).append(tri)
Y=res.get('yellow',[])
print(len(Y))
V=np.concatenate(Y); 
# cluster by region
for name,sel in [('chest y>1.0&<1.40',(V[:,1]>1.0)&(V[:,1]<1.40)),('head y>1.40',V[:,1]>1.40),('other',V[:,1]<=1.0)]:
    q=V[sel]
    if len(q): print(name,len(q),q.min(0).round(3),q.max(0).round(3))
# split chest light by x sign
q=V[(V[:,1]>1.0)&(V[:,1]<1.40)]
for s,nm in [(q[:,0]<0,'x<0 (viewer-left)'),(q[:,0]>0,'x>0 (viewer-right)')]:
    z=q[s]
    if len(z): print(nm,len(z),z.min(0).round(3),z.max(0).round(3))
