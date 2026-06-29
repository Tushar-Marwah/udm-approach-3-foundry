"""
Entity search -- the Palantir-style "type a company, see everywhere it lives".

Given a company / entity name, return every place it appears:
  - documents ingested about it (catalog),
  - ontology objects + the matching rows (and which properties hold its data),
  - narrative mentions,
  - the projects it was ingested under.
"""
import docs
import rag
from resolver import resolve

IDENTITY_PROPS = ["name", "company", "brand", "ticker", "symbol", "operator",
                  "bank", "client", "patient_id", "sku"]


def _objects_with_identity(conn):
    bound = {}
    for (op,) in conn.execute(
            "SELECT DISTINCT object_property FROM bindings WHERE status='approved'").fetchall():
        o, p = op.split(".", 1)
        bound.setdefault(o, []).append(p)
    out = []
    for o, props in bound.items():
        ident = next((ip for ip in IDENTITY_PROPS if ip in props), None)
        if ident:
            out.append((o, ident, props))
    return out


def entity_search(conn, q):
    q = (q or "").strip()
    empty = {"query": q, "documents": [], "objects": [], "narrative": [], "projects": [],
             "properties": [], "summary": {"documents": 0, "objects": 0, "properties": 0,
                                            "narrative": 0, "projects": 0}}
    if not q:
        return empty
    ql = q.lower()

    dmatches = docs.search_documents(q)

    obj_hits = []
    for obj, ident, props in _objects_with_identity(conn):
        sel = [ident] + [p for p in props if p != ident][:6]
        try:
            r = resolve(conn, obj, sel)
        except Exception:
            continue
        matched = [row for row in r["rows"] if row.get(ident) and ql in str(row[ident]).lower()]
        if matched:
            obj_hits.append({"object": obj, "identity": ident, "columns": sel,
                             "rows": matched[:20], "total": len(matched)})

    narr = rag.search(conn, q, limit=5)
    projects = sorted({d["project"] for d in dmatches if d.get("project")})
    props_ref = sorted({"%s.%s" % (h["object"], c) for h in obj_hits for c in h["columns"]})
    return {
        "query": q, "documents": dmatches, "objects": obj_hits, "narrative": narr,
        "projects": projects, "properties": props_ref,
        "summary": {"documents": len(dmatches), "objects": len(obj_hits),
                    "properties": len(props_ref), "narrative": len(narr),
                    "projects": len(projects)},
    }
