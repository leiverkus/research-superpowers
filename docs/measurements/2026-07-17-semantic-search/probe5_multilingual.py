"""Probelauf 5 — der mehrsprachige Fall: DEUTSCHE Abfrage, ENGLISCHE Papers.

Der einzige Fall, in dem FTS strukturell null liefern kann, egal wie viele Aliase
man addiert. Bibliothek ist 94,4 % Englisch / 5,1 % Deutsch (30 Dok).

Gleicher Heuhaufen wie probe3 (gleicher Seed), damit die Zahlen vergleichbar sind.
"""
import sqlite3, time, random
import numpy as np

DB = '/Users/patrick/.cache/research-superpowers/index-501f85e4.sqlite'
CHUNK_TOKENS, OVERLAP, SAMPLE, SEED, MIN_CHARS = 450, 80, 3000, 20260717, 200

GOLD = [('diezmartin-2021-tracing', 11), ('rabunal-2023-unraveling', 9),
        ('moclan-2023-identifying', 11), ('carreropazos-2019-spatial', 7),
        ('keron-2015-use', 222)]

QUERIES = {
 'EN  (Referenz aus probe3)':
   "the null model shuffles the labels of the observed points while keeping their locations fixed",
 'DE  Prosa':
   "Das Nullmodell vertauscht die Beschriftungen der beobachteten Punkte, "
   "waehrend ihre Positionen unveraendert bleiben.",
 'DE  Fachbegriff':
   "Zufallsbeschriftung der Marken bei festgehaltenen Punktpositionen",
}


def chunk_page(tok, text):
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    offs = enc['offset_mapping']
    if not offs:
        return []
    out, i, step = [], 0, CHUNK_TOKENS - OVERLAP
    while i < len(offs):
        w = offs[i:i + CHUNK_TOKENS]
        out.append((w[0][0], w[-1][1]))
        if i + CHUNK_TOKENS >= len(offs):
            break
        i += step
    return out


def main():
    db = sqlite3.connect(DB)
    rows = db.execute("SELECT bibkey,page,text FROM pages WHERE length(text)>=?", (MIN_CHARS,)).fetchall()
    random.seed(SEED)
    sample = random.sample(rows, SAMPLE)
    have = {(b, p) for b, p, _ in sample}
    for b, p in GOLD:
        if (b, p) not in have:
            sample.append(db.execute("SELECT bibkey,page,text FROM pages WHERE bibkey=? AND page=?",
                                     (b, p)).fetchone())

    # FTS-Kontrolle: was holt eine DEUTSCHE Abfrage lexikalisch?
    print("=== FTS-Kontrolle: deutsche Suchbegriffe gegen den vollen Index ===")
    for t in ['Zufallsbeschriftung', 'Beschriftung*', 'Markierung*', 'vertausch*', 'Nullmodell']:
        n = db.execute("SELECT COUNT(*) FROM pages WHERE pages MATCH ?", (t,)).fetchone()[0]
        gold_hits = db.execute(
            "SELECT COUNT(*) FROM pages WHERE pages MATCH ? AND bibkey IN "
            "('diezmartin-2021-tracing','rabunal-2023-unraveling','moclan-2023-identifying',"
            "'carreropazos-2019-spatial','keron-2015-use')", (t,)).fetchone()[0]
        print(f"   {t:20s} -> {n:4d} Seiten bestandsweit, davon Gold: {gold_hits}")
    db.close()

    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer
    gold_set = set(GOLD)

    for name, pq in [('BAAI/bge-m3', ''),
                     ('Qwen/Qwen3-Embedding-0.6B',
                      'Instruct: Given a research query, retrieve relevant passages\nQuery: ')]:
        tok = AutoTokenizer.from_pretrained(name)
        chunks, owner = [], []
        for b, p, text in sample:
            for s, e in chunk_page(tok, text):
                chunks.append(text[s:e]); owner.append((b, p))
        m = SentenceTransformer(name, device='mps')
        t0 = time.time()
        C = m.encode(chunks, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
        print(f"\n{'='*74}\n{name}: {len(chunks):,} Chunks, embed {time.time()-t0:.0f}s\n{'='*74}")

        for label, qtext in QUERIES.items():
            q = m.encode([pq + qtext], normalize_embeddings=True)[0]
            sims = C @ q
            best = {}
            for ci, key in enumerate(owner):
                if sims[ci] > best.get(key, -9):
                    best[key] = float(sims[ci])
            order = sorted(best.items(), key=lambda kv: -kv[1])
            ranks = {k: i for i, (k, _) in enumerate(order, 1)}
            h10 = sum(1 for k, _ in order[:10] if k in gold_set)
            h20 = sum(1 for k, _ in order[:20] if k in gold_set)
            rr = {g[0][:18]: ranks.get(g) for g in GOLD}
            print(f"  {label:26s} @10={h10}/5 @20={h20}/5   {rr}")
        del m


if __name__ == '__main__':
    main()
