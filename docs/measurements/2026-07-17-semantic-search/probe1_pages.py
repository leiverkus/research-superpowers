"""Modell-Probelauf: BGE-M3 vs Qwen3-Embedding-0.6B über zehn echte Seiten.

Frage: Kann ein Embedding-Modell METHODE von THEMA trennen? Alle zehn Seiten reden
über Punktprozess-Nullmodelle. Nur vier beschreiben random labelling. Ein Modell, das
nur Thema matcht, rankt die Distraktoren mit hoch — und wäre für Choros wertlos.

Gold-Seiten grounded gegen den echten FTS-Index verifiziert, nicht aus corpus-counts.md
übernommen (dessen Seitenanker sind ARTIKEL-Seiten, nicht PDF-Seiten).
"""
import sqlite3, time, sys
import numpy as np

DB = '/Users/patrick/.cache/research-superpowers/index-501f85e4.sqlite'

# (bibkey, pdf_page, ist_gold, kurzbeschreibung)
PAGES = [
    # GOLD — random labelling in PROSA, ohne Jargon (der eigentliche Auftrag)
    ('diezmartin-2021-tracing', 11, True,  'PROSA: "shuffling only the labels of the points"'),
    ('rabunal-2023-unraveling',  9, True,  'PROSA: "random type assignment ... maintaining their proportion"'),
    # GOLD — random labelling MIT Jargon (FTS findet die schon)
    ('moclan-2023-identifying', 11, True,  'JARGON: "random labelling"'),
    ('carreropazos-2019-spatial', 7, True, 'JARGON-nah: rank permutation of marks'),
    # DISTRAKTOREN — Nullmodelle, aber KEIN random labelling
    ('riris-2017-towards',        5, False, 'DISTRAKTOR: homogene CSR-Envelopes, 99 realizations'),
    ('riris-2017-towards',        8, False, 'DISTRAKTOR: homogene CSR, bivariate g(r)'),
    ('moclan-2023-spatial',       8, False, 'DISTRAKTOR: "modified" K = IPP aus eigener Intensitaet'),
    ('kempf-2021-take',           9, False, 'DISTRAKTOR: rpoispp(data_smo) — Selbstkonditionierung, kein labelling'),
    ('bilotti-2024-point',        9, False, 'DISTRAKTOR: ppm/AIC, erste Ordnung'),
    ('carrer-2017-interpreting', 11, False, 'DISTRAKTOR: modellkonditioniertes Envelope'),
]

# Die jargonfreie Abfrage aus dem Plan (Verifikation C)
QUERY = "the null model shuffles the labels of the observed points while keeping their locations fixed"


def load_pages():
    db = sqlite3.connect(DB)
    out = []
    for key, page, gold, desc in PAGES:
        row = db.execute(
            "SELECT text FROM pages WHERE bibkey=? AND page=?", (key, page)).fetchone()
        if not row:
            sys.exit(f"FEHLT: {key} S.{page} — Probe abgebrochen statt still weiterlaufen")
        out.append({'key': key, 'page': page, 'gold': gold, 'desc': desc, 'text': row[0]})
    db.close()
    return out


def run(model_name, docs, prefix_q='', prefix_d=''):
    from sentence_transformers import SentenceTransformer
    t0 = time.time()
    m = SentenceTransformer(model_name, device='mps')
    t_load = time.time() - t0

    texts = [prefix_d + d['text'] for d in docs]
    t0 = time.time()
    D = m.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    t_embed = time.time() - t0
    q = m.encode([prefix_q + QUERY], normalize_embeddings=True)[0]

    sims = D @ q
    order = np.argsort(-sims)
    dim = D.shape[1]
    chars = sum(len(t) for t in texts)
    del m
    return {'order': order, 'sims': sims, 'dim': dim, 't_load': t_load,
            't_embed': t_embed, 'chars': chars}


def report(name, r, docs):
    print(f"\n{'='*78}\n{name}  ·  dim={r['dim']}  ·  laden {r['t_load']:.1f}s  ·  "
          f"10 Seiten embedden {r['t_embed']:.2f}s  ({r['chars']/r['t_embed']:,.0f} Zeichen/s)")
    print(f"{'='*78}")
    ranks_of_gold = []
    for rank, i in enumerate(r['order'], 1):
        d = docs[i]
        mark = 'GOLD' if d['gold'] else '    '
        if d['gold']:
            ranks_of_gold.append(rank)
        print(f"  {rank:2d}. [{mark}] {r['sims'][i]:.4f}  {d['key']:26s} S.{d['page']:<3d} {d['desc']}")
    # Präzision@4: wie viele der vier Gold-Seiten stehen auf den ersten vier Plätzen?
    p4 = sum(1 for x in ranks_of_gold if x <= 4)
    print(f"  → Gold-Ränge: {ranks_of_gold}   Präzision@4: {p4}/4")
    return ranks_of_gold


if __name__ == '__main__':
    docs = load_pages()
    print(f"{len(docs)} echte Seiten geladen, "
          f"{sum(len(d['text']) for d in docs):,} Zeichen "
          f"(Ø {sum(len(d['text']) for d in docs)//len(docs):,}/Seite)")
    print(f"Abfrage: «{QUERY}»")

    results = {}
    for name, pq, pd in [('BAAI/bge-m3', '', ''),
                         ('Qwen/Qwen3-Embedding-0.6B', 'Instruct: Given a research query, retrieve relevant passages\nQuery: ', '')]:
        try:
            r = run(name, docs, pq, pd)
            results[name] = report(name, r, docs)
        except Exception as e:
            print(f"\n{name}: FEHLER — {type(e).__name__}: {e}")
