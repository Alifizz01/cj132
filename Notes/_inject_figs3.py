# -*- coding: utf-8 -*-
"""Inline-SVG figures for the Software Design & Performance PDF."""
import re, os
NAVY="#0b3d63"; NAVY2="#11507a"; AMBER="#c9a227"; AMBER2="#b9851a"
BRICK="#9a3b3b"; TEAL="#1f6a6a"; INK="#1d2733"; MUT="#5d6b79"; RULE="#cfd7df"; GREEN="#3f7a4f"
FS='font-family="Segoe UI,Arial,sans-serif"'
def fig(svg,cap): return '<figure class="fig-frame">\n'+svg+'\n<figcaption>'+cap+'</figcaption></figure>'

D1_1=f'''<svg width="100%" viewBox="0 0 470 220" xmlns="http://www.w3.org/2000/svg" font-size="9.5">
<style>.tx{{fill:{INK};{FS}}}</style>
<text class="tx" x="105" y="16" text-anchor="middle" fill="{BRICK}" font-weight="bold">monolith — low cohesion</text>
<rect x="40" y="40" width="130" height="150" rx="5" fill="#fcefea" stroke="{BRICK}" stroke-width="1.6"/>
<text class="tx" x="105" y="60" text-anchor="middle" font-weight="bold">cell.py</text>
{''.join(f'<text class="tx" x="105" y="{80+i*18}" text-anchor="middle" font-size="9">{t}</text>' for i,t in enumerate(["loads files","parameter maths","builds netlist","runs ngspice","plots"]))}
{''.join(f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="{MUT}"/>' for a,b,c,d in [(20,70,40,70),(20,110,40,110),(20,150,40,150),(170,70,200,70),(170,150,200,150)])}
<text class="tx" x="360" y="16" text-anchor="middle" fill="{GREEN}" font-weight="bold">layered — high cohesion, low coupling</text>
{''.join(f'<rect x="290" y="{40+i*36}" width="150" height="26" rx="4" fill="#eef5fb" stroke="{NAVY}"/><text class="tx" x="365" y="{57+i*36}" text-anchor="middle">{t}</text>' for i,t in enumerate(["render/","simulation/","loader/","schemas/"]))}
{''.join(f'<line x1="365" y1="{66+i*36}" x2="365" y2="{76+i*36}" stroke="{TEAL}" stroke-width="1.4"/><polygon points="365,{76+i*36} 361,{70+i*36} 369,{70+i*36}" fill="{TEAL}"/>' for i in range(3))}
</svg>'''

D1_2=f'''<svg width="100%" viewBox="0 0 420 160" xmlns="http://www.w3.org/2000/svg" font-size="10">
<style>.tx{{fill:{INK};{FS}}}</style>
<rect x="120" y="30" width="180" height="100" rx="8" fill="#eef5fb" stroke="{NAVY}" stroke-width="1.6"/>
<rect x="150" y="14" width="120" height="24" rx="12" fill="{TEAL}"/><text class="tx" x="210" y="30" text-anchor="middle" fill="#fff">public method ( )</text>
<text class="tx" x="210" y="70" text-anchor="middle" font-size="9" fill="{MUT}">— hidden internals —</text>
{''.join(f'<rect x="{150+c*40}" y="{84+r*16}" width="34" height="11" fill="#cfe0ef" stroke="{NAVY2}"/>' for r in range(2) for c in range(3))}
<text class="tx" x="210" y="150" text-anchor="middle" font-size="9" fill="{INK}">callers see the surface; internals can change freely</text>
</svg>'''

D2_1=f'''<svg width="100%" viewBox="0 0 470 210" xmlns="http://www.w3.org/2000/svg" font-size="10">
<style>.tx{{fill:{INK};{FS}}} .pk{{fill:#eef5fb;stroke:{NAVY};stroke-width:1.3}}</style>
<rect class="pk" x="160" y="10" width="150" height="24" rx="4"/><text class="tx" x="235" y="26" text-anchor="middle">powerpy/  (__init__.py)</text>
{''.join(f'<rect class="pk" x="{40+i*108}" y="60" width="96" height="24" rx="4"/><text class="tx" x="{88+i*108}" y="76" text-anchor="middle" font-size="9">{t}</text><line x1="235" y1="34" x2="{88+i*108}" y2="60" stroke="{MUT}"/>' for i,t in enumerate(["render/","simulation/","loader/","schemas/"]))}
<text class="tx" x="235" y="120" text-anchor="middle" fill="{AMBER2}" font-weight="bold">dependency direction →</text>
{''.join(f'<text class="tx" x="{88+i*108}" y="138" text-anchor="middle" font-size="8" fill="{MUT}">depends on ↓</text>' for i in range(3))}
<rect x="40" y="155" width="390" height="40" rx="5" fill="#eaf2f0" stroke="{TEAL}"/><text class="tx" x="235" y="172" text-anchor="middle" font-size="9" fill="{TEAL}">higher layers depend on lower; lower layers know nothing of higher</text>
<text class="tx" x="235" y="188" text-anchor="middle" font-size="8.5">render → simulation → loader → schemas (+ data/ accessed via package resources)</text>
</svg>'''

D2_2=f'''<svg width="100%" viewBox="0 0 470 175" xmlns="http://www.w3.org/2000/svg" font-size="10">
<style>.tx{{fill:{INK};{FS}}}</style>
<rect x="170" y="14" width="130" height="26" rx="4" fill="#fff" stroke="{INK}"/><text class="tx" x="235" y="31" text-anchor="middle"><tspan font-family="monospace">import string</tspan></text>
<rect x="30" y="90" width="170" height="34" rx="4" fill="#fcefea" stroke="{BRICK}" stroke-width="1.6"/><text class="tx" x="115" y="104" text-anchor="middle" font-size="9" fill="{BRICK}">LOCAL ./string.py</text><text class="tx" x="115" y="117" text-anchor="middle" font-size="8" fill="{MUT}">(cwd is first on the path)</text>
<rect x="270" y="90" width="170" height="34" rx="4" fill="#eef5fb" stroke="{NAVY}"/><text class="tx" x="355" y="104" text-anchor="middle" font-size="9">stdlib string</text><text class="tx" x="355" y="117" text-anchor="middle" font-size="8" fill="{MUT}">(what you wanted)</text>
<line x1="210" y1="40" x2="120" y2="90" stroke="{BRICK}" stroke-width="2"/><polygon points="120,90 122,82 128,87" fill="{BRICK}"/><text class="tx" x="120" y="62" fill="{BRICK}" font-size="9">picks this ✗</text>
<line x1="260" y1="40" x2="350" y2="90" stroke="{MUT}" stroke-width="1.2" stroke-dasharray="4 3"/>
<text class="tx" x="235" y="150" text-anchor="middle" fill="{BRICK}" font-size="9">→ breaks dateutil → pandas import. Fix: rename the module / install the package.</text>
</svg>'''

D3_1=f'''<svg width="100%" viewBox="0 0 470 180" xmlns="http://www.w3.org/2000/svg" font-size="9.5">
<style>.tx{{fill:{INK};{FS}}}</style>
<text class="tx" x="100" y="16" text-anchor="middle" fill="{BRICK}" font-weight="bold">before</text>
<rect x="30" y="30" width="150" height="80" rx="5" fill="#fcefea" stroke="{BRICK}"/><text class="tx" x="105" y="55" text-anchor="middle" font-size="9">one function:</text><text class="tx" x="105" y="72" text-anchor="middle" font-size="9">validate+load+</text><text class="tx" x="105" y="86" text-anchor="middle" font-size="9">compute+format</text>
<rect x="55" y="120" width="100" height="22" rx="3" fill="#fff" stroke="{MUT}"/><text class="tx" x="105" y="135" text-anchor="middle" font-size="8">returns 6-tuple</text>
<text class="tx" x="340" y="16" text-anchor="middle" fill="{GREEN}" font-weight="bold">after</text>
{''.join(f'<rect x="250" y="{28+i*26}" width="120" height="20" rx="3" fill="#eef5fb" stroke="{NAVY}"/><text class="tx" x="310" y="{42+i*26}" text-anchor="middle" font-size="8.5">{t}</text>' for i,t in enumerate(["validate()","load_config()","compute_iv()"]))}
<rect x="390" y="54" width="60" height="40" rx="4" fill="#eaf2f0" stroke="{TEAL}"/><text class="tx" x="420" y="70" text-anchor="middle" font-size="8" fill="{TEAL}">@dataclass</text><text class="tx" x="420" y="83" text-anchor="middle" font-size="8" fill="{TEAL}">Result</text>
{''.join(f'<line x1="370" y1="{38+i*26}" x2="390" y2="74" stroke="{MUT}"/>' for i in range(3))}
<text class="tx" x="320" y="130" text-anchor="middle" font-size="8.5" fill="{MUT}">read by name: r.vmp (never result[4])</text>
</svg>'''

D3_2=f'''<svg width="100%" viewBox="0 0 470 120" xmlns="http://www.w3.org/2000/svg" font-size="11">
<style>.tx{{fill:{INK};font-family:monospace}}</style>
<rect x="20" y="24" width="430" height="34" rx="4" fill="#fcefea" stroke="{BRICK}"/>
<text class="tx" x="34" y="46" font-size="12">def setTemperature(self, self, temperature):</text>
<line x1="232" y1="41" x2="290" y2="41" stroke="{BRICK}" stroke-width="2.5"/><text {FS} x="300" y="45" fill="{BRICK}" font-size="9">duplicate self → SyntaxError</text>
<rect x="20" y="72" width="430" height="34" rx="4" fill="#eaf2f0" stroke="{TEAL}"/>
<text class="tx" x="34" y="94" font-size="12">def set_temperature(self, temperature):</text>
<text {FS} x="360" y="94" fill="{TEAL}" font-size="9">✓ one self, snake_case</text>
</svg>'''

D4_1=f'''<svg width="100%" viewBox="0 0 470 150" xmlns="http://www.w3.org/2000/svg" font-size="9.5">
<style>.tx{{fill:{INK};{FS}}} .b{{fill:#eef5fb;stroke:{NAVY};stroke-width:1.3}}</style>
{''.join(f'<rect class="b" x="{20+i*120}" y="40" width="104" height="40" rx="5"/>' for i in range(4))}
{''.join(f'<text class="tx" x="{72+i*120}" y="{58}" text-anchor="middle" font-size="9">{a}</text><text class="tx" x="{72+i*120}" y="{72}" text-anchor="middle" font-size="9">{b}</text>' for i,(a,b) in enumerate([("run","cProfile"),("read top","hot function"),("optimise","only that"),("re-","measure")]))}
{''.join(f'<path d="M{124+i*120} 60 H{140+i*120}" stroke="{AMBER2}" stroke-width="2" fill="none"/><polygon points="{140+i*120},60 {134+i*120},56 {134+i*120},64" fill="{AMBER2}"/>' for i in range(3))}
<path d="M384 80 V110 H72 V82" stroke="{NAVY}" stroke-width="1.4" fill="none" stroke-dasharray="4 3"/><polygon points="72,82 68,90 76,90" fill="{NAVY}"/>
<text class="tx" x="235" y="106" text-anchor="middle" font-size="9" fill="{NAVY}">loop — measure, don't guess</text>
</svg>'''

D4_2=f'''<svg width="100%" viewBox="0 0 440 170" xmlns="http://www.w3.org/2000/svg" font-size="10">
<style>.tx{{fill:{INK};{FS}}}</style>
<line stroke="{INK}" x1="120" y1="140" x2="420" y2="140"/>
<rect x="150" y="20" width="80" height="120" fill="{BRICK}"/><text class="tx" x="190" y="15" text-anchor="middle" font-size="9" fill="{BRICK}">~600 ms</text><text class="tx" x="190" y="155" text-anchor="middle" font-size="9">N fsolve calls</text><text class="tx" x="190" y="166" text-anchor="middle" font-size="8" fill="{MUT}">(Python loop)</text>
<rect x="300" y="138" width="80" height="2" fill="{TEAL}"/><text class="tx" x="340" y="130" text-anchor="middle" font-size="9" fill="{TEAL}">~2 ms</text><text class="tx" x="340" y="155" text-anchor="middle" font-size="9">one vectorised</text><text class="tx" x="340" y="166" text-anchor="middle" font-size="8" fill="{MUT}">Newton</text>
<text class="tx" x="220" y="60" fill="{AMBER2}" font-size="9">~100× — and ×1000 runs</text>
<text class="tx" x="220" y="74" fill="{AMBER2}" font-size="9">in a Monte-Carlo sweep</text>
<text class="tx" x="40" y="80" transform="rotate(-90 40 80)" text-anchor="middle" font-size="9" fill="{INK}">thermal time / run</text>
</svg>'''

D5_1=f'''<svg width="100%" viewBox="0 0 420 170" xmlns="http://www.w3.org/2000/svg" font-size="9.5">
<style>.tx{{fill:{INK};{FS}}}</style>
<polygon points="210,20 330,60 90,60" fill="#fbe3df" stroke="{BRICK}"/><text class="tx" x="210" y="48" text-anchor="middle" font-size="9">end-to-end (few)</text>
<polygon points="90,62 330,62 360,105 60,105" fill="#fbf4e2" stroke="{AMBER}"/><text class="tx" x="210" y="90" text-anchor="middle" font-size="9">integration tests</text>
<polygon points="60,107 360,107 390,150 30,150" fill="#eaf2f0" stroke="{TEAL}"/><text class="tx" x="210" y="134" text-anchor="middle" font-size="9">many fast unit tests</text>
<text class="tx" x="210" y="165" text-anchor="middle" font-size="8.5" fill="{MUT}">base = cheap &amp; numerous; top = few &amp; precious · parity vs hand-worked oracle sits at the base</text>
</svg>'''

D5_2=f'''<svg width="100%" viewBox="0 0 470 150" xmlns="http://www.w3.org/2000/svg" font-size="9.5">
<style>.tx{{fill:{INK};{FS}}}</style>
<rect x="160" y="14" width="150" height="26" rx="4" fill="#eef5fb" stroke="{NAVY}"/><text class="tx" x="235" y="31" text-anchor="middle" font-size="9">same inputs (Ch.2 cell)</text>
<rect x="40" y="64" width="160" height="26" rx="4" fill="#fff" stroke="{MUT}"/><text class="tx" x="120" y="81" text-anchor="middle" font-size="9">legacy fsolve → 65.26°C</text>
<rect x="270" y="64" width="160" height="26" rx="4" fill="#eaf2f0" stroke="{TEAL}"/><text class="tx" x="350" y="81" text-anchor="middle" font-size="9">vectorised → 65.26°C</text>
<line x1="200" y1="40" x2="120" y2="64" stroke="{MUT}"/><line x1="270" y1="40" x2="350" y2="64" stroke="{MUT}"/>
<rect x="150" y="112" width="170" height="26" rx="4" fill="{NAVY}"/><text class="tx" x="235" y="129" text-anchor="middle" fill="#fff" font-size="9">assert |Δ| &lt; 1e-3 → PASS</text>
<line x1="120" y1="90" x2="220" y2="112" stroke="{INK}"/><line x1="350" y1="90" x2="250" y2="112" stroke="{INK}"/>
</svg>'''

D6_1=f'''<svg width="100%" viewBox="0 0 440 195" xmlns="http://www.w3.org/2000/svg" font-size="9.5">
<style>.tx{{fill:{INK};{FS}}}</style>
{''.join(f'<rect x="{40+i*16}" y="{30+i*30}" width="{360-i*32}" height="26" rx="3" fill="{c}" stroke="{s}"/><text class="tx" x="220" y="{47+i*30}" text-anchor="middle" font-size="9">{t}</text>' for i,(t,c,s) in enumerate([("5 · new features","#fbe3df",BRICK),("4 · profile &amp; optimise","#fbf0e0",AMBER2),("3 · refactor structure","#eef5fb",NAVY),("2 · add tests","#e8f0ec",GREEN),("1 · make it run / import","#eaf2f0",TEAL)]))}
<text class="tx" x="410" y="180" text-anchor="end" font-size="9" fill="{AMBER2}">build bottom-up ↑</text>
</svg>'''

D6_2=f'''<svg width="100%" viewBox="0 0 470 130" xmlns="http://www.w3.org/2000/svg" font-size="10">
<style>.tx{{fill:{INK};font-family:monospace}} .l{{fill:{INK};{FS}}}</style>
<rect x="20" y="20" width="210" height="44" rx="4" fill="#fcefea" stroke="{BRICK}"/><text class="l" x="125" y="16" text-anchor="middle" font-size="8" fill="{BRICK}">before</text>
<text class="tx" x="30" y="40" font-size="9">return (model, config,</text><text class="tx" x="30" y="54" font-size="9"> isc, imp, vmp, voc)</text>
<rect x="250" y="20" width="200" height="44" rx="4" fill="#eaf2f0" stroke="{TEAL}"/><text class="l" x="350" y="16" text-anchor="middle" font-size="8" fill="{TEAL}">after</text>
<text class="tx" x="260" y="40" font-size="9">@dataclass</text><text class="tx" x="260" y="54" font-size="9">class CellResult: ...</text>
<path d="M232 42 H248" stroke="{AMBER2}" stroke-width="2"/><polygon points="248,42 242,38 242,46" fill="{AMBER2}"/>
<rect x="120" y="84" width="240" height="32" rx="4" fill="#fff" stroke="{NAVY}"/><text class="tx" x="240" y="104" text-anchor="middle" font-size="9">assert cell_result(c).vmp == 2.35</text>
<text class="l" x="240" y="128" text-anchor="middle" font-size="8" fill="{MUT}">a test pins the field by name</text>
</svg>'''

FIGS={
 "_frag_D1.html":[fig(D1_1,"Figure 1 — One monolithic file doing five jobs (low cohesion, many couplings) versus separated layers each with one responsibility."),
                  fig(D1_2,"Figure 2 — Encapsulation: callers use a small public surface; the hidden internals can change without breaking them.")],
 "_frag_D2.html":[fig(D2_1,"Figure 3 — A layered package: higher layers depend on lower ones, never the reverse."),
                  fig(D2_2,"Figure 4 — The shadowing trap: a local string.py is found before the standard library's, silently breaking pandas.")],
 "_frag_D3.html":[fig(D3_1,"Figure 5 — Refactoring one fat function with a 6-tuple return into small typed functions feeding a @dataclass result."),
                  fig(D3_2,"Figure 6 — Spot the bug: a duplicated self makes the method uncallable; the fix takes self exactly once.")],
 "_frag_D4.html":[fig(D4_1,"Figure 7 — Profile, optimise only the proven hot function, then re-measure — a loop, not a guess."),
                  fig(D4_2,"Figure 8 — N per-cell fsolve calls versus one vectorised Newton solve: an order-of-magnitude saving that multiplies across a Monte-Carlo sweep.")],
 "_frag_D5.html":[fig(D5_1,"Figure 9 — The testing pyramid: many cheap unit tests at the base, a few end-to-end at the top."),
                  fig(D5_2,"Figure 10 — A parity test: the same inputs feed both solvers; the outputs must agree within a tolerance.")],
 "_frag_D6.html":[fig(D6_1,"Figure 11 — The improvement roadmap, built bottom-up: make it run, add tests, refactor, optimise, then new features."),
                  fig(D6_2,"Figure 12 — One concrete fix: a 6-tuple return becomes a typed dataclass, pinned by a test.")],
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
