"""Probelauf 4 — die Entwurfsfrage: bei welcher Chunkgroesse ueberlebt das Signal?

Kontrolle (kurze Saetze): BGE-M3 trennt rabunals Paraphrase (0.4555) klar vom
CSR-Distraktor (0.3093). Auf 450-Token-Chunks kippt es (Gold auf 7,8,9,10).
Also: Sweep ueber die Chunkgroesse auf demselben Hartdistraktoren-Set.

Metrik: Praezision@4 (vier Gold unter zehn Seiten) + die Kosten, die der Plan
gegen die Chunkgroesse aufrechnen muss.
"""
import sqlite3, time
import numpy as np

DB = '/Users/patrick/.cache/research-superpowers/index-501f85e4.sqlite'
PAGES = [
    ('diezmartin-2021-tracing', 11, True,  'PROSA: shuffling only the labels'),
    ('rabunal-2023-unraveling',  9, True,  'PROSA: random type assignment'),
    ('moclan-2023-identifying', 11, True,  'JARGON: random labelling'),
    ('carreropazos-2019-spatial', 7, True, 'JARGON-nah: rank permutation'),
    ('riris-2017-towards',        5, False, 'DISTRAKTOR: homogene CSR'),
    ('riris-2017-towards',        8, False, 'DISTRAKTOR: bivariate g(r)'),
    ('moclan-2023-spatial',       8, False, 'DISTRAKTOR: modified K'),
    ('kempf-2021-take',           9, False, 'DISTRAKTOR: rpoispp(data_smo)'),
    ('bilotti-2024-point',        9, False, 'DISTRAKTOR: ppm/AIC'),
    ('carrer-2017-interpreting', 11, False, 'DISTRAKTOR: konditioniertes Envelope'),
]
QUERY = "the null model shuffles the labels of the observed points while keeping their locations fixed"
SIZES = [450, 250, 150, 80, 40]      # Token
OVERLAP_FRAC = 0.18                   # 80/450 des Plans, proportional gehalten


def chunk(tok, text, size):
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    offs = enc['offset_mapping']
    if not offs:
        return []
    ov = max(1, int(size * OVERLAP_FRAC))
    out, i, step = [], 0, max(1, size - ov)
    while i < len(offs):
        w = offs[i:i + size]
        out.append((w[0][0], w[-1][1]))
        if i + size >= len(offs):
            break
        i += step
    return out


def main():
    db = sqlite3.connect(DB)
    docs = []
    for k, p, g, d in PAGES:
        t = db.execute("SELECT text FROM pages WHERE bibkey=? AND page=?", (k, p)).fetchone()[0]
        docs.append({'key': k, 'page': p, 'gold': g, 'desc': d, 'text': t})
    # Gesamtzahl Seiten fuer die Hochrechnung
    total_pages = db.execute("SELECT COUNT(*) FROM pages WHERE length(text)>=200").fetchone()[0]
    avg_chars = db.execute("SELECT AVG(length(text)) FROM pages WHERE length(text)>=200").fetchone()[0]
    db.close()

    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer
    name = 'BAAI/bge-m3'
    tok = AutoTokenizer.from_pretrained(name)
    m = SentenceTransformer(name, device='mps')
    q = m.encode([QUERY], normalize_embeddings=True)[0]

    print(f"Index: {total_pages:,} Seiten >=200 Zeichen, Ø {avg_chars:.0f} Zeichen/Seite\n")
    print(f"{'Größe':>6} {'Chunks/S.':>10} {'Vektoren':>11} {'float32':>9} "
          f"{'Präz@4':>7}  Gold-Ränge")
    print("-" * 72)
    for size in SIZES:
        chunks, owner = [], []
        for di, d in enumerate(docs):
            for s, e in chunk(tok, d['text'], size):
                assert 0 <= s < e <= len(d['text'])
                chunks.append(d['text'][s:e]); owner.append(di)
        C = m.encode(chunks, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
        sims = C @ q
        best = {}
        for ci, di in enumerate(owner):
            best[di] = max(best.get(di, -9), float(sims[ci]))
        order = sorted(best.items(), key=lambda kv: -kv[1])
        granks = [r for r, (di, _) in enumerate(order, 1) if docs[di]['gold']]
        p4 = sum(1 for r in granks if r <= 4)
        cps = len(chunks) / len(docs)
        vec = total_pages * cps
        gb = vec * 1024 * 4 / 1e9
        print(f"{size:>6} {cps:>10.2f} {vec:>11,.0f} {gb:>8.2f}G {p4:>4}/4  {granks}")
    print("\n(Präz@4 = wie viele der vier Gold-Seiten auf den ersten vier Plätzen. "
          "Zufall ≈ 1,6/4)")


if __name__ == '__main__':
    main()
