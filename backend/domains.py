"""
Multi-domain ontology — hundreds of objects/properties spanning every business
domain. This is the "menu" the LLM maps ANY upload into; new objects/properties
still auto-grow when something genuinely novel arrives.

Each domain -> object -> [(property, type, unit)]. PEL lives in canonical.py and
is merged with these.
"""

DOMAINS = {
    "Finance · Corporate / Markets": {
        "Company": [("name", "string", ""), ("ticker", "string", ""), ("index", "enum", ""),
                    ("sector", "string", ""), ("country", "string", ""),
                    ("market_cap_mn", "number", "USD mn"), ("revenue_mn", "number", "USD mn"),
                    ("net_income_mn", "number", "USD mn"), ("pe", "number", "x"),
                    ("dividend_yield", "number", "%"), ("employees", "number", ""),
                    ("gross_margin", "number", "%"), ("rd_pct", "number", "%")],
        "Statement": [("company", "string", ""), ("period", "string", "date"),
                      ("revenue", "number", "USD mn"), ("ebitda", "number", "USD mn"),
                      ("net_income", "number", "USD mn"), ("assets", "number", "USD mn"),
                      ("liabilities", "number", "USD mn"), ("cash_flow", "number", "USD mn")],
        "Filing": [("company", "string", ""), ("type", "enum", ""), ("date", "string", "date"),
                   ("period", "string", ""), ("url", "string", "")],
        "Estimate": [("company", "string", ""), ("metric", "string", ""),
                     ("consensus", "number", ""), ("actual", "number", ""),
                     ("surprise_pct", "number", "%")],
        "Analyst": [("name", "string", ""), ("firm", "string", ""), ("rating", "enum", ""),
                    ("target_price", "number", "USD"), ("company", "string", "")],
    },
    "Stock Trading": {
        "Security": [("ticker", "string", ""), ("name", "string", ""), ("exchange", "enum", ""),
                     ("sector", "string", ""), ("price", "number", "USD"),
                     ("market_cap_mn", "number", "USD mn"), ("pe", "number", "x"),
                     ("beta", "number", ""), ("dividend_yield", "number", "%")],
        "Trade": [("ticker", "string", ""), ("side", "enum", ""), ("qty", "number", ""),
                  ("price", "number", "USD"), ("venue", "string", ""), ("timestamp", "string", "date")],
        "Position": [("portfolio", "string", ""), ("ticker", "string", ""), ("qty", "number", ""),
                     ("avg_cost", "number", "USD"), ("unrealized_pnl", "number", "USD")],
        "Portfolio": [("name", "string", ""), ("aum_mn", "number", "USD mn"),
                      ("strategy", "string", ""), ("return_ytd", "number", "%"),
                      ("sharpe", "number", "")],
        "MarketData": [("ticker", "string", ""), ("date", "string", "date"), ("open", "number", "USD"),
                       ("high", "number", "USD"), ("low", "number", "USD"), ("close", "number", "USD"),
                       ("volume", "number", "")],
    },
    "Crypto · Bitcoin": {
        "CryptoAsset": [("symbol", "string", ""), ("name", "string", ""),
                        ("price_usd", "number", "USD"), ("market_cap_mn", "number", "USD mn"),
                        ("circulating_supply", "number", ""), ("volume_24h_mn", "number", "USD mn"),
                        ("change_24h", "number", "%")],
        "CryptoTxn": [("hash", "string", ""), ("from_addr", "string", ""), ("to_addr", "string", ""),
                      ("amount", "number", ""), ("fee", "number", ""), ("block", "number", ""),
                      ("timestamp", "string", "date")],
        "Wallet": [("address", "string", ""), ("balance", "number", ""), ("label", "string", ""),
                   ("chain", "enum", "")],
        "Exchange": [("name", "string", ""), ("volume_24h_mn", "number", "USD mn"),
                     ("pairs", "number", ""), ("country", "string", "")],
        "Block": [("height", "number", ""), ("hash", "string", ""), ("txns", "number", ""),
                  ("miner", "string", ""), ("reward", "number", "BTC"), ("timestamp", "string", "date")],
    },
    "Healthcare · Medicine": {
        "Drug": [("name", "string", ""), ("generic", "string", ""), ("drug_class", "string", ""),
                 ("form", "enum", ""), ("strength_mg", "number", "mg"), ("manufacturer", "string", ""),
                 ("price_inr", "number", "INR"), ("approval_status", "enum", "")],
        "ClinicalTrial": [("trial_id", "string", ""), ("phase", "enum", ""), ("indication", "string", ""),
                          ("enrollment", "number", ""), ("sponsor", "string", ""), ("status", "enum", ""),
                          ("primary_endpoint", "string", "")],
        "Provider": [("name", "string", ""), ("specialty", "string", ""), ("npi", "string", ""),
                     ("region", "string", ""), ("annual_volume", "number", "")],
        "Diagnosis": [("code", "string", ""), ("description", "string", ""),
                      ("prevalence_pct", "number", "%")],
    },
    "Patient Records": {
        "Patient": [("patient_id", "string", ""), ("age", "number", "years"), ("sex", "enum", ""),
                    ("region", "string", ""), ("risk_score", "number", "")],
        "Encounter": [("patient_id", "string", ""), ("date", "string", "date"), ("type", "enum", ""),
                      ("department", "string", ""), ("los_days", "number", "days")],
        "LabResult": [("patient_id", "string", ""), ("test", "string", ""), ("value", "number", ""),
                      ("unit", "string", ""), ("flag", "enum", "")],
        "Medication": [("patient_id", "string", ""), ("drug", "string", ""), ("dose", "string", ""),
                       ("frequency", "string", ""), ("adherence_pct", "number", "%")],
        "Vital": [("patient_id", "string", ""), ("bp_systolic", "number", "mmHg"),
                  ("bp_diastolic", "number", "mmHg"), ("heart_rate", "number", "bpm"),
                  ("bmi", "number", "")],
    },
    "Strategy Consulting": {
        "Engagement": [("client", "string", ""), ("type", "enum", ""), ("start", "string", "date"),
                       ("duration_weeks", "number", "weeks"), ("fees_inr_mn", "number", "INR mn"),
                       ("partner", "string", ""), ("status", "enum", "")],
        "Recommendation": [("engagement", "string", ""), ("area", "string", ""), ("priority", "enum", ""),
                           ("impact_inr_mn", "number", "INR mn"), ("status", "enum", "")],
        "ConsultingClient": [("name", "string", ""), ("industry", "string", ""),
                             ("revenue_mn", "number", "INR mn"), ("region", "string", "")],
        "Benchmark": [("metric", "string", ""), ("industry", "string", ""), ("value", "number", ""),
                      ("percentile", "number", "")],
    },
    "Tech Consulting": {
        "TechProject": [("name", "string", ""), ("client", "string", ""), ("stack", "string", ""),
                        ("budget_inr_mn", "number", "INR mn"), ("status", "enum", ""),
                        ("team_size", "number", "")],
        "System": [("name", "string", ""), ("type", "enum", ""), ("criticality", "enum", ""),
                   ("uptime_pct", "number", "%"), ("cloud", "enum", "")],
        "TechCapability": [("name", "string", ""), ("maturity", "number", "1-5"), ("owner", "string", "")],
        "TechRisk": [("system", "string", ""), ("risk", "string", ""), ("severity", "enum", ""),
                     ("likelihood", "enum", ""), ("mitigation", "string", "")],
    },
    "Marketing": {
        "Campaign": [("name", "string", ""), ("channel", "enum", ""), ("budget_inr", "number", "INR"),
                     ("impressions", "number", ""), ("clicks", "number", ""),
                     ("conversions", "number", ""), ("roas", "number", "x")],
        "Audience": [("segment", "string", ""), ("size", "number", ""), ("cac_inr", "number", "INR"),
                     ("ltv_inr", "number", "INR")],
        "Lead": [("source", "string", ""), ("score", "number", ""), ("stage", "enum", ""),
                 ("value_inr", "number", "INR")],
        "MktChannel": [("name", "string", ""), ("spend_inr", "number", "INR"), ("cpl_inr", "number", "INR"),
                       ("conversion_rate", "number", "%")],
        "Creative": [("name", "string", ""), ("format", "enum", ""), ("ctr", "number", "%"),
                     ("engagement_rate", "number", "%")],
    },
}


def build_entries():
    """Flatten DOMAINS into canonical entries: {domain, object, property, type, unit, desc, level, aliases, value_kind, seed}."""
    out = []
    for domain, objs in DOMAINS.items():
        level = domain.split("·")[0].strip()[:3].upper()
        for obj, props in objs.items():
            for (p, t, u) in props:
                out.append({"object": obj, "property": p, "type": t, "unit": u,
                            "desc": "%s %s" % (obj, p.replace("_", " ")), "domain": domain,
                            "level": level, "aliases": [], "value_kind": None, "seed": False})
    return out
