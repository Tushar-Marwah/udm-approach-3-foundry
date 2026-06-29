"""
The multi-domain document catalog.

Generates hundreds of ingested-source records spanning PEL and many other
industries / scenarios / use-cases, so the platform reads like a mature,
multi-domain Foundry instance rather than a single demo. Deterministic
(hash-based) -- stable and re-runnable. These are catalog records (the
registry of everything ingested); the PEL scenario is additionally
materialised as live, queryable data + governed ontology.
"""
import datetime
import hashlib

# industry, scenario, use_case, entities, doctypes, objects, periods
DOMAINS = [
    ("Packaged Water (FMCG)", "PEL · Pricing & Positioning", "Competitive strategy",
     ["Bisleri", "Kinley", "Aquafina", "Bailley", "Himalayan", "Qua"],
     ["price_scrape", "spec_sheet", "erp_export", "distributor_sheet", "consumer_survey",
      "market_report", "annual_report"],
     "Brand, Product, PricePoint, Transaction, Attribute", ["FY25", "FY26"]),
    ("Snacks (FMCG)", "PEL · Pricing & Positioning", "Competitive strategy",
     ["Haldiram", "Bikaji", "Balaji", "Lays", "Bingo"],
     ["price_scrape", "spec_sheet", "erp_export", "consumer_survey", "market_report"],
     "Brand, Product, PricePoint, Attribute", ["FY25", "FY26"]),
    ("Personal Care (FMCG)", "PEL · Pricing & Positioning", "Competitive strategy",
     ["HUL", "Dabur", "Patanjali", "Himalaya", "Marico"],
     ["price_scrape", "spec_sheet", "nps_survey", "market_report"],
     "Brand, Product, PricePoint, Attribute", ["FY25", "FY26"]),
    ("Mining & Metals", "ESG · BRSR", "Sustainability reporting",
     ["MSPL", "Baldota Group", "RMML-IGIOM", "Vedanta", "NMDC"],
     ["emissions_log", "water_log", "waste_log", "social_disclosure", "governance_index",
      "brsr_filing", "annual_report"],
     "Company, Emission, WaterUse, WasteStream, SocialMetric", ["FY24", "FY25", "FY26"]),
    ("Packaging", "ESG · GRI", "Sustainability reporting",
     ["UFlex", "EPL", "Huhtamaki", "TimeTechno"],
     ["gri_index", "emissions_log", "lca_report", "annual_report"],
     "Company, Emission, MaterialFlow", ["FY24", "FY25"]),
    ("Automobile", "ESG · GRI", "Sustainability reporting",
     ["Tata Motors", "Mahindra", "Maruti", "Ashok Leyland"],
     ["gri_index", "emissions_log", "supplier_audit", "annual_report"],
     "Company, Emission, Supplier", ["FY24", "FY25", "FY26"]),
    ("Pharmaceuticals", "Supply Chain · Risk", "Operations risk",
     ["Sun Pharma", "Cipla", "Dr Reddy", "Lupin"],
     ["batch_qc", "shipment_log", "supplier_audit", "lab_report", "recall_notice"],
     "Facility, Shipment, Supplier, QualityMetric", ["FY25", "FY26"]),
    ("Telecom", "Competitive Intelligence", "Market analysis",
     ["Jio", "Airtel", "Vi", "BSNL"],
     ["arpu_report", "market_share", "tariff_scrape", "nps_survey"],
     "Operator, Plan, MarketShare, Attribute", ["FY25", "FY26"]),
    ("Banking & FS", "Competitive Intelligence", "Market analysis",
     ["HDFC", "ICICI", "SBI", "Axis", "Kotak"],
     ["rate_card", "market_share", "financials", "nps_survey"],
     "Bank, Product, Rate, MarketShare", ["FY25", "FY26"]),
    ("Retail", "Demand & Pricing", "Revenue management",
     ["DMart", "Reliance Retail", "BigBasket", "Blinkit"],
     ["pos_export", "price_scrape", "basket_analysis", "promo_calendar"],
     "Store, SKU, PricePoint, Transaction", ["FY26"]),
    ("Energy & Utilities", "ESG · CDP", "Climate disclosure",
     ["NTPC", "Adani Power", "Tata Power", "JSW Energy"],
     ["cdp_response", "emissions_log", "fuel_mix", "annual_report"],
     "Company, Emission, FuelMix", ["FY24", "FY25", "FY26"]),
    ("Consumer Electronics", "PEL · Pricing", "Competitive strategy",
     ["Samsung", "Xiaomi", "OnePlus", "Realme", "Apple"],
     ["price_scrape", "spec_sheet", "review_mining", "market_report"],
     "Brand, Product, PricePoint, Attribute", ["FY26"]),
    ("Healthcare · Medicine", "Drug & Trial Intelligence", "R&D / market access",
     ["Pfizer", "Sun Pharma", "Cipla", "Dr Reddy", "Novartis"],
     ["drug_master", "trial_registry", "provider_list", "price_list", "lab_report"],
     "Drug, ClinicalTrial, Provider, Diagnosis", ["FY25", "FY26"]),
    ("Patient Records (EHR)", "Population Health", "Clinical analytics",
     ["Apollo", "Fortis", "Max Healthcare", "Manipal"],
     ["ehr_export", "lab_results", "vitals_log", "medication_log", "encounters"],
     "Patient, Encounter, LabResult, Medication, Vital", ["FY25", "FY26"]),
    ("Equity Trading", "Systematic Trading", "Quant strategy",
     ["AlphaQuant Fund", "Meridian Capital", "BluePeak", "Helios"],
     ["trade_blotter", "positions", "market_data", "pnl_report", "order_log"],
     "Security, Trade, Position, Portfolio, MarketData", ["FY26"]),
    ("Crypto · Bitcoin", "Digital Assets", "On-chain analytics",
     ["Bitcoin", "Ethereum", "Binance", "Coinbase", "Kraken"],
     ["onchain_export", "price_feed", "exchange_volume", "wallet_audit", "block_data"],
     "CryptoAsset, CryptoTxn, Wallet, Exchange, Block", ["FY26"]),
    ("Strategy Consulting", "Corporate Strategy", "Engagement delivery",
     ["Tata Group", "Aditya Birla", "Mahindra", "Reliance"],
     ["engagement_brief", "recommendations", "benchmark_study", "market_scan"],
     "Engagement, Recommendation, ConsultingClient, Benchmark", ["FY25", "FY26"]),
    ("Tech Consulting", "Digital Transformation", "Programme delivery",
     ["HDFC Bank", "Airtel", "Vodafone Idea", "Flipkart"],
     ["project_charter", "system_inventory", "risk_register", "capability_map"],
     "TechProject, System, TechCapability, TechRisk", ["FY26"]),
    ("Marketing", "Growth & Performance", "Demand generation",
     ["Nykaa", "Mamaearth", "boAt", "CRED", "Swiggy"],
     ["campaign_export", "audience_segments", "lead_funnel", "channel_spend", "creative_performance"],
     "Campaign, Audience, Lead, MktChannel, Creative", ["FY26"]),
]

# a realistic project tag per industry (project search + the project column)
PROJECTS = {
    "Packaged Water (FMCG)": "PEL Water Benchmarking FY26", "Snacks (FMCG)": "PEL Snacks Pricing",
    "Personal Care (FMCG)": "PEL Personal Care", "Mining & Metals": "BRSR ESG FY26 — Mining",
    "Packaging": "GRI Disclosure — Packaging", "Automobile": "GRI Disclosure — Auto",
    "Pharmaceuticals": "Supply-Chain Risk Review", "Telecom": "Telecom Market Watch",
    "Banking & FS": "FS Competitive Scan", "Retail": "Retail Revenue Management",
    "Energy & Utilities": "CDP Climate FY26", "Consumer Electronics": "Electronics Price Watch",
    "Healthcare · Medicine": "Drug & Trial Intelligence", "Patient Records (EHR)": "Population Health Analytics",
    "Equity Trading": "Systematic Trading Desk", "Crypto · Bitcoin": "Digital-Asset Analytics",
    "Strategy Consulting": "Corporate Strategy Engagements", "Tech Consulting": "Digital Transformation PMO",
    "Marketing": "Growth & Performance FY26", "Finance · Corporate / Markets": "Index Coverage FY26",
}

EXT = {"price_scrape": "csv", "spec_sheet": "csv", "erp_export": "xlsx", "distributor_sheet": "csv",
       "consumer_survey": "csv", "nps_survey": "csv", "market_report": "pdf", "annual_report": "pdf",
       "emissions_log": "csv", "water_log": "csv", "waste_log": "csv", "social_disclosure": "pdf",
       "governance_index": "xlsx", "brsr_filing": "pdf", "gri_index": "xlsx", "lca_report": "pdf",
       "supplier_audit": "xlsx", "batch_qc": "csv", "shipment_log": "csv", "lab_report": "pdf",
       "recall_notice": "pdf", "arpu_report": "xlsx", "market_share": "xlsx", "tariff_scrape": "csv",
       "rate_card": "xlsx", "financials": "xlsx", "pos_export": "csv", "basket_analysis": "xlsx",
       "promo_calendar": "csv", "cdp_response": "pdf", "fuel_mix": "csv", "review_mining": "csv",
       "material_flow": "csv", "drug_master": "csv", "trial_registry": "xlsx", "provider_list": "csv",
       "price_list": "csv", "ehr_export": "csv", "lab_results": "csv", "vitals_log": "csv",
       "medication_log": "csv", "encounters": "csv", "trade_blotter": "csv", "positions": "xlsx",
       "market_data": "csv", "pnl_report": "xlsx", "order_log": "csv", "onchain_export": "csv",
       "price_feed": "csv", "exchange_volume": "csv", "wallet_audit": "csv", "block_data": "csv",
       "engagement_brief": "pdf", "recommendations": "xlsx", "benchmark_study": "pdf",
       "market_scan": "pdf", "project_charter": "pdf", "system_inventory": "xlsx",
       "risk_register": "xlsx", "capability_map": "xlsx", "campaign_export": "csv",
       "audience_segments": "csv", "lead_funnel": "csv", "channel_spend": "csv",
       "creative_performance": "csv", "10k_filing": "pdf", "broker_note": "pdf"}
DOC_KINDS = {"pdf"}   # unstructured -> Claude extraction


def _h(*p):
    return int(hashlib.md5("|".join(str(x) for x in p).encode()).hexdigest(), 16)


def _date(seed):
    base = datetime.date(2025, 1, 1)
    return (base + datetime.timedelta(days=_h(seed) % 540)).strftime("%Y-%m-%d %H:%M")


def _rows(dt, seed):
    if EXT.get(dt) == "pdf":
        return 1 + _h(seed, "r") % 6            # docs -> few extracted records
    base = {"price_scrape": 1800, "tariff_scrape": 1400, "pos_export": 9000, "erp_export": 4200,
            "emissions_log": 2600, "water_log": 1900, "waste_log": 1500, "consumer_survey": 480,
            "nps_survey": 520, "shipment_log": 7400, "batch_qc": 3100}.get(dt, 900)
    return base + _h(seed, "r") % base


def build():
    out = []
    for industry, scenario, use_case, entities, doctypes, objects, periods in DOMAINS:
        for ent in entities:
            for dt in doctypes:
                # weekly granularity for scrapes -> many files; else 1 per period
                periods_for = (["W%02d" % w for w in range(1, 5)] if "scrape" in dt or dt == "pos_export"
                               else periods)
                for per in periods_for:
                    code = ent.split()[0].lower().replace("&", "")
                    fn = "%s_%s_%s.%s" % (code, dt, per.lower(), EXT.get(dt, "csv"))
                    seed = (industry, ent, dt, per)
                    ext = EXT.get(dt, "csv")
                    st = _h(seed, "s") % 20
                    status = "committed" if st < 17 else ("landed" if st < 19 else "processing")
                    out.append({
                        "filename": fn,
                        "label": "%s — %s" % (ent, dt.replace("_", " ")),
                        "industry": industry, "scenario": scenario, "use_case": use_case,
                        "entities": ent, "project": PROJECTS.get(industry, scenario),
                        "doctype": ext, "source": "seed",
                        "kind": "doc" if ext in DOC_KINDS else "table",
                        "rows": _rows(dt, seed), "status": status,
                        "staging_table": "", "objects": objects if status == "committed" else "",
                        "bindings": (len(objects.split(",")) * (1 + _h(seed) % 4)) if status == "committed" else 0,
                        "narrative": (_h(seed, "n") % 6) if ext in DOC_KINDS and status == "committed" else 0,
                        "cost_usd": round(0.0004 + (_h(seed, "c") % 30) / 10000.0, 5)
                                    if ext in DOC_KINDS else round((_h(seed, "c") % 8) / 10000.0, 5),
                        "date": _date(seed),
                    })
    out.extend(_company_docs())
    return out


def _company_docs():
    """One filing-style doc per company per type -> entity-searchable finance docs."""
    import companies
    docs = []
    roster = [(n, t, s, "S&P 500") for n, t, s in companies.SP500] + \
             [(n, t, s, "BSE 100") for n, t, s in companies.BSE100]
    for name, tick, sector, idx in roster:
        for dt in ["annual_report", "10k_filing", "broker_note"]:
            seed = ("Finance", name, dt)
            ext = EXT.get(dt, "pdf")
            code = tick.lower().replace(".", "").replace("&", "").replace("-", "")
            docs.append({
                "filename": "%s_%s_fy26.%s" % (code, dt, ext),
                "label": "%s (%s) — %s" % (name, tick, dt.replace("_", " ")),
                "industry": "Finance · Corporate / Markets", "scenario": "Capital Markets",
                "use_case": "Equity research", "entities": name,
                "project": "%s Coverage FY26" % idx, "doctype": ext, "source": "seed",
                "kind": "doc", "rows": 1 + _h(seed) % 5, "status": "committed",
                "staging_table": "", "objects": "Company, Statement, Filing, Estimate",
                "bindings": 4 + _h(seed) % 6, "narrative": _h(seed, "n") % 5,
                "cost_usd": round(0.0006 + (_h(seed, "c") % 40) / 10000.0, 5), "date": _date(seed),
            })
    return docs


if __name__ == "__main__":
    d = build()
    from collections import Counter
    print("total catalog docs:", len(d))
    print("industries:", len(Counter(x["industry"] for x in d)))
    print("projects:", len(Counter(x["project"] for x in d)))
    print("with entities:", sum(1 for x in d if x.get("entities")))
