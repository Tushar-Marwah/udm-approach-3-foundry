"""
Database layer for the PEL Foundry demo.

Two layers live in ONE SQLite file, exactly like the real design:

  RAW LAYER     - the actual files, landed as-is in normal tables
                  (t_prices, t_specs, t_sales, plus staging tables for
                   anything ingested at runtime). Messy column names and
                   messy values are preserved on purpose.

  MEANING LAYER - object_registry / bindings / edges. These hold NO business
                  data of their own -- they POINT at raw columns and give them
                  clean business names. This is the whole Foundry trick.

The transforms (strip_currency, parse_brand, ...) are registered as real
SQLite functions, so the SQL the resolver generates literally calls them and
the database executes them. The generated SQL is honest, runnable SQL.
"""
import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "pel_demo.db")


# --------------------------------------------------------------------------
# Transforms — registered as SQLite UDFs. These ARE the "clean rule" stored
# in the bindings table; the resolver emits SQL that calls them by name.
# --------------------------------------------------------------------------
def strip_currency(v):
    """'Rs.20/-' / '₹19' / '18.00' / 'INR 403,000 mn' -> 20.0 / 19.0 / 18.0 / 403000.0"""
    if v is None:
        return None
    s = str(v).replace("₹", "").replace("Rs.", "").replace("Rs", "").replace("/-", "").replace(",", "")
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group()) if m else None


def to_int(v):
    if v is None:
        return None
    m = re.search(r"-?\d+", str(v).replace(",", ""))
    return int(m.group()) if m else None


def to_ml(v):
    """'1 L' / '1L' / '1 ltr' / '1000ml' / '1000' -> 1000 (ml)"""
    if v is None:
        return None
    s = str(v).lower().strip()
    m = re.search(r"(\d+(\.\d+)?)", s)
    if not m:
        return None
    num = float(m.group(1))
    if "ml" in s:
        return int(num)
    if "l" in s:               # litre / ltr / L
        return int(num * 1000)
    if num <= 10:              # bare small number -> assume litres
        return int(num * 1000)
    return int(num)            # bare large number -> assume ml


def parse_months(v):
    """'12mo' / '12 months' / '1 year' -> 12"""
    if v is None:
        return None
    s = str(v).lower()
    m = re.search(r"(\d+)", s)
    if not m:
        return None
    n = int(m.group(1))
    if "year" in s or "yr" in s:
        return n * 12
    return n


_BRANDS = ["bisleri", "kinley", "bailley", "aquafina", "kingfisher",
           "himalayan", "rail neer", "qua", "vedica"]


def parse_brand(v):
    """'Bisleri 1L' / 'Bisleri Water 1L' -> 'Bisleri'"""
    if v is None:
        return None
    s = str(v).strip()
    low = s.lower()
    for b in _BRANDS:
        if b in low:
            return b.title()
    # fallback: first token
    return s.split()[0] if s.split() else s


def parse_sku(v):
    """'Bisleri 1L' -> 'BIS-1L' ; passes through codes like 'BIS-1L' unchanged."""
    if v is None:
        return None
    s = str(v).strip()
    if re.match(r"^[A-Z]{2,4}-", s):          # already a code
        return s
    brand = parse_brand(s)
    low = s.lower()
    pm = re.search(r"(\d+)\s*(ml|l|ltr|litre|liter)", low)
    if pm:
        n = float(pm.group(1))
        unit = pm.group(2)
        size = "1L" if (unit.startswith("l") and n == 1) else (
            "%gL" % n if unit.startswith("l") else "%gml" % n)
    else:
        size = ""
    code = (brand[:3].upper() if brand else "GEN")
    return code + "-" + size if size else code


def enum_channel(v):
    """'Blinkit' / 'Zepto' / 'GT' / 'MT' -> canonical channel enum value."""
    if v is None:
        return None
    s = str(v).strip().lower()
    qc = ["blinkit", "zepto", "instamart", "swiggy", "jiomart", "quick"]
    ec = ["amazon", "flipkart", "ecom", "online"]
    if any(x in s for x in qc):
        return "quick_commerce"
    if any(x in s for x in ec):
        return "ecommerce"
    if s in ("gt", "general trade", "general"):
        return "general_trade"
    if s in ("mt", "modern trade", "modern"):
        return "modern_trade"
    if "horeca" in s:
        return "horeca"
    return s


def divide(a, b):
    """Derived facts, e.g. actual_price = revenue / units."""
    try:
        a = float(a); b = float(b)
        return round(a / b, 2) if b else None
    except (TypeError, ValueError):
        return None


def passthrough(v):
    return v


TRANSFORMS = {
    "-": passthrough,
    "strip_currency": strip_currency,
    "to_int": to_int,
    "to_ml": to_ml,
    "parse_months": parse_months,
    "parse_brand": parse_brand,
    "parse_sku": parse_sku,
    "enum_channel": enum_channel,
    "divide": divide,
}

# How many SQL args each transform takes (for the SQL builder).
TRANSFORM_ARITY = {name: (2 if name == "divide" else 1) for name in TRANSFORMS}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Register every transform as a real SQL function.
    for name, fn in TRANSFORMS.items():
        if name == "-":
            continue
        conn.create_function(name, TRANSFORM_ARITY[name], fn)
    return conn


# --------------------------------------------------------------------------
# Meaning-layer schema
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS object_registry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    object      TEXT NOT NULL,
    property    TEXT NOT NULL,
    type        TEXT,
    unit        TEXT,
    status      TEXT NOT NULL DEFAULT 'approved',   -- approved | proposed
    description TEXT,
    UNIQUE(object, property)
);

CREATE TABLE IF NOT EXISTS bindings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object_property TEXT NOT NULL,        -- 'PricePoint.selling_price'
    source_table    TEXT NOT NULL,        -- raw table name
    source_col      TEXT NOT NULL,        -- raw column (or 'a,b' for 2-arg)
    transform       TEXT NOT NULL DEFAULT '-',
    factor          REAL NOT NULL DEFAULT 1,   -- unit conversion: canonical = clean(col)*factor + offset
    offset          REAL NOT NULL DEFAULT 0,
    source_unit     TEXT DEFAULT '',           -- the unit observed in the source (provenance)
    confidence      REAL DEFAULT 1.0,
    source_file     TEXT,                 -- provenance: which file it came from
    status          TEXT NOT NULL DEFAULT 'approved'  -- approved | proposed
);

CREATE TABLE IF NOT EXISTS edges (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    from_obj  TEXT, from_key TEXT,
    link      TEXT,
    to_obj    TEXT, to_key   TEXT
);

-- Catalogue of landed raw tables (so the UI can show what's in the raw layer).
CREATE TABLE IF NOT EXISTS raw_catalog (
    name         TEXT PRIMARY KEY,
    source_label TEXT,     -- 'Quick-commerce scrape'
    source_file  TEXT,     -- 'blinkit_scrape.csv' or 'seed'
    landed_on    TEXT,
    row_count    INTEGER
);

-- Long-tail narrative store (the RAG fallback) for columns with no canonical home.
CREATE TABLE IF NOT EXISTS rag_tail (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    note        TEXT
);

-- Narrative / qualitative store: the "information" layer the agent retrieves over.
-- Each row is a chunk of text linked to the entity it is ABOUT (e.g. 'Brand:Bisleri').
CREATE TABLE IF NOT EXISTS narrative (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity      TEXT,      -- 'Brand:Bisleri' | 'Market:India...' | 'Product:BIS-1L'
    kind        TEXT,      -- strategy | market_commentary | assessment | doc | tail
    text        TEXT,
    source_file TEXT,
    period      TEXT
);
-- Full-text index over the narrative store (keyword retrieval; no embeddings needed).
CREATE VIRTUAL TABLE IF NOT EXISTS narrative_fts USING fts5(
    text, entity, kind, content='narrative', content_rowid='id'
);

-- ===================== control plane: tenancy / branching / actions / security ===
CREATE TABLE IF NOT EXISTS workspaces (name TEXT PRIMARY KEY, created_at TEXT);
CREATE TABLE IF NOT EXISTS branches (
    name TEXT PRIMARY KEY, base TEXT, created_by TEXT, created_at TEXT, status TEXT DEFAULT 'open');
-- per-property data classification (drives row/property-level security)
CREATE TABLE IF NOT EXISTS classifications (object_property TEXT PRIMARY KEY, level TEXT DEFAULT 'public');
-- write-back / Actions: governed edits applied over the raw layer on read
CREATE TABLE IF NOT EXISTS edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT, branch TEXT, object TEXT,
    key_prop TEXT, key_val TEXT, property TEXT, old_value TEXT, new_value TEXT,
    actor TEXT, role TEXT, reason TEXT, ts TEXT, status TEXT DEFAULT 'applied');
-- immutable audit log (versioning / time-travel)
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, role TEXT, workspace TEXT,
    branch TEXT, action TEXT, target TEXT, detail TEXT);
"""


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()
