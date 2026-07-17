"""Probelauf 2 — DER ENTWURF DES PLANS: 450-Token-Chunks, 80 Überlappung,
niemals über eine Seitengrenze, bester Chunk je Seite.

Probelauf 1 embeddete ganze Seiten (~1300 Token) und rankte alle Gold-Seiten ans Ende.
Das ist aber genau die Variante, die der Plan Z.105 vorhersagend verwirft. Dies hier ist
der faire Test.
"""
import sqlite3, time, sys
import numpy as np

DB = '/Users/patrick/.cache/research-superpowers/index-501f85e4.sqlite'
CHUNK_TOKENS, OVERLAP = 450, 80

PAGES = [
    ('diezmartin-2021-tracing', 11, True,  'PROSA: "shuffling only the labels"'),
    ('rabunal-2023-unraveling',  9, True,  'PROSA: "random type assignment"'),
    ('moclan-2023-identifying', 11, True,  'JARGON: "random labelling"'),
    ('carreropazos-2019-spatial', 7, True, 'JARGON-nah: rank permutation'),
    ('riris-2017-towards',        5, False, 'DISTRAKTOR: homogene CSR, 99 realizations'),
    ('riris-2017-towards',        8, False, 'DISTRAKTOR: homogene CSR, bivariate g(r)'),
    ('moclan-2023-spatial',       8, False, 'DISTRAKTOR: "modified" K aus eigener Intensitaet'),
    ('kempf-2021-take',           9, False, 'DISTRAKTOR: rpoispp(data_smo)'),
    ('bilotti-2024-point',        9, False, 'DISTRAKTOR: ppm/AIC erste Ordnung'),
    ('carrer-2017-interpreting', 11, False, 'DISTRAKTOR: modellkonditioniertes Envelope'),
]
QUERY = "the null model shuffles the labels of the observed points while keeping their locations fixed"


def chunk_page(tok, text):
    """Token-basiert, INNERHALB der Seite. Gibt (start,end)-Zeichenspannen zurueck."""
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    offs = enc['offset_mapping']
    if not offs:
        return []
    out, i, step = [], 0, CHUNK_TOKENS - OVERLAP
    while i < len(offs):
        win = offs[i:i + CHUNK_TOKENS]
        out.append((win[0][0], win[-1][1]))
        if i + CHUNK_TOKENS >= len(offs):
            break
        i += step
    return out


def main():
    db = sqlite3.connect(DB)
    docs = []
    for key, page, gold, desc in PAGES:
        row = db.execute("SELECT text FROM pages WHERE bibkey=? AND page=?", (key, page)).fetchone()
        if not row:
            sys.exit(f"FEHLT: {key} S.{page}")
        docs.append({'key': key, 'page': page, 'gold': gold, 'desc': desc, 'text': row[0]})
    db.close()

    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer

    for name, pq in [('BAAI/bge-m3', ''),
                     ('Qwen/Qwen3-Embedding-0.6B',
                      'Instruct: Given a research query, retrieve relevant passages\nQuery: ')]:
        tok = AutoTokenizer.from_pretrained(name)
        chunks, owner = [], []
        for di, d in enumerate(docs):
            spans = chunk_page(tok, d['text'])
            # ASSERTION: kein Chunk darf die Seite verlassen (der ganze Entwurf haengt daran)
            for s, e in spans:
                assert 0 <= s < e <= len(d['text']), f"Chunk verlaesst Seite {d['key']} S.{d['page']}"
                chunks.append(d['text'][s:e]); owner.append(di)
        m = SentenceTransformer(name, device='mps')
        t0 = time.time()
        C = m.encode(chunks, normalize_embeddings=True, show_progress_bar=False, batch_size=16)
        t_e = time.time() - t0
        q = m.encode([pq + QUERY], normalize_embeddings=True)[0]
        sims = C @ q

        # bester Chunk je Seite (Plan: Chunks -> Seiten kollabieren VOR der Fusion)
        best = {}
        for ci, di in enumerate(owner):
            if sims[ci] > best.get(di, (-9, None))[0]:
                best[di] = (float(sims[ci]), chunks[ci])
        order = sorted(best.items(), key=lambda kv: -kv[1][0])

        print(f"\n{'='*78}\n{name}  ·  {len(chunks)} Chunks aus {len(docs)} Seiten  ·  "
              f"embed {t_e:.1f}s  ({len(chunks)/t_e:.1f} Chunks/s)\n{'='*78}")
        gold_ranks = []
        for rank, (di, (s, ctext)) in enumerate(order, 1):
            d = docs[di]
            if d['gold']:
                gold_ranks.append(rank)
            print(f"  {rank:2d}. [{'GOLD' if d['gold'] else '    '}] {s:.4f}  "
                  f"{d['key']:26s} S.{d['page']:<3d} {d['desc']}")
        p4 = sum(1 for r in gold_ranks if r <= 4)
        print(f"  → Gold-Raenge: {gold_ranks}   Praezision@4: {p4}/4")
        del m


if __name__ == '__main__':
    main()
