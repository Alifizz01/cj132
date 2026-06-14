# -*- coding: utf-8 -*-
"""Assemble Chapter 2 into one self-contained HTML."""
import os
base=os.path.dirname(os.path.abspath(__file__))
def R(n):
    with open(os.path.join(base,n),encoding="utf-8") as f: return f.read()

SECTIONS=[
 ("1","The Customizable Circuit Class","_frag_Q1.html"),
 ("2","Vectorising the Thermal Solve","_frag_Q2.html"),
 ("3","The Electro-Thermal Coupling Loop","_frag_Q3.html"),
 ("4","Orbit-Driven Fluxes with hapsira","_frag_Q4.html"),
 ("5","Breakdown and Melt Criteria","_frag_Q5.html"),
 ("6","The Monte-Carlo Failure Sweep","_frag_Q6.html"),
 ("7","Representing and Storing the Results","_frag_Q7.html"),
 ("8","The Full Pipeline, End to End","_frag_Q8.html"),
]
HEAD='''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>PowerPy — Solar-Array Engineer's Handbook · Chapter 2</title>
<link rel="stylesheet" href="print-base.css">
<link rel="stylesheet" href="design.css">
</head><body>'''
OPENER='''<section class="chapter-opener">
<div class="booktitle">PowerPy · A Solar-Array Engineer's Handbook</div>
<h1>Chapter 2<br>The New Implementation</h1>
<div class="subtitle">A parametric circuit you can fail one cell at a time, a vectorised
electro-thermal solver, orbit-driven fluxes, and a Monte-Carlo hot-spot study — derived in full.</div>
<p class="lede">Chapter 1 built the framework. This chapter designs what we are <em>adding</em> to it: a
customizable <code>Circuit</code> class whose every cell is individually addressable, a thermal
solver that drops the per-cell <code>fsolve</code> loop for a single vectorised Newton step over the
whole array, an electro-thermal loop that makes electricity and temperature agree, hapsira-driven
orbit fluxes, explicit breakdown criteria, and a three-mode Monte-Carlo failure sweep with a sane way
to store and present the results. Every equation is derived, every worked number is verified, and
each idea is built up through a ladder of questions.</p>
<p>Where Chapter 1 leaned on given facts, here we do the mathematics: the 2-node Jacobian, why the
solve vectorises, why the coupling iterates, and how a single failed cell reaches a quantified
187&nbsp;°C hot-spot. Read it with Chapter 1 beside you — the cross-references point back to it.</p>
<div class="meta">Generated for izzuwan · Companion to the design spec
<code>2026-06-07-customized-circuit-thermal-design.md</code>. Print on A4.</div>
</section>'''
def toc():
    items="".join(f'<li><span class="sec-num">{n}</span> {t}</li>' for n,t,_ in SECTIONS)
    return f'''<section class="toc"><h2>Contents</h2><ol>
<li><strong>Words you need first</strong> — the new vocabulary</li>
{items}
<li><strong>Glossary</strong> — every new term</li>
<li><strong>Worked solutions</strong> — answers to all practice questions</li>
</ol></section>'''
FOUND='''<section class="page-break sec">
<h2>Words You Need First</h2>
<p class="lede">Chapter 2 adds some mathematical and software vocabulary on top of Chapter 1. Meet
these once here; each is fully explained where it is used, and all are in the Glossary.</p>
<div class="term"><span class="lbl">Recursion</span> A structure (or function) defined in terms of smaller
copies of itself. Our circuit is a <em>tree</em>: a group made of groups, made of … cells.</div>
<div class="term"><span class="lbl">Series / parallel composition</span> The one electrical rule from Chapter 1,
now made a <em>parameter</em> at every level: voltages add in series, currents add in parallel.</div>
<div class="term"><span class="lbl">Residual</span> The left-over of an equation written as "something = 0". If
<em>f(T)=0</em> at the answer, then <em>f</em> at a guess is the residual — how wrong the guess is.</div>
<div class="term"><span class="lbl">Newton–Raphson</span> A method to drive a residual to zero by repeatedly
following the function's slope (its derivative) to its zero-crossing. It converges very fast (the
correct digits roughly double each step).</div>
<div class="term"><span class="lbl">Jacobian</span> For a system of equations in several unknowns, the table of
all partial derivatives (how each equation responds to each unknown). It is the multi-variable
"slope" Newton's method needs.</div>
<div class="term"><span class="lbl">Vectorised</span> Doing the same arithmetic on a whole array at once with a
single compiled operation (numpy), instead of a slow Python loop over the elements.</div>
<div class="term"><span class="lbl">Fixed point / self-consistent</span> A state that maps to itself: feed it in,
run the model, get the same state out. The electro-thermal loop hunts for one.</div>
<div class="term"><span class="lbl">hapsira</span> The maintained astrodynamics (orbit-mathematics) library we
use to propagate the orbit and compute sun, eclipse, albedo and infrared fluxes over time.</div>
<div class="term"><span class="lbl">Breakdown criteria</span> The explicit rules — a temperature limit AND a
reverse-power limit — that decide when a cell counts as destroyed.</div>
<div class="term"><span class="lbl">Monte-Carlo modes</span> Three ways to choose which failures to simulate:
position sweep, count sweep, and random sampling.</div>
<div class="term"><span class="lbl">Long format &amp; Parquet</span> Storing results as one row per (run, cell) in a
compact columnar file — the source of truth, with Excel as a generated summary.</div>
</section>'''
GLOSS='''<section class="page-break sec"><h2>Glossary</h2><div class="glossary">
<div class="glossary-entry"><span class="gt">Block</span> modules_per_block modules combined (default series) toward the bus voltage.</div>
<div class="glossary-entry"><span class="gt">Block-diagonal</span> a matrix made of independent small blocks on the diagonal, zeros off it.</div>
<div class="glossary-entry"><span class="gt">Breakdown criterion</span> temperature limit OR reverse-power limit; either trips ⇒ cell destroyed.</div>
<div class="glossary-entry"><span class="gt">Circuit (class)</span> the new parametric, per-cell-addressable array object.</div>
<div class="glossary-entry"><span class="gt">Count sweep</span> Monte-Carlo mode varying the number of simultaneous failures.</div>
<div class="glossary-entry"><span class="gt">Damping / under-relaxation</span> taking a partial update step (ω<1) for stability.</div>
<div class="glossary-entry"><span class="gt">Embarrassingly parallel</span> independent tasks that run concurrently with no shared state.</div>
<div class="glossary-entry"><span class="gt">Fault injection</span> circuit.fail(id, mode) — plant a failure at a chosen cell.</div>
<div class="glossary-entry"><span class="gt">Fixed point</span> a self-consistent state the coupled loop converges to.</div>
<div class="glossary-entry"><span class="gt">hapsira</span> astrodynamics library for orbit propagation and flux geometry.</div>
<div class="glossary-entry"><span class="gt">HDF5 / Parquet</span> compact binary table/array formats used as the results source of truth.</div>
<div class="glossary-entry"><span class="gt">Jacobian</span> matrix of partial derivatives; the multivariate slope for Newton's method.</div>
<div class="glossary-entry"><span class="gt">Line</span> cells_per_line cells in series.</div>
<div class="glossary-entry"><span class="gt">Long format</span> one table row per (run, cell); easy to filter and aggregate.</div>
<div class="glossary-entry"><span class="gt">Module</span> lines_parallel lines in parallel (the "two parallel circuits").</div>
<div class="glossary-entry"><span class="gt">Newton–Raphson</span> iterate x ← x − J⁻¹f(x); quadratic convergence near the root.</div>
<div class="glossary-entry"><span class="gt">Position sweep</span> Monte-Carlo mode failing each location in turn to find the worst.</div>
<div class="glossary-entry"><span class="gt">Propagation</span> predicting a satellite's future position from its state and gravity.</div>
<div class="glossary-entry"><span class="gt">Recursion / tree</span> a structure made of smaller copies of itself; our topology.</div>
<div class="glossary-entry"><span class="gt">Residual</span> the value of f at a guess when the equation is f = 0.</div>
<div class="glossary-entry"><span class="gt">Reverse-power criterion</span> |V·I| with V<0 exceeding a per-cell limit.</div>
<div class="glossary-entry"><span class="gt">Seed</span> the starting value of the random generator; fixes reproducibility.</div>
<div class="glossary-entry"><span class="gt">Standard error</span> spread of an estimated mean; falls like s/√N.</div>
<div class="glossary-entry"><span class="gt">Vectorised</span> one array operation replacing a Python element loop.</div>
<div class="glossary-entry"><span class="gt">View factor</span> fraction of a surface's view occupied by another (sets albedo/IR).</div>
</div></section>'''
parts=[HEAD,OPENER,toc(),FOUND]
for n,t,frag in SECTIONS:
    parts.append(f'<section class="page-break sec"><h2><span class="sec-num">{n}</span>{t}</h2>')
    parts.append(R(frag)); parts.append('</section>')
parts.append(GLOSS)
sol=['<section class="solutions"><h2>Worked Solutions</h2>',
     '<p class="small">Full reasoned answers to every Chapter 2 practice question. Try first, then check.</p>']
for n,t,frag in SECTIONS:
    sol.append(f'<h3>Section {n} — {t}</h3>'); sol.append(R(frag.replace("_frag_","_sol_")))
sol.append('</section>'); parts.extend(sol); parts.append('</body></html>')
out=os.path.join(base,"Chapter2_New_Implementation.html")
open(out,"w",encoding="utf-8").write("\n".join(parts))
print("wrote",out,"chars=",sum(len(p) for p in parts))
