"""
The resolver: object query  ->  SQL  ->  JSON.

This is the ~150-line service the decks describe. It reads ONLY the meaning
layer (registry + bindings), never hard-codes a table name, and builds real
SQL that the database executes. Because every property is a pointer, an object
backed by several raw files is just a UNION ALL across those files -- which is
exactly why "a new file = new pointer rows, never a new table".
"""
from db import TRANSFORM_ARITY
import plat


def _approved_props(conn, obj):
    rows = conn.execute(
        "SELECT property FROM object_registry WHERE object=? AND status='approved' "
        "ORDER BY id", (obj,)).fetchall()
    return [r["property"] for r in rows]


def _bindings(conn, obj):
    """All approved bindings for an object, indexed by (property, table)."""
    rows = conn.execute(
        "SELECT object_property, source_table, source_col, transform, factor, offset, "
        "source_unit, confidence, source_file "
        "FROM bindings WHERE object_property LIKE ? AND status='approved'", (obj + ".%",)
    ).fetchall()
    by_prop_table = {}
    tables = []
    for r in rows:
        prop = r["object_property"].split(".", 1)[1]
        by_prop_table[(prop, r["source_table"])] = r
        if r["source_table"] not in tables:
            tables.append(r["source_table"])
    return by_prop_table, tables


def _col_expr(binding):
    """Render one property's source expression, e.g. strip_currency("rate"),
    with any unit conversion applied: clean(col) * factor + offset."""
    cols = [c.strip() for c in binding["source_col"].split(",")]
    quoted = ['"%s"' % c for c in cols]
    t = binding["transform"]
    expr = quoted[0] if t == "-" else "%s(%s)" % (t, ", ".join(quoted))
    f = binding["factor"] if binding["factor"] is not None else 1
    o = binding["offset"] if binding["offset"] is not None else 0
    if f != 1:
        expr = "(%s) * %s" % (expr, _num(f))
    if o != 0:
        expr = "(%s) + %s" % (expr, _num(o))
    return expr


def _num(v):
    return str(int(v)) if float(v) == int(v) else str(v)


def _render_value(v):
    if isinstance(v, (int, float)):
        return str(v)
    return "'%s'" % str(v).replace("'", "''")


_OPS = {"=", "!=", "<", ">", "<=", ">=", "like"}


def generate_sql(conn, obj, select=None, where=None):
    """Build the SQL the resolver would run. `where` is a list of
    {field, op, value} dicts (AND-ed)."""
    props = _approved_props(conn, obj)
    if not props:
        raise ValueError("Unknown object '%s'" % obj)
    select = select or props
    select = [p for p in select if p in props]
    select = plat.visible_props(conn, obj, select)   # security: hide classified props
    if not select:
        raise ValueError("no visible properties for '%s' at this access level" % obj)
    by_prop_table, tables = _bindings(conn, obj)
    if not tables:
        raise ValueError("Object '%s' has no bindings yet" % obj)

    union_parts = []
    for table in tables:
        cols = []
        for p in select:
            b = by_prop_table.get((p, table))
            if b is None:
                cols.append('NULL AS "%s"' % p)
            else:
                cols.append('%s AS "%s"' % (_col_expr(b), p))
        union_parts.append('SELECT %s FROM "%s"' % (", ".join(cols), table))

    inner = "\nUNION ALL\n".join(union_parts)
    sql = "SELECT * FROM (\n%s\n)" % inner

    if where:
        conds = []
        for w in where:
            op = w["op"].lower()
            if op not in _OPS or w["field"] not in select:
                continue
            conds.append('"%s" %s %s' % (w["field"], op.upper(), _render_value(w["value"])))
        if conds:
            sql += "\nWHERE " + " AND ".join(conds)
    return sql, select


def resolve(conn, obj, select=None, where=None):
    """Run an object query end to end. Returns the generated SQL, the
    column list, and the result rows as plain dicts."""
    sql, cols = generate_sql(conn, obj, select, where)
    out = conn.execute(sql).fetchall()
    rows = [dict(r) for r in out]
    rows, edited = plat.apply_edits(conn, obj, cols, rows)   # actions: governed write-back
    return {"object": obj, "sql": sql, "columns": cols, "rows": rows, "edited": edited}
