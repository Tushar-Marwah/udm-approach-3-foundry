"""
Ingestion pipeline: land -> profile -> propose -> confirm -> commit.

Works on the bundled sample files AND on anything uploaded at runtime, of any
type. extract.py turns the file into records; proposer.py maps them; commit
writes the pointer rows and grows the registry. No new business table is ever
created -- canonical objects just gain another source.
"""
import datetime
import os

import extract
import rag
import docs
import plat
from proposer import propose

INCOMING_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "incoming")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")

FILE_LABELS = {
    "blinkit_scrape.csv": "Quick-commerce scrape (new week)",
    "fssai_labels.csv": "FSSAI label / spec sheet",
    "distributor_sheet.csv": "Distributor price sheet (messy)",
    "competitor_financials.json": "Competitor financials (JSON, L2/L4/L5)",
    "market_outlook_note.txt": "Market outlook note (unstructured → Claude)",
}
SAMPLE_EXTS = (".csv", ".tsv", ".json", ".txt", ".md", ".xlsx", ".pdf")


def _today():
    return datetime.date.today().isoformat()


def resolve_path(filename):
    for d in (UPLOAD_DIR, INCOMING_DIR):
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(filename)


def _staging_name(filename):
    import re
    base = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(filename)[0].lower()).strip("_")
    return "stg_" + (base or "upload")


def list_incoming():
    out = []
    import csv
    if os.path.isdir(INCOMING_DIR):
        for fn in sorted(os.listdir(INCOMING_DIR)):
            ext = os.path.splitext(fn)[1].lower()
            if ext not in SAMPLE_EXTS:
                continue
            headers, rc = [], None
            if ext in (".csv", ".tsv"):
                with open(os.path.join(INCOMING_DIR, fn), newline="") as f:
                    rows = list(csv.reader(f, delimiter="\t" if ext == ".tsv" else ","))
                headers = rows[0] if rows else []
                rc = max(0, len(rows) - 1)
            out.append({"file": fn, "label": FILE_LABELS.get(fn, fn), "type": ext.lstrip("."),
                        "headers": headers, "row_count": rc, "uploaded": False})
    return out


def _dedupe(headers):
    seen, out = {}, []
    for h in headers:
        h = str(h) if h is not None else "col"
        if h in seen:
            seen[h] += 1
            h = "%s_%d" % (h, seen[h])
        else:
            seen[h] = 1
        out.append(h)
    return out


def profile(conn, filename, project="", company=""):
    path = resolve_path(filename)
    ext = extract.extract(path)
    headers = _dedupe(ext["headers"])
    records = ext["records"]
    staging = _staging_name(filename)

    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS "%s"' % staging)
    cols = headers + ["_landed_on", "_source_file"]
    cur.execute('CREATE TABLE "%s" (%s)' % (staging, ", ".join('"%s"' % c for c in cols)))
    landed = _today()
    ph = ", ".join("?" for _ in cols)
    orig = ext["headers"]
    for r in records:
        vals = [r.get(orig[i]) if i < len(orig) else None for i in range(len(orig))]
        cur.execute('INSERT INTO "%s" VALUES (%s)' % (staging, ph), vals + [landed, filename])
    label = FILE_LABELS.get(filename, "Uploaded: " + filename)
    cur.execute("DELETE FROM raw_catalog WHERE name=?", (staging,))
    cur.execute("INSERT INTO raw_catalog (name, source_label, source_file, landed_on, row_count) "
                "VALUES (?,?,?,?,?)", (staging, label, filename, landed, len(records)))
    conn.commit()

    plan = propose(headers, records)
    plan["staging_table"] = staging
    plan["file"] = filename
    plan["sample_rows"] = records[:4]
    plan["headers"] = headers
    plan["extract_kind"] = ext["kind"]
    plan["extract_note"] = ext["note"]
    plan["cost_usd"] = round((ext.get("cost_usd", 0) or 0) + (plan.get("cost_usd", 0) or 0), 6)

    is_upload = os.path.exists(os.path.join(UPLOAD_DIR, filename))
    docs.record_profile(filename, label=label, doctype=os.path.splitext(filename)[1].lstrip("."),
                        source="upload" if is_upload else "sample", kind=ext["kind"],
                        rows=len(records), staging_table=staging, cost_usd=plan["cost_usd"],
                        project=project, entities=company,
                        industry=("Uploaded · " + company) if company else "Uploaded", scenario="Ad-hoc")
    return plan


def _registry_has(conn, obj, prop):
    return conn.execute("SELECT 1 FROM object_registry WHERE object=? AND property=?",
                        (obj, prop)).fetchone() is not None


def _object_exists(conn, obj):
    return conn.execute("SELECT 1 FROM object_registry WHERE object=?", (obj,)).fetchone() is not None


def commit(conn, filename, proposals, tail=None):
    staging = _staging_name(filename)
    cur = conn.cursor()
    bind_status = "approved" if plat.can("approve") else "proposed"
    added_objects, added_props, bindings_added = [], [], 0
    for p in proposals:
        obj, prop = p["object"], p["property"]
        if not _object_exists(conn, obj):
            added_objects.append(obj)
        if not _registry_has(conn, obj, prop):
            cur.execute("INSERT INTO object_registry (object, property, type, unit, status) "
                        "VALUES (?,?,?,?, 'approved')",
                        (obj, prop, p.get("type", "string"), p.get("unit", "")))
            added_props.append("%s.%s" % (obj, prop))
        cur.execute("INSERT INTO bindings (object_property, source_table, source_col, transform, "
                    "factor, offset, source_unit, confidence, source_file, status) "
                    "VALUES (?,?,?,?,?,?,?,?,?, ?)",
                    ("%s.%s" % (obj, prop), staging, p["column"], p.get("transform", "-"),
                     p.get("factor", 1.0), p.get("offset", 0.0), p.get("source_unit", ""),
                     p.get("confidence", 1.0), filename, bind_status))
        bindings_added += 1
    file_obj = proposals[0]["object"] if proposals else "Doc"
    narrative_added = 0
    for t in (tail or []):
        note = "%s: %s" % (t.get("column"), t.get("sample", ""))
        cur.execute("INSERT INTO rag_tail (source_file, note) VALUES (?,?)", (filename, note))
        # unmapped free text also becomes retrievable narrative, not a dead bucket
        rag.add(conn, "%s (from %s)" % (file_obj, filename), "tail",
                str(t.get("sample", "")) or note, filename)
        narrative_added += 1
    conn.commit()

    plat.log(conn, "ingest.commit", filename, "%d bindings (%s)" % (bindings_added, bind_status))
    docs.record_commit(filename, objects=sorted(set(p["object"] for p in proposals)),
                       bindings_added=bindings_added, narrative_added=narrative_added)
    return {"staging_table": staging, "bindings_added": bindings_added,
            "added_objects": sorted(set(added_objects)), "added_properties": added_props,
            "tail_added": len(tail or []), "narrative_added": narrative_added,
            "binding_status": bind_status}
