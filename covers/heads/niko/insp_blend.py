"""List the objects in the Niko .blend. Run: WORK/niko-ref/.venv/bin/python covers/heads/niko/insp_blend.py"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from paths import WORK
REF = f"{WORK}/niko-ref"
bpy.ops.wm.open_mainfile(filepath=f"{REF}/model/Niko (Oneshot) 3D Model v6.0.3/Niko(Oneshot).blend")
from mathutils import Vector
for o in bpy.data.objects:
    if o.type in ("MESH","ARMATURE","EMPTY","CURVE"):
        bb=[o.matrix_world@Vector(c) for c in o.bound_box] if o.type=="MESH" else []
        lo=[min(v[i] for v in bb) for i in range(3)] if bb else None
        hi=[max(v[i] for v in bb) for i in range(3)] if bb else None
        print(o.type,o.name,"parent=",o.parent.name if o.parent else None,"verts=",len(o.data.vertices) if o.type=="MESH" else "", "hide=",o.hide_viewport,o.hide_render, "lo=",[round(x,3) for x in lo] if lo else "", "hi=",[round(x,3) for x in hi] if hi else "")
print(bpy.app.version_string, bpy.context.scene.render.engine)
