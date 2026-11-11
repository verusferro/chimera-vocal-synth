"""Software ortho renderer for the an8 V1 mesh. Frame after load: x right (viewer at +z sees +x right), y up, z toward front."""
import sys, math, numpy as np
from PIL import Image, ImageDraw
import an8
ROOT=an8.V1REF+'/'
AN8=an8.AN8
TEX=Image.open(an8.TEXDIR+'/v1colour_tex.png').convert('RGB')
WTEX=Image.open(an8.TEXDIR+'/v1_wingcolour_tex.png').convert('RGB')
def load(wings=True,arm=True):
    out=[]
    objs=[('v1-ultrakill',None)]+([('feedbacker',None)] if arm else [])
    for obj,_ in objs:
        ms=an8.parse(AN8,obj)
        for name,m in ms.items():
            if obj=='v1-ultrakill' and name!='obj1' and not wings: continue
            P=m['P'].copy(); P[:,0]*=-1; P[:,2]*=-1   # base orientation = 180deg about Y; front now +z, viewer at +z sees +x on the right
            tex=WTEX if (obj=='v1-ultrakill' and name!='obj1') else TEX
            UV=m['UV']; w,h=tex.size
            for f,ft in zip(m['F'],m['FT']):
                for k in range(1,len(f)-1):
                    tri=[f[0],f[k],f[k+1]]; tt=[ft[0],ft[k],ft[k+1]]
                    uv=UV[tt].mean(0) if UV is not None else (0,0)
                    c=tex.getpixel((min(int((uv[0]%1)*w),w-1),min(int((1-(uv[1]%1))*h),h-1)))
                    c=tuple(int(255*(ch/255)**0.7) for ch in c)
                    out.append((P[tri],c,obj+'/'+name))
    return out
FLIP=-1
def tris_arrays(tris):
    V=np.array([t[0] for t in tris]); C=np.array([t[1] for t in tris]); return V,C
def render(tris,az,el,center,scale,path,size=700,wire=True,fill=True,bg=(14,16,24),cull=True,wcol=(0,0,0)):
    """az: 0 front (camera on +z), 90 = camera on +x (sees character's left side... see brief), 180 back. el deg."""
    V=np.array([t[0] for t in tris]); C=np.array([t[1] for t in tris])
    a=math.radians(az); e=math.radians(el)
    # camera direction (from target to camera)
    d=np.array([math.sin(a)*math.cos(e), math.sin(e), math.cos(a)*math.cos(e)])
    right=np.cross([0,1,0],d); right/=np.linalg.norm(right)   # world up x d
    up=np.cross(d,right)
    c=np.array(center)
    X=(V-c)@right; Y=(V-c)@up; Z=(V-c)@d
    n=np.cross(V[:,1]-V[:,0],V[:,2]-V[:,0]); nn=np.linalg.norm(n,axis=1,keepdims=True)+1e-12; n=n/nn
    facing=(n@d)
    # light from camera + upper left
    L=d*0.7+up*0.35-right*0.25; L/=np.linalg.norm(L)
    sh=np.clip(np.abs(n@L),0,1)*0.55+0.6
    img=Image.new('RGB',(size,size),bg); dr=ImageDraw.Draw(img)
    s=size/scale
    order=np.argsort(Z.mean(1))
    if cull: order=[i for i in order if facing[i]*FLIP>0]
    for i in order:
        pts=[(size/2+X[i,k]*s,size/2-Y[i,k]*s) for k in range(3)]
        col=tuple(int(min(255,ch*sh[i])) for ch in C[i]) if fill else bg
        dr.polygon(pts,fill=col,outline=(255,255,255) if wire and not fill else None)
    if wire and fill:
        for i in order:
            pts=[(size/2+X[i,k]*s,size/2-Y[i,k]*s) for k in range(3)]
            dr.line(pts+[pts[0]],fill=wcol,width=1)
    img.save(path); return path
if __name__=="__main__":
    tris=load(wings=False)
    render(tris,0,0,(0,1.35,0),1.0,'/tmp/t_front.png')
    render(tris,90,0,(0,1.35,0),1.0,'/tmp/t_side.png')
