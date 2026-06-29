"""
Control plane — the Foundry-style governance the demo was missing:

  Security    — roles (Admin / Data Steward / Analyst / Viewer) + per-property
                data classification (public/internal/confidential/restricted),
                enforced server-side on every resolve.
  Actions     — governed write-back: edits are applied OVER the raw layer on read
                (raw stays raw), fully audited.
  Branching   — edits live on a branch; view/merge branches; time-travel "as of".
  Tenancy     — workspaces scope edits/uploads (one shared model, client-keyed).

A single server-side context (CTX) holds the active actor/workspace/branch
(this is a single-user local demo). Everything reads CTX.
"""
import datetime

ROLES = {
    "Admin":        {"edit", "approve", "classify", "branch", "merge", "ingest",
                     "see_restricted", "see_confidential", "admin"},
    "Data Steward": {"edit", "approve", "classify", "branch", "merge", "ingest",
                     "see_restricted", "see_confidential"},
    "Analyst":      {"ingest", "branch", "see_confidential"},
    "Viewer":       set(),
}
LEVELS = ["public", "internal", "confidential", "restricted"]

CTX = {"actor": "Admin", "role": "Admin", "workspace": "Global", "branch": "main"}


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def context():
    return dict(CTX, roles=sorted(ROLES.keys()), perms=sorted(ROLES.get(CTX["role"], set())))


def set_context(actor=None, workspace=None, branch=None):
    if actor in ROLES:
        CTX["actor"] = actor
        CTX["role"] = actor
    if workspace:
        CTX["workspace"] = workspace
    if branch:
        CTX["branch"] = branch
    return context()


def can(perm):
    return perm in ROLES.get(CTX["role"], set())


# --------------------------------------------------------------------------
# history / audit
# --------------------------------------------------------------------------
def log(conn, action, target, detail=""):
    conn.execute(
        "INSERT INTO history (ts,actor,role,workspace,branch,action,target,detail) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (_now(), CTX["actor"], CTX["role"], CTX["workspace"], CTX["branch"], action, target, detail))
    conn.commit()


def history(conn, limit=300):
    rows = conn.execute(
        "SELECT ts,actor,role,workspace,branch,action,target,detail FROM history "
        "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# classification / security
# --------------------------------------------------------------------------
def classification(conn, op):
    r = conn.execute("SELECT level FROM classifications WHERE object_property=?", (op,)).fetchone()
    return r[0] if r else "public"

def classifications(conn):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT object_property, level FROM classifications").fetchall()}


def can_see(conn, obj, prop):
    lvl = classification(conn, "%s.%s" % (obj, prop))
    if lvl == "restricted":
        return can("see_restricted")
    if lvl == "confidential":
        return can("see_confidential")
    return True


def visible_props(conn, obj, props):
    return [p for p in props if can_see(conn, obj, p)]


def set_classification(conn, op, level):
    if level not in LEVELS:
        raise ValueError("bad level")
    conn.execute("INSERT INTO classifications (object_property, level) VALUES (?,?) "
                 "ON CONFLICT(object_property) DO UPDATE SET level=?", (op, level, level))
    conn.commit()
    log(conn, "classify", op, "→ " + level)


# --------------------------------------------------------------------------
# actions / write-back
# --------------------------------------------------------------------------
def add_edit(conn, obj, key_prop, key_val, prop, old, new, reason=""):
    conn.execute(
        "INSERT INTO edits (workspace,branch,object,key_prop,key_val,property,old_value,new_value,"
        "actor,role,reason,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (CTX["workspace"], CTX["branch"], obj, key_prop, key_val, prop, str(old), str(new),
         CTX["actor"], CTX["role"], reason, _now()))
    conn.commit()
    log(conn, "edit", "%s.%s [%s=%s]" % (obj, prop, key_prop, key_val), "%s → %s" % (old, new))


def _branches_in_scope():
    return ("main", CTX["branch"]) if CTX["branch"] != "main" else ("main",)


def edit_map(conn, obj, as_of=None):
    brs = _branches_in_scope()
    q = ("SELECT key_prop,key_val,property,new_value,actor,ts FROM edits WHERE object=? AND "
         "workspace=? AND branch IN (%s) AND status='applied'" % ",".join("?" * len(brs)))
    params = [obj, CTX["workspace"]] + list(brs)
    if as_of:
        q += " AND ts<=?"
        params.append(as_of)
    q += " ORDER BY id"
    m = {}
    for kp, kv, pr, nv, actor, ts in conn.execute(q, params).fetchall():
        m[(str(kv), pr)] = {"value": nv, "actor": actor, "ts": ts, "key_prop": kp}
    return m


def _coerce(new, orig):
    if isinstance(orig, (int, float)):
        try:
            f = float(new)
            return int(f) if f == int(f) else f
        except (TypeError, ValueError):
            return new
    return new


def apply_edits(conn, obj, columns, rows, as_of=None):
    m = edit_map(conn, obj, as_of)
    if not m:
        return rows, []
    keyprops = {v["key_prop"] for v in m.values() if v["key_prop"] in columns}
    edited = set()
    for row in rows:
        for kp in keyprops:
            kv = str(row.get(kp))
            for (mkv, pr), info in m.items():
                if kv == mkv and pr in row:
                    row[pr] = _coerce(info["value"], row[pr])
                    edited.add(pr)
    return rows, sorted(edited)


# --------------------------------------------------------------------------
# branches / workspaces
# --------------------------------------------------------------------------
def list_branches(conn):
    return [dict(r) for r in conn.execute(
        "SELECT name,base,created_by,created_at,status FROM branches ORDER BY created_at").fetchall()]


def create_branch(conn, name):
    conn.execute("INSERT OR IGNORE INTO branches (name,base,created_by,created_at,status) "
                 "VALUES (?,?,?,?, 'open')", (name, CTX["branch"], CTX["actor"], _now()))
    conn.commit()
    log(conn, "branch.create", name, "from " + CTX["branch"])
    CTX["branch"] = name
    return list_branches(conn)


def merge_branch(conn, name):
    n = conn.execute("UPDATE edits SET branch='main' WHERE branch=? AND workspace=?",
                     (name, CTX["workspace"])).rowcount
    conn.execute("UPDATE branches SET status='merged' WHERE name=?", (name,))
    conn.commit()
    log(conn, "branch.merge", name, "%d edit(s) → main" % n)
    CTX["branch"] = "main"
    return {"merged": n}


def list_workspaces(conn):
    return [r[0] for r in conn.execute("SELECT name FROM workspaces ORDER BY name").fetchall()]


def create_workspace(conn, name):
    conn.execute("INSERT OR IGNORE INTO workspaces (name,created_at) VALUES (?,?)", (name, _now()))
    conn.commit()
    log(conn, "workspace.create", name, "")
    CTX["workspace"] = name
    return list_workspaces(conn)
