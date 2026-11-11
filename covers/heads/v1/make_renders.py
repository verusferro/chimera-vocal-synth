"""Render the V1 mesh to PNGs in WORK/v1-ref/render. Run: python covers/heads/v1/make_renders.py"""
import render as R
O=R.ROOT+'render/'
body=R.load(wings=False)
allw=R.load(wings=True)
UP=(0,1.37,0)   # head+upper torso centre
for nm,az,el in [('front',0,0),('back',180,0),('sideL',90,0),('sideR',-90,0),('q35',35,8),('qm35',-35,8),('q145',145,8),('top',0,89)]:
    R.render(body,az,el,UP,0.80,O+f'upper_{nm}.png',size=700)
    R.render(body,az,el,UP,0.80,O+f'upperwire_{nm}.png',size=700,fill=False,wire=True,bg=(8,10,16))
HEAD=(0,1.50,0)
for nm,az,el in [('front',0,0),('back',180,0),('sideL',90,0),('sideR',-90,0),('q35',35,10),('qm35',-35,10),('top',0,89),('bottom',0,-89)]:
    R.render(body,az,el,HEAD,0.34,O+f'head_{nm}.png',size=600)
    R.render(body,az,el,HEAD,0.34,O+f'headwire_{nm}.png',size=600,fill=False,wire=True,bg=(8,10,16))
for nm,az in [('front',0),('side',90),('back',180),('q35',35)]:
    R.render(allw,az,0,(0,0.9,0),2.0,O+f'full_{nm}.png',size=800)
