"""
The agent: a business question -> ontology queries -> a cited answer.

It never sees a raw table name. It asks for objects ("PricePoint",
"Product"), the resolver turns that into SQL, and the agent reasons over the
clean rows. Every answer carries its provenance (which source files fed the
objects it used).

Two modes:
  deterministic  (default)  -- a small intent router; always runs, no key.
  llm            (optional) -- real Claude with a `query_ontology` tool, used
                               when ANTHROPIC_API_KEY is set and use_llm=True.
                               Falls back to deterministic on any error.
"""
import llm
import rag
from resolver import resolve


# ---- shared helpers ------------------------------------------------------
def _object_sources(conn, obj):
    rows = conn.execute(
        "SELECT DISTINCT source_file FROM bindings WHERE object_property LIKE ? "
        "AND status='approved'", (obj + ".%",)).fetchall()
    return sorted({("seed data" if r["source_file"] == "seed" else r["source_file"])
                   for r in rows})


def _step(conn, label, obj, select=None, where=None):
    r = resolve(conn, obj, select, where)
    return {"label": label, "object": obj, "sql": r["sql"],
            "columns": r["columns"], "rows": r["rows"],
            "sources": _object_sources(conn, obj)}


def _ends_1l(sku):
    return bool(sku) and str(sku).upper().endswith("-1L")


# ---- deterministic intent router ----------------------------------------
def _answer_undercut(conn):
    interp = ("Nouns -> objects (competitor, PricePoint); verb 'undercut' -> compare "
              "selling_price; '1L pack' -> filter to the 1L SKU.")
    base = _step(conn, "Read every observed price point", "PricePoint",
                 ["brand", "sku", "selling_price", "channel"])
    bis = [r for r in base["rows"]
           if str(r["brand"]).lower() == "bisleri" and _ends_1l(r["sku"])]
    if not bis:
        return {"interpretation": interp, "steps": [base],
                "answer": "No Bisleri 1L price point is in the model yet.",
                "sources": base["sources"]}
    bp = min(r["selling_price"] for r in bis)
    cmp_step = _step(conn, "Find 1L price points below Bisleri's", "PricePoint",
                     ["brand", "sku", "selling_price", "channel"],
                     [{"field": "selling_price", "op": "<", "value": bp}])
    under = {}
    for r in cmp_step["rows"]:
        if _ends_1l(r["sku"]) and str(r["brand"]).lower() != "bisleri":
            key = (r["brand"], r["channel"])
            if key not in under or r["selling_price"] < under[key]["selling_price"]:
                under[key] = r
    under = sorted(under.values(), key=lambda r: r["selling_price"])
    if under:
        parts = ["%s at Rs.%g (%s)" % (r["brand"], r["selling_price"], r["channel"])
                 for r in under]
        ans = ("Bisleri 1L sits at Rs.%g. Undercut by " % bp) + "; ".join(parts) + "."
    else:
        ans = "Nothing currently undercuts Bisleri 1L at Rs.%g." % bp
    return {"interpretation": interp, "steps": [base, cmp_step], "answer": ans,
            "sources": sorted(set(base["sources"]) | set(cmp_step["sources"]))}


def _answer_tds(conn):
    interp = ("'TDS' / 'quality' -> Product.tds; 'versus peers' -> read all Products "
              "and compare.")
    step = _step(conn, "Read product specs", "Product", ["sku", "tds"])
    rows = [r for r in step["rows"] if r["tds"] is not None]
    if not rows:
        return {"interpretation": interp, "steps": [step],
                "answer": "No TDS values in the model yet.", "sources": step["sources"]}
    bis = [r for r in rows if str(r["sku"]).upper().startswith("BIS")]
    others = [r for r in rows if not str(r["sku"]).upper().startswith("BIS")]
    avg_o = round(sum(r["tds"] for r in others) / len(others), 1) if others else None
    if bis and avg_o is not None:
        bt = bis[0]["tds"]
        verdict = "above" if bt > avg_o else ("below" if bt < avg_o else "in line with")
        ans = ("Bisleri (%s) reads TDS %g mg/L, %s the peer average of %g mg/L."
               % (bis[0]["sku"], bt, verdict, avg_o))
    else:
        ans = "TDS by SKU: " + ", ".join("%s=%g" % (r["sku"], r["tds"]) for r in rows) + "."
    return {"interpretation": interp, "steps": [step], "answer": ans,
            "sources": step["sources"]}


def _answer_realised(conn):
    interp = ("'realised price' -> Transaction.actual_price (revenue / units, derived); "
              "'list price' -> Product.mrp; join on sku in the agent.")
    tx = _step(conn, "Read realised prices from transactions", "Transaction",
               ["sku", "units", "revenue", "actual_price", "channel"])
    pr = _step(conn, "Read list prices from specs", "Product", ["sku", "mrp"])
    mrp = {r["sku"]: r["mrp"] for r in pr["rows"]}
    lines = []
    for r in tx["rows"]:
        lp = mrp.get(r["sku"])
        if lp and r["actual_price"] is not None:
            disc = round((1 - r["actual_price"] / lp) * 100, 1)
            lines.append("%s realised Rs.%g vs list Rs.%g (%g%% off)"
                         % (r["sku"], r["actual_price"], lp, disc))
    ans = ("; ".join(lines) + ".") if lines else "No overlapping realised/list prices yet."
    return {"interpretation": interp, "steps": [tx, pr], "answer": ans,
            "sources": sorted(set(tx["sources"]) | set(pr["sources"]))}


def _answer_channel(conn):
    interp = "'price points by channel' -> read PricePoint, group by channel."
    step = _step(conn, "Read all price points", "PricePoint",
                 ["brand", "sku", "selling_price", "channel"])
    by = {}
    for r in step["rows"]:
        by.setdefault(r["channel"], []).append(r["selling_price"])
    parts = ["%s: avg Rs.%.1f (%d obs)" % (c, sum(v) / len(v), len(v))
             for c, v in sorted(by.items())]
    ans = "Average selling price by channel -- " + "; ".join(parts) + "."
    return {"interpretation": interp, "steps": [step], "answer": ans,
            "sources": step["sources"]}


def _fallback(conn, q):
    ql = q.lower()
    obj = ("Product" if any(w in ql for w in ["spec", "tds", "shelf", "cert", "mrp"])
           else "Transaction" if any(w in ql for w in ["sales", "revenue", "unit", "transaction"])
           else "PricePoint")
    step = _step(conn, "Read %s" % obj, obj)
    return {"interpretation": "No specific intent matched; showing the closest object (%s)." % obj,
            "steps": [step], "answer": "Returned %d %s rows for inspection." % (len(step["rows"]), obj),
            "sources": step["sources"]}


def answer_deterministic(conn, question):
    ql = question.lower()
    if any(w in ql for w in ["undercut", "cheaper", "below bisleri", "lower than"]) \
            or ("competitor" in ql and "price" in ql):
        body = _answer_undercut(conn)
    elif any(w in ql for w in ["tds", "purity", "mineral", "quality"]):
        body = _answer_tds(conn)
    elif any(w in ql for w in ["realis", "realiz", "list price", "discount", "margin"]):
        body = _answer_realised(conn)
    elif "channel" in ql or "average price" in ql or "by channel" in ql:
        body = _answer_channel(conn)
    else:
        body = _fallback(conn, question)
    body["mode"] = "deterministic"
    body["question"] = question
    return body


# ---- optional real-Claude mode ------------------------------------------
def _registry_summary(conn):
    rows = conn.execute(
        "SELECT object, property, type, unit FROM object_registry "
        "WHERE status='approved' ORDER BY object, id").fetchall()
    by = {}
    for r in rows:
        by.setdefault(r["object"], []).append(
            "%s (%s%s)" % (r["property"], r["type"], ("/" + r["unit"] if r["unit"] else "")))
    return "\n".join("- %s: %s" % (o, ", ".join(ps)) for o, ps in by.items())


def answer_llm(conn, question):
    """Gateway mode: Claude plans ontology queries (as JSON), we run them via the
    resolver, then Claude composes a grounded answer. Works through any text
    gateway -- no tool-use / structured-output API needed."""
    reg = _registry_summary(conn)
    plan_sys = ("You plan queries against a business ontology to answer a question. "
                "You output strict JSON only.")
    plan_prompt = (
        "Ontology objects and properties you can query:\n\n" + reg +
        "\n\nFilters use [{\"field\",\"op\",\"value\"}], op in =,!=,<,>,<=,>=,like. "
        "Any field used in a filter MUST also be in select.\n\n"
        "Question: " + question + "\n\n"
        "Return JSON:\n"
        '{"interpretation": "how you read the question",\n'
        ' "queries": [{"object": "...", "select": ["..."], "where": [{"field":"...","op":"...","value": ...}]}]}'
    )
    plan_res = llm.complete(plan_prompt, system=plan_sys, model=llm.AGENT_MODEL, max_tokens=1200)
    plan = llm.extract_json(plan_res["text"])
    cost = plan_res.get("cost_usd", 0)

    steps = []
    for q in plan.get("queries", []):
        try:
            r = resolve(conn, q["object"], q.get("select"), q.get("where"))
            steps.append({"label": "query " + q["object"], "object": q["object"],
                          "sql": r["sql"], "columns": r["columns"], "rows": r["rows"],
                          "sources": _object_sources(conn, q["object"])})
        except Exception as e:  # noqa
            steps.append({"label": "query " + str(q.get("object")), "object": str(q.get("object")),
                          "sql": "-- error: " + str(e), "columns": [], "rows": [], "sources": []})

    # retrieve qualitative / narrative context and fuse it with the structured rows
    passages = rag.search(conn, question, limit=4)
    if passages:
        steps.append({"label": "retrieve narrative", "object": "Narrative",
                      "sql": "FTS5 keyword search over the narrative store",
                      "columns": ["entity", "kind", "text"],
                      "rows": [{"entity": p["entity"], "kind": p["kind"], "text": p["text"]}
                               for p in passages],
                      "sources": sorted({("seed narrative" if p["source_file"] == "seed"
                                          else p["source_file"]) for p in passages}),
                      "narrative": True})

    def _ev(s):
        rows = s["rows"]
        head = rows[:40]
        more = " ...(%d rows total)" % len(rows) if len(rows) > 40 else ""
        return "Query %s -> %s%s" % (s["object"], head, more)
    evidence = "\n".join(_ev(s) for s in steps if not s.get("narrative"))
    narr = "\n".join("- (%s) %s" % (p["entity"], p["text"]) for p in passages)
    ans_sys = ("You answer concisely. Use the structured numbers as the backbone, and weave in the "
               "qualitative narrative where it adds context (e.g. stated strategy vs. what the data shows). "
               "Cite actual numbers.")
    ans_prompt = ("Question: " + question + "\n\nStructured data from the ontology:\n" + evidence +
                  (("\n\nNarrative / qualitative context:\n" + narr) if narr else "") +
                  "\n\nAnswer in one short paragraph, fusing the numbers with the narrative where relevant.")
    ans_res = llm.complete(ans_prompt, system=ans_sys, model=llm.AGENT_MODEL, max_tokens=600)
    cost += ans_res.get("cost_usd", 0)

    return {"mode": "llm", "question": question,
            "interpretation": plan.get("interpretation", "Claude planned its own ontology queries."),
            "steps": steps, "answer": ans_res["text"].strip() or "(no answer)",
            "sources": sorted({s for st in steps for s in st["sources"]}),
            "engine": "llm (%s)" % llm.AGENT_MODEL, "cost_usd": round(cost, 6)}


def answer(conn, question, use_llm=False):
    if use_llm and llm.available():
        try:
            return answer_llm(conn, question)
        except Exception as e:  # noqa
            body = answer_deterministic(conn, question)
            body["llm_error"] = str(e)
            return body
    return answer_deterministic(conn, question)


SUGGESTED = [
    "What is Bisleri's stated strategy, and does the data support it?",
    "Which competitors undercut Bisleri on the 1L pack?",
    "Which brand has the highest market share, and what is its gross margin?",
    "How is quick commerce reshaping the category, and who is most exposed?",
    "What is the TAM and value CAGR for the category?",
    "Which brand scores highest on the Purity attribute?",
]
