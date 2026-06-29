"""
Flask API for the PEL Foundry demo + serves the browser front-end.

Run:  python backend/app.py      (or ./run.sh)  ->  http://127.0.0.1:5050
"""
import os
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from db import get_conn, init_schema, DB_PATH
import seed
import ingest
import agent
import llm
import rag
import docs
import governance
import search
import plat
from resolver import resolve

os.makedirs(ingest.UPLOAD_DIR, exist_ok=True)

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
app = Flask(__name__, static_folder=FRONTEND, static_url_path="")


def ensure_db():
    if not os.path.exists(DB_PATH):
        seed.reset_all()
    else:
        conn = get_conn(); init_schema(conn); conn.close()


# ---- pages ---------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


# ---- read endpoints ------------------------------------------------------
@app.route("/api/meta")
def api_meta():
    return jsonify({
        "suggested_questions": agent.SUGGESTED,
        "llm": llm.status(),
        "llm_available": llm.available(),
    })


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    name = secure_filename(f.filename or "upload")
    if not name:
        return jsonify({"error": "bad filename"}), 400
    f.save(os.path.join(ingest.UPLOAD_DIR, name))
    return jsonify({"file": name})


@app.route("/api/stats")
def api_stats():
    conn = get_conn()
    sources = conn.execute("SELECT COUNT(*) FROM raw_catalog").fetchone()[0]
    rows = 0
    for (n,) in conn.execute("SELECT name FROM raw_catalog").fetchall():
        rows += conn.execute('SELECT COUNT(*) FROM "%s"' % n).fetchone()[0]
    props = conn.execute("SELECT COUNT(*) FROM object_registry").fetchone()[0]
    binds = conn.execute("SELECT COUNT(*) FROM bindings").fetchone()[0]
    mapped = conn.execute("SELECT COUNT(DISTINCT object_property) FROM bindings").fetchone()[0]
    objects = conn.execute(
        "SELECT COUNT(DISTINCT substr(object_property,1,instr(object_property,'.')-1)) FROM bindings"
    ).fetchone()[0]
    narr = rag.count(conn)
    conn.close()
    d = docs.stats()
    coverage = int(round(100.0 * mapped / props)) if props else 0
    return jsonify({"sources": sources, "rows": rows, "objects": objects,
                    "properties": props, "bindings": binds, "coverage": coverage,
                    "narrative": narr, "documents": d["documents"],
                    "industries": d["industries"], "scenarios": d["scenarios"],
                    "doc_rows": d["doc_rows"]})


@app.route("/api/documents")
def api_documents():
    industry = request.args.get("industry") or None
    scenario = request.args.get("scenario") or None
    status = request.args.get("status") or None
    project = request.args.get("project") or None
    return jsonify({"documents": docs.list_all(industry, scenario, status, project),
                    "facets": docs.facets(), "stats": docs.stats()})


@app.route("/api/entity-search")
def api_entity_search():
    conn = get_conn()
    out = search.entity_search(conn, request.args.get("q", ""))
    conn.close()
    return jsonify(out)


@app.route("/api/companies")
def api_companies():
    return jsonify({"companies": docs.entities_list()})


@app.route("/api/projects")
def api_projects():
    return jsonify({"projects": docs.projects_list()})


@app.route("/api/object")
def api_object():
    obj = request.args.get("object", "")
    conn = get_conn()
    try:
        r = resolve(conn, obj)
        out = {"object": obj, "columns": r["columns"], "rows": r["rows"][:1000], "sql": r["sql"],
               "edited": r.get("edited", []), "can_edit": plat.can("edit")}
    except Exception as e:  # noqa
        out = {"object": obj, "columns": [], "rows": [], "sql": "-- " + str(e),
               "edited": [], "can_edit": plat.can("edit")}
    conn.close()
    return jsonify(out)


@app.route("/api/document")
def api_document():
    fname = request.args.get("file", "")
    d = docs.get(fname)
    if not d:
        return jsonify({"error": "not found"}), 404
    conn = get_conn()
    cols, rows = [], []
    if d.get("staging_table"):
        try:
            info = conn.execute('PRAGMA table_info("%s")' % d["staging_table"]).fetchall()
            cols = [i["name"] for i in info]
            rows = [dict(r) for r in conn.execute(
                'SELECT * FROM "%s" LIMIT 100' % d["staging_table"]).fetchall()]
        except Exception:
            pass
    conn.close()
    d["columns"] = cols
    d["data"] = rows
    d["downloadable"] = os.path.exists(os.path.join(ingest.UPLOAD_DIR, fname))
    return jsonify(d)


@app.route("/api/document/download")
def api_document_download():
    fname = secure_filename(request.args.get("file", ""))
    path = os.path.join(ingest.UPLOAD_DIR, fname)
    if not os.path.exists(path):
        return jsonify({"error": "no file on disk (catalog/seed record)"}), 404
    return send_from_directory(ingest.UPLOAD_DIR, fname, as_attachment=True)


@app.route("/api/raw/table")
def api_raw_table():
    name = request.args.get("name", "")
    conn = get_conn()
    try:
        info = conn.execute('PRAGMA table_info("%s")' % name).fetchall()
        cols = [i["name"] for i in info]
        rows = [dict(r) for r in conn.execute('SELECT * FROM "%s" LIMIT 100' % name).fetchall()]
    except Exception:
        cols, rows = [], []
    conn.close()
    return jsonify({"name": name, "columns": cols, "rows": rows})


@app.route("/api/readiness")
def api_readiness():
    conn = get_conn()
    out = governance.readiness(conn)
    conn.close()
    return jsonify(out)


@app.route("/api/health")
def api_health():
    conn = get_conn()
    out = governance.health(conn)
    conn.close()
    return jsonify(out)


@app.route("/api/governance/objects")
def api_gov_objects():
    conn = get_conn()
    out = governance.objects_with_props(conn)
    conn.close()
    return jsonify({"objects": out})


@app.route("/api/lineage")
def api_lineage():
    conn = get_conn()
    out = governance.lineage(conn, request.args.get("object", ""), request.args.get("property", ""))
    conn.close()
    return jsonify(out)


# ===================== control plane: identity / actions / branches / tenancy ====
@app.route("/api/context", methods=["GET", "POST"])
def api_context():
    if request.method == "POST":
        d = request.get_json(force=True)
        plat.set_context(d.get("actor"), d.get("workspace"), d.get("branch"))
    conn = get_conn()
    out = plat.context()
    out["branches"] = [b["name"] for b in plat.list_branches(conn) if b["status"] == "open"]
    out["workspaces"] = plat.list_workspaces(conn)
    conn.close()
    return jsonify(out)


def _deny():
    return jsonify({"error": "%s is not permitted to do that" % plat.CTX["role"]}), 403


@app.route("/api/action/edit", methods=["POST"])
def api_action_edit():
    if not plat.can("edit"):
        return _deny()
    d = request.get_json(force=True)
    conn = get_conn()
    try:
        plat.add_edit(conn, d["object"], d.get("key_prop", "name"), d["key_val"],
                      d["property"], d.get("old_value", ""), d["new_value"], d.get("reason", ""))
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/api/action/classify", methods=["POST"])
def api_classify():
    if not plat.can("classify"):
        return _deny()
    d = request.get_json(force=True)
    conn = get_conn()
    try:
        plat.set_classification(conn, d["object_property"], d["level"])
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/api/classifications")
def api_classifications():
    conn = get_conn()
    out = plat.classifications(conn)
    conn.close()
    return jsonify({"classifications": out})


@app.route("/api/branches")
def api_branches():
    conn = get_conn()
    out = plat.list_branches(conn)
    conn.close()
    return jsonify({"branches": out})


@app.route("/api/branch", methods=["POST"])
def api_branch():
    if not plat.can("branch"):
        return _deny()
    conn = get_conn()
    try:
        plat.create_branch(conn, request.get_json(force=True)["name"])
        out = plat.list_branches(conn)
    finally:
        conn.close()
    return jsonify({"branches": out, "active": plat.CTX["branch"]})


@app.route("/api/branch/merge", methods=["POST"])
def api_branch_merge():
    if not plat.can("merge"):
        return _deny()
    conn = get_conn()
    try:
        out = plat.merge_branch(conn, request.get_json(force=True)["name"])
    finally:
        conn.close()
    return jsonify(out)


@app.route("/api/workspace", methods=["POST"])
def api_workspace():
    if not plat.can("merge"):
        return _deny()
    conn = get_conn()
    try:
        out = plat.create_workspace(conn, request.get_json(force=True)["name"])
    finally:
        conn.close()
    return jsonify({"workspaces": out, "active": plat.CTX["workspace"]})


@app.route("/api/history")
def api_history():
    conn = get_conn()
    out = plat.history(conn)
    conn.close()
    return jsonify({"history": out})


@app.route("/api/pending")
def api_pending():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT id,object_property,source_table,source_col,transform,confidence,source_file "
        "FROM bindings WHERE status='proposed' ORDER BY id").fetchall()]
    conn.close()
    return jsonify({"pending": rows})


@app.route("/api/action/approve-binding", methods=["POST"])
def api_approve_binding():
    if not plat.can("approve"):
        return _deny()
    d = request.get_json(force=True)
    conn = get_conn()
    decision = "approved" if d.get("decision", "approve") == "approve" else "rejected"
    conn.execute("UPDATE bindings SET status=? WHERE id=?", (decision, d["id"]))
    plat.log(conn, "binding." + decision, str(d["id"]), "")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/narrative")
def api_narrative():
    q = request.args.get("q", "").strip()
    conn = get_conn()
    if q:
        items = rag.search(conn, q, limit=20)
    else:
        items = rag.list_all(conn)
    conn.close()
    return jsonify({"items": items, "query": q})


@app.route("/api/raw")
def api_raw():
    conn = get_conn()
    cat = conn.execute("SELECT * FROM raw_catalog ORDER BY landed_on, name").fetchall()
    tables = []
    for c in cat:
        info = conn.execute('PRAGMA table_info("%s")' % c["name"]).fetchall()
        tables.append({
            "name": c["name"], "label": c["source_label"], "source_file": c["source_file"],
            "landed_on": c["landed_on"], "row_count": c["row_count"],
            "ncols": len(info), "columns": [i["name"] for i in info],
        })
    tail = [dict(r) for r in conn.execute("SELECT * FROM rag_tail ORDER BY id").fetchall()]
    conn.close()
    return jsonify({"tables": tables, "rag_tail": tail})


@app.route("/api/ontology")
def api_ontology():
    conn = get_conn()
    reg = conn.execute("SELECT * FROM object_registry ORDER BY object, id").fetchall()
    objects = {}
    for r in reg:
        objects.setdefault(r["object"], []).append(
            {"property": r["property"], "type": r["type"], "unit": r["unit"],
             "status": r["status"]})
    binds = [dict(r) for r in conn.execute(
        "SELECT object_property, source_table, source_col, transform, factor, offset, "
        "source_unit, confidence, source_file, status FROM bindings ORDER BY object_property, id"
    ).fetchall()]
    edges = [dict(r) for r in conn.execute(
        "SELECT from_obj, from_key, link, to_obj, to_key FROM edges").fetchall()]
    conn.close()
    return jsonify({"objects": objects, "bindings": binds, "edges": edges})


@app.route("/api/incoming")
def api_incoming():
    return jsonify({"files": ingest.list_incoming()})


# ---- ingestion -----------------------------------------------------------
@app.route("/api/ingest/profile", methods=["POST"])
def api_profile():
    data = request.get_json(force=True)
    conn = get_conn()
    try:
        plan = ingest.profile(conn, data["file"], project=data.get("project", ""),
                              company=data.get("company", ""))
    finally:
        conn.close()
    return jsonify(plan)


@app.route("/api/ingest/commit", methods=["POST"])
def api_commit():
    data = request.get_json(force=True)
    conn = get_conn()
    try:
        result = ingest.commit(conn, data["file"], data.get("proposals", []),
                               data.get("tail", []))
    finally:
        conn.close()
    return jsonify(result)


# ---- agent ---------------------------------------------------------------
@app.route("/api/agent", methods=["POST"])
def api_agent():
    data = request.get_json(force=True)
    conn = get_conn()
    try:
        out = agent.answer(conn, data["question"], use_llm=data.get("use_llm", False))
    finally:
        conn.close()
    return jsonify(out)


# ---- reset ---------------------------------------------------------------
@app.route("/api/reset", methods=["POST"])
def api_reset():
    seed.reset_all()
    return jsonify({"ok": True})


if __name__ == "__main__":
    ensure_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5050"))
    print("PEL Foundry demo -> http://%s:%d" % (host, port))
    app.run(host=host, port=port, debug=False)
