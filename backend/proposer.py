"""
The mapping proposer -- proposes how each incoming column binds to a canonical
PEL property, with a confidence each.

Two engines:
  propose_llm  (default when a backend is configured) -- Claude reads the headers,
               sample values, and the whole PEL dictionary, and returns bindings.
               It can also propose BRAND-NEW objects/properties (auto-grow) when a
               column is a genuinely new concept, or send it to the RAG tail.
  heuristic    (offline fallback) -- value-aware matching against the water core.

Both return: {file_object, proposals, tail, engine, cost_usd}
Each proposal: {column, sample, object, property, transform, confidence, kind,
                note, is_new(bool), type, unit}
"""
import re

import llm
import units
from canonical import HEURISTIC, dictionary_text, canonical_for

AUTO = 0.85
TAIL = 0.50
SHARED_PROPS = {"sku", "brand", "channel", "period"}
TRANSFORMS = ["-", "strip_currency", "to_int", "to_ml", "parse_months",
              "enum_channel", "parse_brand", "parse_sku", "divide"]

_BRANDS = ["bisleri", "kinley", "bailley", "aquafina", "kingfisher",
           "himalayan", "rail neer", "qua", "vedica"]
_CHANNELS = ["blinkit", "zepto", "instamart", "swiggy", "jiomart", "amazon",
             "flipkart", "gt", "mt", "general trade", "modern trade", "horeca",
             "quick", "ecom"]
_REGIONS = ["mumbai", "delhi", "bangalore", "bengaluru", "chennai", "kolkata",
            "pune", "hyderabad"]


def _nonempty(vals):
    return [str(v).strip() for v in vals if v is not None and str(v).strip() != ""]


def _sample_of(vals):
    ne = _nonempty(vals)
    return ne[0] if ne else ""


# ==========================================================================
# LLM proposer (default)
# ==========================================================================
def propose_llm(headers, rows):
    samples = {h: _nonempty([r.get(h) for r in rows])[:4] for h in headers}
    sample_block = "\n".join("  %s: %s" % (h, samples[h]) for h in headers)
    sys = ("You map columns from an incoming data file onto a fixed business ontology "
           "(the PEL data model). You output strict JSON only, no prose.")
    prompt = (
        "Here is the canonical ontology (objects and their properties):\n\n"
        + dictionary_text()
        + "\n\nAvailable transforms (clean rules applied on read): "
        + ", ".join(TRANSFORMS)
        + " ('-' means no transform; strip_currency for 'Rs.20'->20; to_ml for '1L'->1000; "
        "parse_months for '12mo'->12; enum_channel for 'Blinkit'->quick_commerce; "
        "parse_brand/parse_sku to split a product name like 'Bisleri 1L' into a brand and a sku; "
        "divide(a,b) for derived ratios).\n\n"
        "INCOMING FILE columns with sample values:\n" + sample_block + "\n\n"
        "Map each column to the best object.property in the ontology. Rules:\n"
        "- Prefer an existing ontology property. Choose the object that the file as a whole is about.\n"
        "- A product-name column may map to TWO properties (brand via parse_brand AND sku via parse_sku) "
        "-> emit two proposals for it.\n"
        "- If a column is a genuinely new concept that does not fit any property, propose a NEW property "
        "(set is_new=true, give a snake_case property name, the best object or a new object name, plus type and unit).\n"
        "- If a column is noise / free-text with no analytical value, put it in tail instead.\n"
        "- confidence is 0..1 (how sure the mapping is).\n"
        "- source_unit: the unit you can SEE in this column's header or values "
        "(e.g. 'INR crore', 'INR mn', '1-10', '%', 'mg/L', 'ml', 'USD'). Leave '' if none/plain count. "
        "Do NOT try to convert it yourself — just report what you see.\n\n"
        "Return JSON exactly:\n"
        '{"file_object": "<the dominant object>",\n'
        ' "proposals": [{"column": "...", "object": "...", "property": "...", "transform": "<one of the transforms>",\n'
        '   "confidence": 0.0, "is_new": false, "type": "string|number|enum", "unit": "", "source_unit": "", "note": "why"}],\n'
        ' "tail": [{"column": "...", "reason": "..."}]}'
    )
    res = llm.complete(prompt, system=sys, model=llm.EXTRACT_MODEL, max_tokens=3000)
    parsed = llm.extract_json(res["text"])

    proposals = []
    for p in parsed.get("proposals", []):
        col = p.get("column")
        if col is None:
            continue
        conf = float(p.get("confidence", 0.7))
        tf = p.get("transform", "-")
        if tf not in TRANSFORMS:
            tf = "-"
        prop = {
            "column": col, "sample": _sample_of([r.get(col) for r in rows]),
            "object": p.get("object", parsed.get("file_object", "Unknown")),
            "property": p.get("property", "value"),
            "transform": tf, "confidence": round(conf, 2),
            "kind": "auto" if conf >= AUTO else "review",
            "note": p.get("note", ""), "is_new": bool(p.get("is_new", False)),
            "type": p.get("type", "string"), "unit": p.get("unit", ""),
            "factor": 1.0, "offset": 0.0, "source_unit": p.get("source_unit", "") or "",
        }
        _attach_units(prop)
        proposals.append(prop)
    tail = [{"column": t.get("column", ""), "sample": _sample_of([r.get(t.get("column")) for r in rows]),
             "reason": t.get("reason", "no canonical home")} for t in parsed.get("tail", [])]

    _infer_period(proposals, parsed.get("file_object", ""))
    return {"file_object": parsed.get("file_object", ""), "proposals": proposals,
            "tail": tail, "engine": "llm (%s)" % llm.EXTRACT_MODEL,
            "cost_usd": res.get("cost_usd", 0)}


def _attach_units(p):
    """Detected source unit -> deterministic conversion on the binding."""
    if p.get("is_new"):                       # a new property defines its own unit
        return
    canon = canonical_for(p["object"], p["property"])
    canon_unit = canon["unit"] if canon else ""
    det = p.get("source_unit") or ""
    if not canon_unit or not det:
        return
    f, o, status, note = units.conversion(det, canon_unit)
    if status == "exact":
        p["factor"], p["offset"] = f, o
        p["note"] = (p.get("note", "") + " · unit " + note).strip(" ·")
    elif status == "flag":
        p["kind"] = "review"
        p["confidence"] = min(p.get("confidence", 0.7), 0.55)
        p["note"] = ("⚠ " + note + " · " + p.get("note", "")).strip(" ·")
    elif status == "unknown" and note:
        p["note"] = (p.get("note", "") + " · " + note).strip(" ·")


def _infer_period(proposals, file_object):
    objs_with_period = {p["object"] for p in proposals if p["property"] == "period"}
    price_objs = {p["object"] for p in proposals
                  if p["property"] in ("selling_price", "list_price", "channel")}
    for obj in price_objs:
        if obj not in objs_with_period:
            proposals.append({
                "column": "_landed_on", "sample": "(ingest date)", "object": obj,
                "property": "period", "transform": "-", "confidence": 1.0, "kind": "auto",
                "note": "dimension inferred from the source", "is_new": False,
                "type": "string", "unit": "date"})
            objs_with_period.add(obj)


# ==========================================================================
# Offline heuristic (fallback) -- value-aware, water core only
# ==========================================================================
_COMPAT = {"currency": {"integer"}, "integer": {"currency"},
           "code_or_name": {"brand_name"}, "brand_name": {"code_or_name"}}


def detect_value_kind(vals):
    vals = _nonempty(vals)
    if not vals:
        return "empty"

    def frac(pred):
        return sum(1 for v in vals if pred(v)) / len(vals)

    if frac(lambda v: bool(re.match(r"^[A-Za-z]{2,4}-\d", v))) >= 0.5:
        return "code_or_name"
    if frac(lambda v: any(b in v.lower() for b in _BRANDS)) >= 0.5:
        return "brand_name"
    if frac(lambda v: bool(re.search(r"[₹]|rs\.?|/-", v.lower())) and re.search(r"\d", v)) >= 0.5:
        return "currency"
    if frac(lambda v: bool(re.search(r"\d+\s*(mo|month|months|yr|year|years)\b", v.lower()))) >= 0.5:
        return "duration_months"
    if frac(lambda v: bool(re.search(r"^\s*\d+(\.\d+)?\s*(ml|l|ltr|litre|liter)\s*$", v.lower()))) >= 0.5:
        return "volume"
    if frac(lambda v: any(c in v.lower() for c in _CHANNELS)) >= 0.5:
        return "channel"
    if frac(lambda v: v.lower() in _REGIONS) >= 0.5:
        return "region"
    if frac(lambda v: bool(re.match(r"^\d{4}-\d{2}-\d{2}$", v)) or bool(re.match(r"^\d{4}-q[1-4]$", v.lower()))) >= 0.5:
        return "date"
    if frac(lambda v: bool(re.match(r"^-?\d+$", v))) >= 0.6:
        return "integer"
    if frac(lambda v: bool(re.match(r"^-?\d+(\.\d+)?$", v))) >= 0.6:
        return "currency"
    if frac(lambda v: len(v.split()) >= 3) >= 0.5:
        return "free_text"
    return "free_text"


def _name_score(header, aliases):
    h = re.sub(r"[^a-z0-9 ]", "", header.lower()).strip()
    htoks = set(h.split())
    best = 0.0
    for a in aliases:
        a = a.lower()
        if h == a:
            return 1.0
        if a in h or h in a:
            best = max(best, 0.72)
        if htoks & set(a.split()):
            best = max(best, 0.5)
    return best


def _value_score(vk, canon_kind):
    if vk == canon_kind:
        return 1.0
    if canon_kind in _COMPAT.get(vk, set()):
        return 0.5
    return 0.0


def _best_canonical(header, vk, file_object=None):
    best, best_score = None, 0.0
    for c in HEURISTIC:
        n = _name_score(header, c["aliases"])
        v = _value_score(vk, c["value_kind"])
        score = 0.55 * n + 0.45 * v
        if file_object and c["object"] == file_object:
            score += 0.08
        score = min(1.0, score)
        if score > best_score:
            best, best_score = c, score
    return best, round(best_score, 2)


def _detect_file_object(samples):
    has = {h.lower(): detect_value_kind(v) for h, v in samples.items()}
    vals = list(has.values())
    if "currency" in vals or "channel" in vals:
        if any(detect_value_kind(samples[h]) == "duration_months" for h in samples) and \
                any("tds" in h.lower() or "shelf" in h.lower() for h in samples):
            return "Product"
        return "PricePoint"
    if any(k in h for h in samples for k in ("tds", "shelf", "cert")):
        return "Product"
    if any(k in h for h in samples for k in ("unit", "revenue", "sales")):
        return "Transaction"
    return "PricePoint"


def _transform_for(canon, vk):
    kind = canon["value_kind"]
    return {"currency": "strip_currency", "volume": "to_ml", "integer": "to_int",
            "duration_months": "parse_months", "channel": "enum_channel"}.get(kind, "-")


def propose_heuristic(headers, rows):
    samples = {h: [r.get(h) for r in rows] for h in headers}
    file_object = _detect_file_object(samples)
    proposals, tail = [], []
    for h in headers:
        vk = detect_value_kind(samples[h])
        canon, score = _best_canonical(h, vk, file_object)
        sample = _sample_of(samples[h])
        if canon is None or score < TAIL:
            tail.append({"column": h, "sample": sample, "reason": "no canonical property matched"})
            continue
        prop = canon["property"]
        obj = file_object if prop in SHARED_PROPS else canon["object"]
        if vk in ("code_or_name", "brand_name") and prop in ("sku", "brand", "name"):
            targets = ([("brand", "parse_brand")] if obj == "PricePoint" else []) + [("sku", "parse_sku")]
            for tp, tf in targets:
                proposals.append({"column": h, "sample": sample, "object": obj, "property": tp,
                                  "transform": tf, "confidence": score,
                                  "kind": "auto" if score >= AUTO else "review",
                                  "note": "name parsed into " + tp, "is_new": False,
                                  "type": "string", "unit": ""})
            continue
        proposals.append({"column": h, "sample": sample, "object": obj, "property": prop,
                          "transform": _transform_for(canon, vk), "confidence": score,
                          "kind": "auto" if score >= AUTO else "review",
                          "note": "matched on name/value", "is_new": False,
                          "type": canon["type"], "unit": canon["unit"]})
    _infer_period(proposals, file_object)
    return {"file_object": file_object, "proposals": proposals, "tail": tail,
            "engine": "offline heuristic", "cost_usd": 0}


# ==========================================================================
def propose(headers, rows, use_llm=None):
    want_llm = llm.available() if use_llm is None else use_llm
    if want_llm and llm.available():
        try:
            return propose_llm(headers, rows)
        except Exception as e:  # noqa
            out = propose_heuristic(headers, rows)
            out["llm_error"] = str(e)
            return out
    return propose_heuristic(headers, rows)
