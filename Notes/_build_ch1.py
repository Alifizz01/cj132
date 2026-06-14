# -*- coding: utf-8 -*-
"""Assemble Chapter 1 into one self-contained HTML from the _frag_P*.html fragments
and _sol_P*.html solutions, wrapping each with section headers, a chapter opener,
contents, a foundations section, and a glossary."""
import os
base=os.path.dirname(os.path.abspath(__file__))
def R(n):
    with open(os.path.join(base,n),encoding="utf-8") as f: return f.read()

SECTIONS=[
 ("1","Why a Solar Array — and the Four Numbers of a Cell","_frag_P1.html"),
 ("2","The Equivalent Circuit, Model Fitting, and SPICE","_frag_P2.html"),
 ("3","The Cell Over Its Life: Temperature and Radiation","_frag_P3.html"),
 ("4","Losses, Seasons, Pointing, and the Voltage Corrections","_frag_P4.html"),
 ("5","From Cell to Array: SCA, the Hierarchy, and the Two Diodes","_frag_P5.html"),
 ("6","Reverse Bias, Hot-Spots, and Substrate Damage","_frag_P6.html"),
 ("7","The Space Thermal Environment and the 2-Node Model","_frag_P7.html"),
 ("8","Monte Carlo: Estimating the Unknowable","_frag_P8.html"),
]

HEAD='''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>PowerPy — Solar-Array Engineer's Handbook · Chapter 1</title>
<link rel="stylesheet" href="print-base.css">
<link rel="stylesheet" href="design.css">
</head><body>'''

OPENER='''<section class="chapter-opener">
<div class="booktitle">PowerPy · A Solar-Array Engineer's Handbook</div>
<h1>Chapter 1<br>The Framework</h1>
<div class="subtitle">Solar cells, assemblies, the simulation hierarchy, the space thermal
environment, and Monte-Carlo reliability — taught from the ground up.</div>
<p class="lede">This chapter builds you, step by step, into someone who can read, run and reason
about the PowerPy solar-array simulator. We start with a single solar cell and the four numbers
that describe it, learn how PowerPy turns those into an electrical circuit it can simulate, stack
cells into strings, sections and panels, add the losses and seasons of real spaceflight, see how a
single failed cell can overheat and damage the panel, work out how hot the array gets in orbit, and
finish with the idea of Monte-Carlo analysis that underpins the failure study in Chapter&nbsp;2.</p>
<p>Every hard term is defined the moment it appears and again in the glossary; every formula has its
symbols named; every important idea gets a worked example at human pace and a short ladder of
questions you can try before reading the answer. Practice questions are woven throughout — attempt
them on the printout, then check the worked solutions at the back.</p>
<div class="meta">Generated for izzuwan · Source: the PowerPy codebase (<code>cell</code>, <code>string</code>,
<code>section</code>, <code>panel</code>, <code>thermal</code>, <code>electric</code>). Print on A4.</div>
</section>'''

def toc():
    items="".join(f'<li><span class="sec-num">{n}</span> {t}</li>' for n,t,_ in SECTIONS)
    return f'''<section class="toc">
<h2>Contents</h2>
<ol>
<li><strong>Words you need first</strong> — foundations &amp; key terms</li>
{items}
<li><strong>Glossary</strong> — every term and acronym</li>
<li><strong>Worked solutions</strong> — answers to all practice questions</li>
</ol>
</section>'''

FOUND='''<section class="page-break sec">
<h2>Words You Need First</h2>
<p class="lede">Before the topics, here are the core words in plain language. Don't memorise them —
just meet them once, so they aren't fog when we use them. Each returns, fully explained, in its
own section, and all of them are collected in the Glossary at the back.</p>
<div class="term"><span class="lbl">Photovoltaic (PV) effect</span> Light knocks electrons loose in a
semiconductor and drives them as a current. A <em>solar cell</em> is one such light-to-electricity device.</div>
<div class="term"><span class="lbl">The four numbers</span> <strong>Isc</strong> (short-circuit current, at 0&nbsp;V),
<strong>Voc</strong> (open-circuit voltage, at 0&nbsp;A), and the <strong>MPP</strong> (Maximum Power Point,
the voltage/current pair <strong>Vmp, Imp</strong> where power V·I is greatest). They summarise a cell.</div>
<div class="term"><span class="lbl">IV curve</span> The graph of current against voltage for a cell or
array. Its shape is what PowerPy ultimately computes.</div>
<div class="term"><span class="lbl">SCA — Solar Cell Assembly</span> One manufactured unit: a cell with its
coverglass and interconnects, ready to lay on a panel. Many SCAs wire together into the array.</div>
<div class="term"><span class="lbl">Series vs parallel</span> In <em>series</em> (end to end) voltages add and the
current is shared; in <em>parallel</em> (side by side) currents add and the voltage is shared. This one
rule drives the whole hierarchy.</div>
<div class="term"><span class="lbl">AM0 — Air Mass Zero</span> The strength of sunlight in space at the
Earth's distance: <strong>1367&nbsp;W/m²</strong>. PowerPy's reference irradiance.</div>
<div class="term"><span class="lbl">BOL / EOL</span> Beginning- and End-Of-Life — the cell when fresh versus
after years of space <em>radiation dose</em> has degraded it.</div>
<div class="term"><span class="lbl">α and ε (alpha, epsilon)</span> A surface's solar <em>absorptivity</em>
(how much sunlight it soaks up) and its infrared <em>emissivity</em> (how well it radiates heat away).
They set the temperature.</div>
<div class="term"><span class="lbl">Bypass vs blocking diode</span> A <em>bypass</em> diode sits across a cell to
carry current around it if it fails (preventing a hot-spot); a <em>blocking</em> diode sits in series with a
string to stop current flowing backwards into it. Two different jobs.</div>
<div class="term"><span class="lbl">Reverse bias &amp; hot-spot</span> When a weak cell is forced to pass current it
cannot make, its voltage goes negative and it turns the others' power into heat — a hot-spot that can
damage the panel.</div>
<div class="term"><span class="lbl">ngspice</span> The circuit-simulation engine PowerPy writes netlists for and
runs to solve the array's electrical behaviour.</div>
<div class="term"><span class="lbl">Monte Carlo</span> Estimating a hard quantity by running many random
trials and averaging — here, random cell-failure patterns to find which are most damaging.</div>
</section>'''

GLOSS='''<section class="page-break sec">
<h2>Glossary</h2>
<div class="glossary">
<div class="glossary-entry"><span class="gt">Albedo</span> Sunlight reflected off a planet onto the array (a heat input).</div>
<div class="glossary-entry"><span class="gt">AM0 (Air Mass Zero)</span> Solar irradiance in space at 1 AU = 1367 W/m²; PowerPy constant B_0.</div>
<div class="glossary-entry"><span class="gt">Absorptivity (α)</span> Fraction of incident sunlight a surface absorbs (0–1).</div>
<div class="glossary-entry"><span class="gt">Blocking diode</span> Diode in series with a string; blocks reverse current flowing back into it.</div>
<div class="glossary-entry"><span class="gt">BOL / EOL</span> Beginning / End Of Life — cell before and after the mission's radiation dose.</div>
<div class="glossary-entry"><span class="gt">Bypass (shunt) diode</span> Diode across a cell/group; conducts if the cell is reverse-biased, protecting it.</div>
<div class="glossary-entry"><span class="gt">cell</span> PowerPy object for one solar cell; holds config + regressors and builds a SPICE subcircuit.</div>
<div class="glossary-entry"><span class="gt">Dose (1 MeV e⁻ fluence)</span> Single number standing for the radiation damage a cell has received.</div>
<div class="glossary-entry"><span class="gt">Emissivity (ε)</span> How well a surface radiates infrared heat (0–1).</div>
<div class="glossary-entry"><span class="gt">Fill Factor (FF)</span> Pmp/(Voc·Isc); how "square" the IV curve is (good cells ~0.8).</div>
<div class="glossary-entry"><span class="gt">Hot-spot</span> A small reverse-biased region forced to dissipate many cells' power as heat.</div>
<div class="glossary-entry"><span class="gt">Imp / Vmp / Pmp</span> Current, voltage and power at the Maximum Power Point.</div>
<div class="glossary-entry"><span class="gt">Isc</span> Short-circuit current (terminals shorted, V = 0).</div>
<div class="glossary-entry"><span class="gt">IV curve</span> Current-versus-voltage characteristic of a cell or array.</div>
<div class="glossary-entry"><span class="gt">Loss factor</span> A multiplier (e.g. 0.98) capturing a current or voltage loss; PowerPy multiplies them.</div>
<div class="glossary-entry"><span class="gt">Monte Carlo</span> Estimating via many random trials; error shrinks like 1/√N.</div>
<div class="glossary-entry"><span class="gt">MPP</span> Maximum Power Point — where V·I is greatest on the IV curve.</div>
<div class="glossary-entry"><span class="gt">ngspice</span> Circuit simulator PowerPy drives via NgSpiceShared.</div>
<div class="glossary-entry"><span class="gt">Panel</span> PowerPy object: sections on a substrate, carrying area and thermal behaviour.</div>
<div class="glossary-entry"><span class="gt">Planetary IR</span> Infrared glow of a warm planet absorbed by the array (a heat input).</div>
<div class="glossary-entry"><span class="gt">prepareModel</span> cell method that assembles isc/imp/vmp/voc at the current dose & temperature.</div>
<div class="glossary-entry"><span class="gt">Regressor</span> A stored lookup curve (temperature coefficient or remaining factor) vs dose.</div>
<div class="glossary-entry"><span class="gt">Remaining factor (r_*)</span> Fraction of a BOL value left after a given dose.</div>
<div class="glossary-entry"><span class="gt">Reverse bias</span> A cell forced to negative voltage, acting as a load (dissipating heat).</div>
<div class="glossary-entry"><span class="gt">RSeriesModel / RShuntModel</span> Two ways PowerPy fits the diode circuit from the four numbers.</div>
<div class="glossary-entry"><span class="gt">RSS loss</span> Root-Sum-Square combination of independent loss uncertainties: 1−√Σ(1−l)².</div>
<div class="glossary-entry"><span class="gt">SCA</span> Solar Cell Assembly — cell + coverglass + interconnects.</div>
<div class="glossary-entry"><span class="gt">Season</span> Irradiance multiplier vs AM0 (SS 0.967, AEX 0.993, VEX 1.008, WS 1.034; 0 = dead).</div>
<div class="glossary-entry"><span class="gt">Section</span> PowerPy object: strings wired in parallel.</div>
<div class="glossary-entry"><span class="gt">Stefan–Boltzmann</span> Radiated power = ε·σ·A·T⁴ (σ = 5.67×10⁻⁸ W/m²K⁴, T in kelvin).</div>
<div class="glossary-entry"><span class="gt">String</span> PowerPy object: cells wired in series, plus blocking diode(s).</div>
<div class="glossary-entry"><span class="gt">Substrate</span> The panel board; JSON file of α, ε, conductivity, thickness for the thermal model.</div>
<div class="glossary-entry"><span class="gt">Tilt</span> cos of the Sun-incidence angle: cos(α+season_angle)·cos(β); 1 when square-on.</div>
<div class="glossary-entry"><span class="gt">Thermal equilibrium</span> Temperature where heat in = heat out; PowerPy solves it per panel.</div>
<div class="glossary-entry"><span class="gt">Voc / Isc temperature coeff.</span> dV/dT (negative) and dI/dT (small positive) of the cell.</div>
</div>
</section>'''

parts=[HEAD,OPENER,toc(),FOUND]
for n,t,frag in SECTIONS:
    parts.append(f'<section class="page-break sec"><h2><span class="sec-num">{n}</span>{t}</h2>')
    parts.append(R(frag))
    parts.append('</section>')
parts.append(GLOSS)
# solutions
sol=['<section class="solutions"><h2>Worked Solutions</h2>',
     '<p class="small">Full reasoned answers to every practice question. Try each question on the printout first, then check here.</p>']
for n,t,frag in SECTIONS:
    soln=frag.replace("_frag_","_sol_")
    sol.append(f'<h3>Section {n} — {t}</h3>')
    sol.append(R(soln))
sol.append('</section>')
parts.extend(sol)
parts.append('</body></html>')

out=os.path.join(base,"Chapter1_Solar_Array_Framework.html")
with open(out,"w",encoding="utf-8") as f: f.write("\n".join(parts))
print("wrote",out,"chars=",sum(len(p) for p in parts))
