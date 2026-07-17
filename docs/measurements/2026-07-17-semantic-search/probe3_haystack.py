"""Probelauf 3 — realistischer Heuhaufen, notwendige Bedingung.

3.000 zufaellige Seiten aus dem echten Index (10 % von 30.843) + die 5 Gold-Seiten.
Das macht die Aufgabe ZEHNMAL leichter als die echte Abnahme (Verifikation C laeuft
gegen alle 30.843). Deshalb ist das ein Falsifikationstest:

  Schafft BGE-M3 rabunal S.9 hier NICHT in die Top-20, schafft es das gegen den
  vollen Index erst recht nicht — und Phase 2 ist erledigt, ohne 63-Minuten-Embed.

Schafft es das, ist nichts bewiesen, aber der volle Lauf ist gerechtfertigt.
"""
import sqlite3, time, random
import numpy as np

DB = '/Users/patrick/.cache/research-superpowers/index-501f85e4.sqlite'
CHUNK_TOKENS, OVERLAP, SAMPLE, SEED = 450, 80, 3000, 20260717
MIN_CHARS = 200          # Plan: Mindestlaenge NUR im Vektorarm

GOLD = [('diezmartin-2021-tracing', 11), ('rabunal-2023-unraveling', 9),
        ('moclan-2023-identifying', 11), ('carreropazos-2019-spatial', 7),
        ('keron-2015-use', 222)]
QUERY = "the null model shuffles the labels of the observed points while keeping their locations fixed"


def chunk_page(tok, text):
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
    rows = db.execute(
        "SELECT bibkey, page, text FROM pages WHERE length(text) >= ?", (MIN_CHARS,)).fetchall()
    print(f"Seiten im Index mit >= {MIN_CHARS} Zeichen: {len(rows):,}")
    random.seed(SEED)
    sample = random.sample(rows, min(SAMPLE, len(rows)))
    have = {(b, p) for b, p, _ in sample}
    for b, p in GOLD:
        if (b, p) not in have:
            r = db.execute("SELECT bibkey,page,text FROM pages WHERE bibkey=? AND page=?", (b, p)).fetchone()
            sample.append(r)
    db.close()
    print(f"Heuhaufen: {len(sample):,} Seiten (davon {len(GOLD)} Gold)")

    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer

    gold_set = set(GOLD)
    for name, pq in [('BAAI/bge-m3', ''),
                     ('Qwen/Qwen3-Embedding-0.6B',
                      'Instruct: Given a research query, retrieve relevant passages\nQuery: ')]:
        tok = AutoTokenizer.from_pretrained(name)
        t0 = time.time()
        chunks, owner = [], []
        for b, p, text in sample:
            for s, e in chunk_page(tok, text):
                assert 0 <= s < e <= len(text), "Chunk verlaesst die Seite"
                chunks.append(text[s:e]); owner.append((b, p))
        t_chunk = time.time() - t0
        print(f"\n{name}: {len(chunks):,} Chunks in {t_chunk:.0f}s getokent "
              f"({len(chunks)/len(sample):.2f} Chunks/Seite)")

        m = SentenceTransformer(name, device='mps')
        t0 = time.time()
        C = m.encode(chunks, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
        t_e = time.time() - t0
        q = m.encode([pq + QUERY], normalize_embeddings=True)[0]
        sims = C @ q
        rate = len(chunks) / t_e
        print(f"  embed {t_e:.0f}s  ({rate:.0f} Chunks/s)  "
              f"-> Hochrechnung auf 92.500 Chunks: {92500/rate/60:.0f} min")

        best = {}
        for ci, key in enumerate(owner):
            if sims[ci] > best.get(key, -9):
                best[key] = float(sims[ci])
        order = sorted(best.items(), key=lambda kv: -kv[1])
        ranks = {k: i for i, (k, _) in enumerate(order, 1)}
        h10 = [k for k, _ in order[:10] if k in gold_set]
        h20 = [k for k, _ in order[:20] if k in gold_set]
        print(f"  recall@10 = {len(h10)}/5   recall@20 = {len(h20)}/5")
        for g in GOLD:
            print(f"     {g[0]:26s} S.{g[1]:<4d} Rang {ranks.get(g,'—'):>6} von {len(order):,}")
        del m


if __name__ == '__main__':
    main()
