"""
Deterministic unit conversion.

The LLM only *detects* the source unit; this module *decides* the conversion —
so the factor is never an LLM guess (which gets crore/mn direction wrong).

conversion(source_unit, canonical_unit) -> (factor, offset, status, note)
  status:
    same    -- identical unit, no conversion
    exact   -- same physical dimension (money magnitude / mass / volume / time);
               factor applied automatically:  canonical = value * factor + offset
    flag    -- semantic mismatch that must NOT be auto-scaled: currency/FX change,
               or rating-scale re-anchoring (1-10 vs 0-100). Routed to human confirm.
    unknown -- could not resolve; left as-is (factor 1) and noted.
    none    -- nothing to do (no canonical unit, or no detected unit).
"""
import re

# value of each magnitude token expressed in the family's base unit
MONEY = {"mn": 1, "million": 1, "mm": 1, "m": 1, "crore": 10, "crores": 10, "cr": 10,
         "lakh": 0.1, "lakhs": 0.1, "lac": 0.1, "bn": 1000, "billion": 1000,
         "thousand": 0.001, "k": 0.001}          # base = 1 million
MASS = {"g": 1, "gram": 1, "grams": 1, "gm": 1, "kg": 1000, "kilogram": 1000,
        "mg": 0.001, "ton": 1e6, "tonne": 1e6, "mt": 1e6}                     # base = gram
VOLUME = {"ml": 1, "l": 1000, "ltr": 1000, "litre": 1000, "liter": 1000, "cl": 10, "kl": 1e6}
TIME_MO = {"mo": 1, "month": 1, "months": 1, "mos": 1, "yr": 12, "year": 12, "years": 12,
           "yrs": 12, "quarter": 3, "quarters": 3, "q": 3, "day": 1 / 30.0, "days": 1 / 30.0,
           "week": 7 / 30.0, "weeks": 7 / 30.0}
DIMENSIONS = [("money", MONEY), ("mass", MASS), ("volume", VOLUME), ("time", TIME_MO)]

_SCALE = re.compile(r"\d+\s*(?:-|to)\s*\d+")


def _currency(u):
    low = (u or "").lower()
    if any(c in low for c in ["usd", "us$", "dollar", "$"]):
        return "usd"
    if any(c in low for c in ["eur", "euro", "€"]):
        return "eur"
    if any(c in low for c in ["gbp", "pound", "£"]):
        return "gbp"
    if any(c in low for c in ["inr", "rs.", "rs ", "rupee", "₹"]) or low.strip() in ("rs",):
        return "inr"
    return None


def _magnitude(u, table):
    low = (u or "").lower()
    for token in sorted(table, key=len, reverse=True):
        if re.search(r"(^|[^a-z])%s($|[^a-z])" % re.escape(token), low):
            return table[token], token
    return None


def _scale_sig(u):
    low = (u or "").lower()
    m = _SCALE.search(low)
    if m:
        return re.sub(r"\s|to", lambda x: "-" if x.group() == "to" else "", m.group())
    if "%" in low or "percent" in low:
        return "0-100"
    return None


def conversion(source_unit, canonical_unit):
    src = (source_unit or "").strip()
    canon = (canonical_unit or "").strip()
    if not src or not canon:
        return (1.0, 0.0, "none", "")
    if src.lower() == canon.lower():
        return (1.0, 0.0, "same", "")

    # currency change is an FX question (rate + date) — never auto-scale
    cs, cc = _currency(src), _currency(canon)
    if cs and cc and cs != cc:
        return (1.0, 0.0, "flag", "currency change %s→%s needs an FX rate + date" % (cs, cc))

    # same physical dimension → exact factor
    for _name, table in DIMENSIONS:
        ms, mc = _magnitude(src, table), _magnitude(canon, table)
        if ms and mc:
            factor = ms[0] / mc[0]
            if abs(factor - 1.0) < 1e-9:
                return (1.0, 0.0, "same", "")
            return (round(factor, 6), 0.0, "exact",
                    "%s→%s (×%g)" % (ms[1], mc[1], factor))

    # rating-scale re-anchoring → semantic, confirm before scaling
    ss, sc = _scale_sig(src), _scale_sig(canon)
    if ss and sc and ss != sc:
        return (1.0, 0.0, "flag", "scale re-anchor %s→%s needs confirm" % (ss, sc))

    return (1.0, 0.0, "unknown", "unrecognised unit '%s' vs '%s'" % (src, canon))
