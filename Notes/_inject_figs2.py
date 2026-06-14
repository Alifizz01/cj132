# -*- coding: utf-8 -*-
"""Inline-SVG figures for Chapter 2; inject into _frag_Q*.html in placeholder order."""
import re, numpy as np, os
NAVY="#0b3d63"; NAVY2="#11507a"; AMBER="#c9a227"; AMBER2="#b9851a"
BRICK="#9a3b3b"; TEAL="#1f6a6a"; INK="#1d2733"; MUT="#5d6b79"; RULE="#cfd7df"
FS='font-family="Segoe UI,Arial,sans-serif"'
def fig(svg,cap): return '<figure class="fig-frame">\n'+svg+'\n<figcaption>'+cap+'</figcaption></figure>'
def mappts(xs,ys,x0,x1,y0,y1,X0,X1,Y0,Y1):
    return " ".join(f"{X0+(x-x0)/(x1-x0)*(X1-X0):.1f},{Y1-(y-y0)/(y1-y0)*(Y1-Y0):.1f}" for x,y in zip(xs,ys))

# Q1-1 four-level nesting
Q1_1=f'''<svg width="100%" viewBox="0 0 640 220" xmlns="http://www.w3.org/2000/svg" font-size="11">
<style>.tx{{fill:{INK};{FS}}} .br{{fill:none;stroke:{NAVY};stroke-width:1.4}} .c{{fill:#cfe0ef;stroke:{NAVY2}}}</style>
<text class="tx" x="20" y="20" fill="{AMBER2}" font-size="10">cells_per_line = 10 (series)</text>
{''.join(f'<rect class="c" x="{30+i*16}" y="30" width="12" height="22"/>' for i in range(8))}
<text class="tx" x="200" y="46">= line</text>
<text class="tx" x="20" y="78" fill="{AMBER2}" font-size="10">lines_parallel = 1–2 (parallel)</text>
<rect class="br" x="28" y="64" width="150" height="40"/>
{''.join(f'<rect class="c" x="{34+i*16}" y="{70+j*16}" width="12" height="10"/>' for i in range(8) for j in range(2))}
<text class="tx" x="200" y="90">= module</text>
<text class="tx" x="20" y="132" fill="{AMBER2}" font-size="10">modules_per_block ≈ 3 (series → 70 V)</text>
{''.join(f'<rect class="br" x="{28+k*54}" y="120" width="48" height="26"/>' for k in range(3))}
<text class="tx" x="200" y="138">= block</text>
<text class="tx" x="20" y="186" fill="{AMBER2}" font-size="10">n_blocks ≈ 20 (parallel, blocking diode each)</text>
{''.join(f'<rect class="br" x="{28+k*36}" y="172" width="30" height="22"/><polygon points="{43+k*36},196 {51+k*36},196 {47+k*36},203" fill="#cfe0ef" stroke="{NAVY}"/>' for k in range(6))}
<text class="tx" x="270" y="190">= circuit (≈70 V bus)</text>
</svg>'''

# Q1-2 recursive tree
Q1_2=f'''<svg width="100%" viewBox="0 0 560 230" xmlns="http://www.w3.org/2000/svg" font-size="10.5">
<style>.tx{{fill:{INK};{FS}}} .n{{fill:#eef5fb;stroke:{NAVY};stroke-width:1.3}} .l{{fill:#eaf2f0;stroke:{TEAL};stroke-width:1.3}} .e{{stroke:{MUT};stroke-width:1}}</style>
<rect class="n" x="220" y="12" width="120" height="26" rx="4"/><text class="tx" x="280" y="29" text-anchor="middle">Circuit (parallel)</text>
{''.join(f'<line class="e" x1="280" y1="38" x2="{120+k*160}" y2="62"/><rect class="n" x="{80+k*160}" y="62" width="80" height="24" rx="4"/><text class="tx" x="{120+k*160}" y="78" text-anchor="middle" font-size="9">Block (series)</text>' for k in range(3))}
{''.join(f'<line class="e" x1="120" y1="86" x2="{90+k*60}" y2="110"/><rect class="n" x="{60+k*60}" y="110" width="56" height="22" rx="3"/><text class="tx" x="{88+k*60}" y="125" text-anchor="middle" font-size="8">Module ∥</text>' for k in range(2))}
{''.join(f'<line class="e" x1="88" y1="132" x2="{74+k*30}" y2="152"/><rect class="l" x="{52+k*30}" y="152" width="42" height="20" rx="3"/><text class="tx" x="{73+k*30}" y="166" text-anchor="middle" font-size="8">Line —</text>' for k in range(2))}
{''.join(f'<line class="e" x1="73" y1="172" x2="{62+k*22}" y2="190"/><circle cx="{62+k*22}" cy="198" r="7" fill="#cfe0ef" stroke="{NAVY}"/>' for k in range(3))}
<text class="tx" x="62" y="220" font-size="8" fill="{MUT}">leaf = CellRef</text>
<rect x="360" y="150" width="180" height="60" rx="5" fill="#fbf4e2" stroke="{AMBER}"/>
<text class="tx" x="370" y="168" font-size="9" fill="{AMBER2}">flat registry</text>
<text class="tx" x="370" y="184" font-size="8.5">cells["B3.M2.L1.C7"] → cell</text>
<text class="tx" x="370" y="200" font-size="8.5">O(1) fault injection &amp; readout</text>
</svg>'''

# Q2-1 block-diagonal matrix
def blk(x,y): return f'<rect x="{x}" y="{y}" width="26" height="26" fill="#cfe0ef" stroke="{NAVY}"/><text {FS} x="{x+13}" y="{y+12}" text-anchor="middle" font-size="7" fill="{INK}">a b</text><text {FS} x="{x+13}" y="{y+22}" text-anchor="middle" font-size="7" fill="{INK}">c d</text>'
Q2_1=f'''<svg width="100%" viewBox="0 0 420 200" xmlns="http://www.w3.org/2000/svg" font-size="10">
<rect x="40" y="20" width="170" height="170" fill="#fff" stroke="{RULE}"/>
{''.join(blk(48+i*28,28+i*28) for i in range(5))}
<text {FS} x="150" y="150" fill="{MUT}" font-size="20">0</text><text {FS} x="70" y="60" fill="{MUT}" font-size="20">0</text>
<text {FS} x="240" y="80" fill="{INK}">each cell → an independent</text>
<text {FS} x="240" y="98" fill="{INK}">2×2 block (no off-block terms)</text>
<text {FS} x="240" y="124" fill="{TEAL}" font-weight="bold">⇒ solve all blocks at once</text>
<text {FS} x="240" y="140" fill="{TEAL}">(vectorised, no Python loop)</text>
</svg>'''

# Q2-2 convergence (log y)
res=[3.96,0.38,0.013,1.5e-5,2e-11]; ly=[np.log10(r) for r in res]; xs=[1,2,3,4,5]
cp=mappts(xs,ly,1,5,-11,1,60,400,150,20)
Q2_2=f'''<svg width="100%" viewBox="0 0 430 180" xmlns="http://www.w3.org/2000/svg" font-size="10">
<line stroke="{INK}" x1="60" y1="150" x2="400" y2="150"/><line stroke="{INK}" x1="60" y1="150" x2="60" y2="16"/>
{''.join(f'<line stroke="{RULE}" stroke-width=".5" x1="60" y1="{150-(e+11)/12*130:.0f}" x2="400" y2="{150-(e+11)/12*130:.0f}"/><text {FS} x="34" y="{153-(e+11)/12*130:.0f}" font-size="8" fill="{MUT}">1e{e}</text>' for e in [0,-3,-6,-9])}
<polyline points="{cp}" fill="none" stroke="{NAVY}" stroke-width="2.2"/>
{''.join(f'<circle cx="{60+(x-1)/4*340:.0f}" cy="{150-(y+11)/12*130:.0f}" r="3" fill="{BRICK}"/>' for x,y in zip(xs,ly))}
<text {FS} x="230" y="172" text-anchor="middle" fill="{INK}">Newton iteration</text>
<text {FS} transform="translate(14,90) rotate(-90)" text-anchor="middle" fill="{INK}">residual |f| (W)</text>
<text {FS} x="250" y="40" fill="{BRICK}" font-size="9">quadratic — digits double each step</text>
</svg>'''

# Q3-1 loop diagram
def lbox(x,y,w,txt,fill="#eef5fb",stroke=NAVY):
    inner="".join(f'<text {FS} x="{x+w/2}" y="{y+15+k*12}" text-anchor="middle" font-size="9" fill="{INK}">{ln}</text>' for k,ln in enumerate(txt))
    return f'<rect x="{x}" y="{y}" width="{w}" height="{12+len(txt)*12}" rx="4" fill="{fill}" stroke="{stroke}"/>'+inner
Q3_1=f'''<svg width="100%" viewBox="0 0 620 170" xmlns="http://www.w3.org/2000/svg">
{lbox(10,40,96,["build cells","at T"])}
{lbox(130,40,104,["solve circuit","(ngspice)"])}
{lbox(258,40,96,["per-cell","P = V·I"])}
{lbox(378,40,110,["vectorised","thermal Newton"])}
{lbox(512,40,96,["new T"],fill="#eaf2f0",stroke=TEAL)}
{''.join(f'<path d="M{a} 52 H{b}" stroke="{AMBER2}" stroke-width="2" fill="none"/><polygon points="{b},52 {b-6},48 {b-6},56" fill="{AMBER2}"/>' for a,b in [(106,128),(234,256),(354,376),(488,510)])}
<path d="M560 76 V120 H58 V72" stroke="{NAVY}" stroke-width="1.6" fill="none" stroke-dasharray="5 3"/><polygon points="58,72 54,80 62,80" fill="{NAVY}"/>
<text {FS} x="300" y="116" text-anchor="middle" font-size="9" fill="{NAVY}">repeat with damping  T ← T + ω·(T_new − T)  until |ΔT| &lt; tol</text>
</svg>'''

# Q3-2 T vs outer iteration
it=np.arange(0,8); failed=187-159*np.exp(-0.6*it); healthy=39-11*np.exp(-0.7*it)
fp=mappts(it,failed,0,7,20,200,55,400,150,18); hp=mappts(it,healthy,0,7,20,200,55,400,150,18)
Q3_2=f'''<svg width="100%" viewBox="0 0 430 175" xmlns="http://www.w3.org/2000/svg" font-size="10">
<line stroke="{INK}" x1="55" y1="150" x2="400" y2="150"/><line stroke="{INK}" x1="55" y1="150" x2="55" y2="14"/>
<polyline points="{fp}" fill="none" stroke="{BRICK}" stroke-width="2.2"/>
<polyline points="{hp}" fill="none" stroke="{TEAL}" stroke-width="2.2"/>
<text {FS} x="360" y="{150-(187-20)/180*132:.0f}" fill="{BRICK}" font-size="9">failed → 187°C</text>
<text {FS} x="350" y="{150-(39-20)/180*132+4:.0f}" fill="{TEAL}" font-size="9">healthy → 39°C</text>
<text {FS} x="230" y="170" text-anchor="middle" fill="{INK}">outer iteration</text>
<text {FS} transform="translate(15,88) rotate(-90)" text-anchor="middle" fill="{INK}">T_front (°C)</text>
</svg>'''

# Q4-1 orbit + fluxes + inset
Q4_1=f'''<svg width="100%" viewBox="0 0 470 220" xmlns="http://www.w3.org/2000/svg" font-size="10">
<style>.tx{{fill:{INK};{FS}}}</style>
<circle cx="34" cy="95" r="20" fill="{AMBER}"/><text class="tx" x="18" y="130" fill="{AMBER2}">Sun</text>
<circle cx="220" cy="95" r="36" fill="#6b8fb5" stroke="{NAVY}"/><text class="tx" x="220" y="99" text-anchor="middle" fill="#fff">planet</text>
<polygon points="220,60 220,130 440,112 440,78" fill="#33415577"/><text class="tx" x="330" y="98" font-size="9">umbra</text>
<ellipse cx="220" cy="95" rx="92" ry="74" fill="none" stroke="{MUT}" stroke-dasharray="4 3"/>
<circle cx="140" cy="60" r="6" fill="{TEAL}"/>
<line stroke="{AMBER2}" stroke-width="1.6" x1="56" y1="86" x2="134" y2="62"/><text class="tx" x="60" y="50" font-size="8" fill="{AMBER2}">direct sun</text>
<line stroke="{NAVY}" stroke-width="1.2" x1="190" y1="74" x2="146" y2="62"/><text class="tx" x="150" y="44" font-size="8" fill="{NAVY}">albedo</text>
<line stroke="{BRICK}" stroke-width="1.2" x1="196" y1="84" x2="148" y2="64"/><text class="tx" x="186" y="58" font-size="8" fill="{BRICK}">IR</text>
<rect x="300" y="150" width="150" height="56" fill="#fff" stroke="{RULE}"/>
<polyline points="305,200 330,160 380,160 392,200 420,160 445,160" fill="none" stroke="{NAVY}" stroke-width="1.6"/>
<rect x="380" y="160" width="12" height="40" fill="#33415522"/><text class="tx" x="375" y="214" font-size="8" fill="{MUT}">irradiance vs phase (0 in eclipse)</text>
</svg>'''

# Q4-2 hapsira pipeline strip
Q4_2=f'''<svg width="100%" viewBox="0 0 640 90" xmlns="http://www.w3.org/2000/svg">
{lbox(8,28,86,["Orbit","(elements)"])}
{lbox(118,28,80,["propagate"])}
{lbox(222,28,118,["per-step fluxes","Psun/ecl, alb, IR, tilt"])}
{lbox(364,28,104,["Environment","time series"])}
{lbox(492,28,96,["electro-","thermal loop"],fill="#eaf2f0",stroke=TEAL)}
<text {FS} x="320" y="80" text-anchor="middle" font-size="9" fill="{MUT}">→ T(t), P(t) around the orbit; worst-case hot-spot</text>
{''.join(f'<path d="M{a} 44 H{b}" stroke="{AMBER2}" stroke-width="2" fill="none"/><polygon points="{b},44 {b-6},40 {b-6},48" fill="{AMBER2}"/>' for a,b in [(94,116),(198,220),(340,362),(468,490)])}
</svg>'''

# Q5-1 decision diagram
Q5_1=f'''<svg width="100%" viewBox="0 0 470 190" xmlns="http://www.w3.org/2000/svg" font-size="10">
<style>.tx{{fill:{INK};{FS}}} .b{{fill:#eef5fb;stroke:{NAVY};stroke-width:1.3}}</style>
<rect class="b" x="170" y="12" width="130" height="30" rx="4"/><text class="tx" x="235" y="31" text-anchor="middle">converged per-cell result</text>
<rect x="40" y="78" width="170" height="34" rx="4" fill="#fcefea" stroke="{BRICK}"/><text class="tx" x="125" y="92" text-anchor="middle" font-size="9">T_front ≥ T_limit ?</text><text class="tx" x="125" y="105" text-anchor="middle" font-size="8" fill="{MUT}">(thermal)</text>
<rect x="260" y="78" width="180" height="34" rx="4" fill="#fcefea" stroke="{BRICK}"/><text class="tx" x="350" y="92" text-anchor="middle" font-size="9">V&lt;0 and |V·I| ≥ P_limit ?</text><text class="tx" x="350" y="105" text-anchor="middle" font-size="8" fill="{MUT}">(reverse power)</text>
<line stroke="{MUT}" x1="200" y1="42" x2="125" y2="78"/><line stroke="{MUT}" x1="270" y1="42" x2="350" y2="78"/>
<rect x="175" y="150" width="120" height="30" rx="4" fill="{BRICK}"/><text class="tx" x="235" y="170" text-anchor="middle" fill="#fff">cell destroyed</text>
<line stroke="{BRICK}" x1="125" y1="112" x2="225" y2="150"/><line stroke="{BRICK}" x1="350" y1="112" x2="245" y2="150"/>
<text class="tx" x="235" y="140" text-anchor="middle" font-size="11" fill="{BRICK}">OR</text>
</svg>'''

# Q5-2 P_rev bars
Q5_2=f'''<svg width="100%" viewBox="0 0 420 180" xmlns="http://www.w3.org/2000/svg" font-size="10">
<line stroke="{INK}" x1="70" y1="150" x2="380" y2="150"/>
<rect x="110" y="{150-0.34/11*120:.0f}" width="60" height="{0.34/11*120:.0f}" fill="{TEAL}"/><text {FS} x="140" y="145" text-anchor="middle" font-size="9" fill="#fff"></text><text {FS} x="140" y="165" text-anchor="middle" font-size="9" fill="{INK}">protected</text><text {FS} x="140" y="{150-0.34/11*120-4:.0f}" text-anchor="middle" font-size="9" fill="{TEAL}">0.34 W</text>
<rect x="240" y="{150-9.6/11*120:.0f}" width="60" height="{9.6/11*120:.0f}" fill="{BRICK}"/><text {FS} x="270" y="165" text-anchor="middle" font-size="9" fill="{INK}">unprotected</text><text {FS} x="270" y="{150-9.6/11*120-4:.0f}" text-anchor="middle" font-size="9" fill="{BRICK}">9.6 W</text>
<line x1="70" y1="{150-2/11*120:.0f}" x2="380" y2="{150-2/11*120:.0f}" stroke="{AMBER}" stroke-width="1.6" stroke-dasharray="5 3"/><text {FS} x="384" y="{150-2/11*120+3:.0f}" font-size="9" fill="{AMBER2}">P_limit = 2 W</text>
<text {FS} transform="translate(20,90) rotate(-90)" text-anchor="middle" fill="{INK}">reverse power</text>
</svg>'''

# Q6-1 MC flow
Q6_1=f'''<svg width="100%" viewBox="0 0 640 100" xmlns="http://www.w3.org/2000/svg">
{lbox(8,30,110,["Circuit +","fail(pattern)"])}
{lbox(140,30,118,["electro-thermal","solve"])}
{lbox(282,30,130,["record power,","maxT, hot-spots"])}
{lbox(436,30,90,["repeat ×N"],fill="#fbf4e2",stroke=AMBER)}
{lbox(548,30,84,["histograms","+ ranking"],fill="#eaf2f0",stroke=TEAL)}
{''.join(f'<path d="M{a} 46 H{b}" stroke="{AMBER2}" stroke-width="2" fill="none"/><polygon points="{b},46 {b-6},42 {b-6},50" fill="{AMBER2}"/>' for a,b in [(118,138),(258,280),(412,434),(526,546)])}
<path d="M481 60 V82 H60 V58" stroke="{NAVY}" stroke-width="1.4" fill="none" stroke-dasharray="4 3"/><polygon points="60,58 56,66 64,66" fill="{NAVY}"/>
</svg>'''

# Q6-2 three modes
def grid(ox,oy,fail=None,heat=False):
    s=""
    for r in range(4):
        for c in range(4):
            col="#cfe0ef"
            if heat:
                d=abs(r-1)+abs(c-2); col=["#9a3b3b","#cf6a4a","#e0a96d","#cfe0ef","#cfe0ef"][min(d,4)]
            if fail==(r,c): col="#9a3b3b"
            s+=f'<rect x="{ox+c*11}" y="{oy+r*11}" width="9" height="9" fill="{col}" stroke="#fff"/>'
    return s
xs2=np.arange(1,8); dmg=1-np.exp(-0.4*xs2)
dp=mappts(xs2,dmg,1,7,0,1,250,330,118,80)
Q6_2=f'''<svg width="100%" viewBox="0 0 470 150" xmlns="http://www.w3.org/2000/svg" font-size="9">
<text {FS} x="78" y="14" text-anchor="middle" fill="{NAVY}">1 · position sweep</text>
{grid(40,24,heat=True)}<text {FS} x="78" y="142" text-anchor="middle" fill="{MUT}">max-T by failed position</text>
<text {FS} x="285" y="14" text-anchor="middle" fill="{NAVY}">2 · count sweep</text>
<line stroke="{INK}" x1="250" y1="118" x2="332" y2="118"/><line stroke="{INK}" x1="250" y1="118" x2="250" y2="26"/><polyline points="{dp}" fill="none" stroke="{BRICK}" stroke-width="2"/><text {FS} x="291" y="142" text-anchor="middle" fill="{MUT}">damage vs #failed</text>
<text {FS} x="410" y="14" text-anchor="middle" fill="{NAVY}">3 · random</text>
{''.join(f'<rect x="{372+i*11}" y="{118-h}" width="9" height="{h}" fill="{TEAL}"/>' for i,h in enumerate([10,26,46,60,40,22,12]))}
<line stroke="{INK}" x1="368" y1="118" x2="452" y2="118"/><text {FS} x="410" y="142" text-anchor="middle" fill="{MUT}">outcome histogram</text>
</svg>'''

# Q7-1 long format -> parquet/excel
Q7_1=f'''<svg width="100%" viewBox="0 0 470 180" xmlns="http://www.w3.org/2000/svg" font-size="9">
<style>.tx{{fill:{INK};{FS}}}</style>
<rect x="20" y="20" width="220" height="120" fill="#fff" stroke="{RULE}"/>
<rect x="20" y="20" width="220" height="20" fill="#e9ecf1"/>
{''.join(f'<text class="tx" x="{28+i*36}" y="34" font-size="7.5" fill="{NAVY}">{h}</text>' for i,h in enumerate(["run","cell","V","I","P_el","Tf","hot"]))}
{''.join(f'<line x1="20" y1="{40+r*20}" x2="240" y2="{40+r*20}" stroke="{RULE}"/>'+''.join(f'<text class="tx" x="{28+i*36}" y="{54+r*20}" font-size="7">{v}</text>' for i,v in enumerate(["7","42","-0.7","0.48","-9.6","187","1"] if r==2 else [str(7),str(r),"2.3","0.48","1.1","39","0"])) for r in range(5))}
<text class="tx" x="130" y="156" text-anchor="middle" fill="{MUT}">long format: one row per (run, cell)</text>
<path d="M244 60 H300" stroke="{AMBER2}" stroke-width="2" fill="none"/><polygon points="300,60 294,56 294,64" fill="{AMBER2}"/>
<path d="M244 100 H300" stroke="{AMBER2}" stroke-width="2" fill="none"/><polygon points="300,100 294,96 294,104" fill="{AMBER2}"/>
<path d="M306 44 a30 16 0 1 0 60 0 a30 16 0 1 0 -60 0" fill="#eaf2f0" stroke="{TEAL}"/><rect x="306" y="44" width="60" height="32" fill="#eaf2f0" stroke="none"/><path d="M306 76 a30 16 0 0 0 60 0" fill="#eaf2f0" stroke="{TEAL}"/><line x1="306" y1="44" x2="306" y2="76" stroke="{TEAL}"/><line x1="366" y1="44" x2="366" y2="76" stroke="{TEAL}"/><text class="tx" x="336" y="64" text-anchor="middle" font-size="8" fill="{TEAL}">Parquet</text><text class="tx" x="336" y="92" text-anchor="middle" font-size="7.5" fill="{MUT}">source of truth</text>
<rect x="306" y="90" width="60" height="40" fill="#fff" stroke="#107c41"/><rect x="306" y="90" width="60" height="10" fill="#107c41"/><text class="tx" x="336" y="98" text-anchor="middle" font-size="7" fill="#fff">Excel</text><text class="tx" x="336" y="116" text-anchor="middle" font-size="7" fill="{MUT}">summary</text>
<text class="tx" x="410" y="64" font-size="8" fill="{MUT}">compact,</text><text class="tx" x="410" y="76" font-size="8" fill="{MUT}">columnar</text>
</svg>'''

# Q7-2 heatmap
def hm(ox,oy):
    s=""
    rng=np.random.default_rng(5)
    for r in range(8):
        for c in range(12):
            base=30+ (abs(r-2)+abs(c-8))*-3
            t=187 if (r,c)==(2,8) else max(35, 70 - (abs(r-2)+abs(c-8))*6 + rng.integers(-4,4))
            frac=min(1,(t-35)/152)
            col=f'rgb({int(60+frac*180)},{int(110-frac*70)},{int(150-frac*120)})'
            s+=f'<rect x="{ox+c*22}" y="{oy+r*15}" width="20" height="13" fill="{col}" stroke="#fff"/>'
    return s
Q7_2=f'''<svg width="100%" viewBox="0 0 320 180" xmlns="http://www.w3.org/2000/svg" font-size="9">
{hm(20,16)}
<text {FS} x="180" y="150" font-size="8" fill="{MUT}">each square = a cell; colour = max T if that cell fails</text>
<rect x="20" y="158" width="80" height="10" fill="url(#g)"/>
<defs><linearGradient id="g"><stop offset="0" stop-color="rgb(60,110,150)"/><stop offset="1" stop-color="rgb(240,40,30)"/></linearGradient></defs>
<text {FS} x="20" y="176" font-size="7" fill="{MUT}">cool</text><text {FS} x="84" y="176" font-size="7" fill="{BRICK}">melt</text>
</svg>'''

# Q8-1 module dependency map
def mod(x,y,name,w=120):
    return f'<rect x="{x}" y="{y}" width="{w}" height="22" rx="4" fill="#eef5fb" stroke="{NAVY}"/><text {FS} x="{x+w/2}" y="{y+15}" text-anchor="middle" font-size="8.5" fill="{INK}">{name}</text>'
Q8_1=f'''<svg width="100%" viewBox="0 0 560 210" xmlns="http://www.w3.org/2000/svg">
{mod(40,16,"montecarlo.py",150)}
{mod(40,58,"electrothermal.py",130)}{mod(200,58,"environment_orbit.py",150)}{mod(380,58,"results.py",120)}
{mod(40,100,"circuit.py",110)}{mod(170,100,"thermal_vectorized.py",160)}{mod(360,100,"substrate.py",120)}
<rect x="40" y="150" width="440" height="40" rx="5" fill="#fbf4e2" stroke="{AMBER}"/><text {FS} x="260" y="166" text-anchor="middle" font-size="9" fill="{AMBER2}">Chapter-1 primitives</text><text {FS} x="260" y="182" text-anchor="middle" font-size="8.5" fill="{INK}">cell · electric (cellBuilder, ng_sim) · ngspice · Environment</text>
{''.join(f'<line x1="{a}" y1="{ay}" x2="{b}" y2="{by}" stroke="{MUT}" stroke-width="1"/>' for a,ay,b,by in [(115,38,105,58),(115,38,275,58),(115,38,440,58),(105,80,95,100),(105,80,250,100),(250,80,250,100),(95,122,150,150),(250,122,250,150),(420,122,400,150),(440,80,440,150)])}
</svg>'''

# Q8-2 full pipeline
Q8_2=f'''<svg width="100%" viewBox="0 0 600 200" xmlns="http://www.w3.org/2000/svg">
{mod(20,20,"Circuit §1",100)}{mod(20,60,"Substrate",100)}{mod(20,100,"Orbit/hapsira §4",120)}
<rect x="190" y="40" width="120" height="80" rx="6" fill="#eef5fb" stroke="{NAVY}" stroke-width="1.6"/><text {FS} x="250" y="74" text-anchor="middle" font-size="9.5" fill="{NAVY}">Monte-Carlo</text><text {FS} x="250" y="90" text-anchor="middle" font-size="9.5" fill="{NAVY}">driver §6</text>
{mod(350,20,"fail(pattern) §1",130)}{mod(350,58,"electro-thermal §3",140)}{mod(350,96,"vectorised thermal §2",150)}{mod(350,134,"breakdown §5",120)}
{mod(350,172,"results store §7",130)}
{''.join(f'<path d="M120 {y} H188" stroke="{AMBER2}" stroke-width="1.6" fill="none"/><polygon points="188,{y} 182,{y-4} 182,{y+4}" fill="{AMBER2}"/>' for y in [30,70,110])}
<path d="M310 80 H348" stroke="{AMBER2}" stroke-width="1.6" fill="none"/><polygon points="348,80 342,76 342,84" fill="{AMBER2}"/>
<path d="M250 120 V190 H348" stroke="{NAVY}" stroke-width="1.4" fill="none" stroke-dasharray="4 3"/>
<text {FS} x="470" y="200" font-size="8" fill="{MUT}">→ heat-maps · histograms · Excel</text>
</svg>'''

FIGS={
 "_frag_Q1.html":[fig(Q1_1,"Figure 2.1 — The four-level parametric topology: cells in series → lines in parallel (a module) → modules in series (a block) → blocks in parallel (the circuit), one blocking diode per block."),
                  fig(Q1_2,"Figure 2.2 — The recursive Group/CellRef tree with stable hierarchical ids, plus the flat registry that gives O(1) access to any cell for fault injection.")],
 "_frag_Q2.html":[fig(Q2_1,"Figure 2.3 — Because cells are thermally independent, the global Jacobian is block-diagonal: N independent 2×2 blocks, solved together as numpy arrays."),
                  fig(Q2_2,"Figure 2.4 — Newton convergence: the residual collapses quadratically to ~1e-11 in about five iterations.")],
 "_frag_Q3.html":[fig(Q3_1,"Figure 2.5 — The electro-thermal coupling loop: build cells at T → circuit solve → per-cell P=V·I → vectorised thermal Newton → new T, damped, until converged."),
                  fig(Q3_2,"Figure 2.6 — Outer-iteration history: a healthy cell settles near 39 °C while a failed cell climbs to ~187 °C.")],
 "_frag_Q4.html":[fig(Q4_1,"Figure 2.7 — Around the orbit the array sees direct sun, planet albedo and planetary IR, and passes through the umbra (eclipse) where solar input drops to zero."),
                  fig(Q4_2,"Figure 2.8 — The hapsira flux pipeline: orbit → propagate → per-step fluxes → Environment time series → the electro-thermal loop.")],
 "_frag_Q5.html":[fig(Q5_1,"Figure 2.9 — Breakdown is flagged if EITHER the temperature criterion OR the reverse-power criterion trips."),
                  fig(Q5_2,"Figure 2.10 — Reverse dissipation: a bypass diode keeps it at 0.34 W (below the 2 W limit); unprotected reverse breakdown reaches 9.6 W (well above).")],
 "_frag_Q6.html":[fig(Q6_1,"Figure 2.11 — One Monte-Carlo run: fail a pattern → electro-thermal solve → record outcomes → repeat N times → histograms and rankings."),
                  fig(Q6_2,"Figure 2.12 — The three sampling modes: position sweep (worst location), count sweep (damage vs number of failures), and random sampling (outcome distribution).")],
 "_frag_Q7.html":[fig(Q7_1,"Figure 2.13 — Results are stored long-format (one row per run×cell) in Parquet/HDF5 as the source of truth; Excel is a generated summary on top."),
                  fig(Q7_2,"Figure 2.14 — A failure-position heat-map: each square is a cell, coloured by the maximum temperature reached if that cell fails — the hot reds are the dangerous positions.")],
 "_frag_Q8.html":[fig(Q8_1,"Figure 2.15 — The new modules all stand on the Chapter-1 primitives (cell, electric/ngspice, Environment)."),
                  fig(Q8_2,"Figure 2.16 — The full pipeline: Circuit + Substrate + Orbit feed the Monte-Carlo driver; each run runs fail → electro-thermal (vectorised) → breakdown → results store.")],
}
base=os.path.dirname(os.path.abspath(__file__)); total=0
for fname,svgs in FIGS.items():
    p=os.path.join(base,fname); html=open(p,encoding="utf-8").read(); it=iter(svgs)
    def repl(m):
        global total
        try: s=next(it); total+=1; return s
        except StopIteration: return m.group(0)
    html=re.sub(r"<!--FIG:.*?-->",repl,html,flags=re.S)
    open(p,"w",encoding="utf-8").write(html); print(f"{fname}: {len(svgs)} figs")
print("TOTAL",total)
