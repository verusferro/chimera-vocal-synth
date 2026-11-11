"""Hat ear measurements. Run with the Blender Python: WORK/niko-ref/.venv/bin/python covers/heads/niko/ears.py"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from paths import WORK
REF = f"{WORK}/niko-ref"
bpy.ops.wm.open_mainfile(filepath=f"{REF}/model/Niko (Oneshot) 3D Model v6.0.3/Niko(Oneshot).blend")
dg=bpy.context.evaluated_depsgraph_get()
o=bpy.data.objects["Hat"].evaluated_get(dg); m=o.to_mesh()
vs=[o.matrix_world@v.co for v in m.vertices if (o.matrix_world@v.co).x>0.02]
for z in [1.10,1.13,1.16,1.18,1.20,1.22,1.235]:
    b=[v for v in vs if abs(v.z-z)<0.007]
    if b: print("z=%.3f x[%.3f,%.3f] y[%.3f,%.3f] n=%d"%(z,min(v.x for v in b),max(v.x for v in b),min(v.y for v in b),max(v.y for v in b),len(b)))
# between ears: top at x~0
b=[v for v in vs if v.x<0.04]; print("max z near centre line",round(max(v.z for v in b),3))
