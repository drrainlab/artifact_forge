// Product Cockpit — screens. Truth first: every panel renders view models
// from the pipeline; the UI never invents state.
import { api } from "app/api.js";
import { renderSection, sectionSvg } from "app/section.js";
import { ThreeView } from "app/three_view.js";
import { renderAssemblyWizard } from "app/assembly_wizard.js";

const $ = (sel, el = document) => el.querySelector(sel);
const screenEl = $("#screen");
//: EDIT lens hook — a region pick in the main viewport/tree routes here to
//: update the target select (null whenever the EDIT lens is not showing).
let editSetTarget = null;
const state = {
  status: null,
  catalog: null,
  yaml: null,          // current product/assembly YAML text
  validation: null,    // last /api/validate view model
  buildReport: null,   // last build job result
  lens: "3d",
  selectedRegion: null, // region id targeted by semantic edits
  stlFiles: [],        // {url, file} actually loaded into the 3D view
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ---------------------------------------------------------------- topbar
async function refreshTop() {
  state.status = await api.status();
  const s = state.status;
  const b = s.archetypes.buildable.length + s.archetypes.recipe.length;
  $("#topstatus").innerHTML = `
    <span>archetypes <b>${b}</b>/${b + s.archetypes.metadata_only.length}</span>
    <span>joints <b>${s.joints.length}</b></span>
    <span class="badge ${s.cad ? "on" : "off"}">CAD ${s.cad ? "ON" : "OFF"}</span>
    <span class="badge ${s.llm ? "on" : "off"}">LLM ${s.llm ? "ON" : "OFF"}</span>
    <span class="badge on">STRICT default</span>`;
}

// An async action in flight must be VISIBLE on the button itself:
// spinner + verb, disabled, restored on finish. Re-render inside fn is
// fine — restoring a detached node is harmless.
async function withBusy(btn, label, fn) {
  if (!btn || btn.dataset.busy) return;
  const old = btn.innerHTML;
  btn.dataset.busy = "1";
  btn.disabled = true;
  btn.innerHTML = `<span class="spin"></span>${esc(label)}`;
  try { return await fn(); } finally {
    delete btn.dataset.busy;
    btn.disabled = false;
    btn.innerHTML = old;
  }
}

// ------------------------------------------------------------------ home
function renderHome() {
  const s = state.status;
  screenEl.innerHTML = `<div class="home">
    <h1>ARTIFACT FORGE — product cockpit</h1>
    <div class="sub">understood → capable → built → verified → honestly reported</div>
    <div class="entries">
      <div class="entry" data-go="wizard"><h3>Create from prompt</h3>
        <p>Describe the part; the system shows what it understood, what it can build, and only then forges.</p></div>
      <div class="entry" data-go="assembly"><h3>Assemble from prompt</h3>
        <p>Describe a multi-part product; the model composes parts, joints and wiring from the catalog — the pipeline judges the draft.</p></div>
      <div class="entry" data-go="yaml"><h3>Create from YAML</h3>
        <p>Paste a product or assembly document and validate it against the catalog.</p></div>
      <div class="entry" data-go="catalog"><h3>Browse archetype catalog</h3>
        <p>What the system honestly supports: buildable, recipe, metadata-only.</p></div>
      <div class="entry disabled"><h3>Create from reference image</h3>
        <p><span class="badge off">vision intent — v2</span></p></div>
    </div>
    <a class="entry docs-link" href="https://artifactforge.dev" target="_blank"
       rel="noopener">
      <h3>Documentation → artifactforge.dev</h3>
      <p>The full story: every archetype, joint, recipe op and validator —
      plus guides from prompt to printed part.
      ${s.cad ? "" : '<span class="badge off">CAD OFF</span>'}
      ${s.llm ? "" : '<span class="badge off">LLM OFF — deterministic fallback</span>'}</p>
    </a>
  </div>`;
  screenEl.querySelectorAll(".entry[data-go]").forEach((el) =>
    el.addEventListener("click", () => go(el.dataset.go)));
}

// --------------------------------------------------------------- catalog
// Explorer view state (survives tab switches within the session).
const catView = { tab: "all", q: "", domains: new Set(), packs: new Set(),
                  statuses: new Set(), advanced: false, expanded: new Set() };
const previews = {};  // archetype id -> PreviewVM | null | undefined(=not asked)
let catSearchTimer = null;

function isAdvancedCard(a) {
  return a.audience === "advanced" || a.kind !== "archetype" || a.tier === "private";
}

function cardMatches(a) {
  if (!catView.advanced && isAdvancedCard(a)) return false;
  if (catView.domains.size && !catView.domains.has(a.domain)) return false;
  if (catView.packs.size && !catView.packs.has(a.pack)) return false;
  if (catView.statuses.size && !catView.statuses.has(a.status)) return false;
  if (catView.q) {
    const hay = [a.id, a.summary, a.domain, a.pack_name,
                 ...(a.tags || []), ...(a.use_cases || [])].join(" ").toLowerCase();
    if (!hay.includes(catView.q.toLowerCase())) return false;
  }
  return true;
}

function catalogSort(cards, featured) {
  const featRank = (a) => { const i = featured.indexOf(a.id); return i < 0 ? 99 : i; };
  const packRank = (a) => a.pack === "core" ? 2 : (a.pack === "local" ? 3 : 1);
  return [...cards].sort((x, y) =>
    featRank(x) - featRank(y)
    || (y.status === "buildable" || y.status === "recipe") - (x.status === "buildable" || x.status === "recipe")
    || (y.examples_count > 0) - (x.examples_count > 0)
    || packRank(x) - packRank(y)
    || isAdvancedCard(x) - isAdvancedCard(y)
    || x.id.localeCompare(y.id));
}

function previewHtml(a) {
  const pv = previews[a.id];
  if (pv && pv.section) {
    return sectionSvg(pv.section, { holes: pv.holes, bores: pv.bores });
  }
  const known = pv === null;  // asked and honestly no default preview
  return `<div class="preview-ph">
    <b>${esc((a.domain[0] || "?").toUpperCase())}</b>
    <span>${esc(a.domain)}</span>
    <span class="faint">${known ? "no default preview" : "…"}</span>
  </div>`;
}

function catalogCard(a) {
  const chips = [
    `<span class="chip">${esc(a.domain)}</span>`,
    `<span class="chip">${esc(a.pack_name)}</span>`,
    ...(a.modes || []).map((m) => `<span class="chip dim2">${esc(m)}</span>`),
    `<span class="chip ${a.tier === "free" ? "dim2" : "tier"}">${esc(a.tier)}</span>`,
  ].join(" ");
  const tags = (a.tags || []).length
    ? `<div class="tags">${a.tags.map((t) => esc(t)).join(" · ")}</div>` : "";
  const summary = a.summary.length > 170 ? a.summary.slice(0, 167) + "…" : a.summary;
  const expandable = a.description.trim().length > a.summary.length + 5;
  const open = catView.expanded.has(a.id);
  return `<div class="card hcard">
    <div class="preview" data-pid="${esc(a.id)}">${previewHtml(a)}</div>
    <div class="cbody">
      <h3>${esc(a.id)} <span class="badge ${a.status}">${a.status}</span>${a.maturity ? ` <span class="badge off" title="lifecycle stage (informational)">${esc(a.maturity)}</span>` : ""}</h3>
      <div class="chips">${chips}</div>
      <div class="desc">${esc(summary)}</div>
      ${open ? `<div class="desc full">${esc(a.description)}</div>` : ""}
      ${tags}
      <div class="meta">features ${a.provides_features.length} ·
        validators ${a.validators.length} · examples ${a.examples_count}
        ${a.status === "metadata_only" ? "<br>can author YAML: yes · can build STL: no" : ""}</div>
      <div class="row mt">
        <button class="ghost" data-arch="${esc(a.id)}">open in wizard</button>
        ${expandable ? `<button class="ghost" data-more="${esc(a.id)}">${open ? "less" : "more"}</button>` : ""}
      </div>
    </div>
  </div>`;
}

function checkGroup(title, items, sel, key) {
  return `<div class="fgroup"><div class="dim">${title}</div>${items.map((it) => `
    <label><input type="checkbox" data-facet="${key}" value="${esc(it.id)}"
      ${sel.has(it.id) ? "checked" : ""}> ${esc(it.name || it.id)}
      <span class="faint">${it.count}</span></label>`).join("")}</div>`;
}

async function loadPreviews(ids) {
  const missing = ids.filter((id) => previews[id] === undefined);
  for (let i = 0; i < missing.length; i += 8) {
    const chunk = missing.slice(i, i + 8);
    try {
      const got = await api.previews(chunk);
      chunk.forEach((id) => { previews[id] = got[id] ?? null; });
    } catch (err) {
      console.warn("previews unavailable:", err);
      chunk.forEach((id) => { previews[id] = null; });
    }
    const c = state.catalog;
    if (!c) return;
    chunk.forEach((id) => {
      const el = screenEl.querySelector(`.preview[data-pid="${CSS.escape(id)}"]`);
      const card = c.archetypes.find((a) => a.id === id);
      if (el && card) el.innerHTML = previewHtml(card);
    });
  }
}

async function renderCatalog() {
  if (!state.catalog) state.catalog = await api.catalog();
  const c = state.catalog;
  const featured = c.featured || [];
  const visible = catalogSort(c.archetypes.filter(cardMatches), featured);
  const total = c.archetypes.length;
  const hiddenAdvanced = c.archetypes.filter((a) => isAdvancedCard(a)).length;
  const filtersActive = catView.q || catView.domains.size || catView.packs.size
    || catView.statuses.size;

  const tabDefs = [["all", `All (${visible.length})`], ["featured", "Featured"],
                   ["domains", "Domains"], ["packs", "Packs"]];
  const tabs = tabDefs.map(([t, label]) =>
    `<button class="subtab ${catView.tab === t ? "active" : ""}" data-cattab="${t}">${label}</button>`).join("");

  const showing = `<div class="showing">Showing ${visible.length} of ${total} archetypes
    ${!catView.advanced && hiddenAdvanced ? `· ${hiddenAdvanced} hidden as advanced/reference
      <button class="linklike" data-showadv>show advanced</button>` : ""}
    ${filtersActive ? `<button class="linklike" data-clearf>clear filters ×</button>` : ""}</div>`;

  let body = "";
  if (catView.tab === "featured") {
    const featCards = featured
      .map((id) => visible.find((a) => a.id === id)).filter(Boolean);
    const tiles = (c.facets?.domains || [])
      .map((d) => `<button class="tile" data-domain="${esc(d.id)}">
        <b>${esc(d.id)}</b><span class="faint">${d.count} archetype${d.count === 1 ? "" : "s"}</span></button>`).join("");
    body = `<h3 class="dim">FEATURED STARTERS</h3>
      <div class="cards hgrid">${featCards.map(catalogCard).join("")}</div>
      <h3 class="dim" style="margin-top:22px">BROWSE BY DOMAIN</h3>
      <div class="tiles">${tiles}</div>`;
  } else if (catView.tab === "domains" || catView.tab === "packs") {
    const key = catView.tab === "domains" ? "domain" : "pack_name";
    const groups = new Map();
    visible.forEach((a) => {
      if (!groups.has(a[key])) groups.set(a[key], []);
      groups.get(a[key]).push(a);
    });
    body = [...groups.keys()].sort().map((g) =>
      `<h3 class="dim">${esc(g.toUpperCase())} <span class="faint">${groups.get(g).length}</span></h3>
       <div class="cards hgrid">${groups.get(g).map(catalogCard).join("")}</div>`).join("");
  } else {
    body = `<div class="cards hgrid">${visible.map(catalogCard).join("")}</div>
      <h3 class="dim" style="margin:22px 0 12px">EXAMPLES</h3>
      <div class="cards">${c.examples.map((e) => `
        <div class="card"><h3>${esc(e.id)} <span class="badge recipe">${e.kind}</span></h3>
          <div class="meta">${esc(e.archetype || (e.parts || []).join(" + "))}</div>
          <button class="ghost" data-example="${esc(e.file)}">open in workspace</button>
        </div>`).join("")}</div>`;
  }

  screenEl.innerHTML = `<div class="catalog catalog-layout">
    <aside class="filters">
      <input id="catq" type="text" placeholder="search…" value="${esc(catView.q)}">
      ${checkGroup("Domain", (c.facets?.domains || []), catView.domains, "domains")}
      ${checkGroup("Pack", (c.facets?.packs || []), catView.packs, "packs")}
      ${checkGroup("Status", (c.facets?.statuses || []), catView.statuses, "statuses")}
      <label class="fadv"><input id="catadv" type="checkbox" ${catView.advanced ? "checked" : ""}>
        show advanced <span class="faint">(+${hiddenAdvanced} reference/private)</span></label>
    </aside>
    <div class="catmain">
      <div class="subtabs">${tabs}</div>
      ${showing}
      ${body}
    </div>
  </div>`;

  screenEl.querySelectorAll("[data-cattab]").forEach((b) =>
    b.addEventListener("click", () => { catView.tab = b.dataset.cattab; renderCatalog(); }));
  screenEl.querySelectorAll("[data-domain]").forEach((b) =>
    b.addEventListener("click", () => {
      catView.tab = "domains";
      catView.domains = new Set([b.dataset.domain]);
      renderCatalog();
    }));
  const q = screenEl.querySelector("#catq");
  q.addEventListener("input", () => {
    clearTimeout(catSearchTimer);
    catSearchTimer = setTimeout(async () => {
      catView.q = q.value;
      await renderCatalog();
      const nq = screenEl.querySelector("#catq");
      nq.focus();
      nq.setSelectionRange(nq.value.length, nq.value.length);
    }, 120);
  });
  screenEl.querySelector("#catadv").addEventListener("change", (e) => {
    catView.advanced = e.target.checked; renderCatalog();
  });
  const adv = screenEl.querySelector("[data-showadv]");
  if (adv) adv.addEventListener("click", () => { catView.advanced = true; renderCatalog(); });
  const clearf = screenEl.querySelector("[data-clearf]");
  if (clearf) clearf.addEventListener("click", () => {
    catView.q = ""; catView.domains.clear(); catView.packs.clear();
    catView.statuses.clear(); renderCatalog();
  });
  screenEl.querySelectorAll("[data-facet]").forEach((cb) =>
    cb.addEventListener("change", () => {
      const set = catView[cb.dataset.facet];
      cb.checked ? set.add(cb.value) : set.delete(cb.value);
      renderCatalog();
    }));
  screenEl.querySelectorAll("[data-more]").forEach((b) =>
    b.addEventListener("click", () => {
      const id = b.dataset.more;
      catView.expanded.has(id) ? catView.expanded.delete(id) : catView.expanded.add(id);
      renderCatalog();
    }));
  screenEl.querySelectorAll("[data-example]").forEach((b) =>
    b.addEventListener("click", () => withBusy(b, "opening…", async () => {
      const ex = await api.example(b.dataset.example);
      await openInWorkspace(ex.yaml);
    })));
  screenEl.querySelectorAll("[data-arch]").forEach((b) =>
    b.addEventListener("click", () => renderWizard({ archetype_id: b.dataset.arch })));

  // previews load AFTER first paint, only for rendered cards, in batches
  const shownIds = [...screenEl.querySelectorAll(".preview[data-pid]")]
    .map((el) => el.dataset.pid);
  loadPreviews(shownIds);
}

// ---------------------------------------------------------------- wizard
async function renderWizard(preset = null) {
  if (!state.catalog) state.catalog = await api.catalog();
  setNav("wizard");
  const wiz = { stage: 1, intent: null, archetype: null, params: {}, validation: null };
  if (preset?.archetype_id) {
    wiz.archetype = state.catalog.archetypes.find((a) => a.id === preset.archetype_id);
    wiz.stage = 2;
  }

  const stagesBar = () => `<div class="stages">${[
    "1 Intent", "2 Contract", "3 Capability", "4 Parameters", "5 Validate Form",
  ].map((n, i) => `<div class="${i + 1 === wiz.stage ? "now" : i + 1 < wiz.stage ? "done" : ""}">${n}</div>`).join("")}</div>`;

  function wizYaml() {
    const a = wiz.archetype;
    const params = {};
    for (const [k, v] of Object.entries(wiz.params)) if (v !== "" && v != null) params[k] = v;
    const doc = {
      schema: "product/v1",
      id: (wiz.intent?.suggested_id || `${a.object_class}_draft`),
      archetype: `${a.id}@${a.version}`,
      strict: true,
      params,
    };
    return jsyaml(doc);
  }

  async function revalidate() {
    wiz.validation = await api.validate(wizYaml(), false);
    // a pipeline-level fail carries no param cards — keep the last good
    // set (or the archetype's spec) so the user can still FIX the value
    if (wiz.validation.params?.length) wiz.lastParams = wiz.validation.params;
    else {
      wiz.validation.params = wiz.lastParams
        || (wiz.archetype?.parameters || []).map((p) => ({
             ...p, value: p.default, locked: p.role === "safety_locked",
             min: null, max: null }));
    }
    return wiz.validation;
  }

  // A failed API call must never leave the wizard silently frozen on the
  // previous stage — show the error and offer a retry of the SAME stage.
  const render = async () => {
    try {
      await renderStage();
    } catch (err) {
      screenEl.innerHTML = `<div class="wizard">${stagesBar()}
        <div class="panel"><h3>WIZARD ERROR</h3>
          <div class="mt"><span class="badge fail">stage ${wiz.stage} failed</span></div>
          <pre class="mt" style="white-space:pre-wrap">${esc(String(err?.message || err))}</pre>
          <div class="row mt"><button class="forge" id="retry">Retry</button></div>
        </div></div>`;
      $("#retry").addEventListener("click", () => withBusy(
        $("#retry"), "retrying…", () => render()));
    }
  };

  const renderStage = async () => {
    if (wiz.stage === 1) {
      screenEl.innerHTML = `<div class="wizard">${stagesBar()}
        <div class="panel"><h3>DESCRIBE THE PART</h3>
          <textarea id="prompt" rows="3" placeholder="under-desk cable clip for a 20mm bundle, side entry, two M4 screws"></textarea>
          <div class="row mt">
            <button class="forge" id="detect">Detect intent</button>
            <span class="dim">${state.status.llm ? "LLM intent (Anthropic)" : "LLM OFF — deterministic catalog matching"}</span>
          </div>
          <div id="intent-out" class="mt"></div>
        </div></div>`;
      $("#detect").addEventListener("click", () => withBusy(
          $("#detect"), "detecting intent (LLM)…", async () => {
        $("#intent-out").innerHTML = `<span class="dim">the model is reading the prompt…</span>`;
        const out = await api.intent($("#prompt").value);
        if (!out.ok) {
          $("#intent-out").innerHTML = findingsTable(out.findings || []);
          return;
        }
        wiz.intent = out;
        const cand = out.candidates[0];
        $("#intent-out").innerHTML = `
          <table class="findings">
            <tr><td>Detected object class</td><td class="msg">${esc(cand.object_class)}</td></tr>
            <tr><td>Candidate archetype</td><td class="msg">${esc(cand.archetype_id)}
              <span class="badge ${cand.status}">${cand.status}</span></td></tr>
            <tr><td>Confidence</td><td class="msg">${esc(out.confidence)}</td></tr>
            <tr><td>Source</td><td class="msg">${esc(out.source)}</td></tr>
            <tr><td>Mode</td><td class="msg">strict buildable</td></tr>
          </table>
          <div class="row mt">
            ${out.candidates.map((c, i) =>
              `<button class="${i === 0 ? "forge" : "ghost"}" data-pick="${esc(c.archetype_id)}">use ${esc(c.archetype_id)}</button>`
            ).join("")}
          </div>`;
        screenEl.querySelectorAll("[data-pick]").forEach((b) =>
          b.addEventListener("click", () => withBusy(b, "loading contract…",
            async () => {
            wiz.archetype = state.catalog.archetypes.find((a) => a.id === b.dataset.pick);
            for (const [k, v] of Object.entries(out.params || {}))
              if (wiz.archetype.parameters.some((p) => p.name === k)) wiz.params[k] = v;
            wiz.stage = 2; await render();
          })));
      }));
      return;
    }

    const a = wiz.archetype;
    if (wiz.stage === 2) {
      const c = a.contract;
      screenEl.innerHTML = `<div class="wizard">${stagesBar()}
        <div class="panel"><h3>PRODUCT CONTRACT — ${esc(a.id)}</h3>
          <ul class="contract">
            ${c.must_have.map((f) => `<li class="must">${esc(f)}</li>`).join("")}
            ${c.must_not_have.map((f) => `<li class="mustnot">${esc(f)}</li>`).join("")}
            ${c.forbidden_forms.map((f) => `<li class="mustnot">${esc(f)} (forbidden form)</li>`).join("")}
          </ul>
          <div class="mt dim">Invariants: ${c.invariants.map(esc).join(" · ") || "—"}</div>
          <div class="row mt"><button class="forge" id="next">Accept contract →</button></div>
        </div></div>`;
      $("#next").addEventListener("click", () => withBusy(
        $("#next"), "checking capability…",
        async () => { wiz.stage = 3; await render(); }));
      return;
    }

    if (wiz.stage === 3) {
      const v = await revalidate();
      const cap = v.capability || { requested_features: [], supported_features: [], unsupported_features: [] };
      screenEl.innerHTML = `<div class="wizard">${stagesBar()}
        <div class="panel"><h3>CAPABILITY — honesty before geometry</h3>
          ${a.provides_features.map((f) =>
            `<div class="cap-row"><span class="ok">✓</span><span>${esc(f)}</span><span class="faint">supported</span></div>`).join("")}
          ${cap.unsupported_features.map((f) =>
            `<div class="cap-row"><span class="miss">✗</span><span>${esc(f)}</span><span class="miss">missing — not buildable in strict mode</span></div>`).join("")}
          <div class="row mt">
            <button class="forge" id="next" ${cap.unsupported_features.length ? "disabled" : ""}>Parameters →</button>
            ${cap.unsupported_features.length ? '<span class="badge fail">blocked by missing capability</span>' : ""}
          </div>
        </div></div>`;
      $("#next")?.addEventListener("click", () => withBusy(
        $("#next"), "loading parameters…",
        async () => { wiz.stage = 4; await render(); }));
      return;
    }

    if (wiz.stage === 4) {
      const v = wiz.validation || (await revalidate());
      screenEl.innerHTML = `<div class="wizard">${stagesBar()}
        <div class="panel"><h3>PARAMETERS — live validated (no CAD)</h3>
          <div id="pgroups">${paramGroups(v.params, wiz.params)}</div>
          <div class="row mt"><button class="forge" id="next">Validate form →</button>
            <span id="pstatus" class="badge ${v.status}">${v.status}</span></div>
          <div id="pfindings">${v.status === "fail"
            ? findingsTable((v.findings || []).filter((f) => f.status !== "pass")) : ""}</div>
        </div></div>`;
      let timer = null;
      const bind = () => {
        screenEl.querySelectorAll("[data-param]").forEach((inp) =>
          inp.addEventListener("input", () => {
            wiz.params[inp.dataset.param] = inp.value;
            clearTimeout(timer);
            timer = setTimeout(async () => {
              const nv = await revalidate();
              $("#pstatus").className = `badge ${nv.status}`;
              $("#pstatus").textContent = nv.status;
              $("#pgroups").innerHTML = paramGroups(nv.params, wiz.params);
              $("#pfindings").innerHTML = nv.status === "fail"
                ? findingsTable((nv.findings || []).filter((f) => f.status !== "pass")) : "";
              bind();
            }, 350);
          }));
        screenEl.querySelectorAll("[data-svg-for]").forEach((btn) =>
          btn.addEventListener("click", () =>
            screenEl.querySelector(`[data-svg-file="${btn.dataset.svgFor}"]`).click()));
        screenEl.querySelectorAll("[data-svg-file]").forEach((file) =>
          file.addEventListener("change", async () => {
            const name = file.dataset.svgFile;
            const btn = screenEl.querySelector(`[data-svg-for="${name}"]`);
            const f = file.files[0];
            if (!f) return;
            btn.textContent = "⋯ importing";
            try {
              // layered color art is flattened server-side (luminance
              // painter model); single-layer files pass through exactly
              const motifW = parseFloat(
                screenEl.querySelector('[data-param="motif_w"]')?.value
                || screenEl.querySelector('[data-param="motif_w"]')?.placeholder
                || "60") || 60;
              const res = await api.svgFlatten(await f.text(), motifW);
              if (!res.ok) {
                const msg = res.findings?.[0]?.message || "svg import failed";
                svgImportNotes.set(name, { label: `✗ ${msg}`, title: msg });
                btn.textContent = `✗ ${msg}`;
                return;
              }
              svgImportNotes.set(name, {
                label: res.flattened
                  ? `✓ ${f.name} — ${res.info.layers} layers → union`
                  : `✓ ${f.name}`,
                title: `${res.outlines} outlines, ${res.holes} holes, `
                  + `min feature ${res.min_width_mm}mm at ${motifW}mm`,
              });
              const inp = screenEl.querySelector(`[data-param="${name}"]`);
              inp.value = res.path;
              inp.dispatchEvent(new Event("input"));
              btn.textContent = svgImportNotes.get(name).label;
              btn.title = svgImportNotes.get(name).title;
            } catch (e) {
              svgImportNotes.set(name, { label: `✗ ${e.message}`, title: e.message });
              btn.textContent = `✗ ${e.message}`;
            }
          }));
      };
      bind();
      $("#next").addEventListener("click", () => withBusy(
        $("#next"), "validating form…",
        async () => { wiz.stage = 5; await render(); }));
      return;
    }

    // stage 5
    const v = await revalidate();
    screenEl.innerHTML = `<div class="wizard">${stagesBar()}
      <div class="panel"><h3>FORM IR — validated before any CAD</h3>
        <div style="height:320px;position:relative" id="sec"></div>
        <table class="findings">${Object.entries(v.form_checks || {}).map(([k, val]) =>
          `<tr><td>${esc(k)}</td><td class="msg">${esc(JSON.stringify(val))}</td></tr>`).join("")}
        </table>
        ${findingsTable((v.findings || []).filter((f) => f.status !== "pass"))}
        <div class="row mt">
          <button class="forge" id="forge" ${state.status.cad ? "" : "disabled"}>⚒ Forge (build STL)</button>
          <span class="badge ${v.status}">${v.status}</span>
          ${state.status.cad ? "" : '<span class="badge off">CAD OFF</span>'}
        </div>
        <div id="buildlog" class="mt"></div>
      </div></div>`;
    renderSection($("#sec"), v.form);
    $("#forge").addEventListener("click", () => withBusy(
        $("#forge"), "forging (CAD build)…", async () => {
      $("#buildlog").innerHTML = `<span class="dim">forging…</span>`;
      const { job } = await api.build(wizYaml());
      const done = await api.waitJob(job, (j) => {
        $("#buildlog").innerHTML = `<div class="yaml-pane">${esc(j.log.join("\n"))}</div>`;
      });
      if (done.status === "done") {
        state.buildReport = done.result;
        await openInWorkspace(wizYaml(), done.result);
      } else {
        $("#buildlog").innerHTML = findingsTable([done.error]);
      }
    }));
  };
  render();
}

// last .svg import result per param name — survives the pgroups
// re-render that follows every revalidate
const svgImportNotes = new Map();

function paramGroups(params, current) {
  const roles = ["functional", "assembly", "structural", "manufacturing", "aesthetic", "style"];
  const groups = {};
  for (const p of params || []) (groups[p.role] ||= []).push(p);
  return roles.filter((r) => groups[r]).map((r) => `
    <div class="pgroup"><h4 class="${r}">${r}</h4>
      ${groups[r].map((p) => {
        const val = current[p.name] ?? (p.type === "choice" ? p.value : p.value);
        const input = p.type === "choice"
          ? `<select data-param="${p.name}" ${p.locked ? "disabled" : ""}>${p.choices.map((c) =>
              `<option ${c === val ? "selected" : ""}>${c}</option>`).join("")}</select>`
          : `<input data-param="${p.name}" value="${esc(current[p.name] ?? "")}"
               placeholder="${p.value ?? ""}" ${p.locked ? "disabled" : ""}>`;
        const note = svgImportNotes.get(p.name);
        const filePick = p.format === "svg_path_data" && !p.locked
          ? `<button class="ghost svg-pick" data-svg-for="${p.name}" type="button"
               title="${esc(note?.title || "load path data from an .svg file")}">${esc(note?.label || "📂 .svg")}</button>
             <input type="file" data-svg-file="${p.name}" accept=".svg,image/svg+xml" hidden>`
          : "";
        const range = p.min != null || p.max != null
          ? `${p.min ?? "—"} … ${p.max ?? "—"}` : "";
        return `<div class="prow ${p.locked ? "locked" : ""}">
          <span class="pname" title="${esc(p.description)}">${p.name}${p.exposed ? " ●" : ""}</span>
          ${input}<span class="range">${filePick || range}</span>
          <span class="faint">${p.type}</span></div>`;
      }).join("")}
    </div>`).join("");
}

function findingsTable(findings) {
  if (!findings || !findings.length) return `<div class="dim mt">no findings — clean</div>`;
  return `<table class="findings mt">${findings.map((f) => `
    <tr class="f-${f.status}" data-finding="${esc(f.check)}">
      <td>${f.status.toUpperCase()}</td><td>${esc(f.check)}</td>
      <td class="msg">${esc(f.message)}</td>
      <td class="faint">${f.suggestion ? "→ " + esc(f.suggestion) : ""}</td></tr>`).join("")}
  </table>`;
}

// ------------------------------------------------------- YAML entry point
function renderYamlEntry() {
  screenEl.innerHTML = `<div class="wizard">
    <div class="panel"><h3>PASTE PRODUCT / ASSEMBLY YAML</h3>
      <textarea id="yamlin" rows="18" spellcheck="false"></textarea>
      <div class="row mt"><button class="forge" id="openws">Validate & open workspace</button></div>
    </div></div>`;
  $("#openws").addEventListener("click", () => withBusy(
    $("#openws"), "validating…", () => openInWorkspace($("#yamlin").value)));
}

// ------------------------------------------------------------- workspace
async function openInWorkspace(yamlText, buildReport = null) {
  state.yaml = yamlText;
  state.buildReport = buildReport;
  state.validation = await api.validate(yamlText, false);
  setNav("workspace");
  renderWorkspace();
}

// ------------------------------------------------------------------ library
// The durable device library: every build is an immutable revision with
// provenance. Three INDEPENDENT status axes per entry — saved artifacts,
// rebuild inputs (used deps only), CAD environment. Reopen is byte-exact
// (served from the archived bundle); Rebuild regenerates and archives a
// new revision.

function libChip(cls, label, title = "") {
  return `<span class="badge ${cls}" title="${esc(title)}">${esc(label)}</span>`;
}

function libAxisChips(e) {
  const chips = [];
  const a = e.artifacts?.state;
  if (a === "intact") chips.push(libChip("on", "saved: intact"));
  else if (a === "none") chips.push(libChip("warn", "source only"));
  else chips.push(libChip("off", "saved: damaged",
    (e.artifacts?.bad || []).join(", ")));
  const d = e.drift || {};
  if (d.missing_archetypes?.length)
    chips.push(libChip("off", `rebuild: archetype gone (${d.missing_archetypes.join(", ")})`));
  else if (d.inputs_changed)
    chips.push(libChip("warn",
      `rebuild inputs changed: ${[...(d.changed_archetypes || []), ...(d.changed_modifiers || [])].join(", ")}`));
  else chips.push(libChip("on", "rebuild inputs unchanged",
    d.unrelated_catalog_changes ? "catalog contains unrelated changes" : ""));
  const env = Object.keys(d.cad_env_changed || {});
  chips.push(env.length
    ? libChip("warn", `CAD env changed: ${env.join(", ")}`,
        env.map((k) => `${k}: ${d.cad_env_changed[k].was} → ${d.cad_env_changed[k].now}`).join("; "))
    : libChip("on", "CAD env unchanged"));
  return chips.join(" ");
}

async function renderLibrary() {
  screenEl.innerHTML = `<div class="home"><div class="panel">loading library…</div></div>`;
  let data;
  try { data = await api.library(50); } catch (e) {
    screenEl.innerHTML = `<div class="home"><div class="panel">library unavailable: ${esc(e.message)}</div></div>`;
    return;
  }
  const entries = data.entries || [];
  if (!entries.length) {
    screenEl.innerHTML = `<div class="home"><div class="panel">
      <h3>LIBRARY</h3>
      <p class="dim">No archived builds yet — every <b>Forge</b> (CLI or cockpit)
      lands here as an immutable revision: source, geometry, provenance.</p></div></div>`;
    return;
  }
  screenEl.innerHTML = `<div class="home"><div class="panel">
    <h3>LIBRARY <span class="dim">${entries.length} device(s) — reopen is byte-exact from the archived bundle; rebuild regenerates (drift-checked)</span></h3>
    <table class="findings">${entries.map((e) => `
      <tr class="lib-row" data-dev="${esc(e.id)}" data-bid="${esc(e.build_id)}" style="cursor:pointer">
        <td><span class="badge ${e.grade === "A" ? "on" : e.grade ? "warn" : "off"}">${esc(e.grade || e.status || "?")}</span></td>
        <td>${esc(e.kind)}</td>
        <td class="msg"><b>${esc(e.id)}</b></td>
        <td class="faint">${e.parts ? esc(e.parts + " part(s)") : ""}</td>
        <td class="faint">${esc(String(e.builds || 1))} build(s)</td>
        <td class="faint">${esc((e.ts || "").replace("T", " ").replace("+00:00", ""))}</td>
        <td>${libAxisChips(e)}</td></tr>`).join("")}
    </table></div></div>`;
  screenEl.querySelectorAll(".lib-row").forEach((row) =>
    row.addEventListener("click", () =>
      renderLibraryEntry(row.dataset.dev, row.dataset.bid)));
}

function librarySyntheticReport(manifest, deviceId, buildId) {
  // export URLs point at the CONTROLLED artifact route (allowlisted,
  // containment-checked) — the library is deliberately not a static mount
  const base = `/api/library/${deviceId}/${buildId}/artifact/`;
  const ex = manifest.exports || {};
  if (manifest.kind !== "assembly")
    return ex.stl ? { exports: { stl: base + ex.stl.path } } : null;
  const parts = {};
  for (const [ref, rows] of Object.entries(ex.parts || {}))
    if (rows.stl) parts[ref] = { exports: { stl: base + rows.stl.path } };
  return Object.keys(parts).length ? { parts } : null;
}

async function renderLibraryEntry(deviceId, buildId) {
  screenEl.innerHTML = `<div class="home"><div class="panel">verifying ${esc(deviceId)}…</div></div>`;
  let r, dev;
  try {
    [r, dev] = await Promise.all([
      api.libraryBuild(deviceId, buildId), api.libraryDevice(deviceId)]);
  } catch (e) {
    screenEl.innerHTML = `<div class="home"><div class="panel">entry unavailable: ${esc(e.message)}</div></div>`;
    return;
  }
  if (!r.ok) { renderLibrary(); return; }
  const m = r.manifest;
  const integ = r.integrity || {};
  const sourceOnly = m.artifact_state === "source_only";
  const canOpenSaved = integ.state === "intact" && !sourceOnly;
  const tool = m.tool || {};
  const drift = r.drift || {};
  screenEl.innerHTML = `<div class="home"><div class="panel">
    <h3>${esc(deviceId)} <span class="dim">${esc(m.kind)} · ${esc(buildId)}</span></h3>
    <div class="row">${libAxisChips({ artifacts: integ, drift })}
      ${integ.state === "damaged" ? `<span class="dim">damaged: ${esc((integ.bad || []).join(", "))}</span>` : ""}</div>
    ${drift.unrelated_catalog_changes ? `<p class="dim">catalog contains unrelated changes (this device's inputs are unchanged)</p>` : ""}
    ${Object.keys(drift.af_changed || {}).length ? `<p class="dim">AF code changed since this build: ${esc(Object.keys(drift.af_changed).join(", "))}</p>` : ""}
    <table class="findings">
      <tr><td>built</td><td class="msg">${esc(m.ts || "")}</td></tr>
      <tr><td>grade</td><td class="msg">${esc(m.grade || m.status || "?")}</td></tr>
      <tr><td>archetypes</td><td class="msg">${esc(Object.entries(m.dependencies?.archetypes || {}).map(([k, v]) => `${k}@${v.version}`).join(", "))}</td></tr>
      <tr><td>tool</td><td class="msg">af ${esc(tool.af_version || "?")}${tool.af_commit ? ` (${esc(tool.af_commit)})` : ""} · cadquery ${esc(tool.cadquery || "?")} · ocp ${esc(tool.cadquery_ocp || "?")} · py ${esc(tool.python || "?")}</td></tr>
      <tr><td>source digest</td><td class="msg faint">${esc((m.source_digest || "").slice(0, 16))}… (bytes ${esc((m.source_bytes_digest || "").slice(0, 16))}…)</td></tr>
    </table>
    <div class="row mt">
      ${canOpenSaved
        ? `<button class="forge" id="lib-open">Open saved (byte-exact)</button>`
        : `<button class="forge" id="lib-open-src">Open source</button>`}
      ${canOpenSaved ? `<button class="ghost" id="lib-open-src">Open source</button>` : ""}
      <button class="ghost" id="lib-rebuild" ${state.status?.cad ? "" : "disabled"}>⚒ Rebuild (new revision)</button>
      <button class="ghost" id="lib-back">← Library</button>
    </div>
    <div id="lib-log" class="mt"></div>
    <h3 class="mt">BUILDS</h3>
    <table class="findings">${(dev.revisions || []).map((rev) => `
      <tr class="lib-rev" data-bid="${esc(rev.build_id)}" style="cursor:pointer">
        <td>${rev.build_id === buildId ? "▶" : ""}</td>
        <td class="faint">${esc((rev.ts || "").replace("T", " ").replace("+00:00", ""))}</td>
        <td><span class="badge ${rev.grade === "A" ? "on" : "warn"}">${esc(rev.grade || rev.status || "?")}</span></td>
        <td class="msg faint">${esc(rev.build_id)}</td>
        <td class="faint">${esc(rev.artifact_state || "")}</td></tr>`).join("")}
    </table></div></div>`;
  const openSaved = screenEl.querySelector("#lib-open");
  if (openSaved) openSaved.addEventListener("click", () => withBusy(
    openSaved, "opening saved geometry…", () => openInWorkspace(
      r.source, librarySyntheticReport(m, deviceId, buildId))));
  const openSrc = screenEl.querySelector("#lib-open-src");
  if (openSrc) openSrc.addEventListener("click", () => withBusy(
    openSrc, "validating source…", () => openInWorkspace(r.source)));
  screenEl.querySelector("#lib-back").addEventListener("click", renderLibrary);
  const rebuildBtn = screenEl.querySelector("#lib-rebuild");
  rebuildBtn.addEventListener("click", () => withBusy(
      rebuildBtn, "rebuilding (CAD)…", async () => {
    const log = screenEl.querySelector("#lib-log");
    log.innerHTML = `<span class="dim">rebuilding…</span>`;
    try {
      const { job } = await api.build(r.source);
      const done = await api.waitJob(job, (j) => {
        log.innerHTML = `<div class="yaml-pane">${esc((j.log || []).join("\n"))}</div>`;
      });
      if (done.status === "done") {
        state.buildReport = done.result;
        await openInWorkspace(r.source, done.result);
      } else {
        log.innerHTML = findingsTable([done.error]);
      }
    } catch (e) { log.innerHTML = `<span class="dim">${esc(e.message)}</span>`; }
  }));
}

function renderWorkspace() {
  const v = state.validation;
  if (!v) { screenEl.innerHTML = `<div class="home"><div class="panel">Open an example from the Catalog, or create one in the Wizard.</div></div>`; return; }
  const isAssembly = !!v.assembly_pose;
  screenEl.innerHTML = `<div class="ws">
    <div class="ws-tree tree" id="tree"></div>
    <div class="ws-view">
      <div class="lenses" id="lenses">
        ${["3d", "section", "honesty", "manufacturing"].map((l) =>
          `<button data-lens="${l}" class="${state.lens === l ? "active" : ""}">${l.toUpperCase()}</button>`).join("")}
        <button data-lens="edit" class="${state.lens === "edit" ? "active" : ""}">REGION / EDIT</button>
        <button id="dl-stl" style="display:none" title="download the STL artifact shown in the viewport">⭳ STL</button>
      </div>
      <div id="viewport3d"></div>
      <div id="insp-card" style="display:none"></div>
      <div id="viewport-section" style="display:none"></div>
      <div id="viewport-panel" style="display:none"></div>
    </div>
    <div class="ws-console" id="console"></div>
  </div>`;
  buildTree(v, isAssembly);
  buildConsole(v, isAssembly);
  const view = new ThreeView($("#viewport3d"));
  state.three = view;
  view.enableRegionPicking((r) => inspect({ kind: "region", region: r }, v));
  load3D(view, v, isAssembly);
  $("#lenses").querySelectorAll("button[data-lens]").forEach((b) =>
    b.addEventListener("click", () => setLens(b.dataset.lens, v, isAssembly)));
  setLens(state.lens, v, isAssembly);
}

function artifactUrl(path) {
  // library bundle artifacts arrive as ready /api/ URLs — pass through
  if (String(path).startsWith("/api/")) return String(path);
  // exports paths may be absolute — everything under out/ is served as /artifacts/
  const tail = String(path).split(/\/out\//).pop().replace(/^out\//, "");
  return "/artifacts/" + tail;
}

async function load3D(view, v, isAssembly) {
  view.clear();
  const report = state.buildReport;
  const docId = v.product || v.assembly || "part";
  // download offers exactly what the viewport shows — collected per
  // successful load, so the button can never hand out a 404
  state.stlFiles = [];
  const show = async (url, file, pose = null, tint = undefined) => {
    await view.loadSTL(url, pose, tint);
    state.stlFiles.push({ url, file });
  };
  try {
    if (isAssembly && report?.parts) {
      const poses = {};
      // a library synthetic report has no poses — validate re-derives them
      for (const p of report.assembly_pose || v.assembly_pose || []) poses[p.part] = p;
      for (const [ref, part] of Object.entries(report.parts)) {
        const stl = part.exports?.stl;
        if (!stl) continue;
        const pose = poses[ref]?.rotate ? poses[ref] : null;
        await show(artifactUrl(stl), `${docId}__${ref}.stl`, pose);
      }
    } else if (report?.exports?.stl) {
      await show(artifactUrl(report.exports.stl), `${docId}.stl`);
    } else if (!isAssembly && v.product) {
      // try prebuilt artifact from out/
      await show(`/artifacts/${v.product}/part.stl`, `${docId}.stl`);
    } else if (isAssembly && v.assembly) {
      // prebuilt assembly artifacts, placed by the REPORTED poses
      const poses = {};
      for (const p of v.assembly_pose || []) poses[p.part] = p;
      const tints = [0xb9c2cf, 0x8fb8c9, 0xc9b98f, 0xa9c98f];
      let i = 0;
      for (const ref of Object.keys(v.parts || {})) {
        const pose = poses[ref]?.rotate ? poses[ref] : null;
        await show(`/artifacts/${v.assembly}/${ref}/part.stl`,
          `${docId}__${ref}.stl`, pose, tints[i++ % 4]);
      }
    }
  } catch (e) {
    $("#console").insertAdjacentHTML("afterbegin",
      `<div class="dim">no STL artifact yet — Build to see 3D (section/region lenses work without CAD)</div>`);
  }
  wireStlDownload();
  view.showRegions(v.form?.regions, state.lens === "edit");
  if (state.lens === "edit") view.highlightRegion(state.selectedRegion);
  view.fit();
}

function wireStlDownload() {
  const btn = $("#dl-stl");
  if (!btn) return;
  const files = state.stlFiles;
  btn.style.display = files.length ? "" : "none";
  btn.textContent = files.length > 1 ? `⭳ STL ×${files.length}` : "⭳ STL";
  btn.onclick = () => {
    for (const f of files) {
      const a = document.createElement("a");
      a.href = f.url;
      a.download = f.file;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
  };
}

function setLens(lens, v, isAssembly) {
  if (lens === "region") lens = "edit"; // merged: REGION lives inside EDIT
  state.lens = lens;
  $("#lenses").querySelectorAll("button[data-lens]").forEach((b) =>
    b.classList.toggle("active", b.dataset.lens === lens));
  const v3 = $("#viewport3d"), vs = $("#viewport-section"), vp = $("#viewport-panel");
  const rc = $("#insp-card");
  if (rc) rc.style.display = "none"; // stale card never outlives a lens switch
  // EDIT is a split lens: the edit panel on the left, the REAL region
  // viewport (same ThreeView, same STL, same picking) on the right.
  const split = lens === "edit";
  v3.parentElement.classList.toggle("split", split);
  v3.style.display = lens === "3d" || split ? "block" : "none";
  vs.style.display = lens === "section" ? "flex" : "none";
  vp.style.display = ["honesty", "manufacturing", "edit"].includes(lens) ? "block" : "none";
  if (state.three) state.three.showRegions(v.form?.regions, split);
  if (lens !== "edit") editSetTarget = null;
  if (lens === "section") renderSection(vs, v.form);
  if (lens === "honesty") vp.innerHTML = honestyPanel(v, isAssembly);
  if (lens === "manufacturing") vp.innerHTML = manufacturingPanel(v);
  if (lens === "edit") { vp.innerHTML = editPanel(); wireEdit(v); }
}

function honestyPanel(v, isAssembly) {
  if (isAssembly) {
    return `<h3 class="dim">ASSEMBLY HONESTY</h3>${findingsTable(v.joints || [])}`;
  }
  const cap = v.capability || {};
  const hr = state.buildReport?.honesty_report;
  const built = new Set(hr?.built_features || []);
  const rows = (cap.requested_features || []).map((f) => {
    const sup = (cap.supported_features || []).includes(f);
    const b = built.has(f);
    return `<div class="honesty-row"><span>${esc(f)}</span>
      <span class="h-yes">requested</span>
      <span class="${sup ? "h-yes" : "h-no"}">${sup ? "supported" : "unsupported"}</span>
      <span class="${b ? "h-yes" : hr ? "h-no" : "h-na"}">${b ? "built" : hr ? "NOT built" : "no build yet"}</span>
      <span class="${b ? "h-yes" : "h-na"}">${b ? "verified" : "—"}</span>
      <span class="faint">${!sup ? "missing capability" : ""}</span></div>`;
  }).join("");
  return `<h3 class="dim">HONESTY — requested / supported / built / verified</h3>
    ${rows || '<div class="dim">no requested features declared</div>'}
    ${hr ? `<div class="mt dim">grade ${esc(state.buildReport?.score?.grade)} · engine gaps: ${esc((hr.engine_gaps || []).join(", ") || "none")}</div>`
         : '<div class="mt dim">build to verify features (form-level truth shown in findings)</div>'}`;
}

function manufacturingPanel(v) {
  const f = v.form || {};
  const mfg = (v.findings || []).filter((x) => x.level === "manufacturing");
  return `<h3 class="dim">MANUFACTURING</h3>
    <table class="findings">
      <tr><td>print_orientation</td><td class="msg">${esc(f.print_orientation)}</td></tr>
      <tr><td>kind</td><td class="msg">${esc(f.kind)}</td></tr>
      <tr><td>width / extrusion</td><td class="msg">${esc(f.width)} mm</td></tr>
    </table>
    ${findingsTable(mfg)}
    <div class="mt faint">per-face overhang shading — v2 (findings above are the measured truth)</div>`;
}

function editPanel() {
  return `<h3 class="dim">SEMANTIC EDIT — patch preview before anything is built · click a region in the viewport to set the target</h3>
    <div class="row" id="targetrow" style="display:none">
      <span class="dim">Target region:</span>
      <select id="target"><option value="">— auto —</option></select>
      <span id="targetmeta" class="faint"></span>
    </div>
    <div class="row mt"><input id="nl" type="text" placeholder="make it support-free / make it stronger…" style="flex:1">
    <button class="forge" id="nlgo">Propose patch</button></div>
    <div class="row mt dim">intents:
      ${["make_support_free", "make_stronger", "make_biomorphic", "remove_perforation"].map((i) =>
        `<button class="ghost" data-intent="${i}">${i}</button>`).join("")}</div>
    <div id="editout" class="mt"></div>`;
}

async function wireEdit(v) {
  const out = $("#editout");
  // an apply that just succeeded re-rendered the whole workspace — show
  // its report instead of an empty panel
  if (state.lastEditReport) {
    out.innerHTML = state.lastEditReport;
    state.lastEditReport = null;
  }

  // -- grounded region targeting: picker + mini region viewport ----------
  if (!state.catalog) state.catalog = await api.catalog();
  const archId = String(v.archetype || "").split("@")[0];
  const card = state.catalog.archetypes.find((a) => a.id === archId);
  const regions = card?.regions || [];
  const targetable = regions.filter((r) => r.editable && r.compatible_modifiers.length);
  const sel = $("#target");
  const setTarget = (id) => {
    state.selectedRegion = id || null;
    if (sel) sel.value = id || "";
    const r = regions.find((x) => x.id === id);
    $("#targetmeta").textContent = r
      ? `${r.label ? r.label + " · " : ""}role: ${r.role} · modifiers: ${r.compatible_modifiers.join(", ")}`
      : "backend auto-targets when unambiguous";
    state.three?.highlightRegion(id || null);
  };
  if (targetable.length) {
    $("#targetrow").style.display = "flex";
    // protected regions are LISTED (disabled) — an entry the user can see
    // beats a mysteriously short dropdown
    const shielded = regions.filter((r) => !targetable.includes(r));
    sel.innerHTML = `<option value="">— auto —</option>` + targetable.map((r) =>
      `<option value="${esc(r.id)}">${esc(r.label || r.id)} (${esc(r.id)})</option>`).join("")
      + (shielded.length
        ? `<optgroup label="protected — not editable">` + shielded.map((r) =>
            `<option disabled>${esc(r.label || r.id)}</option>`).join("") + `</optgroup>`
        : "");
    const keep = targetable.some((r) => r.id === state.selectedRegion)
      ? state.selectedRegion
      : targetable.length === 1 ? targetable[0].id : null;
    sel.addEventListener("change", () => setTarget(sel.value));
    // region picks land here from the REAL viewport (workspace ThreeView)
    editSetTarget = (name) => {
      if (!targetable.some((t) => t.id === name)) {
        $("#targetmeta").textContent = `${name}: protected — not a valid edit target`;
        return;
      }
      setTarget(name);
    };
    setTarget(keep);
  }

  const preview = async (intent, patch, note = "") => {
    out.innerHTML = `<span class="dim">computing patch…</span>`;
    let p;
    try {
      p = await api.editPreview(state.yaml, intent, patch);
    } catch (e) {
      // a transport/server error must never leave "computing patch…" up
      out.innerHTML = findingsTable([{ status: "fail", check: "edit.preview", message: String(e) }]);
      return;
    }
    if (!p.ok) {
      out.innerHTML = findingsTable(p.findings);
      // did-you-mean: the pipeline proposes the fix, the user confirms
      if (p.did_you_mean?.length) {
        out.insertAdjacentHTML("beforeend", `<div class="row mt">${p.did_you_mean.map((d, i) =>
          `<button class="forge" data-dym="${i}">Fix target → ${esc(d.suggestion)}${d.label ? ` (${esc(d.label)})` : ""}</button>`).join("")}</div>`);
        out.querySelectorAll("[data-dym]").forEach((b) =>
          b.addEventListener("click", () => {
            const d = p.did_you_mean[+b.dataset.dym];
            const fixed = JSON.parse(JSON.stringify(patch || {}));
            for (const key of ["add", "update"])
              for (const m of fixed.modifiers?.[key] || [])
                if (m.target === d.given) m.target = d.suggestion;
            preview(intent, fixed, `target fixed: ${d.given} → ${d.suggestion}`);
          }));
      }
      return;
    }
    const val = p.validation;
    const noteHtml = note ? `<div class="dim mt">${esc(note)}</div>` : "";
    const noopHtml = p.noop
      ? `<div class="mt"><span class="badge warn">NO-OP</span> this patch changes nothing — the instance already satisfies it</div>`
      : "";
    const cb = (p.ir_diff?.field_cells_before || []).reduce((a, b) => a + b, 0);
    const ca = (p.ir_diff?.field_cells_after || []).reduce((a, b) => a + b, 0);
    const cellsNote = (cb || ca) && cb !== ca
      ? `<div class="mt ${ca < cb ? "" : "dim"}">field cells: ${cb} → ${ca}${ca < cb ? ' <span class="badge warn">fewer cells — likely the OPPOSITE of the intent</span>' : ""}</div>`
      : "";
    // a patch whose RESULT fails validation must not be appliable — the
    // build would only fail later with the same findings
    const blocked = val.status === "fail";
    out.innerHTML = `
      ${noteHtml}
      ${noopHtml}
      <div class="yaml-pane">${esc(jsyaml(p.patch))}</div>
      ${cellsNote}
      <div class="mt">edited product validates: <span class="badge ${val.status}">${val.status}</span></div>
      ${findingsTable((val.findings || []).filter((f) => f.status !== "pass"))}
      ${blocked ? `<div class="mt dim">fix the request (see suggestions above) and propose again — applying would fail the build with these findings</div>` : ""}
      <div class="row mt">
        <button class="forge" id="apply" ${p.noop || blocked ? "disabled" : ""}>Apply patch (rebuild + verify preserve)</button>
        <button class="ghost" id="cancel">Cancel</button></div>`;
    $("#cancel").addEventListener("click", () => (out.innerHTML = ""));
    $("#apply").addEventListener("click", () => withBusy(
        $("#apply"), "rebuilding + verifying…", async () => {
      out.innerHTML = `<span class="dim">rebuilding + verifying preserve…</span>`;
      const { job } = await api.editApply(state.yaml, intent, patch);
      const done = await api.waitJob(job);
      const rep = done.result?.edit_report;
      if (!rep) { out.innerHTML = findingsTable([done.error]); return; }
      const repHtml = `
        <table class="findings">
          <tr><td>status</td><td class="msg"><span class="badge ${rep.status}">${rep.status}</span></td></tr>
          <tr><td>preserved (verified)</td><td class="msg">${rep.preserved.map((x) => esc(x.name)).join(", ")}</td></tr>
          <tr><td>changed</td><td class="msg">${esc(JSON.stringify(rep.changed))}</td></tr>
          <tr><td>supports before → after</td><td class="msg">${rep.printability.supports_recommended_before} → ${rep.printability.supports_recommended_after}</td></tr>
          <tr><td>overhang after</td><td class="msg">${esc(rep.printability.overhang_after.message)}</td></tr>
        </table>`;
      if (rep.status === "pass") {
        // the edit landed: the workspace must show the NEW truth, not
        // leave the old part on screen behind a "success" table
        state.lastEditReport = repHtml +
          `<div class="dim mt">workspace switched to the edited product</div>`;
        const txt = await (await fetch(artifactUrl(rep.edited_yaml))).text();
        await openInWorkspace(txt, { exports: { stl: rep.stl } });
        return;
      }
      out.innerHTML = repHtml +
        `<div class="row mt"><button class="ghost" id="openedited">open edited product in workspace</button></div>`;
      $("#openedited").addEventListener("click", () => withBusy(
        $("#openedited"), "opening…", async () => {
        const txt = await (await fetch(artifactUrl(rep.edited_yaml))).text();
        await openInWorkspace(txt);
      }));
    }));
  };
  $("#nlgo").addEventListener("click", () => withBusy(
      $("#nlgo"), "translating (LLM)…", async () => {
    if (!$("#nl").value.trim()) {
      $("#nl").focus();
      out.innerHTML = `<div class="dim">describe the change first (e.g. "add voronoi pattern", "make it support-free") — or use an intent button below</div>`;
      return;
    }
    out.innerHTML = `<span class="dim">translating…</span>`;
    try {
      const r = await api.nlEdit(state.yaml, $("#nl").value, state.selectedRegion);
      if (!r.ok) { out.innerHTML = findingsTable(r.findings); return; }
      if (r.intent) preview(r.intent, null, r.notes); else preview(null, r.patch, r.notes);
    } catch (e) {
      out.innerHTML = findingsTable([{ status: "fail", check: "edit.nl", message: String(e) }]);
    }
  }));
  document.querySelectorAll("[data-intent]").forEach((b) =>
    b.addEventListener("click", () => preview(b.dataset.intent, null)));
}

function buildTree(v, isAssembly) {
  const tree = $("#tree");
  if (isAssembly) {
    tree.innerHTML = `<ul>
      <li><span class="grp">assembly</span></li>
      <li><span>root: ${esc(v.root)}</span></li>
      <li><span class="grp">parts</span></li>
      ${Object.keys(v.parts || {}).map((r) => `<li><span>▸ ${esc(r)}</span></li>`).join("")}
      <li><span class="grp">poses</span></li>
      ${(v.assembly_pose || []).map((p) =>
        `<li><span>${esc(p.part)}: ${p.transform || `rot ${p.rotate} @ ${p.translate}`}</span></li>`).join("")}
    </ul>`;
    return;
  }
  const f = v.form || {};
  const li = (label, data) =>
    `<li><span data-insp='${esc(JSON.stringify(data))}'>${esc(label)}</span></li>`;
  tree.innerHTML = `<ul>
    <li><span class="grp">contract</span></li>
    ${(v.contract?.must_have || []).map((m) => li("✓ " + m, { kind: "feature", name: m })).join("")}
    ${(v.contract?.must_not_have || []).map((m) => li("✗ " + m, { kind: "forbidden", name: m })).join("")}
    <li><span class="grp">archetype</span></li>
    ${li(v.archetype, { kind: "archetype", name: v.archetype })}
    <li><span class="grp">form ir</span></li>
    ${li("section: " + (f.section?.name || "—"), { kind: "section" })}
    ${(f.regions || []).map((r) => li("region: " + r.name, { kind: "region", region: r })).join("")}
    ${(f.holes || []).length ? li(`holes ×${f.holes.length}`, { kind: "holes" }) : ""}
    ${(f.pins || []).length ? li(`pins ×${f.pins.length}`, { kind: "pins" }) : ""}
    ${(f.fields || []).map((fd) => li(`field: ${fd.pattern} ×${fd.cells}`, { kind: "field", field: fd })).join("")}
    <li><span class="grp">parameters</span></li>
    ${(v.params || []).filter((p) => p.exposed).map((p) => li(`${p.name} = ${p.value}`, { kind: "param", param: p })).join("")}
  </ul>`;
  tree.querySelectorAll("[data-insp]").forEach((el) =>
    el.addEventListener("click", () => inspect(JSON.parse(el.dataset.insp), v)));
}

// One inspection surface: everything renders as a card OVER the viewport —
// the eye stays on the geometry, no separate inspector column.
function cardHead(title, dot = null) {
  return `<div class="rc-head">${dot ? `<span class="rc-dot" style="background:${dot}"></span>` : ""}
    <b>${esc(title)}</b><button class="ghost rc-close" title="hide">✕</button></div>`;
}

function showCard(html, onClose = null) {
  const card = $("#insp-card");
  if (!card) return null;
  card.style.display = "block";
  card.innerHTML = html;
  card.querySelector(".rc-close")?.addEventListener("click", () => {
    card.style.display = "none";
    if (onClose) onClose();
  });
  return card;
}

function inspect(sel, v) {
  if (sel.kind === "param") {
    const p = sel.param;
    const used = Object.keys(v.form?.frame || {}).filter((k) => k.includes(p.name)).slice(0, 8);
    showCard(cardHead(p.name) + `<table>
      <tr><td>value</td><td>${esc(p.value)}</td></tr>
      <tr><td>role</td><td>${esc(p.role)}</td></tr>
      <tr><td>range</td><td>${p.min ?? "—"} … ${p.max ?? "—"}</td></tr>
      <tr><td>rule</td><td>${esc(p.description || "—")}</td></tr>
      <tr><td>frame</td><td>${used.map(esc).join("<br>") || "—"}</td></tr></table>`);
  } else if (sel.kind === "region") {
    const r = sel.region;
    if (editSetTarget) {
      editSetTarget(r.name); // validates protected roles, syncs the select
    } else {
      state.selectedRegion = r.name;
    }
    // the pick must be VISIBLE whatever the lens: reveal the region boxes
    // and light the picked one up (others ghost out)
    state.three?.showRegions(v.form?.regions, true);
    state.three?.highlightRegion(r.name);
    // no STL yet (validate-only) → the camera never fitted; frame the boxes
    if (state.three && !state.three.meshes.children.length) state.three.fit();
    showRegionCard(r, v);
  } else if (sel.kind === "field") {
    showCard(cardHead(`field: ${sel.field.pattern}`) + `<table>
      <tr><td>cells</td><td>${sel.field.cells}</td></tr>
      <tr><td>web</td><td>${sel.field.min_ligament} mm (measured, not hoped)</td></tr>
      <tr><td>depth</td><td>${sel.field.depth} mm</td></tr></table>`);
  } else {
    showCard(cardHead(sel.name || sel.kind) + `<div class="dim">${esc(sel.kind)}</div>`);
  }
}

// Region details live ON the viewport (one screen: geometry + meaning),
// not in a separate panel the eye has to travel to.
async function showRegionCard(r, v) {
  const b = r.box || {};
  const num = (x) => (Number.isFinite(x) ? +(+x).toFixed(1) : "∞");
  const dims = [b.x1 - b.x0, b.y1 - b.y0, b.z1 - b.z0].map(num).join(" × ");
  if (!state.catalog) { try { state.catalog = await api.catalog(); } catch (e) { /* card still renders */ } }
  const archId = String(v.archetype || "").split("@")[0];
  const spec = (state.catalog?.archetypes || []).find((a) => a.id === archId)
    ?.regions?.find((x) => x.id === r.name);
  const mods = spec?.compatible_modifiers || [];
  const editable = spec ? spec.editable && mods.length : false;
  showCard(
    cardHead(spec?.label || r.name, regionColor(r.role)) + `
    <table>
      <tr><td>id</td><td>${esc(r.name)}</td></tr>
      <tr><td>role</td><td>${esc(r.role)}</td></tr>
      <tr><td>box</td><td>${dims} mm</td></tr>
      <tr><td>edit</td><td>${editable
        ? `editable · modifiers: ${mods.map(esc).join(", ")}`
        : `<span class="rc-protected">protected</span> — keepouts derive from this role`}</td></tr>
    </table>
    ${spec?.description ? `<div class="dim mt">${esc(spec.description)}</div>` : ""}`,
    () => {
      state.three?.highlightRegion(null);
      state.three?.showRegions(v.form?.regions, state.lens === "edit");
    });
}

function regionColor(role) {
  return {
    mounting_surface: "#d9b544", fastener_keepout: "#e05575",
    soft_contact_surface: "#4dc3d6", high_stress_region: "#f0a832",
    retaining_flexure: "#46c07a", aesthetic_lightening: "#8a93a3",
    seal_surface: "#a06be0",
  }[role] || "#8a93a3";
}

function buildConsole(v, isAssembly) {
  const el = $("#console");
  const findings = isAssembly
    ? [...(v.joints || [])]
    : (v.findings || []);
  const nonPass = findings.filter((f) => f.status !== "pass");
  el.innerHTML = `
    <div class="console-tabs">
      <span class="badge ${v.status}">${(v.status || "?").toUpperCase()}</span>
      <span class="dim">findings: ${findings.length} (${nonPass.length} non-pass) — validate is CAD-free truth; build adds geometry probes</span>
    </div>
    ${findingsTable(findings)}`;
}

// ------------------------------------------------------------- utilities
function jsyaml(obj, indent = 0) {
  // minimal YAML emitter for display purposes
  const pad = "  ".repeat(indent);
  if (obj === null || obj === undefined) return "null";
  if (typeof obj !== "object") return String(obj);
  if (Array.isArray(obj))
    return obj.map((x) => `${pad}- ${typeof x === "object" ? "\n" + jsyaml(x, indent + 1) : x}`).join("\n");
  return Object.entries(obj)
    .filter(([, val]) => val !== null && val !== undefined &&
      !(typeof val === "object" && !Array.isArray(val) && !Object.keys(val).length) &&
      !(Array.isArray(val) && !val.length))
    .map(([k, val]) =>
      typeof val === "object"
        ? `${pad}${k}:\n${jsyaml(val, indent + 1)}`
        : `${pad}${k}: ${val}`)
    .join("\n");
}

// ---------------------------------------------------------------- router
function setNav(name) {
  document.querySelectorAll("#nav button").forEach((b) =>
    b.classList.toggle("active", b.dataset.screen === name));
}
function go(name) {
  setNav(name);
  if (name === "home") renderHome();
  else if (name === "catalog") renderCatalog();
  else if (name === "wizard") renderWizard();
  else if (name === "assembly")
    renderAssemblyWizard({ screenEl, api, openInWorkspace, status: state.status });
  else if (name === "yaml") renderYamlEntry();
  else if (name === "library") renderLibrary();
  else renderWorkspace();
}
document.querySelectorAll("#nav button").forEach((b) =>
  b.addEventListener("click", () => go(b.dataset.screen)));

// the boot loader (index.html #boot) spins until the first /api/status
// answers — a cold start loads the whole catalog server-side. If the API
// never answers, say so honestly instead of spinning forever.
try {
  await refreshTop();
  renderHome();
} catch (err) {
  screenEl.innerHTML = `<div class="home"><div class="panel">
    <h3>FORGE OFFLINE</h3>
    <p class="dim">the cockpit API did not answer: ${esc(String(err?.message || err))}</p>
    <div class="row mt"><button class="forge" id="boot-retry">Retry</button></div>
  </div></div>`;
  $("#boot-retry").addEventListener("click", () => location.reload());
}
