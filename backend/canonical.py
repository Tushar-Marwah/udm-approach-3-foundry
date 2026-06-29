"""
The PEL canonical dictionary -- the "menu" the ontology maps into.

This is the full six-level PEL spec rendered as business objects + properties.
Any incoming file (any level, any source system) maps into this. The LLM mapper
reads this whole dictionary; brand-new concepts that don't fit become PROPOSED
new objects/properties (auto-grow).

Entry fields:
  object, property, level, type, unit, desc   -- always present
  aliases, value_kind, seed                    -- only on the water-scenario core,
                                                  used by the offline heuristic
                                                  matcher and the seeded ontology.
"""

# ---- the water-scenario core (seeded into the DB; offline matcher uses these) ----
_CORE = [
    ("Product", "sku", "L4", "string", "", "Stock-keeping unit / product id",
     ["sku", "product", "item", "code", "name"], "code_or_name"),
    ("Product", "brand", "L4", "string", "", "Brand the product belongs to",
     ["brand", "company", "co", "co.", "maker"], "brand_name"),
    ("Product", "pack_ml", "L4", "number", "ml", "Pack size in millilitres",
     ["pack", "qty", "quantity", "size", "volume"], "volume"),
    ("Product", "tds", "L4", "number", "mg/L", "Total dissolved solids (a technical spec)",
     ["tds", "total dissolved solids", "purity"], "integer"),
    ("Product", "shelf_life_mo", "L4", "number", "months", "Shelf life in months",
     ["shelf", "shelf life", "best before", "expiry"], "duration_months"),
    ("Product", "mrp", "L4", "number", "INR", "Printed / list price",
     ["mrp", "list price", "rrp", "printed price"], "currency"),
    ("Product", "certifications", "L4", "string", "", "Quality/safety certifications held",
     ["certs", "certifications", "marks", "standards"], "free_text"),

    ("PricePoint", "brand", "L2", "string", "", "Brand at this price point",
     ["brand", "company", "co", "co."], "brand_name"),
    ("PricePoint", "sku", "L2", "string", "", "SKU at this price point",
     ["sku", "item", "product", "name"], "code_or_name"),
    ("PricePoint", "selling_price", "L2", "number", "INR", "Observed selling price",
     ["price", "rate", "mrp", "selling price", "amount", "list"], "currency"),
    ("PricePoint", "channel", "L2", "enum", "", "Sales channel",
     ["channel", "platform", "site", "trade", "store"], "channel"),
    ("PricePoint", "period", "L2", "string", "date", "When the price was observed",
     ["period", "date", "scraped_on", "as of"], "date"),

    ("Transaction", "sku", "L5", "string", "", "SKU sold",
     ["sku", "item", "product"], "code_or_name"),
    ("Transaction", "units", "L5", "number", "units", "Units sold in the period",
     ["units", "qty sold", "quantity", "units sold"], "integer"),
    ("Transaction", "revenue", "L5", "number", "INR", "Revenue in the period",
     ["revenue", "sales", "turnover", "value"], "currency"),
    ("Transaction", "channel", "L5", "enum", "", "Channel of the transactions",
     ["channel", "ch", "trade", "platform"], "channel"),
    ("Transaction", "period", "L5", "string", "date", "Reporting period",
     ["period", "month", "date", "quarter"], "date"),
    ("Transaction", "actual_price", "L5", "number", "INR", "Realised price = revenue / units",
     ["actual price", "realised price", "asp"], "currency"),
]

# ---- the rest of the PEL spec (LLM mapping targets; available for auto-grow) ----
# (object, property, level, type, unit, desc)
_EXT = [
    # L0 - executive qualitative
    ("Assessment", "role", "L0", "string", "", "Executive role giving the assessment (CEO/COO/CSO/CPO/Pricing)"),
    ("Assessment", "market_growth_outlook", "L0", "number", "1-10", "Forward view of category growth"),
    ("Assessment", "brand_strength", "L0", "number", "1-10", "Perceived brand strength vs competitors"),
    ("Assessment", "innovation_posture", "L0", "number", "1-10", "Maturity/pace of innovation"),
    ("Assessment", "competitive_intensity", "L0", "number", "1-10", "Perceived crowding/aggressiveness"),
    ("Assessment", "customer_value_perception", "L0", "number", "1-10", "Leadership read on value-for-money"),
    ("Assessment", "disruption_risk", "L0", "number", "1-10", "Assessed likelihood of disruption"),
    ("Assessment", "strategic_priorities", "L0", "string", "", "Stated strategic direction/constraints"),

    # L1 - market context
    ("Market", "name", "L1", "string", "", "Market / category / geography"),
    ("Market", "tam", "L1", "number", "INR mn", "Total addressable market"),
    ("Market", "sam", "L1", "number", "INR mn", "Serviceable addressable market"),
    ("Market", "som", "L1", "number", "INR mn", "Serviceable obtainable market"),
    ("Market", "cagr_value", "L1", "number", "%", "Category value CAGR"),
    ("Market", "cagr_volume", "L1", "number", "%", "Category volume CAGR"),
    ("Market", "hhi", "L1", "number", "index", "Concentration (HHI / CR4 inputs)"),
    ("Market", "avg_firm_age", "L1", "number", "years", "Mean age of established players (maturity)"),
    ("Market", "growth_deceleration", "L1", "number", "index", "Slowing-growth measure"),

    # L2 - competitive intelligence (company level)
    ("Brand", "name", "L2", "string", "", "Brand / company name"),
    ("Brand", "sector", "L2", "string", "", "Sector / category"),
    ("Brand", "market_share", "L2", "number", "%", "Share of category revenue or volume"),
    ("Brand", "brand_perception", "L2", "number", "1-10", "Customer brand-attribute rating"),
    ("Brand", "feature_completeness", "L2", "number", "0-1", "Share of category features offered"),
    ("Brand", "gross_margin", "L5", "number", "%", "Gross profit as % of revenue"),
    ("Brand", "rd_investment", "L4", "number", "%", "R&D spend as % of revenue"),
    ("Brand", "patents", "L4", "number", "count", "Active patents held"),
    ("Brand", "sustainability_score", "L4", "number", "0-1", "ESG / sustainability composite"),
    ("Brand", "new_product_revenue_share", "L4", "number", "%", "Revenue from products launched recently"),

    ("Channel", "name", "L2", "string", "", "Channel name (MT/GT/HoReCa/ecom/D2C/...)"),
    ("Channel", "coverage", "L2", "number", "0-1", "Presence in this channel"),
    ("Channel", "importance_weight", "L2", "number", "decimal", "Strategic weight of the channel"),

    # L3 - customer value perception
    ("Attribute", "name", "L3", "string", "", "Value attribute (purity/taste/trust/availability/...)"),
    ("Attribute", "importance_weight", "L3", "number", "decimal", "Importance weight (sums to 1)"),
    ("Attribute", "performance_score", "L3", "number", "1-10", "Brand performance on the attribute"),
    ("Attribute", "brand", "L3", "string", "", "Brand the score applies to"),
    ("Market", "price_sensitivity", "L3", "number", "elasticity", "Demand elasticity wrt price"),
    ("Market", "wtp_premium", "L3", "number", "%", "Willingness-to-pay premium over anchor"),

    # L4 - product / service performance (extra metrics)
    ("Product", "defect_rate", "L4", "number", "%", "Share of output failing quality standards"),
    ("Product", "customer_issues_rate", "L4", "number", "%", "Customer-reported quality issues rate"),
    ("Product", "return_rate", "L4", "number", "%", "Units/orders returned"),
    ("Product", "shipping_lead_time", "L4", "number", "days", "Order-to-delivery time"),
    ("Product", "order_accuracy", "L4", "number", "%", "Orders fulfilled correctly"),
    ("Product", "feature_completeness", "L4", "number", "0-1", "Features present vs category set"),

    # L5 - transaction-level (extra metrics)
    ("PricePoint", "list_price", "L5", "number", "INR", "Pre-discount nominal list price"),
    ("PricePoint", "region", "L2", "string", "", "Geography of the observation"),
    ("Transaction", "aov", "L5", "number", "INR", "Average order value"),
    ("Transaction", "cac", "L5", "number", "INR", "Customer acquisition cost"),
    ("Transaction", "clv", "L5", "number", "INR", "Customer lifetime value"),
    ("Transaction", "repeat_rate", "L5", "number", "%", "Share of repeat customers"),
    ("Transaction", "churn_rate", "L5", "number", "%", "Customer attrition rate"),
    ("Transaction", "price_realization", "L5", "number", "%", "Realised price as % of list"),
    ("Transaction", "discount_frequency", "L5", "number", "%", "Share of orders discounted"),
    ("Transaction", "gross_margin", "L5", "number", "%", "Gross margin %"),
]

_PEL_DOMAIN = "PEL · Packaged Goods"
CANONICAL = []
for o, p, lv, t, u, d, al, vk in _CORE:
    CANONICAL.append({"object": o, "property": p, "level": lv, "type": t, "unit": u,
                      "desc": d, "domain": _PEL_DOMAIN, "aliases": al, "value_kind": vk, "seed": True})
for o, p, lv, t, u, d in _EXT:
    CANONICAL.append({"object": o, "property": p, "level": lv, "type": t, "unit": u,
                      "desc": d, "domain": _PEL_DOMAIN, "aliases": [], "value_kind": None, "seed": False})

# merge every other business domain (hundreds of objects/properties)
import domains
CANONICAL.extend(domains.build_entries())

# the offline heuristic only considers the PEL water core (entries with a value_kind)
HEURISTIC = [c for c in CANONICAL if c.get("value_kind")]


def canonical_for(obj, prop):
    for c in CANONICAL:
        if c["object"] == obj and c["property"] == prop:
            return c
    return None


def dictionary_text():
    """Compact, domain-grouped rendering of the whole multi-domain dictionary
    for the LLM mapper's prompt (one line per object)."""
    by_dom = {}
    for c in CANONICAL:
        by_dom.setdefault(c.get("domain", "Other"), {}).setdefault(c["object"], []).append(c["property"])
    lines = []
    for dom, objs in by_dom.items():
        lines.append("# %s" % dom)
        for obj, props in objs.items():
            lines.append("  %s: %s" % (obj, ", ".join(props)))
    return "\n".join(lines)


def known_objects():
    return sorted({c["object"] for c in CANONICAL})
