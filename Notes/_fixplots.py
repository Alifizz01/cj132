# -*- coding: utf-8 -*-
"""Fix vertically-inverted data polylines in both chapters' fragments.
Broken helper used sy = Y1-(t)*(Y1-Y0); correct is sy = Y0-(t)*(Y0-Y1).
We reproduce each polyline's OLD string and NEW string and replace in-file."""
import numpy as np, os
base=os.path.dirname(os.path.abspath(__file__))

def S(xs,ys,x0,x1,y0,y1,X0,X1,Y0,Y1,fix):
    out=[]
    for x,y in zip(xs,ys):
        sx=X0+(x-x0)/(x1-x0)*(X1-X0)
        t=(y-y0)/(y1-y0)
        sy=(Y0-t*(Y0-Y1)) if fix else (Y1-t*(Y1-Y0))
        out.append(f"{sx:.1f},{sy:.1f}")
    return " ".join(out)

repl={}  # filename -> list of (old,new)
def add(fn,xs,ys,*args):
    old=S(xs,ys,*args,False); new=S(xs,ys,*args,True)
    repl.setdefault(fn,[]).append((old,new))

# ---- Chapter 1 ----
vt=0.0979; i0=0.5/(np.exp(2.67/vt)-1); V=np.linspace(0,2.67,160)
I=np.clip(0.5-i0*(np.exp(V/vt)-1),0,None); P=V*I
add("_frag_P1.html",V,I,0,2.8,0,0.55,58,420,150,18)
add("_frag_P1.html",V,P,0,2.8,0,1.25,58,420,150,18)
xe=np.linspace(0,1,80); ye=np.exp(3*xe); ye=ye/ye.max()
add("_frag_P2.html",xe,ye,0,1,0,1,55,300,120,18)
dose=np.logspace(13,16,60); r_isc=1-0.06*(np.log10(dose)-13)/3; r_voc=1-0.12*(np.log10(dose)-13)/3
add("_frag_P3.html",np.log10(dose),r_isc,13,16,0.8,1.0,55,250,118,18)
add("_frag_P3.html",np.log10(dose),r_voc,13,16,0.8,1.0,55,250,118,18)
Tc=np.linspace(-120,80,50); voc=2.67-0.006*(Tc-28)
add("_frag_P3.html",Tc,voc,-120,80,2.4,3.4,310,470,118,18)
rng=np.random.default_rng(7); Ns=np.arange(1,400); samp=rng.uniform(1,6,400); run=np.cumsum(samp)/np.arange(1,401)
add("_frag_P8.html",Ns,run[1:],1,400,2.0,5.0,55,440,150,20)
band_u=3.5+2.0/np.sqrt(Ns); band_l=3.5-2.0/np.sqrt(Ns)
add("_frag_P8.html",Ns,band_u,1,400,2.0,5.0,55,440,150,20)
add("_frag_P8.html",Ns,band_l,1,400,2.0,5.0,55,440,150,20)

# ---- Chapter 2 ----
res=[3.96,0.38,0.013,1.5e-5,2e-11]; ly=[np.log10(r) for r in res]; xs=[1,2,3,4,5]
add("_frag_Q2.html",xs,ly,1,5,-11,1,60,400,150,20)
it=np.arange(0,8); failed=187-159*np.exp(-0.6*it); healthy=39-11*np.exp(-0.7*it)
add("_frag_Q3.html",it,failed,0,7,20,200,55,400,150,18)
add("_frag_Q3.html",it,healthy,0,7,20,200,55,400,150,18)
xs2=np.arange(1,8); dmg=1-np.exp(-0.4*xs2)
add("_frag_Q6.html",xs2,dmg,1,7,0,1,250,330,118,80)

total=0; miss=0
for fn,pairs in repl.items():
    p=os.path.join(base,fn); html=open(p,encoding="utf-8").read()
    for old,new in pairs:
        if old in html:
            html=html.replace(old,new,1); total+=1
        else:
            miss+=1; print("MISS in",fn,"->",old[:50])
    open(p,"w",encoding="utf-8").write(html)
print(f"replaced {total} polylines, {miss} misses")
