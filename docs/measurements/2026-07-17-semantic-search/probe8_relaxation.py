"""Does filling a thin strict result from two-term pairs recover what probe7 found by hand?

Same gold set and queries as probe6 (one 3–4-term query per language), run through the
CLI twice: `--no-relax` (the old behaviour) and the default. Document level, --limit 40.
PROJECT_ROOT / RESEARCH_LIBRARY from the environment; run from the repo root.
"""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
T = eval(re.search(r"^T = (\[.*?^\])", open(os.path.join(HERE, "probe6_crosslingual_strict.py")).read(), re.S | re.M).group(1))
SCRIPT = os.path.join(HERE, "..", "..", "..", "templates", "research-project-template", "scripts", "bib-search.py")

def rank(gold, q, *flags):
    out = subprocess.run([sys.executable, SCRIPT, q, "--limit", "40", "--json", "--root", os.environ["PROJECT_ROOT"], *flags],
                         capture_output=True, text=True, timeout=180).stdout
    seen = []
    for h in json.loads(out or "[]"):
        if h["bibkey"] not in seen:
            seen.append(h["bibkey"])
    return seen.index(gold) + 1 if gold in seen else None

rows = []
for gold, lang, de, en in T:
    q = de if lang == "de" else en              # the query in the SOURCE's language
    r = (rank(gold, q, "--no-relax"), rank(gold, q))
    rows.append(r); print(f"{gold[:44]:44} strict={r[0]}  relaxed={r[1]}", flush=True)
for i, name in enumerate(("strict", "relaxed")):
    print(name, *(f"top{l} {sum(1 for r in rows if r[i] and r[i] <= l)}" for l in (1, 5, 10, 40)), "of", len(rows))
print("worse under relaxation:", sum(1 for s, r in rows if s and (not r or r > s)))
