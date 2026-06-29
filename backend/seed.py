"""
Seed the demo database: a RICH raw layer (~100x the original) covering every PEL
level, plus the ontology (full PEL registry + bindings) that points at it.

Everything is generated deterministically (hash-based jitter, no randomness) so
the demo is stable and re-runnable. POST /api/reset calls reset_all().
"""
import hashlib
import os

from db import get_conn, init_schema, DB_PATH
from canonical import CANONICAL
import rag
import docs
import catalog
import companies
import plat

SEED_DATE = "2026-06-20"

# (code, name, premium, base_tds, esg, patents, rd_pct, share, perception, feature)
BRANDS = [
    ("BIS", "Bisleri", 1.00, 120, 0.62, 14, 1.2, 32, 8.4, 0.90),
    ("KIN", "Kinley", 0.95, 85, 0.55, 6, 0.9, 18, 7.6, 0.82),
    ("AQU", "Aquafina", 0.92, 40, 0.58, 4, 1.0, 11, 7.4, 0.80),
    ("BAI", "Bailley", 0.90, 110, 0.50, 3, 0.6, 9, 6.8, 0.70),
    ("KFR", "Kingfisher", 0.98, 90, 0.52, 5, 0.8, 6, 6.9, 0.74),
    ("RLN", "Rail Neer", 0.80, 70, 0.45, 2, 0.4, 5, 6.2, 0.60),
    ("OXY", "Oxyrich", 0.93, 95, 0.54, 3, 0.7, 3, 6.6, 0.72),
    ("HIM", "Himalayan", 1.60, 250, 0.70, 9, 1.5, 4, 8.1, 0.92),
    ("QUA", "Qua", 1.50, 180, 0.66, 7, 1.3, 2, 7.7, 0.88),
    ("VED", "Vedica", 1.55, 200, 0.68, 8, 1.4, 3, 7.9, 0.90),
    ("BNA", "Bonaqua", 0.96, 60, 0.57, 4, 0.9, 2, 6.7, 0.76),
    ("CAT", "Catch", 1.40, 160, 0.64, 6, 1.1, 2, 7.5, 0.86),
]
PACKS = [(250, "250ml", 8), (500, "500ml", 12), (1000, "1L", 20),
         (2000, "2L", 35), (5000, "5L", 60), (20000, "20L", 80)]
# (raw site string, canonical, multiplier)
CHANNELS = [("blinkit", "quick_commerce", 1.00), ("zepto", "quick_commerce", 1.00),
            ("amazon", "ecommerce", 0.98), ("MT", "modern_trade", 1.03),
            ("GT", "general_trade", 0.96), ("HoReCa", "horeca", 1.18)]
REGIONS = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata", "Pune"]
SALES_PERIODS = ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"]
ATTRIBUTES = [("Purity", 0.30), ("Taste", 0.22), ("Brand Trust", 0.20),
              ("Availability", 0.14), ("Packaging", 0.08), ("Sustainability", 0.06)]
ROLES = ["CEO", "COO", "CSO", "CPO", "Pricing"]
CERTS = ["BIS, ISI", "BIS", "BIS, FSSAI", "BIS, ISI, FSSAI", "BIS, FSSC 22000"]


def _h(*parts):
    s = "|".join(str(p) for p in parts)
    return int(hashlib.md5(s.encode()).hexdigest(), 16)


def jit(key, lo, hi):
    return lo + (_h(key) % 1000) / 1000.0 * (hi - lo)


def _fmt_price(v, i):
    return ["Rs.%g" % v, "₹%g" % v, "%g" % v, "%.1f" % v][i % 4]


def build_raw():
    raw = {}

    # ---- t_prices : quick-commerce / retail scrape (messy) ----
    rows = []
    i = 0
    for code, name, prem, *_ in BRANDS:
        for ml, plabel, base in PACKS[:4]:           # 250/500/1L/2L on shelf
            for site, _canon, cm in CHANNELS[:5]:     # 5 channels
                region = REGIONS[_h(code, ml, site) % len(REGIONS)]
                v = round(base * prem * cm * jit((code, ml, site), 0.95, 1.07))
                rows.append(("%s %s" % (name, plabel), _fmt_price(v, i), site, region, "2026-06-15"))
                i += 1
    raw["t_prices"] = {"label": "Quick-commerce price scrape",
                       "cols": ["item", "rate", "site", "region", "scraped_on"], "rows": rows}

    # ---- t_specs : label / spec sheet ----
    rows = []
    for code, name, prem, tds, esg, *_ in BRANDS:
        for ml, plabel, base in PACKS:
            shelf = "12mo" if ml < 5000 else "18 months"
            rows.append(("%s-%s" % (code, plabel), str(int(tds + (_h(code, ml) % 8))),
                         shelf, str(round(base * prem)), CERTS[_h(code) % len(CERTS)], plabel))
    raw["t_specs"] = {"label": "FSSAI label / spec sheet",
                      "cols": ["product", "tds", "shelf", "mrp", "certs", "pack"], "rows": rows}

    # ---- t_sales : internal ERP export ----
    rows = []
    for code, name, prem, tds, esg, pat, rd, share, *_ in BRANDS:
        for ml, plabel, base in PACKS[:4]:
            for site, _canon, cm in CHANNELS[:4]:
                for pi, period in enumerate(SALES_PERIODS):
                    units = int(share * 40 * (1.0 + 0.05 * pi) * jit((code, ml, site, period), 0.6, 1.4)
                                * (3.0 if ml == 1000 else 1.0))
                    realised = round(base * prem * 0.92 * cm)
                    rows.append(("%s-%s" % (code, plabel), units, float(units * realised),
                                 site, period))
    raw["t_sales"] = {"label": "Internal ERP / sales export",
                      "cols": ["sku", "units", "revenue", "ch", "period"], "rows": rows}

    # ---- t_financials : brand financials + competitive (one clean row per brand) ----
    rows = []
    for code, name, prem, tds, esg, pat, rd, share, perc, feat in BRANDS:
        gm = round(34 + (esg * 20) + jit((code, "gm"), -2, 4), 1)
        rows.append((name, "packaged water", share, gm, rd, pat, esg,
                     round(jit((code, "np"), 4, 16), 1), perc, feat))
    raw["t_financials"] = {"label": "Brand financials & competitive (BSE/investor)",
                           "cols": ["company", "sector", "share", "gross_margin", "rd_pct",
                                    "patents", "esg", "new_prod", "perception", "feature"],
                           "rows": rows}

    # ---- t_product_perf : ops / QA per SKU ----
    rows = []
    for code, name, *_ in BRANDS:
        for ml, plabel, _b in [(1000, "1L", 0), (2000, "2L", 0)]:
            rows.append(("%s-%s" % (code, plabel),
                         round(jit((code, ml, "def"), 0.3, 2.4), 2),
                         round(jit((code, ml, "ret"), 0.5, 3.5), 2),
                         int(jit((code, ml, "lt"), 1, 6)),
                         round(jit((code, ml, "oa"), 95, 99.5), 1),
                         round(jit((code, ml, "ci"), 0.2, 1.8), 2)))
    raw["t_product_perf"] = {"label": "Operations / QA system export",
                             "cols": ["sku", "defect_rate", "return_rate", "lead_time",
                                      "order_accuracy", "issues"], "rows": rows}

    # ---- t_attributes : customer value survey (L3) ----
    rows = []
    for attr, imp in ATTRIBUTES:
        for code, name, *_ in BRANDS:
            rows.append((attr, imp, name, round(jit((attr, code), 5.5, 9.2), 1)))
    raw["t_attributes"] = {"label": "Customer value survey (conjoint)",
                           "cols": ["attribute", "importance", "brand", "score"], "rows": rows}

    # ---- t_assessments : executive qualitative (L0) ----
    rows = []
    for role in ROLES:
        rows.append((role,
                     round(jit((role, "mgo"), 6, 9)), round(jit((role, "bs"), 6, 9)),
                     round(jit((role, "ip"), 5, 9)), round(jit((role, "ci"), 5, 9)),
                     round(jit((role, "cvp"), 5, 9)), round(jit((role, "dr"), 3, 8)),
                     "Defend share in 1L; premiumise via mineral SKUs"))
    raw["t_assessments"] = {"label": "Leadership assessment (Level 0)",
                            "cols": ["role", "market_growth_outlook", "brand_strength",
                                     "innovation_posture", "competitive_intensity",
                                     "customer_value_perception", "disruption_risk",
                                     "strategic_priorities"], "rows": rows}

    # ---- t_market : market context (L1) over horizons ----
    rows = []
    tam0, cagr_v, cagr_q = 403000.0, 13.2, 9.8
    horizons = [(-10, "FY16"), (-5, "FY21"), (-3, "FY23"), (-1, "FY25"), (0, "FY26"),
                (1, "FY27F"), (3, "FY29F"), (5, "FY31F"), (10, "FY36F")]
    for dy, label in horizons:
        tam = round(tam0 * ((1 + cagr_v / 100.0) ** dy))
        rows.append(("India packaged drinking water", label, tam, round(tam * 0.60),
                     round(tam * 0.36), cagr_v, cagr_q, 0.18, 21))
    raw["t_market"] = {"label": "Market sizing & outlook (Level 1)",
                       "cols": ["market", "horizon", "tam", "sam", "som",
                                "cagr_value", "cagr_volume", "hhi", "firm_age"], "rows": rows}

    # ---- t_companies : BSE 100 + S&P 500 entities (Finance domain) ----
    raw["t_companies"] = {"label": "BSE 100 + S&P 500 company master",
                          "cols": companies.COLS, "rows": companies.build_rows()}
    return raw


# object_property, source_table, source_col, transform
BINDINGS = [
    ("Product.sku", "t_specs", "product", "-"),
    ("Product.tds", "t_specs", "tds", "to_int"),
    ("Product.shelf_life_mo", "t_specs", "shelf", "parse_months"),
    ("Product.mrp", "t_specs", "mrp", "to_int"),
    ("Product.certifications", "t_specs", "certs", "-"),
    ("Product.pack_ml", "t_specs", "pack", "to_ml"),
    ("Product.sku", "t_product_perf", "sku", "-"),
    ("Product.defect_rate", "t_product_perf", "defect_rate", "-"),
    ("Product.return_rate", "t_product_perf", "return_rate", "-"),
    ("Product.shipping_lead_time", "t_product_perf", "lead_time", "to_int"),
    ("Product.order_accuracy", "t_product_perf", "order_accuracy", "-"),
    ("Product.customer_issues_rate", "t_product_perf", "issues", "-"),

    ("PricePoint.brand", "t_prices", "item", "parse_brand"),
    ("PricePoint.sku", "t_prices", "item", "parse_sku"),
    ("PricePoint.selling_price", "t_prices", "rate", "strip_currency"),
    ("PricePoint.channel", "t_prices", "site", "enum_channel"),
    ("PricePoint.region", "t_prices", "region", "-"),
    ("PricePoint.period", "t_prices", "scraped_on", "-"),

    ("Transaction.sku", "t_sales", "sku", "-"),
    ("Transaction.units", "t_sales", "units", "to_int"),
    ("Transaction.revenue", "t_sales", "revenue", "-"),
    ("Transaction.channel", "t_sales", "ch", "enum_channel"),
    ("Transaction.period", "t_sales", "period", "-"),
    ("Transaction.actual_price", "t_sales", "revenue,units", "divide"),

    ("Brand.name", "t_financials", "company", "-"),
    ("Brand.sector", "t_financials", "sector", "-"),
    ("Brand.market_share", "t_financials", "share", "-"),
    ("Brand.gross_margin", "t_financials", "gross_margin", "-"),
    ("Brand.rd_investment", "t_financials", "rd_pct", "-"),
    ("Brand.patents", "t_financials", "patents", "to_int"),
    ("Brand.sustainability_score", "t_financials", "esg", "-"),
    ("Brand.new_product_revenue_share", "t_financials", "new_prod", "-"),
    ("Brand.brand_perception", "t_financials", "perception", "-"),
    ("Brand.feature_completeness", "t_financials", "feature", "-"),

    ("Attribute.name", "t_attributes", "attribute", "-"),
    ("Attribute.importance_weight", "t_attributes", "importance", "-"),
    ("Attribute.brand", "t_attributes", "brand", "-"),
    ("Attribute.performance_score", "t_attributes", "score", "-"),

    ("Assessment.role", "t_assessments", "role", "-"),
    ("Assessment.market_growth_outlook", "t_assessments", "market_growth_outlook", "-"),
    ("Assessment.brand_strength", "t_assessments", "brand_strength", "-"),
    ("Assessment.innovation_posture", "t_assessments", "innovation_posture", "-"),
    ("Assessment.competitive_intensity", "t_assessments", "competitive_intensity", "-"),
    ("Assessment.customer_value_perception", "t_assessments", "customer_value_perception", "-"),
    ("Assessment.disruption_risk", "t_assessments", "disruption_risk", "-"),
    ("Assessment.strategic_priorities", "t_assessments", "strategic_priorities", "-"),

    ("Market.name", "t_market", "market", "-"),
    ("Market.tam", "t_market", "tam", "strip_currency"),
    ("Market.sam", "t_market", "sam", "strip_currency"),
    ("Market.som", "t_market", "som", "strip_currency"),
    ("Market.cagr_value", "t_market", "cagr_value", "-"),
    ("Market.cagr_volume", "t_market", "cagr_volume", "-"),
    ("Market.hhi", "t_market", "hhi", "-"),
    ("Market.avg_firm_age", "t_market", "firm_age", "to_int"),
]


def _edges():
    edges = []
    leaders = ["BIS", "KIN", "AQU", "BAI", "KFR"]
    for plabel in ("1L", "2L"):
        for other in leaders[1:]:
            edges.append(("Product", "BIS-%s" % plabel, "competesWith", "Product", "%s-%s" % (other, plabel)))
    return edges


def _tier(prem):
    return "premium mineral" if prem >= 1.3 else ("value / mass" if prem < 0.85 else "mainstream")


def seed_narrative(conn):
    """Brand strategy + market commentary + leadership narrative, linked to entities."""
    for code, name, prem, tds, esg, pat, rd, share, perc, feat in BRANDS:
        tier = _tier(prem)
        if prem >= 1.3:
            strat = ("leads the premium mineral segment on provenance, a high mineral profile "
                     "(TDS ~%d mg/L) and distinctive packaging, accepting lower volumes for "
                     "superior gross margin and brand strength" % tds)
            prio = "premiumisation; protect price integrity; selective HoReCa and modern-trade push"
        elif prem < 0.85:
            strat = ("competes on ubiquitous availability and the sharpest mass price points, "
                     "prioritising volume and distribution depth over margin")
            prio = "distribution expansion; cost leadership; defend mass 1L"
        else:
            strat = ("defends the mass 1L pack on availability and price while premiumising through "
                     "mineral and large-format SKUs to lift blended gross margin")
            prio = "defend share in 1L; premiumise via mineral SKUs; grow quick-commerce"
        txt = ("%s is a %s brand (est. %s%% category share, ESG %d/100, %d patents). "
               "Strategy: %s. Stated priorities: %s." %
               (name, tier, share, int(esg * 100), pat, strat, prio))
        rag.add(conn, "Brand:%s" % name, "strategy", txt, "seed", "FY26")

    market = [
        "The India packaged drinking water category is growing ~13% in value on health-led "
        "consumption and rising on-the-go demand; volume growth runs slightly lower at ~10%.",
        "Quick commerce (Blinkit, Zepto, Instamart) is reshaping price discovery and shrinking the "
        "shelf-price gap between brands, intensifying competition on the 1L mass pack.",
        "Concentration is moderate (HHI ~0.18); the top four organised players hold a little over "
        "half of organised sales, with a long tail of regional and unorganised supply.",
        "The premium natural-mineral segment is outpacing the mass segment, pulling category value "
        "growth above volume growth and rewarding brands with credible provenance.",
    ]
    for m in market:
        rag.add(conn, "Market:India packaged drinking water", "market_commentary", m, "seed", "FY26")

    leadership = [
        ("Brand:Bisleri", "Leadership view: defend the 1L mass pack as the volume engine while "
                          "shifting mix toward mineral and 2L+ formats to protect blended margin; "
                          "treat quick commerce as the priority growth channel."),
        ("Brand:Bisleri", "Pricing committee note: realised price runs ~8% below list on the mass "
                          "pack due to trade promotions; premium SKUs hold price far better."),
    ]
    for ent, txt in leadership:
        rag.add(conn, ent, "assessment", txt, "seed", "FY26")
    conn.commit()


def reset_all():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_conn()
    init_schema(conn)
    cur = conn.cursor()

    raw = build_raw()
    for name, spec in raw.items():
        cols_sql = ", ".join('"%s"' % c for c in spec["cols"])
        cur.execute('CREATE TABLE "%s" (%s)' % (name, cols_sql))
        ph = ", ".join("?" for _ in spec["cols"])
        cur.executemany('INSERT INTO "%s" VALUES (%s)' % (name, ph), spec["rows"])
        cur.execute("INSERT INTO raw_catalog (name, source_label, source_file, landed_on, row_count) "
                    "VALUES (?,?,?,?,?)", (name, spec["label"], "seed", SEED_DATE, len(spec["rows"])))

    # registry = the full PEL dictionary (the whole menu is visible)
    seen = set()
    reg = []
    for c in CANONICAL:
        k = (c["object"], c["property"])
        if k in seen:
            continue
        seen.add(k)
        reg.append((c["object"], c["property"], c["type"], c["unit"], "approved"))
    cur.executemany("INSERT INTO object_registry (object, property, type, unit, status) "
                    "VALUES (?,?,?,?,?)", reg)
    cur.executemany("INSERT INTO bindings (object_property, source_table, source_col, transform, "
                    "confidence, source_file, status) VALUES (?,?,?,?,1.0,'seed','approved')",
                    BINDINGS + companies.BINDINGS)
    cur.executemany("INSERT INTO edges (from_obj, from_key, link, to_obj, to_key) VALUES (?,?,?,?,?)",
                    _edges())
    conn.commit()

    # narrative / information layer
    seed_narrative(conn)

    # ---- control plane: tenancy / security / actions / branching ----
    plat.CTX.update({"actor": "Admin", "role": "Admin", "workspace": "Global", "branch": "main"})
    for ws in ("Global", "MSPL / Baldota", "Index Coverage"):
        cur.execute("INSERT OR IGNORE INTO workspaces (name,created_at) VALUES (?,?)", (ws, SEED_DATE))
    cur.execute("INSERT OR IGNORE INTO branches (name,base,created_by,created_at,status) "
                "VALUES ('main','','system',?, 'open')", (SEED_DATE,))
    for op, lvl in [("Company.revenue_mn", "confidential"), ("Company.net_income_mn", "confidential"),
                    ("Company.market_cap_mn", "confidential"), ("Brand.gross_margin", "confidential"),
                    ("Transaction.revenue", "confidential"), ("Transaction.actual_price", "restricted"),
                    ("Patient.age", "restricted"), ("Patient.risk_score", "restricted"),
                    ("LabResult.value", "restricted"), ("Medication.adherence_pct", "restricted")]:
        cur.execute("INSERT OR IGNORE INTO classifications (object_property,level) VALUES (?,?)", (op, lvl))
    conn.commit()
    # demo write-back + a branch (as a Data Steward), then back to Admin/main
    plat.set_context(actor="Data Steward")
    plat.add_edit(conn, "Brand", "name", "Kinley", "new_product_revenue_share", "9.2", "11.5",
                  "QA correction from FY26 filing")
    plat.create_branch(conn, "fy27-restatement")
    plat.add_edit(conn, "Brand", "name", "Bisleri", "gross_margin", "45.1", "46.0",
                  "Restated under FY27 accounting basis")
    plat.set_context(actor="Admin", workspace="Global", branch="main")

    # document registry (separate store; persists across reset)
    all_binds = BINDINGS + companies.BINDINGS
    src_objects = {}
    for op, tbl, col, tf in all_binds:
        src_objects.setdefault(tbl, set()).add(op.split(".")[0])
    fin = ("Finance · Corporate / Markets", "Capital Markets", "Equity research")
    pel = ("Packaged Water (FMCG)", "PEL · Pricing & Positioning", "Competitive strategy")
    tags = {"t_companies": fin}
    op_docs = []
    for name, spec in raw.items():
        ind, scn, uc = tags.get(name, pel)
        op_docs.append({
            "filename": name, "label": spec["label"], "industry": ind, "scenario": scn,
            "use_case": uc, "doctype": "seed", "source": "seed", "kind": "table",
            "rows": len(spec["rows"]), "status": "committed", "staging_table": name,
            "objects": ", ".join(sorted(src_objects.get(name, []))),
            "bindings": sum(1 for b in all_binds if b[1] == name)})
    docs.seed_samples(op_docs)
    # the broad multi-domain catalog (hundreds of sources across industries)
    docs.seed_samples(catalog.build())
    conn.close()


if __name__ == "__main__":
    reset_all()
    c = get_conn()
    for (n,) in c.execute("SELECT name FROM raw_catalog ORDER BY name"):
        cnt = c.execute('SELECT COUNT(*) FROM "%s"' % n).fetchone()[0]
        print("  %-18s %d rows" % (n, cnt))
    print("bindings:", c.execute("SELECT COUNT(*) FROM bindings").fetchone()[0],
          "| registry:", c.execute("SELECT COUNT(*) FROM object_registry").fetchone()[0])
    c.close()
