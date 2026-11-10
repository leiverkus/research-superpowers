import json, subprocess, os, sqlite3, sys
P = os.environ["PROJECT_ROOT"]          # any scaffolded project (for scripts/bib-search.py)
env = dict(os.environ)                  # RESEARCH_LIBRARY must point at the library
# gold, source language, German query, source-language/English query
T = [
 ("bienkowski-2015-iron","en","Keramik Eisenzeit Perserzeit Kontinuität","pottery \"Iron IIC\" Persian continu*"),
 ("benyosef-2019-architectural","en","Nomaden Architektur unsichtbar Archäologie","nomad* monumental architecture invisible"),
 ("bartlett-1978-yahweh","en","Jahwe Qaus Verhältnis Edom","Yahweh Qaus Edomite deity"),
 ("tebes-2019-memories","en","Edomiter Minderheit Juda Idumäa","Edomite* minority Judah Idumea*"),
 ("bienkowski-2025-edom","en","Besiedlungslücke Edom Perserzeit","\"occupation gap\" Edom Persian"),
 ("stroumsa-2008-nessana-identities","en","Nitzana Festung Treppe","Nessana fortress staircase"),
 ("kreimerman-2025-hazor-2023","en","Hazor Kasemattenmauer Zerstörungsschicht","Hazor casemate wall destruction"),
 ("knauf-niemann-2026-geschichte-israels","de","Dan Aschenschicht Brandrodung","Dan ash layer conquest"),
 ("erickson-gini-2012-nabataean-agriculture","en","nabatäische Landwirtschaft Bewässerung Quelle","Nabataean agriculture spring irrigation"),
 ("stoekl-2025-elephantine","?","Elephantine Gottheiten Eschem-Bethel","Elephantine deities Eshem-Bethel"),
 ("naaman-2017-search","en","JHWH Teman Beerscheba Tempel","YHWH Teman Beersheba temple"),
 ("hensel-2021b-wie-sich-die-wege-trennen","de","Zion Garizim zwei Zentren Perserzeit","Zion Gerizim two centres Persian"),
 ("gambash-2021-harbor-akko-ptolemais","en","Akko Hafen Schiffshäuser","Akko harbor shipsheds"),
 ("mazar-2001-radiocarbon-beth-shean-rehov","en","Rehov Radiokarbon Eisenzeit","Rehov radiocarbon \"Iron Age\""),
 ("stern-2001-archaeology","en","Tripolis drei Städte Diodor","Tripolis Diodorus three"),
 ("frevel-2018-geschichte-israels","de","Landnahme Modelle Hypothesen","conquest infiltration \"peasant revolt\" model*"),
 ("bartlett-1999-edomites","en","Idumäa Bezeichnung Perserzeit Provinz","Idumaea name Persian province"),
 ("hensel-2026-yhwh-fearing-sailors","en","Jona Seeleute Niniviten Bekenntnis","Jonah sailors Ninevites confession"),
 ("roll-1999-apollonia-arsuf","en","Apollonia Arsuf Gleichsetzung Clermont-Ganneau","Apollonia Arsuf identification Clermont-Ganneau"),
 ("hensel-2024-transjordan","en","Qos Nabatäer Perserzeit","Qos Nabataean* Persian"),
]
con = sqlite3.connect(os.path.expanduser("~/.cache/research-superpowers/index-9387d3e3.sqlite"))
def rank(gold, q, extra=()):
    cmd = ["python3","scripts/bib-search.py",q,"--limit","40","--json"]
    for x in extra: cmd += ["--q", x]
    r = subprocess.run(cmd, cwd=P, env=env, capture_output=True, text=True, timeout=120)
    try: hits = json.loads(r.stdout)
    except Exception: return "ERR", 0
    seen = []
    for h in hits:
        if h["bibkey"] not in seen: seen.append(h["bibkey"])
    return (seen.index(gold)+1 if gold in seen else None), len(seen)
res = []
for gold, lang, de, en in T:
    pages = con.execute("select pages from docs where bibkey=?", (gold,)).fetchone()
    two = " ".join(en.replace('"','').split()[:2])
    r_de, n_de = rank(gold, de); r_en, n_en = rank(gold, en); r_all, n_all = rank(gold, en, (de, two))
    res.append(dict(gold=gold, lang=lang, pages=pages[0] if pages else None, de=r_de, en=r_en, fused=r_all, n_de=n_de, n_en=n_en))
    print(f"{gold[:42]:42} src={lang} pages={pages[0] if pages else 'NOT INDEXED'} | DE-query rank={r_de} ({n_de} docs) | EN-query rank={r_en} ({n_en} docs) | fused rank={r_all}", flush=True)
json.dump(res, open(sys.argv[1],"w"), indent=1)
def c(k, lim): return sum(1 for r in res if isinstance(r[k], int) and r[k] <= lim)
for k in ("de","en","fused"): print(k, "top1", c(k,1), "top5", c(k,5), "top10", c(k,10), "top40", c(k,40), "of", len(res))
for name, q in (("de","und der die nicht"),("en","the and of which"),("fr","les des dans est")):
    print("lang", name, con.execute("select count(distinct bibkey) from pages where pages match ?", (q,)).fetchone()[0])
