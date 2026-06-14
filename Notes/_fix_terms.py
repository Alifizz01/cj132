import re
for fn in ["_frag_P1.html","_frag_P2.html"]:
    txt=open(fn,encoding="utf-8").read()
    stack=[]; out=[]; last=0; fixes=0
    for m in re.finditer(r"<div\b[^>]*>|</div>|</p>", txt):
        tok=m.group()
        if tok.startswith("<div"):
            stack.append("term" if 'class="term"' in tok else "other")
        elif tok=="</div>":
            if stack: stack.pop()
        else:  # </p>
            if stack and stack[-1]=="term":
                # broken term close -> rewrite this </p> as </div>
                out.append(txt[last:m.start()]); out.append("</div>")
                last=m.end(); stack.pop(); fixes+=1
    out.append(txt[last:])
    new="".join(out)
    open(fn,"w",encoding="utf-8").write(new)
    op=new.count("<div"); cl=new.count("</div>")
    print(f"{fn}: fixed {fixes} terms | now <div>={op} </div>={cl} diff={op-cl}")
