"""
Document registry -- "every document since inception", across all industries.

Lives in its OWN SQLite file (data/registry.db) so it SURVIVES a demo reset.
Holds the full catalog of ingested sources (hundreds, multi-domain) with
industry / scenario / use-case facets, plus what each became in the model.
"""
import datetime
import os
import sqlite3

REG_DB = os.path.join(os.path.dirname(__file__), "..", "data", "registry.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    filename        TEXT PRIMARY KEY,
    label           TEXT,
    industry        TEXT DEFAULT '',
    scenario        TEXT DEFAULT '',
    use_case        TEXT DEFAULT '',
    entities        TEXT DEFAULT '',   -- companies/entities the doc is about
    project         TEXT DEFAULT '',   -- project tag (set at upload, or seeded)
    doctype         TEXT,      -- csv | xlsx | json | pdf | docx | txt
    source          TEXT,      -- seed | sample | upload
    kind            TEXT,      -- table | doc
    rows            INTEGER,
    status          TEXT,      -- committed | landed | processing
    staging_table   TEXT,
    objects         TEXT,
    bindings_added  INTEGER DEFAULT 0,
    narrative_added INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0,
    first_seen      TEXT,
    last_action     TEXT
);
"""

_NEW_COLS = ["industry", "scenario", "use_case", "entities", "project"]


def _conn():
    os.makedirs(os.path.dirname(REG_DB), exist_ok=True)
    c = sqlite3.connect(REG_DB)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    for col in _NEW_COLS:                       # migrate older registries
        try:
            c.execute("ALTER TABLE documents ADD COLUMN %s TEXT DEFAULT ''" % col)
        except Exception:
            pass
    return c


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def seed_samples(samples):
    """Insert catalog rows (idempotent by filename)."""
    c = _conn()
    for s in samples:
        if c.execute("SELECT 1 FROM documents WHERE filename=?", (s["filename"],)).fetchone():
            continue
        c.execute(
            "INSERT INTO documents (filename,label,industry,scenario,use_case,entities,project,"
            "doctype,source,kind,rows,status,staging_table,objects,bindings_added,narrative_added,"
            "cost_usd,first_seen,last_action) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (s["filename"], s.get("label", ""), s.get("industry", ""), s.get("scenario", ""),
             s.get("use_case", ""), s.get("entities", ""), s.get("project", ""),
             s.get("doctype", ""), s.get("source", "seed"),
             s.get("kind", "table"), s.get("rows", 0), s.get("status", "committed"),
             s.get("staging_table", ""), s.get("objects", ""), s.get("bindings", 0),
             s.get("narrative", 0), s.get("cost_usd", 0),
             s.get("date", _now()), s.get("date", _now())))
    c.commit(); c.close()


def count(c=None):
    own = c is None
    c = c or _conn()
    n = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if own:
        c.close()
    return n


def record_profile(filename, **kw):
    c = _conn()
    now = _now()
    exists = c.execute("SELECT first_seen FROM documents WHERE filename=?", (filename,)).fetchone()
    first = exists["first_seen"] if exists else now
    cols = dict(label=kw.get("label", ""), industry=kw.get("industry", "Uploaded"),
                scenario=kw.get("scenario", "Ad-hoc"), use_case=kw.get("use_case", ""),
                project=kw.get("project", "") or "", entities=kw.get("entities", "") or "",
                doctype=kw.get("doctype", ""), source=kw.get("source", "upload"),
                kind=kw.get("kind", "table"), rows=kw.get("rows", 0), status="landed",
                staging_table=kw.get("staging_table", ""), cost_usd=kw.get("cost_usd", 0),
                first_seen=first, last_action=now)
    c.execute(
        "INSERT INTO documents (filename,label,industry,scenario,use_case,project,entities,doctype,"
        "source,kind,rows,status,staging_table,cost_usd,first_seen,last_action) VALUES (:fn,:label,"
        ":industry,:scenario,:use_case,:project,:entities,:doctype,:source,:kind,:rows,:status,"
        ":staging_table,:cost_usd,:first_seen,:last_action) "
        "ON CONFLICT(filename) DO UPDATE SET label=:label,doctype=:doctype,kind=:kind,rows=:rows,"
        "status=:status,staging_table=:staging_table,cost_usd=:cost_usd,project=:project,"
        "entities=:entities,last_action=:last_action",
        dict(fn=filename, **cols))
    c.commit(); c.close()


def record_commit(filename, objects=None, bindings_added=0, narrative_added=0):
    c = _conn()
    c.execute(
        "UPDATE documents SET status='committed', objects=?, bindings_added=?, "
        "narrative_added=?, last_action=? WHERE filename=?",
        (", ".join(sorted(set(objects or []))), bindings_added, narrative_added, _now(), filename))
    c.commit(); c.close()


def list_all(industry=None, scenario=None, status=None, project=None, limit=2000):
    c = _conn()
    where, params = [], []
    if industry:
        where.append("industry=?"); params.append(industry)
    if scenario:
        where.append("scenario=?"); params.append(scenario)
    if status:
        where.append("status=?"); params.append(status)
    if project:
        where.append("project=?"); params.append(project)
    sql = "SELECT * FROM documents"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY last_action DESC, filename LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close()
    return rows


def facets():
    c = _conn()

    def grp(col):
        return [{"key": r[0], "n": r[1]} for r in c.execute(
            "SELECT %s, COUNT(*) FROM documents GROUP BY %s ORDER BY COUNT(*) DESC" % (col, col)
        ).fetchall() if r[0]]

    out = {"by_industry": grp("industry"), "by_scenario": grp("scenario"),
           "by_status": grp("status"), "by_type": grp("doctype"), "by_project": grp("project")}
    c.close()
    return out


def get(filename):
    c = _conn()
    r = c.execute("SELECT * FROM documents WHERE filename=?", (filename,)).fetchone()
    c.close()
    return dict(r) if r else None


def projects_list():
    c = _conn()
    rows = c.execute(
        "SELECT project, COUNT(*) n, GROUP_CONCAT(DISTINCT industry) FROM documents "
        "WHERE project != '' GROUP BY project ORDER BY n DESC").fetchall()
    out = [{"project": p, "docs": n,
            "industries": sorted({i for i in (inds or "").split(",") if i})}
           for p, n, inds in rows]
    c.close()
    return out


def entities_list(limit=600):
    c = _conn()
    rows = c.execute(
        "SELECT entities, COUNT(*) n, GROUP_CONCAT(DISTINCT industry), GROUP_CONCAT(DISTINCT project) "
        "FROM documents WHERE entities != '' GROUP BY entities ORDER BY n DESC LIMIT ?",
        (limit,)).fetchall()
    out = [{"entity": e, "docs": n,
            "industries": sorted({i for i in (inds or "").split(",") if i}),
            "projects": sorted({p for p in (projs or "").split(",") if p})}
           for e, n, inds, projs in rows]
    c.close()
    return out


def search_documents(q, limit=80):
    c = _conn()
    like = "%" + q.lower() + "%"
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM documents WHERE lower(coalesce(filename,'')||' '||coalesce(label,'')||' '||"
        "coalesce(entities,'')||' '||coalesce(objects,'')||' '||coalesce(project,'')||' '||"
        "coalesce(industry,'')||' '||coalesce(scenario,'')) LIKE ? "
        "ORDER BY (coalesce(entities,'') != '') DESC, last_action DESC LIMIT ?",
        (like, limit)).fetchall()]
    c.close()
    return rows


def stats():
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    committed = c.execute("SELECT COUNT(*) FROM documents WHERE status='committed'").fetchone()[0]
    rows = c.execute("SELECT COALESCE(SUM(rows),0) FROM documents").fetchone()[0]
    industries = c.execute("SELECT COUNT(DISTINCT industry) FROM documents WHERE industry!=''").fetchone()[0]
    scenarios = c.execute("SELECT COUNT(DISTINCT scenario) FROM documents WHERE scenario!=''").fetchone()[0]
    c.close()
    return {"documents": total, "committed": committed, "doc_rows": rows,
            "industries": industries, "scenarios": scenarios}
