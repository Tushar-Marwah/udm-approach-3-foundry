"""
Governance layer -- the Foundry-shaped "Data Health + Lineage + Readiness" pillar.

  readiness(conn)        -- per-PEL-level coverage: which parameters are bound to
                            real data (fully / partial / none) -- the PEL spec's
                            "readiness assessment".
  health(conn)           -- validation checks over the unified model: completeness,
                            outliers, low-confidence mappings, unit conversions.
  lineage(conn, o, p)    -- the full chain for any property: object.property -> its
                            bindings (raw table.col, transform, unit conversion,
                            source file) -> a sample raw value -> the resolved value.
"""
import statistics

from resolver import resolve
from canonical import CANONICAL


def _isnum(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _bound_set(conn):
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT object_property FROM bindings WHERE status='approved'").fetchall()}


def objects_with_props(conn):
    rows = conn.execute(
        "SELECT DISTINCT object_property FROM bindings WHERE status='approved' "
        "ORDER BY object_property").fetchall()
    by = {}
    for (op,) in rows:
        o, p = op.split(".", 1)
        by.setdefault(o, []).append(p)
    return by


def readiness(conn):
    """Coverage of the canonical model, grouped by business domain."""
    bound = _bound_set(conn)
    groups = {}
    for c in CANONICAL:
        g = c.get("domain") or c.get("level") or "Other"
        d = groups.setdefault(g, {"label": g, "total": 0, "bound": 0, "objects": set()})
        d["total"] += 1
        d["objects"].add(c["object"])
        if "%s.%s" % (c["object"], c["property"]) in bound:
            d["bound"] += 1
    out = []
    for g in sorted(groups, key=lambda k: (-groups[k]["bound"], k)):
        d = groups[g]
        pct = round(100 * d["bound"] / d["total"]) if d["total"] else 0
        status = "fully" if pct >= 80 else ("partial" if pct > 0 else "none")
        out.append({"label": d["label"], "total": d["total"], "bound": d["bound"], "pct": pct,
                    "status": status, "objects": sorted(d["objects"])})
    tot = sum(d["total"] for d in groups.values())
    bnd = sum(d["bound"] for d in groups.values())
    return {"levels": out, "overall_pct": round(100 * bnd / tot) if tot else 0,
            "bound": bnd, "total": tot, "domains": len(groups)}


def health(conn):
    bound = objects_with_props(conn)
    reg = {(r[0], r[1]): r[2] for r in conn.execute(
        "SELECT object, property, type FROM object_registry").fetchall()}
    checks = []
    for obj, props in bound.items():
        try:
            r = resolve(conn, obj, props)
        except Exception:
            continue
        n = len(r["rows"])
        if not n:
            continue
        for p in props:
            vals = [row.get(p) for row in r["rows"]]
            nn = [v for v in vals if v is not None and str(v) != ""]
            miss = round(100 * (n - len(nn)) / n)
            if miss >= 70:
                sev, msg = "fail", "%d%% missing" % miss
            elif miss >= 30:
                sev, msg = "warn", "%d%% missing" % miss
            else:
                sev, msg = "ok", "%d%% populated" % (100 - miss)
            checks.append({"target": "%s.%s" % (obj, p), "check": "completeness",
                           "value": msg, "severity": sev})
            if reg.get((obj, p)) == "number":
                nums = [float(v) for v in nn if _isnum(v)]
                if len(nums) >= 4:
                    med = statistics.median(nums)
                    if med:
                        far = [x for x in nums if x > med * 5 or x < med / 5]
                        if far:
                            checks.append({"target": "%s.%s" % (obj, p), "check": "range / outlier",
                                           "value": "%d value(s) far from median %g" % (len(far), med),
                                           "severity": "warn"})
    for op, conf, sf in conn.execute(
            "SELECT object_property, confidence, source_file FROM bindings "
            "WHERE confidence < 0.7 AND status='approved'").fetchall():
        checks.append({"target": op, "check": "low-confidence mapping",
                       "value": "conf %.2f (%s)" % (conf, sf), "severity": "warn"})
    for op, su, fac in conn.execute(
            "SELECT object_property, source_unit, factor FROM bindings "
            "WHERE source_unit != '' AND status='approved'").fetchall():
        checks.append({"target": op, "check": "unit conversion applied",
                       "value": "source '%s' ×%s" % (su, fac), "severity": "ok"})
    tail = conn.execute("SELECT COUNT(*) FROM rag_tail").fetchone()[0]
    summary = {"fail": sum(1 for c in checks if c["severity"] == "fail"),
               "warn": sum(1 for c in checks if c["severity"] == "warn"),
               "ok": sum(1 for c in checks if c["severity"] == "ok")}
    # surface failing/warning first
    order = {"fail": 0, "warn": 1, "ok": 2}
    checks.sort(key=lambda c: order[c["severity"]])
    return {"checks": checks, "summary": summary, "tail": tail}


def lineage(conn, obj, prop):
    op = "%s.%s" % (obj, prop)
    binds = conn.execute(
        "SELECT source_table, source_col, transform, factor, offset, source_unit, "
        "source_file, confidence FROM bindings WHERE object_property=? AND status='approved'",
        (op,)).fetchall()
    chain = []
    for b in binds:
        col = b["source_col"].split(",")[0].strip()
        try:
            row = conn.execute('SELECT "%s" FROM "%s" LIMIT 1' % (col, b["source_table"])).fetchone()
            raw = row[0] if row else None
        except Exception:
            raw = None
        conv = ""
        if b["factor"] and b["factor"] != 1:
            conv = "×%s" % b["factor"]
        if b["offset"]:
            conv += " +%s" % b["offset"]
        chain.append({
            "source_file": "seed data" if b["source_file"] == "seed" else b["source_file"],
            "source_table": b["source_table"], "source_col": b["source_col"],
            "transform": b["transform"], "conversion": conv, "source_unit": b["source_unit"] or "",
            "confidence": b["confidence"], "raw_sample": raw,
        })
    try:
        r = resolve(conn, obj, [prop])
        sample = [row[prop] for row in r["rows"][:3] if row[prop] is not None]
        sql = r["sql"]
    except Exception:
        sample, sql = [], ""
    canon = next((c for c in CANONICAL if c["object"] == obj and c["property"] == prop), None)
    return {"object": obj, "property": prop, "unit": canon["unit"] if canon else "",
            "level": canon["level"] if canon else "", "bindings": chain,
            "resolved_sample": sample, "sql": sql}
