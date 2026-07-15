// prompt -> assembly wizard (wave W4). Standalone screen module: deps are
// injected, nothing here imports main.js. Badges follow the three-tier
// verification model; a hand-edited draft goes stale (EDITED) until
// "Validate changes" re-measures it.
//
// TODO(ui_utils): esc/findingsTable are duplicated from main.js on purpose
// — extract a shared ui_utils.js after the previews work merges.

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function findingsTable(findings) {
  if (!findings || !findings.length) return `<div class="dim mt">no findings — clean</div>`;
  return `<table class="findings mt">${findings.map((f) => `
    <tr class="f-${esc(f.status)}">
      <td>${esc((f.status || "").toUpperCase())}</td><td>${esc(f.check)}</td>
      <td class="msg">${esc(f.message)}</td>
      <td class="faint">${f.suggestion ? "→ " + esc(f.suggestion) : ""}</td></tr>`).join("")}
  </table>`;
}

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

const BADGES = {
  failed:        { label: "FAIL",           cls: "off" },
  pre_cad_pass:  { label: "PRE-CAD PASS",   cls: "on" },
  build_required:{ label: "BUILD REQUIRED", cls: "warn" },
  fully_verified:{ label: "FULLY VERIFIED", cls: "on" },
  build_failed:  { label: "BUILD FAILED",   cls: "off" },
  edited:        { label: "EDITED",         cls: "warn" },
  validating:    { label: "VALIDATING…",    cls: "warn" },
};

function reportFindings(validation) {
  const out = [];
  for (const j of validation?.joints || []) if (j.status !== "pass") out.push(j);
  for (const [ref, part] of Object.entries(validation?.parts || {}))
    for (const f of part.findings || []) out.push({ ...f, check: `${ref}: ${f.check}` });
  return out;
}

export function renderAssemblyWizard({ screenEl, api, openInWorkspace, status }) {
  const st = {
    result: null,          // last intent result
    validation: null,      // current validation report (may be re-measured)
    state: "prompt",       // prompt | progress | draft
    verification: "failed",
    dirty: false,
    log: [],
    svg: null,             // attached SVG text (engraving/cutout asset)
    svgName: "",
    history: null,         // fetched history metas (null = loading)
  };

  function badge() {
    const key = st.dirty ? "edited" : st.verification;
    const b = BADGES[key] || BADGES.failed;
    return `<span class="badge ${b.cls}">${b.label}</span>`;
  }

  function canForge() {
    return !st.dirty && (st.verification === "pre_cad_pass" ||
                         st.verification === "build_required") &&
           !!status?.cad;
  }

  function render() {
    if (st.state === "prompt") return renderPrompt();
    if (st.state === "progress") return renderProgress();
    return renderDraft();
  }

  function renderPrompt() {
    screenEl.innerHTML = `<div class="wizard">
      <div class="panel"><h3>DESCRIBE THE ASSEMBLY
        <span class="badge ${status?.llm ? "on" : "off"}">${status?.llm ? "LLM ON" : "LLM OFF"}</span></h3>
        <p class="dim">Multi-part composition from the catalog: parts, joints, shared
        dimensions, wiring. The model drafts; the deterministic pipeline judges.</p>
        <textarea id="asm-prompt" rows="4" spellcheck="false"
          placeholder="pegboard bench station: dovetail slider, adapter plate with a snap-fit controller box, E27 lamp on a bracket, cable from the controller to the socket; lighten the box"></textarea>
        <div class="row mt">
          <button class="forge" id="asm-go">Compose assembly</button>
          <button class="ghost" id="asm-svg-btn"
            title="attach an SVG for engravings / contour cutouts — the model references it, the server injects the path data">${st.svgName ? `⌘ ${esc(st.svgName)}` : "+ SVG asset"}</button>
          ${st.svgName ? '<button class="ghost" id="asm-svg-clear" title="detach">✕</button>' : ""}
          <input type="file" id="asm-svg-file" accept=".svg,image/svg+xml" style="display:none">
        </div>
      </div>
      <div class="panel"><h3>HISTORY</h3>
        <p class="dim">Every composed draft is kept — the failed ones too
        (their findings are part of the story). Click to reopen.</p>
        <div id="asm-history">${historyRows()}</div>
      </div></div>`;
    screenEl.querySelector("#asm-go").addEventListener("click", compose);
    wireHistory();
    if (st.history === null) {
      api.assemblyHistory().then((r) => {
        st.history = r.entries || [];
        const el = screenEl.querySelector("#asm-history");
        if (el) { el.innerHTML = historyRows(); wireHistory(); }
      }).catch(() => { st.history = []; });
    }
    const fileEl = screenEl.querySelector("#asm-svg-file");
    screenEl.querySelector("#asm-svg-btn").addEventListener("click", () => fileEl.click());
    fileEl.addEventListener("change", async () => {
      const f = fileEl.files && fileEl.files[0];
      if (!f) return;
      const prompt = screenEl.querySelector("#asm-prompt").value;
      st.svg = await f.text(); st.svgName = f.name;
      render();
      screenEl.querySelector("#asm-prompt").value = prompt;
    });
    const clearEl = screenEl.querySelector("#asm-svg-clear");
    if (clearEl) clearEl.addEventListener("click", () => {
      const prompt = screenEl.querySelector("#asm-prompt").value;
      st.svg = null; st.svgName = "";
      render();
      screenEl.querySelector("#asm-prompt").value = prompt;
    });
  }

  function historyRows() {
    if (st.history === null) return `<div class="dim">loading…</div>`;
    if (!st.history.length) return `<div class="dim">no drafts yet</div>`;
    return `<table class="findings">${st.history.map((h) => {
      const b = BADGES[h.verification_state] || BADGES.failed;
      const when = (h.ts || "").replace("T", " ").replace("+00:00", " UTC");
      return `<tr class="asm-hist" data-hid="${esc(h.id)}" style="cursor:pointer">
        <td class="faint">${esc(when)}</td>
        <td><span class="badge ${b.cls}">${esc(b.label)}</span></td>
        <td>${h.parts ? esc(h.parts + " parts") : ""}${h.svg_attached ? " ⌘svg" : ""}</td>
        <td class="msg">${esc((h.prompt || "").slice(0, 110))}</td></tr>`;
    }).join("")}</table>`;
  }

  function wireHistory() {
    screenEl.querySelectorAll(".asm-hist").forEach((row) =>
      row.addEventListener("click", async () => {
        const r = await api.assemblyHistoryEntry(row.dataset.hid);
        if (!r.ok || !r.result) return;
        st.result = r.result;
        st.validation = r.result.validation || null;
        st.verification = r.result.verification_state || "failed";
        st.dirty = false;
        st.state = "draft";
        render();
      }));
  }

  function renderProgress() {
    screenEl.innerHTML = `<div class="wizard"><div class="panel">
      <h3>COMPOSING…</h3>
      <pre class="joblog" id="asm-log">${esc(st.log.join("\n"))}</pre>
    </div></div>`;
  }

  async function compose() {
    const prompt = screenEl.querySelector("#asm-prompt").value.trim();
    if (!prompt) return;
    st.state = "progress"; st.log = []; render();
    try {
      const { job } = await api.assemblyIntent(prompt, st.svg);
      const done = await api.waitJob(job, (j) => {
        st.log = j.log || [];
        const el = screenEl.querySelector("#asm-log");
        if (el) el.textContent = st.log.join("\n");
      });
      if (done.status !== "done") {
        st.log.push(`job ${done.status}: ${done.error || "unknown"}`);
        st.state = "prompt"; render(); return;
      }
      st.history = null;      // a fresh run belongs in the list
      st.result = done.result;
      st.validation = done.result.validation || null;
      st.verification = done.result.verification_state || "failed";
      st.dirty = false;
      st.state = "draft";
      render();
    } catch (e) {
      st.log.push(String(e)); st.state = "prompt"; render();
    }
  }

  function renderDraft() {
    const r = st.result;
    const current = st.validation;
    const suggestions = (r.suggestions || []).map((s) =>
      `<button class="linklike asm-sug" data-file="${esc(s.file)}">${esc(s.file)}</button>`).join(" ");
    screenEl.innerHTML = `<div class="wizard">
      <div class="panel">
        <h3>ASSEMBLY DRAFT ${badge()}</h3>
        ${r.notes ? `<p class="dim">${esc(r.notes)}</p>` : ""}
        ${r.deferred_checks?.length ? `<p class="dim">deferred to build: ${esc(r.deferred_checks.join(", "))}</p>` : ""}
        ${r.iterations ? `<p class="faint">iterations: ${r.iterations}, selected: ${r.selected_iteration}</p>` : ""}
        ${suggestions ? `<p>closest examples: ${suggestions}</p>` : ""}
        <textarea id="asm-yaml" rows="22" spellcheck="false">${esc(r.yaml || "")}</textarea>
        <div class="row mt">
          <button id="asm-validate">Validate changes</button>
          <button id="asm-open">Open in workspace</button>
          <button class="forge" id="asm-forge" ${canForge() ? "" : "disabled"}>⚒ Forge assembly</button>
          <button id="asm-back" class="linklike">new prompt</button>
        </div>
        <h4 class="mt">Current validation findings</h4>
        <div id="asm-findings">${findingsTable(
          reportFindings(current).length || !(r.grounding_findings || []).length
            ? reportFindings(current)      // validation ran — its truth leads
            : r.grounding_findings         // it never ran — show WHY, not "clean"
        )}</div>
        <details class="mt"><summary>Generation history (grounding)</summary>
          ${findingsTable(r.grounding_findings)}
          <pre class="joblog">${esc(st.log.join("\n"))}</pre>
        </details>
      </div></div>`;

    const yamlEl = screenEl.querySelector("#asm-yaml");
    yamlEl.addEventListener("input", () => {
      if (!st.dirty) { st.dirty = true; refreshControls(); }
    });
    screenEl.querySelector("#asm-back").addEventListener("click", () => {
      st.state = "prompt"; render();
    });
    const openBtn = screenEl.querySelector("#asm-open");
    openBtn.addEventListener("click", () => withBusy(
      openBtn, "validating…", () => openInWorkspace(yamlEl.value)));
    const valBtn = screenEl.querySelector("#asm-validate");
    valBtn.addEventListener("click", () => withBusy(
      valBtn, "validating…", () => revalidate(yamlEl.value)));
    const forgeBtn = screenEl.querySelector("#asm-forge");
    forgeBtn.addEventListener("click", () => withBusy(
      forgeBtn, "forging (CAD build)…", () => forge(yamlEl.value)));
    screenEl.querySelectorAll(".asm-sug").forEach((b) =>
      b.addEventListener("click", () => withBusy(b, "opening…", async () => {
        const ex = await api.example(b.dataset.file);
        if (ex?.yaml) await openInWorkspace(ex.yaml);
      })));
  }

  function refreshControls() {
    const h = screenEl.querySelector("h3");
    if (h) h.innerHTML = `ASSEMBLY DRAFT ${badge()}`;
    const f = screenEl.querySelector("#asm-forge");
    if (f) f.disabled = !canForge();
  }

  async function revalidate(yamlText) {
    const prev = st.verification;
    st.verification = "validating"; st.dirty = false;
    const h = screenEl.querySelector("h3");
    if (h) h.innerHTML = `ASSEMBLY DRAFT <span class="badge warn">VALIDATING…</span>`;
    try {
      const res = await api.validate(yamlText);
      st.validation = res;
      // schema errors arrive as {ok:false, findings:[...]}
      const pass = res.ok === true && (res.status ? res.status === "pass" : true);
      const hadDeferred = st.result?.deferred_checks?.length;
      st.verification = pass ? (hadDeferred ? "build_required" : "pre_cad_pass")
                             : "failed";
      const findingsEl = screenEl.querySelector("#asm-findings");
      if (findingsEl) findingsEl.innerHTML =
        findingsTable(res.findings?.length ? res.findings : reportFindings(res));
    } catch (e) {
      st.verification = prev;
      alert(`validate failed: ${e}`);
    }
    refreshControls();
  }

  async function forge(yamlText) {
    st.state = "progress"; st.log = ["forging assembly…"]; render();
    try {
      const { job } = await api.build(yamlText);
      const done = await api.waitJob(job, (j) => {
        st.log = j.log || [];
        const el = screenEl.querySelector("#asm-log");
        if (el) el.textContent = st.log.join("\n");
      });
      if (done.status === "done") {
        st.verification = "fully_verified";
        await openInWorkspace(yamlText, done.result);
        return;
      }
      st.verification = "build_failed";
      st.state = "draft"; render();
    } catch (e) {
      st.verification = "build_failed";
      st.log.push(String(e)); st.state = "draft"; render();
    }
  }

  render();
}
