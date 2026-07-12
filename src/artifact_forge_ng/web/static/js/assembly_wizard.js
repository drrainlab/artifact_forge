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
          placeholder="верстачная станция на перфопанель: слайдер по ласточкину хвосту, площадка со snap-корпусом контроллера, лампа E27 на кронштейне, кабель от контроллера к патрону; корпус облегчить"></textarea>
        <div class="row mt">
          <button class="forge" id="asm-go">Compose assembly</button>
          <button class="ghost" id="asm-svg-btn"
            title="attach an SVG for engravings / contour cutouts — the model references it, the server injects the path data">${st.svgName ? `⌘ ${esc(st.svgName)}` : "+ SVG asset"}</button>
          ${st.svgName ? '<button class="ghost" id="asm-svg-clear" title="detach">✕</button>' : ""}
          <input type="file" id="asm-svg-file" accept=".svg,image/svg+xml" style="display:none">
        </div>
      </div></div>`;
    screenEl.querySelector("#asm-go").addEventListener("click", compose);
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
    screenEl.querySelector("#asm-open").addEventListener("click", () =>
      openInWorkspace(yamlEl.value));
    screenEl.querySelector("#asm-validate").addEventListener("click", () =>
      revalidate(yamlEl.value));
    screenEl.querySelector("#asm-forge").addEventListener("click", () =>
      forge(yamlEl.value));
    screenEl.querySelectorAll(".asm-sug").forEach((b) =>
      b.addEventListener("click", async () => {
        const ex = await api.example(b.dataset.file);
        if (ex?.yaml) openInWorkspace(ex.yaml);
      }));
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
