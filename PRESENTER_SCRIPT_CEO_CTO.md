# AmploFly4.0 — Unified Data Model
## Live-demo presenter script · for the CEO + CTO

> **How to use this.** Talking points, not a teleprompter. Left column = what you *click/show*; the
> bullets = what you *say*. Drive the live app (http://localhost:5050) and let the screen do the work.
> Two voices in the room: the **CEO** wants the *why* (fungibility, moat, speed, cost); the **CTO** wants
> the *what's real* (architecture, what's stored vs not, honest scope). This script serves both.

---

## 0 · The one thing to land (your through-line)

> "We've built the **data backbone** that makes AmploFly fungible — the same platform can be pointed at
> any business problem, in any industry, because underneath it all sits **one governed model**, not a
> new database per use case. It's the Palantir-Foundry *pattern*, built for us, and it's **running, not a slide.**"

Say this once at the top, and return to it at the end.

---

## 1 · Open (30 seconds)

- "What you're looking at is a **working** Unified Data Model — real code, real database, the SQL you'll
  see is generated and actually executed. Nothing is mocked."
- "I'll show you **what it stores, what it deliberately does *not* store, how it works, and where the
  honest boundaries are.** Then I'll ask you for a direction."
- "The proof scenario is **PEL packaged water (Bisleri)**, but you'll see it already spans **20 industries
  and 1,200 documents** — that breadth *is* the point."

---

## 2 · The core idea — two layers (the whole trick)
**Show: Overview tab (the diagrams).**

- "The entire concept is **two layers.**
  - **Raw layer** — your files land **exactly as they arrived**, messy values and all. We change nothing.
  - **Meaning layer** — a thin **ontology** sits on top and **points** at the raw columns, giving them
    clean business names. It holds **no data of its own** — only pointers."
- Point to the **object diagram**: "An **object** — like `Product` — is just a set of **properties**, and
  each property is a **pointer** to a raw column, *plus a clean rule* (strip the ₹, convert crore→mn).
  **All the intelligence lives in the pointer, not in a copy of the data.**"
- The contacts-list line (great for the CEO): "It's a **contacts list for your data**. You never dial the
  raw number — you tap 'Mom'. The agent never touches the raw table — it asks the object."

**The sentence to repeat:** *"Raw stays raw. The meaning layer is pointers, not copies."*

---

## 3 · What is STORED vs what is NOT stored
**Say this explicitly — the CTO will be listening hard here.**

**Stored:**
- **The raw files**, landed as-is (kept for audit & re-processing).
- **The ontology** — registry (objects/properties), **bindings** (the pointers + clean rule + unit
  conversion), and **links** (relationships).
- **A narrative store** — qualitative text (strategy notes, prose, anything unmapped), keyword-searchable.
- **A document registry** — *every file ingested since inception*, with metadata, **persists across resets**.
- **A control plane** — data classifications, governed edits, branches, and a full audit trail.

**NOT stored (by design):**
- **No second copy of your data.** The meaning layer duplicates nothing — it points.
- **No table-per-file / table-per-client sprawl.** One shared canonical model; a new file adds **pointers,
  not tables** — which is exactly why it scales to hundreds of clients.
- **Raw is never mutated.** When someone corrects a value, that edit is a **governed overlay applied on
  read** — the source stays pristine and the change is audited.

**Honest "not stored" (volunteer this — it buys credibility):**
- It is **not** storing *real* operational data yet — the figures are **synthetic/illustrative**; the
  **engine** is real.
- **No media** (images / audio / video / scanned-image PDFs) — text and tables today.
- Retrieval is **keyword (FTS)**, not true semantic embeddings — a known, addable upgrade.

---

## 4 · How it actually works — the agent fetching across objects
**Show: Overview → the "How the agent answers" fan-out diagram, then the Agent tab.**

- "When you ask about a **company or a scenario**, the agent does **not** read one giant table."
- Walk the fan-out: "① It **plans** which objects hold a slice of the answer. ② It **asks each object**
  only what it can answer — `Brand` for share & margin, `PricePoint` for prices, `Product` for specs,
  `Attribute` for perception, plus the **narrative store** for *stated strategy*. ③ The **resolver** turns
  every ask into **real SQL** over the right raw file, **joining across objects** on shared keys
  (`brand`, `sku`) and the links. ④ It **fuses** the numbers and the narrative into one **cited** answer."
- **Now make it live.** Agent tab → click *"What is Bisleri's stated strategy, and does the data support it?"*
  - As it runs: "Watch — it's querying `Assessment`, `Brand`, and the `Narrative` store, then writing the
    answer from the rows. You can see the **generated SQL** and the **sources** it cited."
- The killer line: *"Same machinery for any company or scenario — only the set of objects asked changes.
  That's what 'fungible' means in practice."*

---

## 5 · The platform around it (drive these tabs briskly)

| Show | Say |
|---|---|
| **Raw layer** (drill into a table) | "This is *what's stored* — the files, untouched. `Rs.20`, `blinkit`, `BIS-1L`. Click any source to view its data." |
| **Meaning layer** | "The pointers. Note the **transform** and **source unit** columns — e.g. a source in **crore** is auto-converted ×10 to millions on read. Same parameter, different units, one consistent column." |
| **Documents** → **Entity search** | "Type a company — **Reliance** — and it shows everywhere it lives: documents, the objects holding its data, and the projects. **1,197 files across 20 industries**, including the **MSPL BRSR** mining files." |
| **Ingest** | "Drop **any** file — CSV, Excel, PDF, prose. The LLM maps every column to the model and proposes new objects when something's genuinely new. ~**half a cent** a file." |
| **Governance** | "The Foundry-defining layer: **data health** checks, **lineage** (value → conversion → transform → raw cell → source), and a **readiness** score per domain. This is *trust*." |
| **Console** | "The control plane. Switch **role** in the top bar to **Viewer** — confidential columns (revenue, margin) **disappear**, enforced server-side. An **Analyst's** uploads need a **Steward's** approval. A **branch** isolates a restatement until merged. Everything is **audited**." |

---

## 6 · Why it matters — the business case (for the CEO)

- **Fungibility = product leverage.** "One platform, many problems. ESG today, PEL pricing, competitive
  intel, supply-chain — same modules, swap the data model. We don't rebuild per client."
- **Speed.** "A new scenario's data layer is **weeks, not a rebuild** — drop files, map, govern, query."
- **Cost.** "LLM mapping and answering cost **fractions of a cent** per action — a whole demo run is under a dollar."
- **The moat / IP.** "The **bindings** — the pointer-map with the clean rules and unit logic — are the
  defensible asset. Not the raw data; the **governed model over it.** That's what's hard to copy."
- **The diligence line.** "This is the difference between 'we have an ESG tool' and 'we have a **governed,
  multi-domain data platform** an agent reasons over' — a much stronger story for investors."

---

## 7 · Honest scope — what this is and isn't (for the CTO)

> Say this *unprompted*. It builds more trust than it costs, and it pre-empts the hard question.

- "This is **Foundry-*shaped*, not Foundry-*scale*.** The **patterns are real and working** —
  ontology, pointers, lineage, health, RBAC + classification, write-back, branching, audit, multi-tenancy."
- "But it's the **framework on SQLite, single-node.** It is **not** Spark/petabyte compute, not enterprise
  per-cell security hardened over years, not hundreds of live connectors. The **data is illustrative.**"
- "Think **working architectural prototype** — proof the paradigm runs and that *our* UDM is the same idea.
  Present it as **'our Foundry-pattern data model, demonstrated,'** never as a Foundry equivalent."

---

## 8 · Q&A prep (likely questions + crisp answers)

**CTO — "Where does the data physically live? Is it duplicated?"**
> "Raw files in normal tables; the ontology is **metadata that points** at them — no duplication. Edits are
> an overlay applied on read, so the source is never mutated."

**CTO — "How does this scale to hundreds of clients?"**
> "**One shared canonical schema keyed by client.** New files add **rows and pointers, not tables** — table
> count stays flat; only rows grow. Raw archived cheaply in object storage. The table-per-file approach is
> the anti-pattern; we don't do it."

**CTO — "Is the AI a black box? Can we trust the numbers?"**
> "The LLM only **proposes** mappings and **detects** units — a human confirms low-confidence ones, and the
> actual conversion is **deterministic code**, not an LLM guess. Every value has **lineage** back to the raw
> cell, and there are **health checks**. Numbers are auditable end-to-end."

**CEO — "How is this different from Palantir?"**
> "Same core idea — a governed ontology over messy data. The difference is **cost and speed to stand up** for
> *our* use cases, and it's **ours.** We're not buying a six-month Foundry deployment."

**CEO — "Can it really do non-ESG?"**
> "It already spans **20 industries** — finance with BSE 100 + S&P 500, pharma, telecom, crypto, consulting.
> The model doesn't *know* it's doing ESG; it operates on whatever's mapped in."

**Either — "What's real vs demo?"**
> "**Real:** the engine — ingestion, mapping, the resolver, governance, security, branching, the agent.
> **Illustrative:** the figures and the breadth of seeded data. **Next to make production-grade:** real DB +
> connectors, embeddings, media/OCR, and hardening."

**CTO — "What would it take to productionize?"**
> "Four things, in order: (1) real DB (Postgres/lakehouse) + raw archive in S3; (2) connectors + scheduled
> refresh; (3) semantic embeddings; (4) enterprise security hardening. Each is a known build, not a rethink —
> the **architecture already accommodates them.**"

---

## 9 · Close — the ask

- Restate the through-line: *"One governed model, many problems, running today."*
- Then make a **specific ask** (pick what you actually want):
  - **Greenlight** to make one scenario production-grade (recommend **PEL/Bisleri** or **MSPL BRSR**), or
  - **Resourcing** (a backend dev + the four productionization items), or
  - **Direction**: which scenario/client to aim the next build at.
- Land it: *"This is the data foundation the whole AmploFly story stands on. I'm asking for a direction and
  the room to make one scenario real end-to-end."*

---

### Pocket numbers (have these ready)
- **1,197** documents · **20** industries · **16** scenarios · **~1.5M** rows catalogued
- **276** properties · **45** objects · **9** domains · **8** live objects
- **120** companies (BSE 100 + S&P 500) · **191** tracked entities · **21** projects
- **~$0.0005** per file mapping · **~$0.0006** per agent answer
- Roles: **Admin · Data Steward · Analyst · Viewer** · classifications: public → restricted
