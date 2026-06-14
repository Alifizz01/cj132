# -*- coding: utf-8 -*-
"""Compute + plot everything for Chapter 6 (worked-by-hand examples).
Loads the REAL modules by file path (like the tests) so every number in the
notes is exactly what the code produces. Also does the lumped one-node hand
approximations and Newton/coupling traces, and renders PNG figures.
Run from the Notes/ folder (neutral cwd) so imports/matplotlib work.
"""
import importlib.util, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "..", "src", "powerpy")

def load(m):
    spec = importlib.util.spec_from_file_location(m, os.path.join(PKG, m + ".py"))
    mod = importlib.util.module_from_spec(spec); sys.modules[m] = mod
    spec.loader.exec_module(mod); return mod

tv  = load("thermal_vectorized")
sub = load("substrate")
et  = load("electrothermal")
bd  = load("breakdown")
env = load("environment_orbit")
mc  = load("montecarlo")

S = sub.load_substrate("msro_case2")
SIG = tv.SIGMA; TSP = tv.T_SPACE; A = 0.003; PSUN = 1367.0
print("=== substrate ===")
print("aF,aR,eF,eR,cond,thick,c_cond =", S.alpha_front,S.alpha_rear,S.epsilon_front,S.epsilon_rear,
      S.conductivity,S.thickness,S.c_cond)

# absorbed front heat
qF = S.alpha_front*A*PSUN
print("q_front = aF*A*Psun =", qF)
# lumped radiative coefficient (front+rear)
klump = (S.epsilon_front+S.epsilon_rear)*A*SIG
print("k_lump = (eF+eR)*A*sigma =", klump)

def lumpedT(Pe):
    # absorbed - extracted = radiated:  qF - Pe = klump*T^4  (ignore tiny Tsp^4)
    T4 = (qF - Pe)/klump
    return T4**0.25 - 273.15

print("\n=== lumped one-node hand answers (degC) ===")
for Pe,label in [(0.0,"idle"),(1.1,"healthy +1.1W"),(2.0,"powered +2W"),(-9.6,"reverse -9.6W")]:
    print(f"  Pe={Pe:+6.1f} ({label:14s}) -> {lumpedT(Pe):8.2f} C")

print("\n=== exact two-node solver (the code) ===")
for Pe in [0.0,1.1,2.0,-9.6]:
    r = tv.solve_thermal_for_substrate(S, area=A, p_sun=PSUN, p_albedo=0.0, p_ir=0.0, p_elec=Pe)
    print(f"  Pe={Pe:+6.1f} -> front {float(r.t_front_c[0]):8.3f}  rear {float(r.t_rear_c[0]):8.3f}  iters {r.iterations}")

# 4-cell array (the test)
arr = np.array([1.1,1.1,0.0,-9.6])
r4 = tv.solve_thermal_for_substrate(S, area=A, p_sun=PSUN, p_albedo=0.0, p_ir=0.0, p_elec=arr)
print("  4-cell front:", np.round(np.asarray(r4.t_front_c),2))

# ---- Newton trace, lumped reverse-bias case, by hand-able -------------------
print("\n=== Newton trace (lumped reverse-bias Pe=-9.6), start 28C ===")
Pe=-9.6
f  = lambda T: (qF - Pe) - klump*T**4         # T in kelvin
fp = lambda T: -4*klump*T**3
T = 28+273.15
trace=[T]
for i in range(8):
    fv=f(T); fpv=fp(T);
    print(f"  it {i}: T={T-273.15:8.3f}C  f={fv:10.5f}W  f'={fpv:.3e}  ->next")
    Tn = T - fv/fpv
    trace.append(Tn)
    if abs(Tn-T)<1e-6: T=Tn; break
    T=Tn
print(f"  converged T = {T-273.15:.3f} C")
newton_trace=[t-273.15 for t in trace]

# ---- electro-thermal coupling bounce ---------------------------------------
print("\n=== electro-thermal coupling bounce ===")
# a partially-shaded cell DISSIPATING power that grows a little as it heats
# (Pe<0 = heat in); positive feedback, so it climbs to a hot fixed point.
def power_fn(Tfront):
    Tf=np.asarray(Tfront,dtype=float)
    return -(8.0 + 0.02*(Tf-50.0))       # ~-8 W, slightly more when hotter
# replicate the damped outer loop and record T each round
omega=0.5; T=np.array([28.0]); bounce=[float(T[0])]
for it in range(1,40):
    Pe=power_fn(T)
    res=tv.solve_thermal_for_substrate(S, area=A, p_sun=PSUN, p_albedo=0.0, p_ir=0.0, p_elec=Pe)
    tnew=np.asarray(res.t_front_c,dtype=float)
    step=omega*(tnew-T); T=T+step
    bounce.append(float(T[0]))
    if abs(float(step[0]))<1e-3: break
print("  bounce T per round:", [round(x,3) for x in bounce])
print("  settled:", round(bounce[-1],3),"C  rounds:",len(bounce)-1)
# also the full-jump (omega=1) to show oscillation contrast
T=np.array([28.0]); bounce1=[float(T[0])]
for it in range(1,12):
    Pe=power_fn(T); res=tv.solve_thermal_for_substrate(S,area=A,p_sun=PSUN,p_albedo=0,p_ir=0,p_elec=Pe)
    T=np.asarray(res.t_front_c,dtype=float); bounce1.append(float(T[0]))
print("  full-jump (omega=1):", [round(x,2) for x in bounce1[:8]])

# ---- breakdown -------------------------------------------------------------
print("\n=== breakdown ===")
rep=bd.evaluate_breakdown(t_front_c=[65.26,187.48], v=[2.3,-20.0], i=[0.48,0.48], t_limit_c=150.0, p_rev_limit_w=2.0)
print("  destroyed:",rep.destroyed.tolist()," p_rev:",rep.reverse_power_w.tolist())

# ---- fluxes ----------------------------------------------------------------
print("\n=== fluxes ===")
print("  sun@1AU   :",env.solar_irradiance(1.0))
print("  sun@1.52  :",round(env.solar_irradiance(1.52),2))
print("  albedo    :",env.albedo_flux(0.25,591.0,0.3))
print("  IR@255K   :",round(env.planetary_ir_flux(255.0,1.0,0.3),3))
print("  tilt30    :",round(env.cosine_tilt(30,0),4))

# ---- monte carlo -----------------------------------------------------------
print("\n=== monte carlo ===")
print("  SE([0,2]) :",mc.standard_error([0,2]))
print("  runs_needed(8,100,2):",mc.runs_needed(8.0,100,2.0))

# ============================================================ PLOTS
NAVY="#0b3d63"; AMBER="#b9851a"; BRICK="#9a3b3b"; TEAL="#2f8f6b"; MUT="#5d6b79"
plt.rcParams.update({"font.size":11,"axes.edgecolor":"#9aa7b3","axes.labelcolor":"#1d2733",
                     "xtick.color":MUT,"ytick.color":MUT,"font.family":"DejaVu Sans"})

# Fig A: absorbed vs radiated, three intersections
Tc=np.linspace(-40,260,400); Tk=Tc+273.15
rad=klump*Tk**4
fig,ax=plt.subplots(figsize=(6.6,4.0))
ax.plot(Tc,rad,color=NAVY,lw=2.4,label="heat radiated away  ∝ T⁴")
for Pe,c,lab in [(0.0,TEAL,"idle: absorb 3.98 W → 65°C"),
                 (1.1,AMBER,"healthy: 3.98−1.1=2.88 W → 39°C"),
                 (-9.6,BRICK,"reverse: 3.98+9.6=13.58 W → 187°C")]:
    lvl=qF-Pe
    ax.axhline(lvl,color=c,ls="--",lw=1.3)
    Tsol=lumpedT(Pe)
    ax.plot([Tsol],[lvl],"o",color=c,ms=8)
    ax.annotate(lab,(Tsol,lvl),textcoords="offset points",xytext=(8,-14 if Pe>0 else 8),
                fontsize=8.5,color=c)
ax.set_xlabel("cell temperature  (°C)"); ax.set_ylabel("heat per second  (W)")
ax.set_title("Balance = where heat-in line meets the T⁴ glow curve",color=NAVY,fontsize=11)
ax.set_ylim(0,16); ax.grid(True,color="#eef0ec"); ax.legend(loc="upper left",fontsize=8.5,frameon=False)
fig.tight_layout(); fig.savefig("fig_ch6_balance.png",dpi=200); plt.close(fig)

# Fig B: f(T) crossing zero with Newton steps (reverse case)
fig,ax=plt.subplots(figsize=(6.6,3.8))
Tc2=np.linspace(0,260,400); Tk2=Tc2+273.15
ax.plot(Tc2,(qF+9.6)-klump*Tk2**4,color=NAVY,lw=2.2)
ax.axhline(0,color=BRICK,ls="--",lw=1.2)
for i,Tc_i in enumerate(newton_trace[:5]):
    fv=(qF+9.6)-klump*(Tc_i+273.15)**4
    ax.plot([Tc_i],[fv],"o",color=AMBER,ms=7)
    ax.annotate(f"x{i}",(Tc_i,fv),textcoords="offset points",xytext=(4,6),fontsize=8,color=AMBER)
ax.set_xlabel("guess temperature (°C)"); ax.set_ylabel("net heat  f(T)  (W)")
ax.set_title("Newton: drive net heat f(T)=0  (reverse-bias case → 186°C)",color=NAVY,fontsize=11)
ax.grid(True,color="#eef0ec"); fig.tight_layout(); fig.savefig("fig_ch6_newton.png",dpi=200); plt.close(fig)

# Fig C: Newton convergence (T vs iteration)
fig,ax=plt.subplots(figsize=(6.0,3.4))
ax.plot(range(len(newton_trace)),newton_trace,"o-",color=NAVY,lw=2)
ax.axhline(newton_trace[-1],color=TEAL,ls="--",lw=1.2,label=f"answer {newton_trace[-1]:.1f}°C")
ax.set_xlabel("Newton iteration"); ax.set_ylabel("temperature (°C)")
ax.set_title("Correct digits roughly double each step",color=NAVY,fontsize=11)
ax.grid(True,color="#eef0ec"); ax.legend(frameon=False,fontsize=9)
fig.tight_layout(); fig.savefig("fig_ch6_newtonconv.png",dpi=200); plt.close(fig)

# Fig D: coupling bounce damped vs full-jump
fig,ax=plt.subplots(figsize=(6.4,3.6))
ax.plot(range(len(bounce)),bounce,"o-",color=TEAL,lw=2,label="damped (ω=0.5) — settles")
ax.plot(range(len(bounce1)),bounce1,"s--",color=BRICK,lw=1.6,label="full jump (ω=1) — overshoots/oscillates")
ax.axhline(bounce[-1],color=NAVY,ls=":",lw=1.2)
ax.set_xlabel("outer round"); ax.set_ylabel("front temperature (°C)")
ax.set_title("The electro-thermal bounce converging",color=NAVY,fontsize=11)
ax.grid(True,color="#eef0ec"); ax.legend(frameon=False,fontsize=9)
fig.tight_layout(); fig.savefig("fig_ch6_bounce.png",dpi=200); plt.close(fig)

# Fig E: 4-cell array bar
fig,ax=plt.subplots(figsize=(6.0,3.4))
front=np.asarray(r4.t_front_c)
cols=[TEAL,TEAL,NAVY,BRICK]; labels=["healthy\n+1.1W","healthy\n+1.1W","idle\n0W","reverse\n−9.6W"]
ax.bar(range(4),front,color=cols)
for i,v in enumerate(front): ax.text(i,v+4,f"{v:.1f}°C",ha="center",fontsize=9,color="#1d2733")
ax.set_xticks(range(4)); ax.set_xticklabels(labels,fontsize=8.5)
ax.set_ylabel("front temperature (°C)"); ax.set_ylim(0,210)
ax.set_title("One vectorised solve, four cells at once",color=NAVY,fontsize=11)
ax.grid(True,axis="y",color="#eef0ec"); fig.tight_layout(); fig.savefig("fig_ch6_array.png",dpi=200); plt.close(fig)

# Fig F: T^4 law
fig,ax=plt.subplots(figsize=(5.8,3.2))
Tk3=np.linspace(200,500,300)
ax.plot(Tk3-273.15,SIG*Tk3**4,color=NAVY,lw=2.2)
ax.set_xlabel("temperature (°C)"); ax.set_ylabel("glow per m²  σT⁴  (W/m²)")
ax.set_title("Stefan–Boltzmann: glow rises with the 4th power",color=NAVY,fontsize=11)
ax.grid(True,color="#eef0ec"); fig.tight_layout(); fig.savefig("fig_ch6_t4.png",dpi=200); plt.close(fig)

# Fig G: Monte-Carlo 1/sqrt(N)
fig,ax=plt.subplots(figsize=(5.8,3.2))
Ns=np.arange(10,2001)
ax.plot(Ns,8.0/np.sqrt(Ns),color=NAVY,lw=2)
ax.axhline(2.0,color=BRICK,ls="--",lw=1.2,label="target 2°C")
ax.axvline(1600,color=TEAL,ls=":",lw=1.2,label="N=1600")
ax.set_xlabel("number of Monte-Carlo runs  N"); ax.set_ylabel("wobble (standard error, °C)")
ax.set_title("Accuracy improves like 1/√N",color=NAVY,fontsize=11)
ax.grid(True,color="#eef0ec"); ax.legend(frameon=False,fontsize=9)
fig.tight_layout(); fig.savefig("fig_ch6_mc.png",dpi=200); plt.close(fig)

print("\nALL FIGURES WRITTEN")
