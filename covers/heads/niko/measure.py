"""Measure the hat, hair, scarf and head. Run: WORK/niko-ref/.venv/bin/python covers/heads/niko/measure.py"""
import bpy, math, json, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from paths import WORK
REF = f"{WORK}/niko-ref"
bpy.ops.wm.open_mainfile(filepath=f"{REF}/model/Niko (Oneshot) 3D Model v6.0.3/Niko(Oneshot).blend")
dg=bpy.context.evaluated_depsgraph_get()
def ev(name):
    o=bpy.data.objects[name].evaluated_get(dg); m=o.to_mesh(); return o,m
def r(x): return round(x,4)
# materials per mesh
for n in ["Head","Hair","Hat","Scarf","Coat"]:
    o,m=ev(n); print("MATS",n,[s.material.name if s.material else None for s in o.material_slots])
# Head faces by material centroid
o,m=ev("Head")
by={}
for p in m.polygons:
    mi=p.material_index; c=o.matrix_world@p.center
    by.setdefault(mi,[]).append(c)
for mi,cs in by.items():
    lo=[min(c[i] for c in cs) for i in range(3)]; hi=[max(c[i] for c in cs) for i in range(3)]
    print("HEADMAT",mi,o.material_slots[mi].material.name if mi<len(o.material_slots) else None,len(cs),[r(x) for x in lo],[r(x) for x in hi])
# Hat profile
o,m=ev("Hat"); vs=[o.matrix_world@v.co for v in m.vertices]
print("HAT z levels (z: xmin xmax ymin ymax)")
zs=sorted(set(round(v.z,2) for v in vs))
import collections
bins=collections.defaultdict(list)
for v in vs: bins[round(v.z/0.01)*0.01].append(v)
for z in sorted(bins):
    b=bins[z]; print(" z=%.2f n=%d x[%.3f,%.3f] y[%.3f,%.3f]"%(z,len(b),min(v.x for v in b),max(v.x for v in b),min(v.y for v in b),max(v.y for v in b)))
top=sorted(vs,key=lambda v:-v.z)[:12]
print("HAT top verts",[(r(v.x),r(v.y),r(v.z)) for v in top])
# brim edge radius vs angle
edge=[v for v in vs if math.hypot(v.x,v.y-0.0)>0.2]
for ang in range(0,360,45):
    a=math.radians(ang); best=max(vs,key=lambda v:(v.x*math.cos(a)+(v.y)*math.sin(a)))
    print(" brim dir %3d (0=+x,90=+y(back)) -> (%.3f,%.3f,%.3f)"%(ang,best.x,best.y,best.z))
# hair
o,m=ev("Hair"); vs=[o.matrix_world@v.co for v in m.vertices]
wh=[v for v in vs if abs(v.x)>0.125]
print("HAIR whisker verts",len(wh),"x",r(min(v.x for v in wh)),r(max(v.x for v in wh)),"z",r(min(v.z for v in wh)),r(max(v.z for v in wh)),"y",r(min(v.y for v in wh)),r(max(v.y for v in wh)))
fr=[v for v in vs if v.y<-0.09]
print("HAIR fringe verts y<-.09: z",r(min(v.z for v in fr)),r(max(v.z for v in fr)),"x",r(min(v.x for v in fr)),r(max(v.x for v in fr)),"ymin",r(min(v.y for v in fr)))
# scarf
o,m=ev("Scarf"); vs=[o.matrix_world@v.co for v in m.vertices]
neck=[v for v in vs if abs(v.x)<0.2 and v.z>0.7]
print("SCARF neck loop n",len(neck),"x",r(min(v.x for v in neck)),r(max(v.x for v in neck)),"y",r(min(v.y for v in neck)),r(max(v.y for v in neck)),"z",r(min(v.z for v in neck)),r(max(v.z for v in neck)))
for z0 in [0.5,0.6,0.7,0.75,0.8,0.85,0.9]:
    b=[v for v in vs if abs(v.z-z0)<0.01 and abs(v.x)<0.25]
    if b: print(" scarf z=%.2f x[%.3f,%.3f] y[%.3f,%.3f] n=%d"%(z0,min(v.x for v in b),max(v.x for v in b),min(v.y for v in b),max(v.y for v in b),len(b)))
ends=[v for v in vs if abs(v.x)>0.25]
print("SCARF ends x",r(min(v.x for v in ends)),r(max(v.x for v in ends)),"z",r(min(v.z for v in ends)),r(max(v.z for v in ends)))
# armature pose: head bone
arm=bpy.data.objects["Niko_rig"]
for b in arm.pose.bones:
    if b.name.lower() in("head","neck","spine.006","head.001") or "head" in b.name.lower()[:6]:
        print("BONE",b.name,[r(x) for x in (arm.matrix_world@b.head)],[r(x) for x in (arm.matrix_world@b.tail)])
