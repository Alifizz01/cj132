# -*- coding: utf-8 -*-
"""Generate inline-SVG figures and inject them into the _frag_P*.html files,
replacing each <!--FIG: ...--> placeholder (in order) with a <figure>.
Run from the Notes/ folder (outside the package -> no stdlib shadowing).
Data-driven plots are computed with numpy for honesty; schematics are templated.
"""
import re, numpy as np, os

NAVY="#0b3d63"; NAVY2="#11507a"; AMBER="#c9a227"; AMBER2="#b9851a"
BRICK="#9a3b3b"; TEAL="#1f6a6a"; INK="#1d2733"; MUT="#5d6b79"; RULE="#cfd7df"
FS='font-family="Segoe UI,Arial,sans-serif"'

def fig(svg, cap):
    return ('<figure class="fig-frame">\n'+svg+'\n<figcaption>'+cap+'</figcaption></figure>')

def pts(xs, ys, x0,x1,y0,y1, X0,X1,Y0,Y1):
    """map data (xs,ys) in [x0,x1]x[y0,y1] to svg coords [X0,X1]x[Y1,Y0]."""
    out=[]
    for x,y in zip(xs,ys):
        sx=X0+(x-x0)/(x1-x0)*(X1-X0)
        sy=Y0+(y-y0)/(y1-y0)*(Y0-Y1) if False else Y1-(y-y0)/(y1-y0)*(Y1-Y0)
        out.append(f"{sx:.1f},{sy:.1f}")
    return " ".join(out)

# ----------------------------------------------------------------------------- P1
# 1) hierarchy ladder
P1_1 = '''<svg width="100%" viewBox="0 0 640 130" xmlns="http://www.w3.org/2000/svg" font-size="12">
<style>.bx{{fill:#eef5fb;stroke:{n};stroke-width:1.5}} .t{{fill:{i};{f}}} .ar{{stroke:{a};stroke-width:2;fill:none}} .lab{{fill:{m};font-size:10px;{f}}}</style>
<rect class="bx" x="14" y="48" width="58" height="34" rx="4"/><text class="t" x="43" y="69" text-anchor="middle">cell</text>
<rect class="bx" x="120" y="40" width="118" height="50" rx="4"/>
<g>{cells}</g><text class="t" x="179" y="103" text-anchor="middle" font-size="11">string (series)</text>
<rect class="bx" x="286" y="30" width="150" height="70" rx="4"/>
<g>{strs}</g><text class="t" x="361" y="113" text-anchor="middle" font-size="11">section (parallel)</text>
<rect class="bx" x="484" y="24" width="142" height="84" rx="4"/>
<rect x="496" y="40" width="118" height="56" fill="#fbf4e2" stroke="{am}"/>
<text class="t" x="555" y="120" text-anchor="middle" font-size="11">panel (+substrate)</text>
<path class="ar" d="M76 65 H114"/><path class="ar" d="M242 65 H282"/><path class="ar" d="M440 65 H480"/>
<polygon points="114,65 108,61 108,69" fill="{a}"/><polygon points="282,65 276,61 276,69" fill="{a}"/><polygon points="480,65 474,61 474,69" fill="{a}"/>
<text class="lab" x="95" y="58" text-anchor="middle">series</text><text class="lab" x="262" y="58" text-anchor="middle">parallel</text><text class="lab" x="460" y="58" text-anchor="middle">mount</text>
</svg>'''.format(n=NAVY,i=INK,f=FS,a=AMBER2,m=MUT,am=AMBER,
   cells="".join(f'<rect x="{128+i*20}" y="56" width="14" height="18" fill="#cfe0ef" stroke="{NAVY2}"/>' for i in range(5)),
   strs="".join(f'<rect x="{294}" y="{40+j*20}" width="134" height="13" fill="#cfe0ef" stroke="{NAVY2}"/>' for j in range(3)))

# 2) triple junction stack
P1_2 = f'''<svg width="100%" viewBox="0 0 460 180" xmlns="http://www.w3.org/2000/svg" font-size="11">
<style>.s{{stroke:{INK};stroke-width:1}} .tx{{fill:{INK};{FS}}}</style>
{''.join(f'<line x1="{120+i*30}" y1="6" x2="{110+i*30}" y2="40" stroke="{AMBER}" stroke-width="2"/><polygon points="{110+i*30},40 {106+i*30},32 {116+i*30},34" fill="{AMBER}"/>' for i in range(4))}
<text class="tx" x="60" y="20" fill="{AMBER2}">Sun</text>
<rect x="150" y="44" width="180" height="6" fill="#444"/><text class="tx" x="345" y="50" font-size="9" fill="{MUT}">+ contact (grid)</text>
<rect x="150" y="52" width="180" height="26" fill="#3b6ea5" class="s"/><text class="tx" x="240" y="69" text-anchor="middle" fill="#fff">top sub-cell — blue</text>
<rect x="150" y="80" width="180" height="26" fill="#4f9a6b" class="s"/><text class="tx" x="240" y="97" text-anchor="middle" fill="#fff">middle sub-cell — green</text>
<rect x="150" y="108" width="180" height="26" fill="#a8504b" class="s"/><text class="tx" x="240" y="125" text-anchor="middle" fill="#fff">bottom sub-cell — red</text>
<rect x="150" y="136" width="180" height="8" fill="#777"/><text class="tx" x="345" y="143" font-size="9" fill="{MUT}">− contact</text>
<text class="tx" x="240" y="162" text-anchor="middle" font-size="10" fill="{MUT}">three junctions in series ≈ 2.6 V, ~30% efficiency</text>
</svg>'''

# 3) IV + power curve (real single-diode data)
vt=0.0979; i0=0.5/(np.exp(2.67/vt)-1); V=np.linspace(0,2.67,160)
I=np.clip(0.5 - i0*(np.exp(V/vt)-1),0,None); P=V*I
imp_i=int(np.argmax(P)); Vmp,Imp,Pmp=V[imp_i],I[imp_i],P[imp_i]
X0,X1,Y0,Y1=58,420,150,18
ivp=pts(V,I,0,2.8,0,0.55,X0,X1,Y0,Y1)
pwp=pts(V,P,0,2.8,0,1.25,X0,X1,Y0,Y1)
mppx=X0+Vmp/2.8*(X1-X0); mppyI=Y1-Imp/0.55*(Y1-Y0)+ (Y1-Y0)*0;
mppyI=Y0-(Imp-0)/(0.55)*(Y0-Y1) if False else Y0-(Imp)/(0.55)*(Y0-Y1)
mppyP=Y0-(Pmp)/(1.25)*(Y0-Y1)
P1_3 = f'''<svg width="100%" viewBox="0 0 470 175" xmlns="http://www.w3.org/2000/svg" font-size="11">
<style>.ax{{stroke:{INK};stroke-width:1.2}} .gl{{stroke:{RULE};stroke-width:.6}} .tx{{fill:{INK};{FS}}}</style>
<line class="ax" x1="{X0}" y1="{Y0}" x2="{X1}" y2="{Y0}"/><line class="ax" x1="{X0}" y1="{Y0}" x2="{X0}" y2="{Y1}"/>
<polyline points="{ivp}" fill="none" stroke="{NAVY}" stroke-width="2.2"/>
<polyline points="{pwp}" fill="none" stroke="{BRICK}" stroke-width="2" stroke-dasharray="5 3"/>
<circle cx="{mppx:.1f}" cy="{mppyP:.1f}" r="4" fill="{BRICK}"/>
<circle cx="{mppx:.1f}" cy="{mppyI:.1f}" r="3.5" fill="{NAVY}"/>
<line class="gl" x1="{mppx:.1f}" y1="{Y0}" x2="{mppx:.1f}" y2="{min(mppyI,mppyP):.1f}"/>
<circle cx="{X0}" cy="{Y0-0.5/0.55*(Y0-Y1):.1f}" r="3" fill="{NAVY}"/><text class="tx" x="{X0+6}" y="{Y0-0.5/0.55*(Y0-Y1)-4:.1f}" font-size="10">Isc</text>
<circle cx="{X1-(2.8-2.67)/2.8*(X1-X0):.1f}" cy="{Y0}" r="3" fill="{NAVY}"/><text class="tx" x="{X1-46:.1f}" y="{Y0+14}" font-size="10">Voc</text>
<text class="tx" x="{mppx+6:.1f}" y="{mppyP-4:.1f}" font-size="10" fill="{BRICK}">MPP (Pmp={Pmp:.2f} W)</text>
<text class="tx" x="{mppx-2:.1f}" y="{Y0+14}" font-size="9" fill={MUT!r}>Vmp</text>
<text class="tx" x="210" y="172" text-anchor="middle">Voltage [V]</text>
<text class="tx" transform="translate(16,90) rotate(-90)" text-anchor="middle">Current [A]</text>
<text class="tx" x="448" y="90" text-anchor="middle" transform="rotate(90 448 90)" fill="{BRICK}">Power [W]</text>
</svg>'''

# ----------------------------------------------------------------------------- P2
# 4) single-diode equivalent circuit
P2_4 = f'''<svg width="100%" viewBox="0 0 470 200" xmlns="http://www.w3.org/2000/svg" font-size="11">
<style>.w{{stroke:{INK};stroke-width:1.6;fill:none}} .tx{{fill:{INK};{FS}}}</style>
<line class="w" x1="60" y1="40" x2="60" y2="160"/>
<!-- current source -->
<circle cx="60" cy="100" r="20" class="w" fill="#eef5fb"/><line class="w" x1="60" y1="112" x2="60" y2="88"/><polygon points="60,86 56,94 64,94" fill="{INK}"/>
<text class="tx" x="22" y="104">Iph</text>
<!-- diode branch -->
<line class="w" x1="150" y1="40" x2="150" y2="160"/>
<polygon points="140,108 160,108 150,92" fill="#cfe0ef" stroke="{INK}"/><line class="w" x1="140" y1="92" x2="160" y2="92"/>
<text class="tx" x="158" y="104">D</text>
<!-- shunt resistor -->
<line class="w" x1="220" y1="40" x2="220" y2="78"/><rect x="211" y="78" width="18" height="44" fill="#fff" class="w"/><line class="w" x1="220" y1="122" x2="220" y2="160"/>
<text class="tx" x="234" y="104">Rsh</text>
<!-- top & bottom rails -->
<line class="w" x1="60" y1="40" x2="300" y2="40"/><line class="w" x1="60" y1="160" x2="360" y2="160"/>
<!-- series resistor to output -->
<rect x="300" y="31" width="44" height="18" fill="#fff" class="w"/><text class="tx" x="322" y="26" text-anchor="middle">Rs</text>
<line class="w" x1="344" y1="40" x2="400" y2="40"/>
<circle cx="402" cy="40" r="3" fill="{INK}"/><circle cx="402" cy="160" r="3" fill="{INK}"/>
<text class="tx" x="410" y="44">high (+)</text><text class="tx" x="410" y="164">low (−)</text>
<text class="tx" x="150" y="186" text-anchor="middle" fill="{MUT}" font-size="10">photocurrent source ∥ junction diode ∥ shunt R, then series R to the terminals</text>
</svg>'''

# 5) exp knee
xe=np.linspace(0,1,80); ye=np.exp(3*xe); ye=ye/ye.max()
ep=pts(xe,ye,0,1,0,1,55,300,120,18)
P2_5 = f'''<svg width="100%" viewBox="0 0 340 140" xmlns="http://www.w3.org/2000/svg" font-size="11">
<line stroke="{INK}" stroke-width="1.2" x1="55" y1="120" x2="320" y2="120"/><line stroke="{INK}" stroke-width="1.2" x1="55" y1="120" x2="55" y2="14"/>
<polyline points="{ep}" fill="none" stroke="{NAVY}" stroke-width="2.2"/>
<text {FS} x="190" y="136" text-anchor="middle" fill="{INK}">diode voltage V</text>
<text {FS} transform="translate(16,70) rotate(-90)" text-anchor="middle" fill="{INK}">I_diode</text>
<text {FS} x="250" y="40" fill="{MUT}" font-size="10">∝ exp(V/nVt)</text>
<text {FS} x="150" y="112" fill="{MUT}" font-size="9">~flat</text><text {FS} x="270" y="80" fill="{MUT}" font-size="9">knee</text>
</svg>'''

# 6) SPICE subckt
P2_6 = f'''<svg width="100%" viewBox="0 0 480 190" xmlns="http://www.w3.org/2000/svg" font-size="10.5">
<style>.w{{stroke:{INK};stroke-width:1.5;fill:none}} .nd{{fill:{NAVY}}} .tx{{fill:{INK};{FS}}} .el{{fill:#eef5fb;stroke:{INK}}}</style>
<rect x="10" y="10" width="460" height="170" rx="6" fill="none" stroke="{RULE}" stroke-dasharray="4 3"/>
<text class="tx" x="20" y="26" fill="{MUT}">.subckt cell  high low</text>
<!-- nodes -->
<circle class="nd" cx="70" cy="150" r="4"/><text class="tx" x="56" y="168">low</text>
<circle class="nd" cx="200" cy="60" r="4"/><text class="tx" x="190" y="52">nc</text>
<circle class="nd" cx="300" cy="60" r="4"/><text class="tx" x="292" y="52">nd</text>
<circle class="nd" cx="430" cy="60" r="4"/><text class="tx" x="424" y="52">high</text>
<!-- II_Cell low->nc -->
<line class="w" x1="70" y1="150" x2="70" y2="60"/><line class="w" x1="70" y1="60" x2="200" y2="60"/>
<circle class="el" cx="120" cy="60" r="12"/><text class="tx" x="106" y="44">II_Cell</text>
<!-- DD_Cell nc->low -->
<line class="w" x1="200" y1="60" x2="200" y2="150"/><polygon points="192,108 208,108 200,96" fill="#cfe0ef" stroke="{INK}"/><text class="tx" x="208" y="106">DD_Cell</text>
<!-- RR_CH nc->nd -->
<rect class="el" x="235" y="51" width="30" height="18"/><text class="tx" x="250" y="44" text-anchor="middle">RR_CH</text>
<line class="w" x1="200" y1="60" x2="235" y2="60"/><line class="w" x1="265" y1="60" x2="300" y2="60"/>
<!-- RR_Cell_Shunt nd->low -->
<line class="w" x1="300" y1="60" x2="300" y2="150"/><rect class="el" x="291" y="95" width="18" height="30"/><text class="tx" x="312" y="114" font-size="9">RR_Cell_Shunt</text>
<!-- DD_Shunt low->nd (bypass) -->
<line class="w" x1="350" y1="150" x2="350" y2="60"/><line class="w" x1="300" y1="150" x2="350" y2="150"/><line class="w" x1="350" y1="60" x2="300" y2="60"/>
<polygon points="342,108 358,108 350,120" fill="#fbe3df" stroke="{BRICK}"/><text class="tx" x="356" y="120" fill="{BRICK}">DD_Shunt</text>
<!-- RR_Iconn nd->high -->
<rect class="el" x="360" y="51" width="34" height="18"/><text class="tx" x="377" y="44" text-anchor="middle">RR_Iconn</text>
<line class="w" x1="300" y1="60" x2="360" y2="60"/><line class="w" x1="394" y1="60" x2="430" y2="60"/>
<line class="w" x1="70" y1="150" x2="350" y2="150"/>
</svg>'''

# ----------------------------------------------------------------------------- P3
# 7) remaining factor + voc(T)
dose=np.logspace(13,16,60); r_isc=1-0.06*(np.log10(dose)-13)/3; r_voc=1-0.12*(np.log10(dose)-13)/3
rp1=pts(np.log10(dose),r_isc,13,16,0.8,1.0,55,250,118,18)
rp2=pts(np.log10(dose),r_voc,13,16,0.8,1.0,55,250,118,18)
Tc=np.linspace(-120,80,50); voc=2.67-0.006*(Tc-28)
vp=pts(Tc,voc,-120,80,2.4,3.4,310,470,118,18)
P3_7 = f'''<svg width="100%" viewBox="0 0 490 150" xmlns="http://www.w3.org/2000/svg" font-size="10">
<line stroke="{INK}" x1="55" y1="118" x2="255" y2="118"/><line stroke="{INK}" x1="55" y1="118" x2="55" y2="16"/>
<polyline points="{rp1}" fill="none" stroke="{NAVY}" stroke-width="2"/><polyline points="{rp2}" fill="none" stroke="{BRICK}" stroke-width="2"/>
<text {FS} x="150" y="135" text-anchor="middle" fill="{INK}">1 MeV e⁻ dose (log)</text>
<text {FS} transform="translate(18,70) rotate(-90)" text-anchor="middle" fill="{INK}">remaining factor</text>
<text {FS} x="200" y="40" fill="{NAVY}" font-size="9">r_isc</text><text {FS} x="200" y="92" fill="{BRICK}" font-size="9">r_voc</text>
<line stroke="{INK}" x1="310" y1="118" x2="478" y2="118"/><line stroke="{INK}" x1="310" y1="118" x2="310" y2="16"/>
<polyline points="{vp}" fill="none" stroke="{TEAL}" stroke-width="2.2"/>
<text {FS} x="394" y="135" text-anchor="middle" fill="{INK}">temperature (°C)</text>
<text {FS} x="320" y="30" fill="{TEAL}" font-size="9">Voc rises as T falls</text>
</svg>'''

# 8) prepareModel flow strip
def flowbox(x,txt,fill="#eef5fb",stroke=NAVY,w=92):
    return f'<rect x="{x}" y="40" width="{w}" height="50" rx="5" fill="{fill}" stroke="{stroke}"/>'+ \
           "".join(f'<text {FS} x="{x+w/2}" y="{58+k*15}" text-anchor="middle" font-size="10" fill="{INK}">{ln}</text>' for k,ln in enumerate(txt))
P3_8 = f'''<svg width="100%" viewBox="0 0 640 120" xmlns="http://www.w3.org/2000/svg">
{flowbox(8,["base numbers","isc imp vmp voc"])}
{flowbox(150,["× remaining","r(dose)"],fill="#eef5fb")}
{flowbox(292,["+ temp coeff","·(T − t_ref)"])}
{flowbox(434,["× losses,","season corr."],fill="#fbf4e2",stroke=AMBER)}
<rect x="560" y="40" width="74" height="50" rx="5" fill="#eaf2f0" stroke="{TEAL}"/><text {FS} x="597" y="60" text-anchor="middle" font-size="10" fill="{TEAL}">operating</text><text {FS} x="597" y="74" text-anchor="middle" font-size="9" fill="{TEAL}">isc..voc</text>
{''.join(f'<path d="M{x} 65 H{x+18}" stroke="{AMBER2}" stroke-width="2" fill="none"/><polygon points="{x+18},65 {x+12},61 {x+12},69" fill="{AMBER2}"/>' for x in [100,242,384,526])}
</svg>'''

# ----------------------------------------------------------------------------- P4
# 9) seasons bar
seas=[("SS",0.967),("AEX",0.993),("VEX",1.008),("WS",1.034)]
def sbar(i,name,val):
    x=70+i*90; base=120; top=base-(val-0.95)/0.10*90
    col=BRICK if val<1 else TEAL
    return f'<rect x="{x}" y="{top:.1f}" width="44" height="{base-top:.1f}" fill="{col}" opacity=".82"/>'+\
           f'<text {FS} x="{x+22}" y="135" text-anchor="middle" font-size="10" fill="{INK}">{name}</text>'+\
           f'<text {FS} x="{x+22}" y="{top-4:.1f}" text-anchor="middle" font-size="9" fill="{INK}">{val}</text>'
yline=120-(1.0-0.95)/0.10*90
P4_9 = f'''<svg width="100%" viewBox="0 0 470 150" xmlns="http://www.w3.org/2000/svg">
{''.join(sbar(i,n,v) for i,(n,v) in enumerate(seas))}
<line x1="50" y1="{yline:.1f}" x2="450" y2="{yline:.1f}" stroke="{NAVY}" stroke-dasharray="5 3" stroke-width="1.4"/>
<text {FS} x="455" y="{yline+3:.1f}" font-size="10" fill="{NAVY}">AM0 = 1.0 (1367 W/m²)</text>
<text {FS} x="250" y="16" text-anchor="middle" font-size="10" fill="{MUT}">season irradiance multiplier (note: summer SS is the WEAKER sun)</text>
</svg>'''

# 10) tilt geometry
P4_10 = f'''<svg width="100%" viewBox="0 0 440 190" xmlns="http://www.w3.org/2000/svg" font-size="11">
<style>.tx{{fill:{INK};{FS}}}</style>
<rect x="120" y="120" width="200" height="14" fill="#cfe0ef" stroke="{NAVY}" transform="rotate(-12 220 127)"/>
<text class="tx" x="300" y="150" font-size="10" fill="{MUT}">array surface</text>
<line x1="220" y1="127" x2="220" y2="40" stroke="{NAVY}" stroke-width="1.6" stroke-dasharray="4 2"/><text class="tx" x="226" y="50" font-size="10">normal n</text>
<line x1="220" y1="127" x2="120" y2="40" stroke="{AMBER2}" stroke-width="2.4"/><polygon points="120,40 130,44 126,52" fill="{AMBER2}"/><text class="tx" x="96" y="36" fill="{AMBER2}">Sun</text>
<path d="M220 80 A48 48 0 0 0 188 64" fill="none" stroke="{BRICK}" stroke-width="1.4"/><text class="tx" x="186" y="86" fill="{BRICK}">α</text>
<text class="tx" x="60" y="175" fill="{INK}">tilt = cos(α + season_angle) · cos(β)   →   captured light × tilt</text>
</svg>'''

# ----------------------------------------------------------------------------- P5
# 11) hierarchy tree with diodes
P5_11 = f'''<svg width="100%" viewBox="0 0 650 150" xmlns="http://www.w3.org/2000/svg" font-size="11">
<style>.bx{{fill:#eef5fb;stroke:{NAVY};stroke-width:1.4}} .tx{{fill:{INK};{FS}}} .ar{{stroke:{AMBER2};stroke-width:2;fill:none}}</style>
<rect class="bx" x="10" y="58" width="56" height="32" rx="4"/><text class="tx" x="38" y="78" text-anchor="middle">cell</text>
<rect class="bx" x="110" y="50" width="120" height="48" rx="4"/><text class="tx" x="170" y="44" text-anchor="middle" font-size="10">string + bypass∥, blocking⊳</text>
{''.join(f'<rect x="{120+i*20}" y="64" width="13" height="16" fill="#cfe0ef" stroke="{NAVY2}"/>' for i in range(5))}
<polygon points="214,64 222,64 218,58" fill="{BRICK}"/>
<rect class="bx" x="278" y="42" width="140" height="64" rx="4"/><text class="tx" x="348" y="36" text-anchor="middle" font-size="10">section (∥ strings)</text>
{''.join(f'<rect x="288" y="{50+j*18}" width="120" height="12" fill="#cfe0ef" stroke="{NAVY2}"/>' for j in range(3))}
<rect class="bx" x="466" y="34" width="150" height="80" rx="4"/><rect x="478" y="50" width="126" height="50" fill="#fbf4e2" stroke="{AMBER}"/><text class="tx" x="541" y="126" text-anchor="middle" font-size="10">panel → array</text>
{''.join(f'<path class="ar" d="M{a} 74 H{b}"/><polygon points="{b},74 {b-6},70 {b-6},78" fill="{AMBER2}"/>' for a,b in [(70,106),(234,274),(422,462)])}
</svg>'''

# 12) series-with-bypass | parallel-with-blocking
P5_12 = f'''<svg width="100%" viewBox="0 0 470 220" xmlns="http://www.w3.org/2000/svg" font-size="10.5">
<style>.w{{stroke:{INK};stroke-width:1.5;fill:none}} .cell{{fill:#cfe0ef;stroke:{NAVY}}} .tx{{fill:{INK};{FS}}}</style>
<text class="tx" x="105" y="18" text-anchor="middle" fill="{NAVY}">SERIES string — bypass diodes</text>
{''.join(f'<rect class="cell" x="60" y="{30+i*38}" width="46" height="24"/><polygon points="120,{36+i*38} 120,{48+i*38} 132,{42+i*38}" fill="#fbe3df" stroke="{BRICK}"/><line class="w" x1="120" y1="{30+i*38}" x2="120" y2="{54+i*38}"/><line class="w" x1="60" y1="{30+i*38}" x2="40" y2="{30+i*38}"/><line class="w" x1="40" y1="{30+i*38}" x2="40" y2="{54+i*38}"/>' for i in range(4))}
<line class="w" x1="40" y1="30" x2="40" y2="20"/><line class="w" x1="132" y1="42" x2="132" y2="200"/><line class="w" x1="106" y1="42" x2="132" y2="42"/>
<text class="tx" x="138" y="120" fill="{BRICK}" font-size="9">bypass ∥ each cell</text>
<text class="tx" x="350" y="18" text-anchor="middle" fill="{NAVY}">PARALLEL strings — blocking diodes</text>
{''.join(f'<rect class="cell" x="{280+k*60}" y="40" width="34" height="80"/><polygon points="{291+k*60},130 {303+k*60},130 {297+k*60},142" fill="#cfe0ef" stroke="{NAVY}"/><line class="w" x1="{297+k*60}" y1="120" x2="{297+k*60}" y2="130"/><line class="w" x1="{297+k*60}" y1="142" x2="{297+k*60}" y2="170"/>' for k in range(3))}
<line class="w" x1="270" y1="170" x2="420" y2="170"/><text class="tx" x="345" y="186" text-anchor="middle" font-size="9" fill="{MUT}">common bus</text>
<text class="tx" x="345" y="158" text-anchor="middle" font-size="9" fill="{NAVY}">blocking ⊳ in series</text>
</svg>'''

# ----------------------------------------------------------------------------- P6
# 13) reverse-biased failed cell
P6_13 = f'''<svg width="100%" viewBox="0 0 470 210" xmlns="http://www.w3.org/2000/svg" font-size="10.5">
<style>.w{{stroke:{INK};stroke-width:1.6;fill:none}} .cell{{fill:#cfe0ef;stroke:{NAVY}}} .tx{{fill:{INK};{FS}}}</style>
<line class="w" x1="40" y1="30" x2="430" y2="30"/><line class="w" x1="40" y1="180" x2="430" y2="180"/>
{''.join(f'<rect class="cell" x="{70+i*70}" y="60" width="50" height="36"/><line class="w" x1="{95+i*70}" y1="30" x2="{95+i*70}" y2="60"/><line class="w" x1="{95+i*70}" y1="96" x2="{95+i*70}" y2="180"/>' for i in [0,1,3,4])}
<rect x="280" y="60" width="50" height="36" fill="#fbe3df" stroke="{BRICK}" stroke-width="2"/><text class="tx" x="305" y="82" text-anchor="middle" fill="{BRICK}" font-size="9">FAILED</text>
<line class="w" x1="305" y1="30" x2="305" y2="60"/><line class="w" x1="305" y1="96" x2="305" y2="180"/>
<text class="tx" x="305" y="112" text-anchor="middle" fill="{BRICK}" font-size="9">reverse −V → heat</text>
<!-- bypass across failed -->
<polygon points="356,70 356,86 344,78" fill="#fff" stroke="{TEAL}" stroke-width="1.6"/><line stroke="{TEAL}" stroke-width="1.6" x1="350" y1="60" x2="350" y2="70"/><line stroke="{TEAL}" stroke-width="1.6" x1="350" y1="86" x2="350" y2="96"/><line stroke="{TEAL}" x1="330" y1="60" x2="350" y2="60"/><line stroke="{TEAL}" x1="330" y1="96" x2="350" y2="96"/>
<text class="tx" x="360" y="82" fill="{TEAL}" font-size="9">bypass clamps</text>
{''.join(f'<polygon points="{120+i*70},22 {112+i*70},18 {112+i*70},26" fill="{AMBER2}"/>' for i in range(4))}
<text class="tx" x="40" y="200" fill="{MUT}" font-size="9">healthy cells + parallel strings force current → through the failed cell</text>
</svg>'''

# 14) panel cross-section
P6_14 = f'''<svg width="100%" viewBox="0 0 460 175" xmlns="http://www.w3.org/2000/svg" font-size="11">
<style>.tx{{fill:{INK};{FS}}}</style>
<rect x="90" y="30" width="280" height="14" fill="#bfe0ff" stroke="{INK}"/><text class="tx" x="380" y="41" font-size="10">coverglass</text>
<rect x="90" y="44" width="280" height="18" fill="#3b6ea5" stroke="{INK}"/><text class="tx" x="380" y="58" font-size="10" fill="{INK}">solar cell</text>
<rect x="90" y="62" width="280" height="9" fill="#caa" stroke="{INK}"/><text class="tx" x="380" y="70" font-size="10">adhesive</text>
<g stroke="{AMBER2}" fill="#fdf3d6">{''.join(f'<polygon points="{95+i*24},75 {107+i*24},75 {113+i*24},92 {107+i*24},109 {95+i*24},109 {89+i*24},92"/>' for i in range(11))}</g>
<text class="tx" x="380" y="96" font-size="10" fill="{AMBER2}">Al honeycomb</text>
<line x1="230" y1="20" x2="230" y2="62" stroke="{BRICK}" stroke-width="2.4"/><polygon points="230,75 224,62 236,62" fill="{BRICK}"/><text class="tx" x="236" y="22" fill="{BRICK}" font-size="10">hot-spot heat → core</text>
<text class="tx" x="230" y="130" text-anchor="middle" fill="{MUT}" font-size="9">if local T exceeds the aluminium limit → softening / melt</text>
</svg>'''

# ----------------------------------------------------------------------------- P7
# 15) 2-node thermal network
P7_15 = f'''<svg width="100%" viewBox="0 0 470 220" xmlns="http://www.w3.org/2000/svg" font-size="10.5">
<style>.tx{{fill:{INK};{FS}}} .node{{fill:#eef5fb;stroke:{NAVY};stroke-width:1.8}} .arin{{stroke:{AMBER2};stroke-width:2;fill:none}} .arout{{stroke:{BRICK};stroke-width:2;fill:none}}</style>
<circle class="node" cx="170" cy="60" r="30"/><text class="tx" x="170" y="64" text-anchor="middle">T1 front</text>
<circle class="node" cx="170" cy="165" r="30"/><text class="tx" x="170" y="169" text-anchor="middle">T2 rear</text>
<line stroke="{NAVY}" stroke-width="6" x1="170" y1="90" x2="170" y2="135" opacity=".5"/><text class="tx" x="182" y="116" font-size="9">C·A·(T2−T1)</text>
<!-- front inputs/outputs -->
<line class="arin" x1="60" y1="20" x2="150" y2="48"/><polygon points="150,48 140,44 144,54" fill="{AMBER2}"/><text class="tx" x="40" y="20" fill="{AMBER2}" font-size="9">α_F·P_Sun·tilt</text>
<line class="arout" x1="200" y1="40" x2="300" y2="20"/><polygon points="300,20 290,20 296,28" fill="{BRICK}"/><text class="tx" x="305" y="20" fill="{BRICK}" font-size="9">ε_F·σ·T1⁴</text>
<line class="arout" x1="200" y1="60" x2="300" y2="60"/><polygon points="300,60 291,56 291,64" fill="{BRICK}"/><text class="tx" x="305" y="63" fill="#444" font-size="9">P_elec (out)</text>
<!-- rear inputs/outputs -->
<line class="arin" x1="60" y1="200" x2="150" y2="178"/><polygon points="150,178 140,178 145,187" fill="{AMBER2}"/><text class="tx" x="20" y="205" fill="{AMBER2}" font-size="9">α_R·P_Alb + ε_R·P_IR</text>
<line class="arout" x1="200" y1="178" x2="300" y2="200"/><polygon points="300,200 290,196 292,205" fill="{BRICK}"/><text class="tx" x="305" y="203" fill="{BRICK}" font-size="9">ε_R·σ·T2⁴</text>
<text class="tx" x="350" y="120" fill="{MUT}" font-size="9">balance: in − out = 0</text>
</svg>'''

# 16) orbit + umbra
P7_16 = f'''<svg width="100%" viewBox="0 0 470 200" xmlns="http://www.w3.org/2000/svg" font-size="10.5">
<style>.tx{{fill:{INK};{FS}}}</style>
<circle cx="40" cy="100" r="22" fill="{AMBER}"/><text class="tx" x="22" y="138" fill="{AMBER2}">Sun</text>
<circle cx="250" cy="100" r="40" fill="#6b8fb5" stroke="{NAVY}"/><text class="tx" x="250" y="104" text-anchor="middle" fill="#fff">planet</text>
<polygon points="250,62 250,138 460,118 460,82" fill="#33415588"/><text class="tx" x="360" y="104" fill="{INK}" font-size="9">umbra (eclipse)</text>
<ellipse cx="250" cy="100" rx="95" ry="78" fill="none" stroke="{MUT}" stroke-dasharray="4 3"/>
<circle cx="345" cy="100" r="6" fill="{TEAL}"/><text class="tx" x="335" y="86" font-size="9" fill="{TEAL}">sat (in shadow)</text>
<circle cx="155" cy="100" r="6" fill="{TEAL}"/><text class="tx" x="120" y="86" font-size="9" fill="{TEAL}">sat (sunlit)</text>
<line stroke="{AMBER2}" stroke-width="1.6" x1="64" y1="92" x2="150" y2="98"/><line stroke="{AMBER2}" stroke-width="1.6" x1="64" y1="108" x2="150" y2="102"/>
<line stroke="{BRICK}" stroke-width="1.2" x1="210" y1="80" x2="160" y2="96"/><text class="tx" x="196" y="74" font-size="8" fill="{BRICK}">albedo/IR</text>
</svg>'''

# ----------------------------------------------------------------------------- P8
# 17) convergence
rng=np.random.default_rng(7); true=3.5
Ns=np.arange(1,400); samp=rng.uniform(1,6,400); run=np.cumsum(samp)/np.arange(1,401)
cp=pts(Ns,run[1:],1,400,2.0,5.0,55,440,150,20)
band_u=true+2.0/np.sqrt(Ns); band_l=true-2.0/np.sqrt(Ns)
bu=pts(Ns,band_u,1,400,2.0,5.0,55,440,150,20); bl=pts(Ns,band_l,1,400,2.0,5.0,55,440,150,20)
P8_17 = f'''<svg width="100%" viewBox="0 0 470 175" xmlns="http://www.w3.org/2000/svg" font-size="10">
<line stroke="{INK}" x1="55" y1="150" x2="440" y2="150"/><line stroke="{INK}" x1="55" y1="150" x2="55" y2="16"/>
<polyline points="{bu}" fill="none" stroke="{AMBER}" stroke-width="1" stroke-dasharray="3 2"/>
<polyline points="{bl}" fill="none" stroke="{AMBER}" stroke-width="1" stroke-dasharray="3 2"/>
<line x1="55" y1="{150-(true-2.0)/3.0*130:.1f}" x2="440" y2="{150-(true-2.0)/3.0*130:.1f}" stroke="{TEAL}" stroke-width="1.4"/>
<polyline points="{cp}" fill="none" stroke="{NAVY}" stroke-width="1.8"/>
<text {FS} x="245" y="170" text-anchor="middle" fill="{INK}">number of runs N</text>
<text {FS} transform="translate(16,90) rotate(-90)" text-anchor="middle" fill="{INK}">estimate</text>
<text {FS} x="360" y="{150-(true-2.0)/3.0*130-6:.1f}" fill="{TEAL}" font-size="9">true value</text>
<text {FS} x="300" y="40" fill="{AMBER2}" font-size="9">±1/√N band narrows</text>
</svg>'''

# 18) pi darts
rng2=np.random.default_rng(3); xs=rng2.uniform(0,1,260); ys=rng2.uniform(0,1,260); inside=xs*xs+ys*ys<=1
def dot(x,y,ins):
    X=40+x*150; Y=160-y*150
    return f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="2" fill="{TEAL if ins else MUT}" opacity=".8"/>'
pi_est=4*inside.mean()
P8_18 = f'''<svg width="100%" viewBox="0 0 360 185" xmlns="http://www.w3.org/2000/svg" font-size="10">
<rect x="40" y="10" width="150" height="150" fill="#fff" stroke="{INK}"/>
<path d="M40 160 A150 150 0 0 1 190 10" fill="#eaf2f0" stroke="{NAVY}" stroke-width="1.6"/>
{''.join(dot(x,y,i) for x,y,i in zip(xs,ys,inside))}
<text {FS} x="210" y="60" fill="{INK}">inside ≈ π/4</text>
<text {FS} x="210" y="80" fill="{INK}">π ≈ 4 · inside/total</text>
<text {FS} x="210" y="104" fill="{TEAL}">est ≈ {pi_est:.3f}</text>
<text {FS} x="210" y="124" fill="{MUT}" font-size="9">(260 darts)</text>
</svg>'''

FIGS = {
 "_frag_P1.html":[fig(P1_1,"Figure 1.1 — From one cell up to a panel: cells in series make a string, strings in parallel make a section, sections mount on a panel."),
                  fig(P1_2,"Figure 1.2 — A triple-junction space cell: three stacked sub-cells in series capture different parts of the spectrum."),
                  fig(P1_3,"Figure 1.3 — The IV curve (navy) and the power curve P=V·I (red, dashed). Power is zero at Isc and Voc and peaks at the Maximum Power Point.")],
 "_frag_P2.html":[fig(P2_4,"Figure 2.1 — The single-diode equivalent circuit: a photocurrent source in parallel with the junction diode and a shunt resistor, then a series resistor to the terminals."),
                  fig(P2_5,"Figure 2.2 — The diode current rises exponentially: nearly flat, then a sharp knee. This bend shapes the IV curve near Voc."),
                  fig(P2_6,"Figure 2.3 — The ngspice subcircuit built by cellBuilder, between terminals high and low.")],
 "_frag_P3.html":[fig(P3_7,"Figure 3.1 — Left: remaining factors fall with accumulated radiation dose. Right: open-circuit voltage rises as the cell gets colder."),
                  fig(P3_8,"Figure 3.2 — The prepareModel pipeline: base numbers are scaled by the dose remaining factor, shifted by temperature, then corrected for losses and season.")],
 "_frag_P4.html":[fig(P4_9,"Figure 4.1 — The four season multipliers around AM0 = 1.0. Summer Solstice (SS) is the WEAKER sun because Earth is farther away."),
                  fig(P4_10,"Figure 4.2 — Pointing geometry: only the cosine of the incidence angle reaches the array (the tilt factor).")],
 "_frag_P5.html":[fig(P5_11,"Figure 5.1 — The PowerPy object hierarchy, each level forwarding commands to its children."),
                  fig(P5_12,"Figure 5.2 — Two different diodes: a bypass diode across every cell (left) versus a blocking diode in series with each string feeding the bus (right).")],
 "_frag_P6.html":[fig(P6_13,"Figure 6.1 — A failed cell is driven into reverse bias by the surrounding cells and parallel strings; the bypass diode clamps it and carries the current around."),
                  fig(P6_14,"Figure 6.2 — The panel sandwich. A hot-spot drives heat into the aluminium honeycomb core, which can soften or melt.")],
 "_frag_P7.html":[fig(P7_15,"Figure 7.1 — The two-node thermal model: absorbed fluxes in (amber), radiated emission and extracted electrical power out (red), conduction between front and rear."),
                  fig(P7_16,"Figure 7.2 — Around the orbit the array passes through the planet's umbra (eclipse) where the Sun is blocked; albedo and infrared come from the planet.")],
 "_frag_P8.html":[fig(P8_17,"Figure 8.1 — A Monte-Carlo estimate wanders at small N and settles onto the true value; the ±1/√N error band narrows slowly."),
                  fig(P8_18,"Figure 8.2 — Estimating π by random darts: the fraction inside the quarter circle approaches π/4.")],
}

base=os.path.dirname(os.path.abspath(__file__))
total=0
for fname, svgs in FIGS.items():
    path=os.path.join(base,fname)
    with open(path,encoding="utf-8") as f: html=f.read()
    it=iter(svgs)
    def repl(m):
        global total
        try:
            s=next(it); total+=1; return s
        except StopIteration:
            return m.group(0)
    html2=re.sub(r"<!--FIG:.*?-->", repl, html, flags=re.S)
    with open(path,"w",encoding="utf-8") as f: f.write(html2)
    n=len(svgs)
    print(f"{fname}: injected {n} figures")
print("TOTAL injected:", total)
print("pi_est=",round(pi_est,3),"Pmp=",round(Pmp,3),"Vmp=",round(Vmp,3),"Imp=",round(Imp,3))
