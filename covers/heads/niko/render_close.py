"""Close-up renders (hat on and off) into WORK/niko-ref/render. Run: WORK/niko-ref/.venv/bin/python covers/heads/niko/render_close.py"""
import bpy, math, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from paths import WORK
REF = f"{WORK}/niko-ref"
bpy.ops.wm.open_mainfile(filepath=f"{REF}/model/Niko (Oneshot) 3D Model v6.0.3/Niko(Oneshot).blend")
sc=bpy.context.scene
dg=bpy.context.evaluated_depsgraph_get()
def wbb(name):
    o=bpy.data.objects[name].evaluated_get(dg)
    m=o.to_mesh()
    vs=[o.matrix_world@v.co for v in m.vertices]
    lo=[min(v[i] for v in vs) for i in range(3)]; hi=[max(v[i] for v in vs) for i in range(3)]
    return lo,hi,len(vs)
for n in ["Head","Hair","Hat","Scarf","Coat"]:
    lo,hi,c=wbb(n); print("EVAL",n,c,[round(x,4) for x in lo],[round(x,4) for x in hi])
# hide everything but niko, set up render
for o in bpy.data.objects:
    if o.type=="MESH" and o.parent is None: o.hide_render=True; o.hide_viewport=True
for o in list(bpy.data.objects):
    if o.type=="LIGHT": bpy.data.objects.remove(o)
sc.render.engine=sys.argv[-1] if sys.argv[-1] in("BLENDER_WORKBENCH","BLENDER_EEVEE","CYCLES") else "BLENDER_WORKBENCH"
print("engine",sc.render.engine)
sh=sc.display.shading
sh.light="FLAT"; sh.color_type="TEXTURE"
sc.display.render_aa="8"
sc.render.film_transparent=False
w=bpy.data.worlds[0] if bpy.data.worlds else bpy.data.worlds.new("w")
sc.world=w; w.color=(0.05,0.05,0.07)
sc.render.resolution_x=600; sc.render.resolution_y=600
cam=bpy.data.cameras.new("c"); cam.type="ORTHO"
co=bpy.data.objects.new("c",cam); sc.collection.objects.link(co); sc.camera=co
def shot(name,center,scale,az,el=0.0):
    cam.ortho_scale=scale
    d=3.0
    # az: 0 = camera at -Y looking +Y; positive rotates camera toward +X (right side of image's subject = -X?)
    p=Vector((center[0]+d*math.sin(az)*math.cos(el), center[1]-d*math.cos(az)*math.cos(el), center[2]+d*math.sin(el)))
    co.location=p
    direction=Vector(center)-p
    co.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=f"{REF}/render/{name}.png"
    bpy.ops.render.render(write_still=True)
H=(0,0,1.0)
for hide in ("Hat",):
    bpy.data.objects[hide].hide_render=True
for az,nm in [(0,"front"),(math.pi/2,"sideX"),(math.radians(40),"q40")]:
    shot("noHat_"+nm,(0,0,1.0),0.42,az)
bpy.data.objects["Hat"].hide_render=False
for az,nm in [(0,"front"),(math.pi/2,"sideX"),(math.radians(-90+180),"x")]:
    shot("hat_"+nm,(0,0,1.1),0.7,az)
