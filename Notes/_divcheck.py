import re, sys
for fn in ["_frag_P1.html","_frag_P2.html"]:
    txt=open(fn,encoding="utf-8").read()
    # tokenise <div...> and </div> in order, with line numbers
    stack=[];
    for m in re.finditer(r"<div\b[^>]*>|</div>", txt):
        line=txt.count("\n",0,m.start())+1
        if m.group().startswith("</"):
            if stack: stack.pop()
            else: print(f"{fn}: stray </div> at line {line}")
        else:
            # capture a snippet of the open tag + following text for context
            snip=txt[m.start():m.start()+70].replace("\n"," ")
            stack.append((line,snip))
    print(f"\n==== {fn}: {len(stack)} UNCLOSED <div> ====")
    for line,snip in stack:
        print(f"  line {line}: {snip}")
    print()
