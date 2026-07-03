// Product Cockpit — screens. Truth first: every panel renders view models
// from the pipeline; the UI never invents state.
import { api } from "./api.js";
import { renderSection } from "./section.js";
import { ThreeView } from "./three_view.js";

const $ = (sel, el = document) => el.querySelector(sel);
const screenEl = $("#screen");
const state = {
  status: null,
  catalog: null,
  yaml: null,          // current product/assembly YAML text
  validation: null,    // last /api/validate view model
  buildReport: null,   // last build job result
  lens: "3d",
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

// ------------------------------------------------------------------ home
function renderHome() {
  const s = state.status;
  screenEl.innerHTML = `<div class="home">
    <h1>ARTIFACT FORGE — product cockpit</h1>
    <div class="sub">understood → capable → built → verified → honestly reported</div>
    <div class="entries">
      <div class="entry" data-go="wizard"><h3>Create from prompt</h3>
        <p>Describe the part; the system shows what it understood, what it can build, and only then forges.</p></div>
      <div class="entry" data-go="yaml"><h3>Create from YAML</h3>
        <p>Paste a product or assembly document and validate it against the catalog.</p></div>
      <div class="entry" data-go="catalog"><h3>Browse archetype catalog</h3>
        <p>What the system honestly supports: buildable, recipe, metadata-only.</p></div>
      <div class="entry disabled"><h3>Create from reference image</h3>
        <p><span class="badge off">vision intent — v2</span></p></div>
    </div>
    <div class="sysstatus"><table>
      <tr><td>Buildable archetypes (python)</td><td>${s.archetypes.buildable.length}</td></tr>
      <tr><td>Recipe archetypes (pure YAML)</td><td>${s.archetypes.recipe.length}</td></tr>
      <tr><td>Metadata-only</td><td>${s.archetypes.metadata_only.length}</td></tr>
      <tr><td>Modifiers</td><td>${s.modifiers.length}</td></tr>
      <tr><td>Assembly joints</td><td>${s.joints.join(", ")}</td></tr>
      <tr><td>Recipe ops</td><td>${s.recipe_ops.length}</td></tr>
      <tr><td>CAD backend</td><td>${s.cad ? "ON" : "OFF"}</td></tr>
      <tr><td>LLM</td><td>${s.llm ? "ON (Anthropic)" : "OFF — deterministic intent fallback"}</td></tr>
    </table></div>
  </div>`;
  screenEl.querySelectorAll(".entry[data-go]").forEach((el) =>
    el.addEventListener("click", () => go(el.dataset.go)));
}

// --------------------------------------------------------------- catalog
async function renderCatalog() {
  if (!state.catalog) state.catalog = await api.catalog();
  const c = state.catalog;
  screenEl.innerHTML = `<div class="catalog">
    <h3 class="dim" style="margin-bottom:12px">ARCHETYPES</h3>
    <div class="cards">${c.archetypes.map((a) => `
      <div class="card">
        <h3>${esc(a.id)} <span class="badge ${a.status}">${a.status}</span></h3>
        <div class="desc">${esc(a.description)}</div>
        <div class="meta">features ${a.provides_features.length} ·
          validators ${a.validators.length} · modifiers ${a.allowed_modifiers.length}
          ${a.status === "metadata_only" ? "<br>can author YAML: yes · can build STL: no" : ""}</div>
        <button class="ghost" data-arch="${esc(a.id)}">open in wizard</button>
      </div>`).join("")}</div>
    <h3 class="dim" style="margin:22px 0 12px">EXAMPLES</h3>
    <div class="cards">${c.examples.map((e) => `
      <div class="card"><h3>${esc(e.id)} <span class="badge recipe">${e.kind}</span></h3>
        <div class="meta">${esc(e.archetype || (e.parts || []).join(" + "))}</div>
        <button class="ghost" data-example="${esc(e.file)}">open in workspace</button>
      </div>`).join("")}</div>
  </div>`;
  screenEl.querySelectorAll("[data-example]").forEach((b) =>
    b.addEventListener("click", async () => {
      const ex = await api.example(b.dataset.example);
      await openInWorkspace(ex.yaml);
    }));
  screenEl.querySelectorAll("[data-arch]").forEach((b) =>
    b.addEventListener("click", () => renderWizard({ archetype_id: b.dataset.arch })));
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
    return wiz.validation;
  }

  const render = async () => {
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
      $("#detect").addEventListener("click", async () => {
        $("#intent-out").innerHTML = `<span class="dim">detecting…</span>`;
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
          b.addEventListener("click", () => {
            wiz.archetype = state.catalog.archetypes.find((a) => a.id === b.dataset.pick);
            for (const [k, v] of Object.entries(out.params || {}))
              if (wiz.archetype.parameters.some((p) => p.name === k)) wiz.params[k] = v;
            wiz.stage = 2; render();
          }));
      });
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
      $("#next").addEventListener("click", () => { wiz.stage = 3; render(); });
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
      $("#next")?.addEventListener("click", () => { wiz.stage = 4; render(); });
      return;
    }

    if (wiz.stage === 4) {
      const v = wiz.validation || (await revalidate());
      screenEl.innerHTML = `<div class="wizard">${stagesBar()}
        <div class="panel"><h3>PARAMETERS — live validated (no CAD)</h3>
          <div id="pgroups">${paramGroups(v.params, wiz.params)}</div>
          <div class="row mt"><button class="forge" id="next">Validate form →</button>
            <span id="pstatus" class="badge ${v.status}">${v.status}</span></div>
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
              bind();
            }, 350);
          }));
      };
      bind();
      $("#next").addEventListener("click", () => { wiz.stage = 5; render(); });
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
    $("#forge").addEventListener("click", async () => {
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
    });
  };
  render();
}

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
        const range = p.min != null || p.max != null
          ? `${p.min ?? "—"} … ${p.max ?? "—"}` : "";
        return `<div class="prow ${p.locked ? "locked" : ""}">
          <span class="pname" title="${esc(p.description)}">${p.name}${p.exposed ? " ●" : ""}</span>
          ${input}<span class="range">${range}</span>
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
  $("#openws").addEventListener("click", () => openInWorkspace($("#yamlin").value));
}

// ------------------------------------------------------------- workspace
async function openInWorkspace(yamlText, buildReport = null) {
  state.yaml = yamlText;
  state.buildReport = buildReport;
  state.validation = await api.validate(yamlText, false);
  setNav("workspace");
  renderWorkspace();
}

function renderWorkspace() {
  const v = state.validation;
  if (!v) { screenEl.innerHTML = `<div class="home"><div class="panel">Open an example from the Catalog, or create one in the Wizard.</div></div>`; return; }
  const isAssembly = !!v.assembly_pose;
  screenEl.innerHTML = `<div class="ws">
    <div class="ws-tree tree" id="tree"></div>
    <div class="ws-view">
      <div class="lenses" id="lenses">
        ${["3d", "section", "region", "honesty", "manufacturing"].map((l) =>
          `<button data-lens="${l}" class="${state.lens === l ? "active" : ""}">${l.toUpperCase()}</button>`).join("")}
        <button data-lens="edit">EDIT</button>
      </div>
      <div id="viewport3d"></div>
      <div id="viewport-section" style="display:none"></div>
      <div id="viewport-panel" style="display:none"></div>
    </div>
    <div class="ws-insp insp" id="insp"><h3>INSPECTOR</h3><div class="dim">click a tree node, region, parameter or finding</div></div>
    <div class="ws-console" id="console"></div>
  </div>`;
  buildTree(v, isAssembly);
  buildConsole(v, isAssembly);
  const view = new ThreeView($("#viewport3d"));
  state.three = view;
  load3D(view, v, isAssembly);
  $("#lenses").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => setLens(b.dataset.lens, v, isAssembly)));
  setLens(state.lens, v, isAssembly);
}

async function load3D(view, v, isAssembly) {
  view.clear();
  const report = state.buildReport;
  try {
    if (isAssembly && report?.parts) {
      const poses = {};
      for (const p of report.assembly_pose || []) poses[p.part] = p;
      for (const [ref, part] of Object.entries(report.parts)) {
        const stl = part.exports?.stl;
        if (!stl) continue;
        const pose = poses[ref]?.rotate ? poses[ref] : null;
        await view.loadSTL("/artifacts/" + stl.replace(/^out\//, ""), pose);
      }
    } else if (report?.exports?.stl) {
      await view.loadSTL("/artifacts/" + report.exports.stl.replace(/^out\//, ""));
    } else if (!isAssembly && v.product) {
      // try prebuilt artifact from out/
      await view.loadSTL(`/artifacts/${v.product}/part.stl`);
    } else if (isAssembly && v.assembly) {
      // prebuilt assembly artifacts, placed by the REPORTED poses
      const poses = {};
      for (const p of v.assembly_pose || []) poses[p.part] = p;
      const tints = [0xb9c2cf, 0x8fb8c9, 0xc9b98f, 0xa9c98f];
      let i = 0;
      for (const ref of Object.keys(v.parts || {})) {
        const pose = poses[ref]?.rotate ? poses[ref] : null;
        await view.loadSTL(`/artifacts/${v.assembly}/${ref}/part.stl`, pose, tints[i++ % 4]);
      }
    }
  } catch (e) {
    $("#console").insertAdjacentHTML("afterbegin",
      `<div class="dim">no STL artifact yet — Build to see 3D (section/region lenses work without CAD)</div>`);
  }
  view.showRegions(v.form?.regions, state.lens === "region");
  view.fit();
}

function setLens(lens, v, isAssembly) {
  state.lens = lens;
  $("#lenses").querySelectorAll("button").forEach((b) =>
    b.classList.toggle("active", b.dataset.lens === lens));
  const v3 = $("#viewport3d"), vs = $("#viewport-section"), vp = $("#viewport-panel");
  v3.style.display = lens === "3d" || lens === "region" ? "block" : "none";
  vs.style.display = lens === "section" ? "flex" : "none";
  vp.style.display = ["honesty", "manufacturing", "edit"].includes(lens) ? "block" : "none";
  if (state.three) state.three.showRegions(v.form?.regions, lens === "region");
  if (lens === "section") renderSection(vs, v.form);
  if (lens === "honesty") vp.innerHTML = honestyPanel(v, isAssembly);
  if (lens === "manufacturing") vp.innerHTML = manufacturingPanel(v);
  if (lens === "edit") { vp.innerHTML = editPanel(); wireEdit(); }
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
  return `<h3 class="dim">SEMANTIC EDIT — patch preview before anything is built</h3>
    <div class="row"><input id="nl" type="text" placeholder="сделай без поддержек / make it stronger…" style="flex:1">
    <button class="forge" id="nlgo">Propose patch</button></div>
    <div class="row mt dim">intents:
      ${["make_support_free", "make_stronger", "make_biomorphic", "remove_perforation"].map((i) =>
        `<button class="ghost" data-intent="${i}">${i}</button>`).join("")}</div>
    <div id="editout" class="mt"></div>`;
}

function wireEdit() {
  const out = $("#editout");
  const preview = async (intent, patch) => {
    out.innerHTML = `<span class="dim">computing patch…</span>`;
    const p = await api.editPreview(state.yaml, intent, patch);
    if (!p.ok) { out.innerHTML = findingsTable(p.findings); return; }
    const val = p.validation;
    out.innerHTML = `
      <div class="yaml-pane">${esc(jsyaml(p.patch))}</div>
      <div class="mt">edited product validates: <span class="badge ${val.status}">${val.status}</span></div>
      ${findingsTable((val.findings || []).filter((f) => f.status !== "pass"))}
      <div class="row mt">
        <button class="forge" id="apply">Apply patch (rebuild + verify preserve)</button>
        <button class="ghost" id="cancel">Cancel</button></div>`;
    $("#cancel").addEventListener("click", () => (out.innerHTML = ""));
    $("#apply").addEventListener("click", async () => {
      out.innerHTML = `<span class="dim">rebuilding + verifying preserve…</span>`;
      const { job } = await api.editApply(state.yaml, intent, patch);
      const done = await api.waitJob(job);
      const rep = done.result?.edit_report;
      if (!rep) { out.innerHTML = findingsTable([done.error]); return; }
      out.innerHTML = `
        <table class="findings">
          <tr><td>status</td><td class="msg"><span class="badge ${rep.status}">${rep.status}</span></td></tr>
          <tr><td>preserved (verified)</td><td class="msg">${rep.preserved.map((x) => esc(x.name)).join(", ")}</td></tr>
          <tr><td>changed</td><td class="msg">${esc(JSON.stringify(rep.changed))}</td></tr>
          <tr><td>supports before → after</td><td class="msg">${rep.printability.supports_recommended_before} → ${rep.printability.supports_recommended_after}</td></tr>
          <tr><td>overhang after</td><td class="msg">${esc(rep.printability.overhang_after.message)}</td></tr>
        </table>
        <div class="row mt"><button class="ghost" id="openedited">open edited product in workspace</button></div>`;
      $("#openedited").addEventListener("click", async () => {
        const txt = await (await fetch("/artifacts/" + rep.edited_yaml.replace(/^out\//, ""))).text();
        await openInWorkspace(txt);
      });
    });
  };
  $("#nlgo").addEventListener("click", async () => {
    out.innerHTML = `<span class="dim">translating…</span>`;
    const r = await api.nlEdit(state.yaml, $("#nl").value);
    if (!r.ok) { out.innerHTML = findingsTable(r.findings); return; }
    if (r.intent) preview(r.intent, null); else preview(null, r.patch);
  });
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

function inspect(sel, v) {
  const insp = $("#insp");
  if (sel.kind === "param") {
    const p = sel.param;
    const used = Object.keys(v.form?.frame || {}).filter((k) => k.includes(p.name)).slice(0, 8);
    insp.innerHTML = `<h3>${esc(p.name)}</h3><table>
      <tr><td>value</td><td>${esc(p.value)}</td></tr>
      <tr><td>role</td><td>${esc(p.role)}</td></tr>
      <tr><td>range</td><td>${p.min ?? "—"} … ${p.max ?? "—"}</td></tr>
      <tr><td>rule</td><td>${esc(p.description || "—")}</td></tr>
      <tr><td>frame keys</td><td>${used.map(esc).join("<br>") || "—"}</td></tr></table>`;
  } else if (sel.kind === "region") {
    const r = sel.region;
    insp.innerHTML = `<h3>region: ${esc(r.name)}</h3><table>
      <tr><td>role</td><td>${esc(r.role)}</td></tr>
      <tr><td>box</td><td>${esc(JSON.stringify(r.box))}</td></tr></table>
      <div class="mt dim">modifiers target regions; keepouts derive from protected roles</div>`;
  } else if (sel.kind === "field") {
    insp.innerHTML = `<h3>field: ${esc(sel.field.pattern)}</h3><table>
      <tr><td>cells</td><td>${sel.field.cells}</td></tr>
      <tr><td>min ligament</td><td>${sel.field.min_ligament} mm (measured, not hoped)</td></tr>
      <tr><td>depth</td><td>${sel.field.depth} mm</td></tr></table>`;
  } else {
    insp.innerHTML = `<h3>${esc(sel.name || sel.kind)}</h3>
      <div class="dim">${esc(sel.kind)}</div>`;
  }
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
  else if (name === "yaml") renderYamlEntry();
  else renderWorkspace();
}
document.querySelectorAll("#nav button").forEach((b) =>
  b.addEventListener("click", () => go(b.dataset.screen)));

await refreshTop();
renderHome();
