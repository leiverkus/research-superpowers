import json, subprocess, os, sys, re, itertools, shlex
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe6_crosslingual_strict.py")).read()
T = eval(re.search(r"^T = (\[.*?^\])", src, re.S|re.M).group(1))
P = os.environ["PROJECT_ROOT"]          # any scaffolded project (for scripts/bib-search.py)
env = dict(os.environ)                  # RESEARCH_LIBRARY must point at the library
def terms(q): return shlex.split(q)
def fmt(t): return f'"{t}"' if " " in t else t
def rank(gold, qs):
    cmd = ["python3","scripts/bib-search.py",qs[0],"--limit","40","--json"]
    for x in qs[1:]: cmd += ["--q", x]
    hits = json.loads(subprocess.run(cmd, cwd=P, env=env, capture_output=True, text=True, timeout=180).stdout or "[]")
    seen = []
    for h in hits:
        if h["bibkey"] not in seen: seen.append(h["bibkey"])
    return seen.index(gold)+1 if gold in seen else None
res = []
for gold, lang, de, en in T:
    pe = [" ".join(map(fmt,p)) for p in itertools.combinations(terms(en), 2)]
    pd = [" ".join(map(fmt,p)) for p in itertools.combinations(terms(de), 2)]
    r = dict(gold=gold, lang=lang, en_pairs=rank(gold, pe), de_pairs=rank(gold, pd), both=rank(gold, pe+pd))
    res.append(r); print(f"{gold[:42]:42} src={lang} | EN pairs={r['en_pairs']} | DE pairs={r['de_pairs']} | both={r['both']}", flush=True)
json.dump(res, open(sys.argv[1],"w"), indent=1)
for k in ("en_pairs","de_pairs","both"):
    print(k, *(f"top{l} {sum(1 for r in res if r[k] and r[k]<=l)}" for l in (1,5,10,40)), "of", len(res))
