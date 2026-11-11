"""Print band profiles of the torso and upper body. Run: python covers/heads/v1/profile.py"""
import numpy as np, segment
c=segment.comps()
torso=c[3]
print('TORSO core band profile (y_lo y_hi: x[min,max] z[min,max] n)')
for y0 in np.arange(0.87,1.39,0.04):
    b=torso[(torso[:,1]>=y0)&(torso[:,1]<y0+0.04)]
    if len(b): print(f'{y0:.2f}-{y0+0.04:.2f}: x[{b[:,0].min():.3f},{b[:,0].max():.3f}] z[{b[:,2].min():.3f},{b[:,2].max():.3f}] n={len(b)}')
# whole upper body incl shoulders/arms (y>1.0, no head/neck)
body=np.concatenate([c[3],c[4],c[5],c[6],c[7],c[8]])
print('\nUPPER BODY (torso+shoulder+upper arm R) y-band x extent: y x_min x_max')
for y0 in np.arange(1.0,1.40,0.04):
    b=body[(body[:,1]>=y0)&(body[:,1]<y0+0.04)]
    if len(b): print(f'{y0:.2f}-{y0+0.04:.2f}: x[{b[:,0].min():.3f},{b[:,0].max():.3f}] z[{b[:,2].min():.3f},{b[:,2].max():.3f}]')
print('\nback knob (comp4):',c[4].min(0).round(3),c[4].max(0).round(3),'centre',c[4].mean(0).round(3))
print('neck rod (comp2) endpoints: lowest',c[2][c[2][:,1].argmin()].round(3),'highest',c[2][c[2][:,1].argmax()].round(3), 'centroid low-half',c[2][c[2][:,1]<c[2][:,1].mean()].mean(0).round(3),'high-half',c[2][c[2][:,1]>=c[2][:,1].mean()].mean(0).round(3))
rear=c[1]; print('rear joint (comp1) low-half',rear[rear[:,1]<rear[:,1].mean()].mean(0).round(3),'high-half',rear[rear[:,1]>=rear[:,1].mean()].mean(0).round(3))
