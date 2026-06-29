# PEL Ontology — a working Foundry-style demo

A **real**, runnable demonstration of the Unified Data Model for AmploFly 4.0. It ingests
**any file, from any sub-domain of the PEL spec**, maps it onto a stable business ontology
with an LLM, and lets an agent answer questions over it — with real generated SQL and real
provenance. It exists to let you *understand* the Palantir-Foundry-style approach by clicking
through it, and to *show* it to others (Andy, Sagnik, a client).

It is not a slide. SQLite database, real query resolver, real LLM calls (through your Magica
key). The SQL on screen is generated from the bindings and actually executed.

---

## Run it

```bash
cd pel-foundry-demo
./run.sh                      # installs deps if needed, then starts the server
```

Open **http://127.0.0.1:5050**.

**LLM backend** (what makes "any file, any domain" work) is read from `.env`:

```
MAGICA_API_KEY=gx_...         # routes Claude through the Magica gateway  (current setup)
# ANTHROPIC_API_KEY=sk-ant-…  # alternative: call the Anthropic API directly
# EXTRACT_MODEL=claude_sonnet_4_6   # mapping/extraction model (cheap); override to cut/raise cost
# AGENT_MODEL=claude_opus_4_8       # the agent model (sharpest answers)
```

Without a key the demo still runs — structured files (CSV/Excel/JSON) ingest via an offline
matcher, and the agent answers in a deterministic router mode. The key unlocks PDFs/Word/prose,
arbitrary domains, and auto-grow.

---

## The idea in one paragraph

Files stay **raw**, in ordinary tables. A thin **meaning layer** (registry + bindings + edges)
sits on top and *points* at the raw columns, giving them clean business names. The agent only
talks to the meaning layer. A new file — any shape, any domain — doesn't change the concepts or
add a business table; the LLM maps its columns to the **full PEL spec** (all six levels), and
where something genuinely new appears it proposes a **new object/property** (auto-grow). That is
what makes the model fungible without being a shapeshifting database.

---

## What the five tabs show (the demo script)

1. **How it works** — the two-layer mental model.
2. **Raw layer** — the messy files as they landed (`Rs.20`, `blinkit`, `BIS-1L`). Nothing cleaned.
3. **The meaning layer** — `object_registry` (what exists), `bindings` (the pointers + clean
   rules), `edges` (links). The full PEL ontology lives here and grows as you ingest.
4. **Ingest a file** — **drop any file** (CSV/Excel/JSON/PDF/Word/txt) or click a bundled sample.
   Spreadsheets parse locally; PDFs and prose are read by **Claude** into rows. The LLM then maps
   every column to the PEL spec with a confidence each — high auto-accepts, low routes to you,
   no-fit columns become **new properties** or fall to the RAG tail. Each step shows its **cost**.
5. **Ask the agent** — a business question → ontology queries → real SQL → a cited answer.

Bundled samples cover several sub-domains so you can show breadth without your own files:
`blinkit_scrape.csv` (L2 price), `fssai_labels.csv` (L4 specs), `distributor_sheet.csv` (messy +
tail), `competitor_financials.json` (L2/L4/L5 → a `Brand` object), `market_outlook_note.txt`
(unstructured prose → a `Market` object, extracted by Claude).

Use **Reset demo** (top-right) any time to re-seed.

---

## Architecture

```
frontend/ (vanilla HTML/CSS/JS, drag-drop upload)
      │  fetch /api/...
      ▼
backend/app.py        Flask API + serves the frontend + /api/upload
      ├── llm.py        gateway-agnostic LLM: Magica (poll a Claude node) OR Anthropic SDK
      ├── canonical.py  the FULL PEL dictionary (L0–L5) — the mapping target
      ├── extract.py    any file → records (CSV/Excel/JSON local; PDF/Word/prose → Claude)
      ├── proposer.py   LLM column-mapper (+ auto-grow) with an offline heuristic fallback
      ├── ingest.py     land → profile → propose → commit
      ├── resolver.py   object query → SQL → JSON  (UNION across every source of an object)
      ├── agent.py      NL question → ontology queries → cited answer (LLM or deterministic)
      ├── db.py         SQLite + transforms registered as real SQL functions
      └── seed.py       the water-scenario seed (re-runnable)
```

The four Foundry pieces, made concrete: object types/properties = `object_registry`;
property→column binding = `bindings` (with a transform); links = `edges`; ontology resolver =
`resolver.py`. An object backed by several files is a `UNION ALL` across them — which is exactly
why ingesting a new file is *additive*, never a migration.

---

## The LLM layer (and the cost)

Everything that needs an LLM calls `llm.complete(prompt, system) → {text, cost_usd}`. The backend
is swappable; with `MAGICA_API_KEY` set it POSTs a run to a Claude node, polls until `COMPLETED`,
and reads the text. Because a gateway only does prompt-in/text-out, the mapper/extractor/agent ask
for **JSON in the response** and parse it — no dependence on tool-use or structured-output APIs.

Indicative cost (Sonnet for mapping/extraction, Opus for the agent): mapping a spreadsheet
≈ $0.0005; extracting a PDF/report ≈ a few tenths of a cent to ~$0.01; an agent answer ≈ $0.0006.
A whole demo run is a few cents. The UI shows the real `cost_usd` on every LLM action.

### Swapping the backend / model

Set `ANTHROPIC_API_KEY` (and unset Magica) to call Anthropic directly. Change `EXTRACT_MODEL` /
`AGENT_MODEL` in `.env` to trade cost vs. quality. No code changes.

---

## How this maps to the real product

- `canonical.py` is the PEL Data Requirements Spec rendered as objects/properties; in production
  the dictionary is generated from that spec (and, for ESG, the 388-field BRSR tables).
- The proposer *is* the Osmos/Foundry mapping move — here driven by Claude, reading headers +
  values + the dictionary, with a human confirming low-confidence and auto-grow for new concepts.
- The agent's LLM mode plans its own ontology queries and answers from the rows.

## Honest scope

This proves the **engine** end-to-end across multiple PEL sub-domains and arbitrary file formats.
It deliberately does **not** include: live public-source fetching (the spec's "what Claude
fetches" — easy to add via the gateway's web tools), the in-platform Data Management module wiring,
OCR for scanned image-only PDFs, or tenant isolation at scale (one shared schema keyed by
`client_id`, raw archived in S3 — see `CLAUDE.md` §9). Those are the production build; this is the
architecture made tangible.
