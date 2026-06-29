// ---- tiny helpers --------------------------------------------------------
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

async function api(path, body) {
  const opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opt);
  return r.json();
}

function highlightSql(sql) {
  let s = esc(sql);
  s = s.replace(/\b(SELECT|FROM|WHERE|UNION ALL|AS|AND|OR|LIKE|NULL)\b/g, '<span class="kw">$1</span>');
  s = s.replace(/\b(parse_brand|parse_sku|strip_currency|to_int|to_ml|parse_months|enum_channel|divide)\b/g, '<span class="fn">$1</span>');
  return s;
}

function dataTable(columns, rows, cap = 80) {
  const wrap = el("div", "table-wrap");
  const t = el("table");
  const thead = el("thead");
  const trh = el("tr");
  columns.forEach(c => trh.appendChild(el("th", null, esc(c))));
  thead.appendChild(trh); t.appendChild(thead);
  const tb = el("tbody");
  rows.slice(0, cap).forEach(row => {
    const tr = el("tr");
    columns.forEach(c => tr.appendChild(el("td", null, esc(row[c]))));
    tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t);
  if (rows.length > cap) wrap.appendChild(el("div", "more-rows", `+ ${rows.length - cap} more rows`));
  return wrap;
}

async function loadIngestStats() {
  const host = $("#ingest-stats"); if (!host) return;
  const s = await api("/api/stats");
  const cards = [
    ["sc-blue", "▦", "Raw rows ingested", s.rows],
    ["sc-purple", "◆", "Business objects", s.objects],
    ["sc-orange", "↦", "Bindings (pointers)", s.bindings],
    ["sc-teal", "❝", "Narrative chunks", s.narrative],
    ["sc-green", "▥", "Documents (since inception)", s.documents],
  ];
  host.innerHTML = "";
  cards.forEach(([cls, ic, lbl, num]) => {
    const c = el("div", "stat-card " + cls);
    c.innerHTML = `<div class="icon">${ic}</div><div><div class="lbl">${lbl}</div><div class="num">${num}</div></div>`;
    host.appendChild(c);
  });
}

let docFilter = "";
function fmtN(n) { n = +n || 0; return n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : "" + n; }

async function loadDocuments() {
  const host = $("#documents-table"); host.innerHTML = '<div class="spinner">Loading…</div>';
  const data = await api("/api/documents" + (docFilter ? "?industry=" + encodeURIComponent(docFilter) : ""));
  const s = data.stats;
  host.innerHTML = "";

  const sum = el("div", "stat-row");
  [["sc-blue", "▥", "Documents (since inception)", s.documents],
   ["sc-purple", "◷", "Industries", s.industries],
   ["sc-orange", "◆", "Scenarios / use-cases", s.scenarios],
   ["sc-green", "▦", "Rows catalogued", fmtN(s.doc_rows)],
   ["sc-teal", "✓", "Committed to model", s.committed]
  ].forEach(([cls, ic, lbl, num]) => {
    const c = el("div", "stat-card " + cls);
    c.innerHTML = `<div class="icon">${ic}</div><div><div class="lbl">${lbl}</div><div class="num">${num}</div></div>`;
    sum.appendChild(c);
  });
  host.appendChild(sum);

  const facets = el("div", "question-chips");
  const all = el("button", "q-chip" + (docFilter ? "" : " chip-on"), "All industries");
  all.addEventListener("click", () => { docFilter = ""; loadDocuments(); });
  facets.appendChild(all);
  data.facets.by_industry.forEach(f => {
    const c = el("button", "q-chip" + (docFilter === f.key ? " chip-on" : ""), `${esc(f.key)} · ${f.n}`);
    c.addEventListener("click", () => { docFilter = f.key; loadDocuments(); });
    facets.appendChild(c);
  });
  host.appendChild(facets);

  const rows = data.documents.map(d => ({
    "document": d.filename, "industry": d.industry, "scenario": d.scenario,
    "type": d.doctype, "status": d.status, "rows": d.rows,
    "objects fed": d.objects || "—", "ingested": d.last_action,
  }));
  const card = el("div", "card");
  card.appendChild(el("div", "card-head",
    `<span class="name">${docFilter ? esc(docFilter) : "all documents"}</span><span class="meta">${data.documents.length} shown</span>`));
  card.appendChild(dataTable(
    ["document", "industry", "scenario", "type", "status", "rows", "objects fed", "ingested"], rows, 250));
  host.appendChild(card);
  if (!loaded.narr) { loaded.narr = true; loadNarrative(); }
}

async function loadNarrative(q) {
  const host = $("#narrative-list"); host.innerHTML = '<div class="spinner">Loading…</div>';
  const data = await api("/api/narrative" + (q ? "?q=" + encodeURIComponent(q) : ""));
  host.innerHTML = "";
  if (!data.items.length) { host.innerHTML = '<div class="empty">No narrative found.</div>'; return; }
  data.items.forEach(p => {
    const kindBadge = { strategy: "badge-new", market_commentary: "badge-soft",
      assessment: "badge-review", tail: "badge-tail" }[p.kind] || "badge-soft";
    host.appendChild(el("div", "passage",
      `<div class="p-head"><span class="badge ${kindBadge}">${esc(p.kind)}</span>
        <span class="p-ent">${esc(p.entity)}</span></div>
       <div class="p-text">${esc(p.text)}</div>`));
  });
}

// ---- tab switching -------------------------------------------------------
const loaders = {
  raw: loadRaw, ontology: loadOntology, governance: loadGovernance,
  documents: loadDocuments, companies: loadCompanies, projects: loadProjects,
  console: loadConsole, ingest: loadIncoming, agent: loadAgentMeta,
};

// ---- control plane: context (role / branch / workspace) -----------------
let CTX = { actor: "Admin", role: "Admin", branch: "main", workspace: "Global", perms: [] };
function _can(p) { return CTX.perms.includes(p); }

async function initContext() {
  const c = await api("/api/context");
  CTX = c;
  const fill = (sel, items, val) => {
    sel.innerHTML = items.map(x => `<option ${x === val ? "selected" : ""}>${esc(x)}</option>`).join("");
  };
  fill($("#ctx-actor"), c.roles, c.actor);
  fill($("#ctx-branch"), c.branches, c.branch);
  fill($("#ctx-workspace"), c.workspaces, c.workspace);
  ["#ctx-actor", "#ctx-branch", "#ctx-workspace"].forEach(id => {
    const s = $(id);
    if (s && !s._wired) {
      s._wired = true;
      s.addEventListener("change", () => setContext({
        actor: $("#ctx-actor").value, branch: $("#ctx-branch").value, workspace: $("#ctx-workspace").value,
      }));
    }
  });
}

async function setContext(patch) {
  CTX = await api("/api/context", patch);
  // refresh the active panel + any open drawer
  const active = $(".tab.active") && $(".tab.active").dataset.tab;
  Object.keys(loaded).forEach(k => loaded[k] = false);
  if (loaders[active]) loaders[active]();
}

async function loadConsole() {
  const c = await api("/api/context");
  CTX = c;
  $("#console-ctx").innerHTML =
    `<div class="interp">You are <b>${esc(c.actor)}</b> · branch <b>${esc(c.branch)}</b> · workspace <b>${esc(c.workspace)}</b>.
     <br><span class="muted">Permissions: ${c.perms.length ? c.perms.map(esc).join(", ") : "read-only"}</span></div>`;

  // pending approvals
  const pend = (await api("/api/pending")).pending;
  const ph = $("#console-pending"); ph.innerHTML = "";
  if (!pend.length) ph.appendChild(el("div", "empty", "Nothing pending — all bindings approved."));
  else {
    const card = el("div", "card");
    pend.forEach(b => {
      const row = el("div", "tail-row");
      row.innerHTML = `<span class="badge badge-review">proposed</span>
        <span class="col">${esc(b.object_property)}</span> ← ${esc(b.source_table)}.${esc(b.source_col)}
        <span class="muted">conf ${b.confidence} · ${esc(b.source_file)}</span>`;
      if (_can("approve")) {
        const ok = el("button", "btn btn-primary", "approve"); ok.style.padding = "4px 10px"; ok.style.marginLeft = "auto";
        ok.addEventListener("click", async () => { await api("/api/action/approve-binding", { id: b.id, decision: "approve" }); loadConsole(); });
        const no = el("button", "btn btn-ghost", "reject"); no.style.padding = "4px 10px";
        no.addEventListener("click", async () => { await api("/api/action/approve-binding", { id: b.id, decision: "reject" }); loadConsole(); });
        row.appendChild(ok); row.appendChild(no);
      }
      card.appendChild(row);
    });
    ph.appendChild(card);
  }

  // branches
  const branches = (await api("/api/branches")).branches;
  const bh = $("#console-branches"); bh.innerHTML = "";
  const bcard = el("div", "card");
  branches.forEach(b => {
    const row = el("div", "tail-row");
    row.innerHTML = `<span class="badge ${b.status === "merged" ? "badge-soft" : "badge-new"}">${esc(b.status)}</span>
      <span class="col" style="color:var(--blue)">${esc(b.name)}</span>
      <span class="muted">from ${esc(b.base || "—")} · ${esc(b.created_by)} · ${esc(b.created_at)}</span>`;
    if (b.name !== "main" && b.status === "open" && _can("merge")) {
      const m = el("button", "btn btn-primary", "merge → main"); m.style.padding = "4px 10px"; m.style.marginLeft = "auto";
      m.addEventListener("click", async () => { await api("/api/branch/merge", { name: b.name }); await initContext(); loadConsole(); });
      row.appendChild(m);
    }
    bcard.appendChild(row);
  });
  bh.appendChild(bcard);
  if (_can("branch")) bh.appendChild(_creator("New branch name…", async (v) => { await api("/api/branch", { name: v }); await initContext(); loadConsole(); }));

  // workspaces
  const wsh = $("#console-workspaces"); wsh.innerHTML = "";
  const wcard = el("div", "card");
  c.workspaces.forEach(w => wcard.appendChild(el("div", "tail-row",
    `<span class="badge ${w === c.workspace ? "badge-auto" : "badge-soft"}">${w === c.workspace ? "active" : "—"}</span> <span class="col">${esc(w)}</span>`)));
  wsh.appendChild(wcard);
  if (_can("merge")) wsh.appendChild(_creator("New workspace name…", async (v) => { await api("/api/workspace", { name: v }); await initContext(); loadConsole(); }));

  // classifications
  const cls = (await api("/api/classifications")).classifications;
  const ch = $("#console-class"); ch.innerHTML = "";
  const ccard = el("div", "card");
  const keys = Object.keys(cls).sort();
  if (!keys.length) ccard.appendChild(el("div", "tail-row", "All properties public."));
  keys.forEach(op => {
    const lvl = cls[op];
    const badge = { restricted: "badge-tail", confidential: "badge-review", internal: "badge-soft" }[lvl] || "badge-auto";
    ccard.appendChild(el("div", "tail-row",
      `<span class="badge ${badge}">${esc(lvl)}</span> <span class="col">${esc(op)}</span>`));
  });
  ch.appendChild(ccard);

  // history
  const hist = (await api("/api/history")).history;
  const hh = $("#console-history"); hh.innerHTML = "";
  const rows = hist.map(x => ({ time: x.ts, actor: x.actor, role: x.role, branch: x.branch, action: x.action, target: x.target, detail: x.detail }));
  const hc = el("div", "card");
  hc.appendChild(el("div", "card-head", `<span class="name">audit trail</span><span class="meta">${hist.length} events</span>`));
  hc.appendChild(dataTable(["time", "actor", "role", "branch", "action", "target", "detail"], rows, 200));
  hh.appendChild(hc);
}

function _creator(ph, onAdd) {
  const wrap = el("div", "narr-search"); wrap.style.marginTop = "10px";
  const inp = el("input"); inp.placeholder = ph; inp.type = "text";
  const b = el("button", "btn btn-primary", "Create");
  b.addEventListener("click", () => { if (inp.value.trim()) onAdd(inp.value.trim()); });
  wrap.appendChild(inp); wrap.appendChild(b);
  return wrap;
}

// ---- drawer (drill-down overlay) ----------------------------------------
function openDrawer(title, node) {
  $("#drawer-title").innerHTML = title;
  const b = $("#drawer-body"); b.innerHTML = ""; b.appendChild(node);
  $("#drawer").classList.remove("hidden"); $("#drawer-scrim").classList.remove("hidden");
}
function closeDrawer() { $("#drawer").classList.add("hidden"); $("#drawer-scrim").classList.add("hidden"); }
document.addEventListener("DOMContentLoaded", () => {
  if ($("#drawer-close")) $("#drawer-close").addEventListener("click", closeDrawer);
  if ($("#drawer-scrim")) $("#drawer-scrim").addEventListener("click", closeDrawer);
});

async function openDocument(file) {
  const node = el("div"); node.innerHTML = '<div class="spinner">Loading…</div>';
  openDrawer("Document", node);
  const d = await api("/api/document?file=" + encodeURIComponent(file));
  node.innerHTML = "";
  const meta = el("div", "interp",
    `<b>${esc(d.filename)}</b><br><span class="muted">${esc(d.label || "")}</span><br>
     industry: ${esc(d.industry || "—")} · scenario: ${esc(d.scenario || "—")} ·
     project: ${esc(d.project || "—")} · entity: ${esc(d.entities || "—")}<br>
     type: ${esc(d.doctype)} · ${d.rows} rows · status: ${esc(d.status)} · objects fed: ${esc(d.objects || "—")}`);
  node.appendChild(meta);
  if (d.downloadable) {
    const a = el("a", "btn btn-primary", "⤓ Download file");
    a.href = "/api/document/download?file=" + encodeURIComponent(file); a.style.display = "inline-block";
    node.appendChild(a);
  } else {
    node.appendChild(el("div", "muted",
      d.staging_table ? "Extracted data below (catalog/seed record — no original file on disk)."
        : "Catalog record — synthetic source, no extracted table or file on disk."));
  }
  if (d.data && d.data.length) {
    const card = el("div", "card"); card.style.marginTop = "12px";
    card.appendChild(el("div", "card-head", `<span class="name">${esc(d.staging_table)}</span><span class="meta">extracted rows</span>`));
    card.appendChild(dataTable(d.columns, d.data, 100));
    node.appendChild(card);
  }
}

async function openObjectDrawer(obj) {
  const node = el("div"); node.innerHTML = '<div class="spinner">Resolving…</div>';
  openDrawer("Object · " + esc(obj), node);
  const d = await api("/api/object?object=" + encodeURIComponent(obj));
  node.innerHTML = "";
  if (!d.columns.length) {
    node.appendChild(el("div", "interp",
      `<b>${esc(obj)}</b> is defined in the ontology menu but has <b>no data bound yet</b> — it will populate automatically when a matching file is uploaded.`));
    return;
  }
  node.appendChild(el("div", "interp",
    `<b>${esc(obj)}</b> — ${d.rows.length} record(s), ${d.columns.length} propert${d.columns.length === 1 ? "y" : "ies"}. Resolved live from the ontology.${d.edited && d.edited.length ? ` <span class="badge badge-new">✎ edited: ${d.edited.map(esc).join(", ")}</span>` : ""}`));

  const IDENTS = ["name", "company", "brand", "ticker", "symbol", "operator", "bank", "client", "patient_id", "sku"];
  const keyProp = IDENTS.find(p => d.columns.includes(p));
  if (d.can_edit && d.rows.length && keyProp) {
    const form = el("div", "card"); form.style.marginTop = "10px";
    form.appendChild(el("div", "card-head", `<span class="name">✎ write-back (Action)</span><span class="meta">governed edit · audited · applied on read</span>`));
    const body = el("div"); body.style.padding = "12px 14px"; body.className = "editform";
    const keyVals = [...new Set(d.rows.map(r => r[keyProp]).filter(v => v != null))];
    const props = d.columns.filter(c => c !== keyProp);
    body.innerHTML = `
      <select id="ed-key">${keyVals.map(v => `<option>${esc(v)}</option>`).join("")}</select>
      <select id="ed-prop">${props.map(p => `<option>${esc(p)}</option>`).join("")}</select>
      <input id="ed-val" placeholder="new value">
      <input id="ed-reason" placeholder="reason (audited)">
      <button id="ed-save" class="btn btn-primary">Apply</button>`;
    form.appendChild(body); node.appendChild(form);
    body.querySelector("#ed-save").addEventListener("click", async () => {
      const v = body.querySelector("#ed-val").value.trim(); if (!v) return;
      await api("/api/action/edit", {
        object: obj, key_prop: keyProp, key_val: body.querySelector("#ed-key").value,
        property: body.querySelector("#ed-prop").value, new_value: v,
        reason: body.querySelector("#ed-reason").value.trim(),
      });
      openObjectDrawer(obj);
    });
  }

  if (d.sql) node.appendChild(el("div", "sql", highlightSql(d.sql)));
  const card = el("div", "card"); card.style.marginTop = "10px";
  card.appendChild(dataTable(d.columns, d.rows, 300));
  node.appendChild(card);
}

async function openPropertyDrawer(obj, prop) {
  const node = el("div"); node.innerHTML = '<div class="spinner">Tracing…</div>';
  openDrawer("Property · " + esc(obj) + "." + esc(prop), node);
  const d = await api(`/api/lineage?object=${encodeURIComponent(obj)}&property=${encodeURIComponent(prop)}`);
  node.innerHTML = "";
  if (!d.bindings.length) {
    node.appendChild(el("div", "interp",
      `<b>${esc(obj)}.${esc(prop)}</b> — defined in the menu (${esc(d.level || "")}${d.unit ? ", " + esc(d.unit) : ""}) but <b>not yet bound</b> to any source.`));
    return;
  }
  node.appendChild(el("div", "interp",
    `<b>${esc(obj)}.${esc(prop)}</b> — ${esc(d.level || "")}${d.unit ? ", unit " + esc(d.unit) : ""}. Values: <code>${esc((d.resolved_sample || []).join(", "))}</code>. ${d.bindings.length} source(s):`));
  const card = el("div", "card");
  card.appendChild(el("div", "card-head", `<span class="name">lineage</span><span class="meta">raw → unified</span>`));
  d.bindings.forEach(b => {
    const flow = el("div", "flow");
    flow.innerHTML = `<span class="node raw">${esc(b.source_table)}.${esc(b.source_col)} = ${esc(b.raw_sample)}</span>
      <span class="op">${b.transform === "-" ? "(direct)" : esc(b.transform) + "()"}</span>
      ${b.conversion ? `<span class="conv">${esc(b.conversion)}${b.source_unit ? " (" + esc(b.source_unit) + ")" : ""}</span>` : ""}
      <span>→</span><span class="node unified">${esc(obj)}.${esc(prop)}</span>
      <span class="muted">· ${esc(b.source_file)} · conf ${esc(b.confidence)}</span>`;
    card.appendChild(flow);
  });
  node.appendChild(card);
  if (d.sql) node.appendChild(el("div", "sql", highlightSql(d.sql)));
}

async function openRawTable(name, label, rowcount) {
  const node = el("div"); node.innerHTML = '<div class="spinner">Loading…</div>';
  openDrawer("Raw table · " + esc(name), node);
  const d = await api("/api/raw/table?name=" + encodeURIComponent(name));
  node.innerHTML = "";
  node.appendChild(el("div", "interp",
    `<b>${esc(name)}</b> — ${esc(label || "")} · ${rowcount} rows, ${d.columns.length} columns. Stored exactly as ingested (showing first 100).`));
  const card = el("div", "card");
  card.appendChild(dataTable(d.columns, d.rows, 100));
  node.appendChild(card);
}
const loaded = {};
$$(".tab").forEach(tab => tab.addEventListener("click", () => {
  $$(".tab").forEach(t => t.classList.remove("active"));
  $$(".panel").forEach(p => p.classList.remove("active"));
  tab.classList.add("active");
  const id = tab.dataset.tab;
  $("#" + id).classList.add("active");
  if (loaders[id]) loaders[id]();   // refresh each time so cross-tab changes show
}));

// ---- RAW -----------------------------------------------------------------
async function loadRaw() {
  const host = $("#raw-tables"); host.innerHTML = '<div class="spinner">Loading…</div>';
  const data = await api("/api/raw");
  host.innerHTML = "";
  host.appendChild(el("div", "muted", `${data.tables.length} raw source tables — click a row to view its data.`));
  const card = el("div", "card"); card.style.marginTop = "10px";
  card.appendChild(el("div", "card-head", `<span class="name">raw layer</span><span class="meta">stored as-is</span>`));
  const wrap = el("div", "table-wrap"), t = el("table");
  t.innerHTML = "<thead><tr><th>table</th><th>source</th><th>rows</th><th>columns</th><th>landed</th></tr></thead>";
  const tb = el("tbody");
  data.tables.forEach(x => {
    const tr = el("tr"); tr.style.cursor = "pointer";
    const stg = x.name.startsWith("stg_") ? ' <span class="badge badge-new">ingested</span>' : "";
    tr.innerHTML = `<td><b>${esc(x.name)}</b>${stg}</td><td>${esc(x.label)}</td><td>${x.row_count}</td><td>${x.ncols}</td><td>${esc(x.landed_on)}</td>`;
    tr.addEventListener("click", () => openRawTable(x.name, x.label, x.row_count));
    tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t); card.appendChild(wrap); host.appendChild(card);
  const tailHost = $("#raw-tail"); tailHost.innerHTML = "";
  if (data.rag_tail.length) {
    const c = el("div", "card"); c.style.marginTop = "18px";
    c.innerHTML = `<div class="card-head"><span class="name">rag_tail</span>
      <span class="meta">long-tail narrative · the RAG fallback</span></div>`;
    data.rag_tail.forEach(t => {
      const r = el("div", "tail-row", `<span class="badge badge-tail">tail</span>
        <span>${esc(t.note)}</span> <span class="muted">— ${esc(t.source_file)}</span>`);
      c.appendChild(r);
    });
    tailHost.appendChild(c);
  }
}

// ---- ONTOLOGY ------------------------------------------------------------
async function loadOntology() {
  const data = await api("/api/ontology");
  const boundObj = {};
  data.bindings.forEach(b => { const [o, p] = b.object_property.split("."); (boundObj[o] = boundObj[o] || new Set()).add(p); });
  const reg = $("#onto-registry"); reg.innerHTML = "";
  const live = Object.keys(data.objects).filter(o => boundObj[o]);
  const menu = Object.keys(data.objects).filter(o => !boundObj[o]);
  reg.appendChild(el("div", "muted", `${Object.keys(data.objects).length} objects in the ontology — ${live.length} live (have data), ${menu.length} menu-defined (mappable on upload). Click an object or property to drill in.`));
  const grid = el("div", "obj-grid"); grid.style.marginTop = "12px";
  [...live, ...menu].forEach(obj => {
    const props = data.objects[obj];
    const isLive = !!boundObj[obj];
    const card = el("div", "obj-card");
    const head = el("h4");
    head.innerHTML = `${esc(obj)} <span class="badge ${isLive ? "badge-auto" : "badge-soft"}">${isLive ? "live" : "menu"}</span>`;
    head.style.cursor = "pointer";
    head.addEventListener("click", () => openObjectDrawer(obj));
    card.appendChild(head);
    props.forEach(p => {
      const bound = boundObj[obj] && boundObj[obj].has(p.property);
      const row = el("div", "prop"); row.style.cursor = "pointer";
      row.innerHTML = `<span class="pname" style="${bound ? "" : "color:var(--muted)"}">${esc(p.property)}</span>
        <span class="ptype">${esc(p.type)}${p.unit ? " · " + esc(p.unit) : ""}</span>`;
      row.addEventListener("click", () => openPropertyDrawer(obj, p.property));
      card.appendChild(row);
    });
    grid.appendChild(card);
  });
  reg.appendChild(grid);

  const bh = $("#onto-bindings"); bh.innerHTML = "";
  const card = el("div", "card");
  const rows = data.bindings.map(b => {
    let xf = b.transform === "-" ? "—" : b.transform;
    if (b.factor && b.factor !== 1) xf += ` ×${b.factor}`;
    if (b.offset) xf += ` +${b.offset}`;
    return {
      "object.property": b.object_property,
      "← reads": `${b.source_table}.${b.source_col}`,
      "transform": xf,
      "source unit": b.source_unit || "—",
      "from file": b.source_file === "seed" ? "seed" : b.source_file,
      "conf": b.confidence,
    };
  });
  card.appendChild(dataTable(["object.property", "← reads", "transform", "source unit", "from file", "conf"], rows, 300));
  bh.appendChild(card);

  const eh = $("#onto-edges"); eh.innerHTML = "";
  if (!data.edges.length) eh.innerHTML = '<div class="empty">No links yet.</div>';
  data.edges.forEach(e => {
    eh.appendChild(el("div", "edge",
      `${esc(e.from_obj)}:${esc(e.from_key)} <span class="lk">--${esc(e.link)}--&gt;</span> ${esc(e.to_obj)}:${esc(e.to_key)}`));
  });
}

// ---- INGEST --------------------------------------------------------------
async function loadIngestStats() {
  const host = $("#ingest-stats");
  try {
    const [onto, raw] = await Promise.all([api("/api/ontology"), api("/api/raw")]);
    const objects = Object.keys(onto.objects).length;
    const props = Object.values(onto.objects).reduce((a, p) => a + p.length, 0);
    const cards = [
      ["Raw sources", "acc-blue", "▦", raw.tables.length],
      ["Business objects", "acc-purple", "◆", objects],
      ["Mapped properties", "acc-orange", "≡", props],
      ["Bindings (pointers)", "acc-green", "↳", onto.bindings.length],
    ];
    host.innerHTML = "";
    cards.forEach(([label, acc, ic, num]) => {
      host.appendChild(el("div", "stat-card " + acc,
        `<div class="stat-ic">${ic}</div><div><div class="stat-label">${label}</div>
         <div class="stat-num">${num}</div></div>`));
    });
  } catch (e) { host.innerHTML = ""; }
}

// ---- GOVERNANCE ----------------------------------------------------------
const SEV_BADGE = { ok: "badge-auto", warn: "badge-review", fail: "badge-tail" };
async function loadGovernance() {
  // readiness
  const rd = await api("/api/readiness");
  const rh = $("#readiness");
  rh.innerHTML = `<div style="margin-bottom:12px"><b>Overall coverage: ${rd.overall_pct}%</b>
    <span class="muted">— ${rd.bound}/${rd.total} canonical properties bound to data across ${rd.domains} business domains</span></div>`;
  rd.levels.forEach(l => {
    const row = el("div", "readiness-row");
    row.innerHTML = `<span class="rd-lvl">${esc(l.label)}</span>
      <div class="rd-bar"><div class="rd-fill ${l.status}" style="width:${l.pct}%"></div></div>
      <span class="rd-pct">${l.pct}%</span>
      <span class="badge ${l.status === "fully" ? "badge-auto" : l.status === "partial" ? "badge-review" : "badge-tail"}">${l.status}</span>
      <span class="rd-objs">${l.bound}/${l.total}</span>`;
    rh.appendChild(row);
  });

  // health
  const h = await api("/api/health");
  $("#health-summary").innerHTML =
    `<div class="hs-pill hs-ok">${h.summary.ok} OK</div>
     <div class="hs-pill hs-warn">${h.summary.warn} warnings</div>
     <div class="hs-pill hs-fail">${h.summary.fail} failing</div>`;
  const hc = $("#health-checks"); hc.innerHTML = "";
  const card = el("div", "card");
  card.appendChild(el("div", "card-head", `<span class="name">health checks</span><span class="meta">${h.checks.length} checks</span>`));
  const wrap = el("div", "table-wrap"); const t = el("table");
  t.innerHTML = "<thead><tr><th>severity</th><th>target</th><th>check</th><th>finding</th></tr></thead>";
  const tb = el("tbody");
  h.checks.slice(0, 200).forEach(c => {
    const tr = el("tr");
    tr.innerHTML = `<td><span class="badge ${SEV_BADGE[c.severity]}">${esc(c.severity)}</span></td>
      <td>${esc(c.target)}</td><td>${esc(c.check)}</td><td>${esc(c.value)}</td>`;
    tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t); card.appendChild(wrap); hc.appendChild(card);

  // lineage selectors
  const data = await api("/api/governance/objects");
  const objSel = $("#lin-obj"), propSel = $("#lin-prop");
  const objs = data.objects;
  objSel.innerHTML = Object.keys(objs).map(o => `<option>${esc(o)}</option>`).join("");
  function fillProps() {
    const o = objSel.value;
    propSel.innerHTML = (objs[o] || []).map(p => `<option>${esc(p)}</option>`).join("");
  }
  objSel.onchange = () => { fillProps(); loadLineage(); };
  propSel.onchange = loadLineage;
  fillProps();
  loadLineage();
}

async function loadLineage() {
  const obj = $("#lin-obj").value, prop = $("#lin-prop").value;
  if (!obj || !prop) return;
  const host = $("#lineage-view"); host.innerHTML = '<div class="spinner">Tracing…</div>';
  const d = await api(`/api/lineage?object=${encodeURIComponent(obj)}&property=${encodeURIComponent(prop)}`);
  host.innerHTML = "";
  host.appendChild(el("div", "interp",
    `<b>${esc(d.object)}.${esc(d.property)}</b> — level ${esc(d.level)}${d.unit ? ", unit " + esc(d.unit) : ""}.
     Unified values: <code>${esc((d.resolved_sample || []).join(", "))}</code>.
     Backed by <b>${d.bindings.length}</b> source${d.bindings.length === 1 ? "" : "s"}.`));
  const card = el("div", "card");
  card.appendChild(el("div", "card-head", `<span class="name">lineage</span><span class="meta">raw → unified, per source</span>`));
  d.bindings.forEach(b => {
    const flow = el("div", "flow");
    flow.innerHTML = `<span class="node raw">${esc(b.source_table)}.${esc(b.source_col)} = ${esc(b.raw_sample)}</span>
      <span class="op">${b.transform === "-" ? "(direct)" : esc(b.transform) + "()"}</span>
      ${b.conversion ? `<span class="conv">${esc(b.conversion)}${b.source_unit ? " (" + esc(b.source_unit) + ")" : ""}</span>` : ""}
      <span>→</span>
      <span class="node unified">${esc(d.object)}.${esc(d.property)}</span>
      <span class="muted">· ${esc(b.source_file)} · conf ${esc(b.confidence)}</span>`;
    card.appendChild(flow);
  });
  host.appendChild(card);
  if (d.sql) host.appendChild(el("div", "sql", highlightSql(d.sql)));
}

let currentPlan = null;
let dzWired = false;
async function loadIncoming() {
  loadIngestStats();
  wireDropzone();
  const host = $("#incoming-files"); host.innerHTML = '<div class="spinner">Loading…</div>';
  const data = await api("/api/incoming");
  host.innerHTML = "";
  data.files.forEach(f => {
    const card = el("div", "file-card");
    const meta = f.row_count != null ? `${f.row_count} rows` : "Claude extracts the rows";
    card.innerHTML = `<div class="fn">${esc(f.file)} <span class="badge badge-soft">${esc(f.type)}</span></div>
      <div class="fl">${esc(f.label)} · ${meta}</div>
      ${f.headers && f.headers.length ? `<div class="cols">${f.headers.map(esc).join(" · ")}</div>` : ""}`;
    const btn = el("button", "btn btn-primary", "Land &amp; profile");
    btn.addEventListener("click", () => profileFile(f.file));
    card.appendChild(btn);
    host.appendChild(card);
  });
}

function wireDropzone() {
  if (dzWired) return; dzWired = true;
  const dz = $("#dropzone"), input = $("#file-input");
  if (!dz) return;
  input.addEventListener("change", () => { if (input.files[0]) uploadFile(input.files[0]); });
  ["dragenter", "dragover"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("over"); }));
  dz.addEventListener("drop", e => { const f = e.dataTransfer.files[0]; if (f) uploadFile(f); });
}

async function uploadFile(file) {
  const host = $("#ingest-plan");
  host.innerHTML = `<div class="spinner">Uploading ${esc(file.name)}…</div>`;
  const fd = new FormData(); fd.append("file", file);
  const r = await fetch("/api/upload", { method: "POST", body: fd }).then(x => x.json());
  if (r.error) { host.innerHTML = `<div class="empty">Upload failed: ${esc(r.error)}</div>`; return; }
  profileFile(r.file);
}

async function profileFile(file) {
  const host = $("#ingest-plan");
  host.innerHTML = '<div class="spinner">Landing file → extracting → the LLM is mapping columns to the ontology…</div>';
  const project = ($("#project-input") && $("#project-input").value.trim()) || "";
  const company = ($("#company-input") && $("#company-input").value.trim()) || "";
  const plan = await api("/api/ingest/profile", { file, project, company });
  currentPlan = plan;
  renderPlan(plan);
}

// ---- entity / company search (tabbed + drill-down) ----------------------
function _subtabs(host, tabs) {
  const bar = el("div", "subtab-bar"), body = el("div", "subtab-body");
  let first = tabs.findIndex(t => t.count > 0); if (first < 0) first = 0;
  tabs.forEach((t, i) => {
    const b = el("button", "subtab" + (i === first ? " on" : ""),
      `${esc(t.label)} <span class="cnt">${t.count}</span>`);
    b.addEventListener("click", () => {
      [...bar.children].forEach(x => x.classList.remove("on")); b.classList.add("on");
      body.innerHTML = ""; t.render(body);
    });
    bar.appendChild(b);
  });
  host.appendChild(bar); host.appendChild(body);
  if (tabs.length) tabs[first].render(body);
}

function _docTable(documents, note) {
  const card = el("div", "card");
  card.appendChild(el("div", "card-head",
    `<span class="name">documents</span><span class="meta">${note || (documents.length + " — click a row to view / download")}</span>`));
  const wrap = el("div", "table-wrap"), t = el("table");
  t.innerHTML = "<thead><tr><th>document</th><th>industry</th><th>project</th><th>type</th><th>status</th><th>rows</th></tr></thead>";
  const tb = el("tbody");
  documents.slice(0, 250).forEach(x => {
    const tr = el("tr"); tr.style.cursor = "pointer";
    tr.innerHTML = `<td><b>${esc(x.filename)}</b></td><td>${esc(x.industry)}</td><td>${esc(x.project || "—")}</td><td>${esc(x.doctype)}</td><td><span class="badge ${x.status === "committed" ? "badge-auto" : x.status === "landed" ? "badge-review" : "badge-soft"}">${esc(x.status)}</span></td><td>${x.rows}</td>`;
    tr.addEventListener("click", () => openDocument(x.filename));
    tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t); card.appendChild(wrap);
  return card;
}

function renderEntity(host, d) {
  host.innerHTML = "";
  const s = d.summary;
  host.appendChild(el("div", "interp",
    `<b>“${esc(d.query)}”</b> — ${s.documents} document(s) · ${s.objects} object(s) · ${s.properties} propert${s.properties === 1 ? "y" : "ies"} · ${s.projects} project(s)${s.narrative ? " · " + s.narrative + " narrative" : ""}.`));
  if (!s.documents && !s.objects && !s.narrative) {
    host.appendChild(el("div", "empty", "No ingested data found for that entity.")); return;
  }
  _subtabs(host, [
    {
      label: "Objects", count: d.objects.length, render: (node) => {
        d.objects.forEach(h => {
          const card = el("div", "card"); card.style.marginBottom = "12px";
          const head = el("div", "card-head");
          head.innerHTML = `<span class="name">${esc(h.object)}</span><span class="meta">${h.total} record(s) · identity ${esc(h.identity)}</span>`;
          const v = el("button", "btn btn-ghost", "view object →"); v.style.padding = "4px 10px";
          v.addEventListener("click", () => openObjectDrawer(h.object)); head.appendChild(v);
          card.appendChild(head); card.appendChild(dataTable(h.columns, h.rows, 20));
          node.appendChild(card);
        });
      },
    },
    { label: "Documents", count: d.documents.length, render: (node) => node.appendChild(_docTable(d.documents)) },
    {
      label: "Projects", count: d.projects.length, render: (node) => {
        d.projects.forEach(pr => {
          const c = el("button", "q-chip", esc(pr)); c.style.marginRight = "8px";
          c.addEventListener("click", () => openProjectDrawer(pr)); node.appendChild(c);
        });
      },
    },
    {
      label: "Narrative", count: d.narrative.length, render: (node) => {
        d.narrative.forEach(p => node.appendChild(el("div", "passage",
          `<div class="p-head"><span class="badge badge-soft">${esc(p.kind)}</span>
            <span class="p-ent">${esc(p.entity)}</span></div><div class="p-text">${esc(p.text)}</div>`)));
      },
    },
  ]);
}

async function entitySearch(q) {
  if (!q) return;
  const host = $("#entity-results"); host.innerHTML = '<div class="spinner">Searching the ontology…</div>';
  renderEntity(host, await api("/api/entity-search?q=" + encodeURIComponent(q)));
}

async function openEntityDrawer(entity) {
  const node = el("div"); node.innerHTML = '<div class="spinner">Searching…</div>';
  openDrawer("Entity · " + esc(entity), node);
  renderEntity(node, await api("/api/entity-search?q=" + encodeURIComponent(entity)));
}

// ---- Companies & Projects tracking views --------------------------------
let compCache = null;
async function loadCompanies() {
  const host = $("#companies-list"); host.innerHTML = '<div class="spinner">Loading…</div>';
  if (!compCache) compCache = (await api("/api/companies")).companies;
  const q = ($("#comp-q") && $("#comp-q").value.trim().toLowerCase()) || "";
  const list = compCache.filter(c => !q || c.entity.toLowerCase().includes(q));
  host.innerHTML = "";
  host.appendChild(el("div", "muted", `${list.length} of ${compCache.length} tracked entities — click to drill in`));
  const card = el("div", "card"); card.style.marginTop = "10px";
  const wrap = el("div", "table-wrap"), t = el("table");
  t.innerHTML = "<thead><tr><th>company / entity</th><th>documents</th><th>industries</th><th>projects</th></tr></thead>";
  const tb = el("tbody");
  list.slice(0, 400).forEach(c => {
    const tr = el("tr"); tr.style.cursor = "pointer";
    tr.innerHTML = `<td><b>${esc(c.entity)}</b></td><td>${c.docs}</td><td>${esc(c.industries.join(", "))}</td><td>${esc(c.projects.slice(0, 3).join(", "))}</td>`;
    tr.addEventListener("click", () => openEntityDrawer(c.entity));
    tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t); card.appendChild(wrap); host.appendChild(card);
  if ($("#comp-q") && !$("#comp-q")._wired) { $("#comp-q")._wired = true; $("#comp-q").addEventListener("input", () => loadCompanies()); }
}

async function loadProjects() {
  const host = $("#projects-list"); host.innerHTML = '<div class="spinner">Loading…</div>';
  const data = await api("/api/projects");
  host.innerHTML = "";
  const card = el("div", "card");
  card.appendChild(el("div", "card-head", `<span class="name">projects</span><span class="meta">${data.projects.length} — click to drill in</span>`));
  const wrap = el("div", "table-wrap"), t = el("table");
  t.innerHTML = "<thead><tr><th>project</th><th>documents</th><th>industries</th></tr></thead>";
  const tb = el("tbody");
  data.projects.forEach(p => {
    const tr = el("tr"); tr.style.cursor = "pointer";
    tr.innerHTML = `<td><b>${esc(p.project)}</b></td><td>${p.docs}</td><td>${esc(p.industries.join(", "))}</td>`;
    tr.addEventListener("click", () => openProjectDrawer(p.project));
    tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t); card.appendChild(wrap); host.appendChild(card);
}

async function openProjectDrawer(project) {
  const node = el("div"); node.innerHTML = '<div class="spinner">Loading…</div>';
  openDrawer("Project · " + esc(project), node);
  const data = await api("/api/documents?project=" + encodeURIComponent(project));
  node.innerHTML = "";
  node.appendChild(el("div", "interp", `<b>${esc(project)}</b> — ${data.documents.length} document(s).`));
  node.appendChild(_docTable(data.documents));
}

function renderPlan(plan) {
  const host = $("#ingest-plan");
  host.innerHTML = "";
  const cost = plan.cost_usd ? ` · cost $${Number(plan.cost_usd).toFixed(5)}` : "";
  const intro = el("div", "interp",
    `Landed as raw table <code>${esc(plan.staging_table)}</code> — ${esc(plan.extract_note || "")}.
     <br>Mapped by <b>${esc(plan.engine || "matcher")}</b>${cost}; the file describes
     <b>${esc(plan.file_object)}</b> records. Approve the mapping below.`);
  host.appendChild(intro);
  if (plan.llm_error) host.appendChild(el("div", "interp",
    `<span class="badge badge-review">LLM unavailable</span> used the offline matcher. <span class="muted">${esc(plan.llm_error)}</span>`));

  const card = el("div", "card");
  card.appendChild(el("div", "card-head",
    `<span class="name">Proposed bindings</span><span class="meta">${plan.file}</span>`));

  plan.proposals.forEach((p, i) => {
    const row = el("div", "proposal");
    const badge = p.kind === "auto" ? "badge-auto" : "badge-review";
    const fillCls = p.kind === "auto" ? "" : "review";
    const checked = "checked";
    row.innerHTML = `
      <div class="col">${esc(p.column)}<span class="sample">${esc(p.sample)}</span></div>
      <div class="arrow">→</div>
      <div class="tgt">${esc(p.object)}.${esc(p.property)} ${p.is_new ? '<span class="badge badge-new">new</span>' : ''}
        <span class="xform">${p.transform === "-" ? "no transform" : esc(p.transform) + "()"}${p.note ? " · " + esc(p.note) : ""}</span></div>
      <div class="conf">
        <span class="badge ${badge}">${p.kind} ${Math.round(p.confidence * 100)}%</span>
        <div class="conf-bar"><div class="conf-fill ${fillCls}" style="width:${Math.round(p.confidence * 100)}%"></div></div>
        <input type="checkbox" data-i="${i}" ${checked}>
      </div>`;
    card.appendChild(row);
  });
  host.appendChild(card);

  if (plan.tail.length) {
    const tcard = el("div", "card"); tcard.style.marginTop = "14px";
    tcard.appendChild(el("div", "card-head",
      `<span class="name">No canonical home → RAG tail</span><span class="meta">kept as narrative, still answerable</span>`));
    plan.tail.forEach(t => tcard.appendChild(el("div", "tail-row",
      `<span class="badge badge-tail">tail</span><span class="col">${esc(t.column)}</span>
       <span class="muted">${esc(t.sample)} — ${esc(t.reason)}</span>`)));
    host.appendChild(tcard);
  }

  const commit = el("button", "btn btn-primary", "Commit — make it live");
  commit.style.marginTop = "16px";
  commit.addEventListener("click", () => commitPlan());
  host.appendChild(commit);
}

async function commitPlan() {
  if (!currentPlan) return;
  const checks = $$('#ingest-plan input[type=checkbox]');
  const accepted = checks.filter(c => c.checked).map(c => currentPlan.proposals[+c.dataset.i]);
  const res = await api("/api/ingest/commit",
    { file: currentPlan.file, proposals: accepted, tail: currentPlan.tail });
  const host = $("#ingest-plan");
  const sum = el("div", "commit-summary");
  let h = `<b>Committed.</b> ${res.bindings_added} pointer rows added to the bindings table`;
  if (res.added_objects.length) h += `, new object(s): ${res.added_objects.map(esc).join(", ")}`;
  if (res.added_properties.length) h += `, new propertie(s): ${res.added_properties.map(esc).join(", ")}`;
  if (res.tail_added) h += `, ${res.tail_added} item(s) to the RAG tail`;
  h += `.<br><span class="muted">No new business table was created — the canonical objects just gained another source.
    Check the <b>Raw layer</b> (new <code>${esc(res.staging_table)}</code>), the <b>meaning layer</b> (new bindings),
    and re-run a question on the <b>agent</b> tab to see the new data answer.</span>`;
  sum.innerHTML = h;
  host.appendChild(sum);
  loaded.ontology = false; // force refresh next visit
  loadIngestStats();
}

// ---- AGENT ---------------------------------------------------------------
async function loadAgentMeta() {
  if (loaded.agentMeta) return; loaded.agentMeta = true;
  const meta = await api("/api/meta");
  const chips = $("#suggested"); chips.innerHTML = "";
  meta.suggested_questions.forEach(q => {
    const c = el("button", "q-chip", esc(q));
    c.addEventListener("click", () => { $("#question").value = q; ask(); });
    chips.appendChild(c);
  });
  if (meta.llm_available) {
    $("#llm-toggle-wrap").classList.remove("hidden");
    $("#use-llm").checked = true;
  }
}

async function ask() {
  const q = $("#question").value.trim();
  if (!q) return;
  const useLlm = $("#use-llm") && $("#use-llm").checked;
  const host = $("#agent-result");
  host.innerHTML = '<div class="spinner">Thinking…</div>';
  const r = await api("/api/agent", { question: q, use_llm: useLlm });
  renderAgent(r);
}

function renderAgent(r) {
  const host = $("#agent-result");
  host.innerHTML = "";
  const modeBadge = r.mode === "llm" ? '<span class="badge badge-new">Claude</span>'
    : '<span class="badge badge-soft">router</span>';
  host.appendChild(el("div", "interp",
    `${modeBadge} <b>Interpretation:</b> ${esc(r.interpretation)}`));
  if (r.llm_error) host.appendChild(el("div", "interp",
    `<span class="badge badge-review">Claude unavailable</span> fell back to the router. <span class="muted">${esc(r.llm_error)}</span>`));

  r.steps.forEach(s => {
    const step = el("div", "step");
    step.appendChild(el("div", "step-head",
      `<span>${esc(s.label)}</span><span class="obj">${esc(s.object)}</span>`));
    if (s.narrative) {
      step.appendChild(el("div", "sql", esc(s.sql)));
      const body = el("div"); body.style.padding = "12px 14px";
      (s.rows || []).forEach(p => body.appendChild(el("div", "passage",
        `<div class="p-head"><span class="badge badge-soft">${esc(p.kind)}</span>
          <span class="p-ent">${esc(p.entity)}</span></div>
         <div class="p-text">${esc(p.text)}</div>`)));
      step.appendChild(body);
    } else {
      step.appendChild(el("div", "sql", highlightSql(s.sql)));
      if (s.rows && s.rows.length) step.appendChild(dataTable(s.columns, s.rows));
      else step.appendChild(el("div", "empty", "No rows."));
    }
    host.appendChild(step);
  });

  const ans = el("div", "answer");
  ans.innerHTML = `<div class="lbl">Agent answer</div>${esc(r.answer)}`;
  if (r.sources && r.sources.length)
    ans.appendChild(el("div", "sources", `<b>Grounded in:</b> ${r.sources.map(esc).join(", ")}`));
  if (r.cost_usd)
    ans.appendChild(el("div", "sources", `<b>LLM cost:</b> $${Number(r.cost_usd).toFixed(5)} (${esc(r.engine || "")})`));
  host.appendChild(ans);
}

$("#ask-btn").addEventListener("click", ask);
$("#question").addEventListener("keydown", e => { if (e.key === "Enter") ask(); });
if ($("#narr-btn")) $("#narr-btn").addEventListener("click", () => loadNarrative($("#narr-q").value.trim()));
if ($("#narr-q")) $("#narr-q").addEventListener("keydown", e => { if (e.key === "Enter") loadNarrative($("#narr-q").value.trim()); });
if ($("#ent-btn")) $("#ent-btn").addEventListener("click", () => entitySearch($("#ent-q").value.trim()));
if ($("#ent-q")) $("#ent-q").addEventListener("keydown", e => { if (e.key === "Enter") entitySearch($("#ent-q").value.trim()); });

// ---- reset ---------------------------------------------------------------
$("#reset-btn").addEventListener("click", async () => {
  await api("/api/reset", {});
  currentPlan = null;
  $("#ingest-plan").innerHTML = "";
  $("#agent-result").innerHTML = "";
  ["raw", "ontology", "ingest", "documents"].forEach(t => { loaded[t] = false; });
  loaded.narr = false; compCache = null;
  await initContext();
  const active = $(".tab.active").dataset.tab;
  if (loaders[active]) loaders[active]();
});

// ---- startup: header AI-badge status ----
(async function initBadge() {
  try {
    const m = await api("/api/meta");
    $("#mode-badge").textContent = m.llm_available
      ? `${m.llm.backend} · ${m.llm.extract_model}`
      : "offline · structured files only";
  } catch (e) { $("#mode-badge").textContent = "backend offline"; }
})();
initContext();

// scene-based narrated explainer on the Overview: the composition recomposes per step, in sync with voice-over
function initOverviewDemo() {
  const svg = $("#sg");
  if (!svg || svg._wired) return;
  svg._wired = true;
  const capText = $("#hp-cap-text"), counter = $("#hp-counter"), playBtn = $("#hp-play");

  // element refs
  const q = $("#sg-q"), fuse = $("#sg-fuse"), ans = $("#sg-ans"), fa = $("#sg-fa");
  const objs = [1, 2, 3, 4, 5].map(i => $("#sg-o" + i));
  const raws = [1, 2, 3, 4, 5].map(i => $("#sg-r" + i));
  const chips = [1, 2, 3, 4, 5].map(i => $("#sg-c" + i));
  const qo = [1, 2, 3, 4, 5].map(i => $("#sg-qo" + i));
  const or = [1, 2, 3, 4, 5].map(i => $("#sg-or" + i));
  const of = [1, 2, 3, 4, 5].map(i => $("#sg-of" + i));
  const nodes = [q, fuse, ans, ...objs, ...raws];
  const edges = [...qo, ...or, ...of, fa];
  const SH = e => e && e.classList.add("show");
  const DR = e => e && e.classList.add("draw");
  const first = (arr, n) => arr.slice(0, n);

  function reset() {
    svg.classList.remove("establish");
    nodes.forEach(e => e && e.classList.remove("show"));
    q.classList.remove("center");
    chips.forEach(c => c && c.classList.remove("show"));
    edges.forEach(e => e && e.classList.remove("draw", "flow"));
  }
  // each scene is a fresh composition; transitions between them are the "video"
  function applyScene(n) {
    reset();
    if (n === 1) {
      svg.classList.add("establish");
      [q, ...objs, ...raws].forEach(SH); [...qo, ...or].forEach(DR);
    } else if (n === 2) {
      SH(q); q.classList.add("center");
    } else if (n === 3) {
      SH(q); first(objs, 4).forEach(SH); first(qo, 4).forEach(DR);
    } else if (n === 4) {
      SH(q); first(objs, 4).forEach(SH); first(raws, 4).forEach(SH);
      first(qo, 4).forEach(DR); first(or, 4).forEach(DR);
    } else if (n === 5) {
      SH(q); first(objs, 4).forEach(SH); first(raws, 4).forEach(SH);
      first(qo, 4).forEach(DR); first(or, 4).forEach(e => { DR(e); e.classList.add("flow"); });
    } else if (n === 6) {
      SH(q); first(objs, 4).forEach(SH); first(raws, 4).forEach(SH); first(chips, 4).forEach(SH);
      first(qo, 4).forEach(DR); first(or, 4).forEach(DR);
    } else if (n === 7) {
      SH(q); objs.forEach(SH); raws.forEach(SH); chips.forEach(SH);
      qo.forEach(DR); or.forEach(DR);
    } else if (n === 8) {
      SH(q); objs.forEach(SH); chips.forEach(SH); SH(fuse);
      qo.forEach(DR); of.forEach(DR);
    } else if (n === 9) {
      SH(q); objs.forEach(SH); chips.forEach(SH); SH(fuse); SH(ans);
      qo.forEach(DR); of.forEach(DR); DR(fa);
    }
  }
  svg._scene = applyScene; // debug/verification hook

  // captions for the silent, self-paced walkthrough (no voice-over)
  const NAR = [
    { scene: 1, cap: "Here's the whole flow at a glance — a <b>question</b> at the top, the <b>things we track</b> in the middle, your <b>raw files</b> at the bottom. Now let's watch it happen." },
    { scene: 2, cap: "It all starts with one <b>question</b>, in plain English." },
    { scene: 3, cap: "The question <b>breaks apart</b> and links to the <b>objects</b> that can answer it. <span class='def'>An object is a business thing — a Brand, a Product, a Price.</span>" },
    { scene: 4, cap: "Each object reaches <b>down through a pointer</b> to where that fact really lives. <span class='def'>A pointer is like a phone contact — the name points to the number.</span>" },
    { scene: 5, cap: "The pointers <b>fetch the real values</b>, live, with a query written in <b>SQL</b>. <span class='def'>SQL is the standard language for asking a database for data.</span>" },
    { scene: 6, cap: "Values come back <b>cleaned</b> — rupee signs stripped, crore turned into millions — so everything lines up." },
    { scene: 7, cap: "The <b>words</b> join too — strategy and notes from the narrative store, found by keyword search." },
    { scene: 8, cap: "Everything <b>converges</b> — the numbers and the narrative fuse into one connected picture." },
    { scene: 9, cap: "Out comes a single <b>cited</b> answer. <b>Nothing was pre-stored</b> — the same path runs for any question, any company." },
  ];
  // rough reading time per caption
  function holdMs(html) {
    const words = html.replace(/<[^>]+>/g, "").split(/\s+/).filter(Boolean).length;
    return Math.min(7000, Math.max(3200, words * 360));
  }

  let i = 0, state = "ambient", ambient = null, timer = null;
  function startAmbient() {
    stopAll();
    let s = 1; applyScene(s);
    ambient = setInterval(() => { s = s >= 9 ? 1 : s + 1; applyScene(s); }, 1900);
  }
  function stopAll() {
    if (ambient) { clearInterval(ambient); ambient = null; }
    if (timer) { clearTimeout(timer); timer = null; }
  }
  function showStep() {
    const s = NAR[i];
    applyScene(s.scene);
    capText.innerHTML = s.cap;
    counter.textContent = "Step " + (i + 1) + " / " + NAR.length;
  }
  function runStep() {
    if (state !== "playing") return;
    if (i >= NAR.length) { finish(); return; }
    showStep();
    timer = setTimeout(() => { if (state !== "playing") return; i++; runStep(); }, holdMs(NAR[i].cap));
  }
  function finish() { state = "done"; playBtn.textContent = "🔁 Replay"; counter.textContent = "done"; startAmbient(); }

  playBtn.addEventListener("click", () => {
    if (state === "playing") { state = "paused"; stopAll(); playBtn.textContent = "▶ Resume"; }
    else if (state === "paused") { state = "playing"; playBtn.textContent = "⏸ Pause"; runStep(); }
    else { stopAll(); i = 0; state = "playing"; playBtn.textContent = "⏸ Pause"; runStep(); }
  });

  startAmbient(); // silent, looping scene animation until the user presses play
}
initOverviewDemo();

// reveal sections on scroll
function initReveal() {
  const els = [...document.querySelectorAll(".reveal")];
  if (!els.length) return;
  if (!("IntersectionObserver" in window)) { els.forEach(e => e.classList.add("in")); return; }
  const io = new IntersectionObserver((ents) => {
    ents.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
  }, { threshold: 0.12 });
  els.forEach(e => io.observe(e));
}
initReveal();

// FAQ accordion
function initFaq() {
  document.querySelectorAll(".faq-q").forEach(btn => {
    if (btn._wired) return; btn._wired = true;
    btn.addEventListener("click", () => btn.parentElement.classList.toggle("open"));
  });
}
initFaq();
