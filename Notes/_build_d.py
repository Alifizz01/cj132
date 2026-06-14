# -*- coding: utf-8 -*-
"""Assemble the Software Design & Performance PDF."""
import os
base=os.path.dirname(os.path.abspath(__file__))
def R(n):
    with open(os.path.join(base,n),encoding="utf-8") as f: return f.read()
SECTIONS=[
 ("1","What Software Design Is, and the Principles That Matter","_frag_D1.html"),
 ("2","Structuring a Python Module and Package Well","_frag_D2.html"),
 ("3","Writing Functions and Classes That Are Clear and Correct","_frag_D3.html"),
 ("4","Making It Fast: Performance and Time-Efficiency","_frag_D4.html"),
 ("5","Testing, Reproducibility, and Trusting Your Results","_frag_D5.html"),
 ("6","A Concrete Improvement Roadmap for PowerPy","_frag_D6.html"),
]
HEAD='''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Software Design & Performance for PowerPy</title>
<link rel="stylesheet" href="print-base.css">
<link rel="stylesheet" href="design.css">
</head><body>'''
OPENER='''<section class="chapter-opener">
<div class="booktitle">PowerPy · A Solar-Array Engineer's Handbook</div>
<h1>Software Design<br>&amp; Performance</h1>
<div class="subtitle">How to design the program, structure the Python, write better functions, make it
fast, test it, and improve PowerPy — for an engineer who can code but hasn't studied software design.</div>
<p class="lede">The two physics chapters taught what PowerPy computes. This companion teaches how to
build it <em>well</em>: how to split a program into parts that stay understandable and changeable, how
to lay out a Python package, how to write functions that are clear and correct, how to make the slow
parts fast (the same vectorisation that powers Chapter&nbsp;2), how to test scientific code so you can
trust it, and finally a prioritised roadmap to bring PowerPy itself up to that standard.</p>
<p>Everything is grounded in PowerPy's real situation: a clean modern core (the
<code>schemas/loader/simulation/render</code> subpackages) alongside a fragile legacy of large,
multi-job files — including a genuine module-shadowing bug and a per-cell solver loop we can make
~100× faster. Worked examples, ladders of questions, and practice run throughout.</p>
<div class="meta">Generated for izzuwan · Companion to Chapters 1 &amp; 2 and the design spec. Print on A4.</div>
</section>'''
def toc():
    items="".join(f'<li><span class="sec-num">{n}</span> {t}</li>' for n,t,_ in SECTIONS)
    return f'''<section class="toc"><h2>Contents</h2><ol>
<li><strong>Words you need first</strong> — the design vocabulary</li>
{items}
<li><strong>Glossary</strong> — every term</li>
<li><strong>Worked solutions</strong> — answers to all practice questions</li>
</ol></section>'''
FOUND='''<section class="page-break sec">
<h2>Words You Need First</h2>
<p class="lede">A little vocabulary makes the rest read easily. Meet these once; each is explained in
full where it is used, and all are in the Glossary.</p>
<div class="term"><span class="lbl">Software design</span> Deciding how to split a program into parts and
how those parts talk — done so the program stays understandable and easy to change.</div>
<div class="term"><span class="lbl">Module &amp; package</span> A <em>module</em> is one <code>.py</code> file; a
<em>package</em> is a folder of modules with an <code>__init__.py</code>. PowerPy is a package.</div>
<div class="term"><span class="lbl">Cohesion &amp; coupling</span> Cohesion = how focused one part is on a single job
(high is good); coupling = how dependent parts are on each other (low is good). The whole aim: high
cohesion, low coupling.</div>
<div class="term"><span class="lbl">Separation of concerns</span> Keep different kinds of job — loading data,
doing the maths, drawing output — in different parts.</div>
<div class="term"><span class="lbl">Encapsulation / interface</span> A part exposes a small, stable set of
methods (its interface) and hides its internals, so the inside can change without breaking callers.</div>
<div class="term"><span class="lbl">Pure function</span> A function whose output depends only on its inputs, with
no hidden side effects — the easiest kind to test and reason about.</div>
<div class="term"><span class="lbl">Dataclass &amp; type hint</span> A <code>@dataclass</code> bundles named fields
together (instead of a bare tuple/dict); a type hint annotates expected types. Both prevent bugs.</div>
<div class="term"><span class="lbl">Vectorisation</span> Replacing a Python loop over array elements with one numpy
array operation that runs in fast compiled code — the key performance lever for scientific Python.</div>
<div class="term"><span class="lbl">Big-O</span> Shorthand for how a program's runtime grows with input size
N (O(N), O(N²), O(2ᴺ) …). The algorithm's Big-O usually matters more than any micro-tweak.</div>
<div class="term"><span class="lbl">Profiling</span> Measuring where a program actually spends its time, so you
optimise the real hot spot instead of guessing.</div>
<div class="term"><span class="lbl">Unit test &amp; parity test</span> A unit test checks one function against a known
answer; a parity test checks a new implementation matches a trusted one on the same input.</div>
<div class="term"><span class="lbl">Refactor</span> Improving the structure of code <em>without</em> changing what it
does — safest done under the protection of tests.</div>
</section>'''
GLOSS='''<section class="page-break sec"><h2>Glossary</h2><div class="glossary">
<div class="glossary-entry"><span class="gt">Abstraction</span> programming to "what" not "how" (e.g. a Substrate object vs a raw dict).</div>
<div class="glossary-entry"><span class="gt">Big-O</span> how runtime grows with input size N; the dominant scaling term.</div>
<div class="glossary-entry"><span class="gt">Batching / amortising</span> doing expensive setup once for many items (e.g. one ngspice run).</div>
<div class="glossary-entry"><span class="gt">CI (Continuous Integration)</span> automatically running tests on every change.</div>
<div class="glossary-entry"><span class="gt">Cohesion</span> how focused a module is on one job (high = good).</div>
<div class="glossary-entry"><span class="gt">Coupling</span> how dependent modules are on each other (low = good).</div>
<div class="glossary-entry"><span class="gt">cProfile</span> Python's profiler; shows time spent per function.</div>
<div class="glossary-entry"><span class="gt">Dataclass</span> @dataclass — bundles named fields; safer than a bare tuple/dict.</div>
<div class="glossary-entry"><span class="gt">Docstring</span> a function/class's built-in description of what it does and returns.</div>
<div class="glossary-entry"><span class="gt">DRY</span> Don't Repeat Yourself — one source of truth, no copy-paste drift.</div>
<div class="glossary-entry"><span class="gt">Encapsulation</span> hiding internals behind a small public interface.</div>
<div class="glossary-entry"><span class="gt">Fixture</span> shared, reusable test input built once for many tests.</div>
<div class="glossary-entry"><span class="gt">GIL</span> Global Interpreter Lock — one thread runs Python at a time; use processes for CPU work.</div>
<div class="glossary-entry"><span class="gt">Integration test</span> checks several parts working together.</div>
<div class="glossary-entry"><span class="gt">Memoisation</span> caching a result to avoid recomputing it.</div>
<div class="glossary-entry"><span class="gt">Module / package</span> a .py file / a folder of modules with __init__.py.</div>
<div class="glossary-entry"><span class="gt">Oracle</span> a trusted source of the expected answer for a test.</div>
<div class="glossary-entry"><span class="gt">Parity test</span> checks a new implementation matches a trusted one.</div>
<div class="glossary-entry"><span class="gt">PEP 8</span> Python's official style guide (snake_case, CapWords, etc.).</div>
<div class="glossary-entry"><span class="gt">Profiling</span> measuring where time is actually spent before optimising.</div>
<div class="glossary-entry"><span class="gt">Pure function</span> output depends only on inputs; no side effects.</div>
<div class="glossary-entry"><span class="gt">pytest</span> the common Python test runner.</div>
<div class="glossary-entry"><span class="gt">Refactor</span> improve structure without changing behaviour.</div>
<div class="glossary-entry"><span class="gt">Regression test</span> pins current correct output against future change.</div>
<div class="glossary-entry"><span class="gt">Separation of concerns</span> different jobs live in different parts.</div>
<div class="glossary-entry"><span class="gt">Shadowing</span> a local module hiding a standard-library one of the same name.</div>
<div class="glossary-entry"><span class="gt">Single Responsibility</span> one part, one reason to change.</div>
<div class="glossary-entry"><span class="gt">Type hint</span> annotation of expected types; documents and catches mistakes.</div>
<div class="glossary-entry"><span class="gt">Vectorisation</span> one numpy array op replacing a Python element loop.</div>
<div class="glossary-entry"><span class="gt">YAGNI / DRY</span> don't build speculative features / don't repeat yourself.</div>
</div></section>'''
parts=[HEAD,OPENER,toc(),FOUND]
for n,t,frag in SECTIONS:
    parts.append(f'<section class="page-break sec"><h2><span class="sec-num">{n}</span>{t}</h2>')
    parts.append(R(frag)); parts.append('</section>')
parts.append(GLOSS)
sol=['<section class="solutions"><h2>Worked Solutions</h2>',
     '<p class="small">Full answers to every practice question. Try first, then check.</p>']
for n,t,frag in SECTIONS:
    sol.append(f'<h3>Section {n} — {t}</h3>'); sol.append(R(frag.replace("_frag_","_sol_")))
sol.append('</section>'); parts.extend(sol); parts.append('</body></html>')
out=os.path.join(base,"Software_Design_and_Performance.html")
open(out,"w",encoding="utf-8").write("\n".join(parts))
print("wrote",out,"chars=",sum(len(p) for p in parts))
