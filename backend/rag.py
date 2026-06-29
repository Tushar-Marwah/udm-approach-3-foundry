"""
The narrative ("information") layer: store qualitative text and retrieve it.

This is the demo's miniature of the RAG / vector store that sits beside the
structured unified model. Each chunk is linked to the entity it is about, so the
agent can fuse narrative ("Bisleri says it will premiumise") with the structured
numbers ("mineral-SKU share, gross margin") in one answer.

Retrieval is SQLite FTS5 keyword search (instant, offline, no embeddings) with a
LIKE fallback. Swapping in semantic embeddings later is a drop-in replacement of
search().
"""
import re


def add(conn, entity, kind, text, source_file="", period=""):
    if not text or not str(text).strip():
        return
    cur = conn.execute(
        "INSERT INTO narrative (entity, kind, text, source_file, period) VALUES (?,?,?,?,?)",
        (entity, kind, str(text).strip(), source_file, period))
    rid = cur.lastrowid
    conn.execute("INSERT INTO narrative_fts (rowid, text, entity, kind) VALUES (?,?,?,?)",
                 (rid, str(text).strip(), entity or "", kind or ""))


def clear_seed(conn):
    """Drop only seeded narrative (keep anything ingested)."""
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM narrative WHERE source_file='seed'").fetchall()]
    for rid in ids:
        conn.execute("DELETE FROM narrative_fts WHERE rowid=?", (rid,))
    conn.execute("DELETE FROM narrative WHERE source_file='seed'")


def _fts_query(q):
    # turn a natural question into a FTS5 OR-of-prefixes query, safely
    toks = re.findall(r"[A-Za-z0-9]+", q.lower())
    stop = {"the", "a", "an", "of", "for", "and", "or", "is", "are", "to", "in",
            "on", "what", "which", "how", "does", "do", "vs", "versus", "with",
            "its", "it", "by", "at", "be"}
    toks = [t for t in toks if t not in stop and len(t) > 2][:12]
    return " OR ".join('"%s"*' % t for t in toks) if toks else ""


def search(conn, question, limit=5):
    fq = _fts_query(question)
    rows = []
    if fq:
        try:
            rows = conn.execute(
                "SELECT n.entity, n.kind, n.text, n.source_file, "
                "bm25(narrative_fts) AS score "
                "FROM narrative_fts JOIN narrative n ON n.id = narrative_fts.rowid "
                "WHERE narrative_fts MATCH ? ORDER BY score LIMIT ?", (fq, limit)).fetchall()
        except Exception:
            rows = []
    if not rows:  # LIKE fallback
        toks = re.findall(r"[A-Za-z0-9]{4,}", question.lower())[:6]
        if toks:
            where = " OR ".join("lower(text) LIKE ?" for _ in toks)
            params = ["%" + t + "%" for t in toks] + [limit]
            rows = conn.execute(
                "SELECT entity, kind, text, source_file, 0 FROM narrative "
                "WHERE %s LIMIT ?" % where, params).fetchall()
    return [{"entity": r[0], "kind": r[1], "text": r[2], "source_file": r[3]} for r in rows]


def list_all(conn, limit=500):
    rows = conn.execute(
        "SELECT entity, kind, text, source_file, period FROM narrative ORDER BY id LIMIT ?",
        (limit,)).fetchall()
    return [{"entity": r[0], "kind": r[1], "text": r[2], "source_file": r[3], "period": r[4]}
            for r in rows]


def count(conn):
    return conn.execute("SELECT COUNT(*) FROM narrative").fetchone()[0]
