// Thin API client. Every response is a view model from serialize.py —
// the UI never derives engine truth on its own.
async function j(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    // 500s carry no view model — surface a readable error instead of
    // letting r.json() throw a cryptic SyntaxError the UI swallows
    const text = await r.text().catch(() => "");
    throw new Error(`${url} → HTTP ${r.status}${text ? `: ${text.slice(0, 300)}` : ""}`);
  }
  return r.json();
}
export const api = {
  status: () => j("/api/status"),
  catalog: () => j("/api/catalog"),
  previews: (ids) => j(`/api/catalog/previews${ids ? `?ids=${ids.join(",")}` : ""}`),
  example: (name) => j(`/api/examples/${name}`),
  validate: (yaml, strict = null) =>
    j("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml, strict }),
    }),
  build: (yaml) =>
    j("/api/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml }),
    }),
  editPreview: (yaml, intent, patch) =>
    j("/api/edit/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml, intent, patch }),
    }),
  editApply: (yaml, intent, patch) =>
    j("/api/edit/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml, intent, patch }),
    }),
  intent: (prompt) =>
    j("/api/intent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    }),
  assemblyIntent: (prompt, svg = null) =>
    j("/api/assembly/intent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(svg ? { prompt, svg } : { prompt }),
    }),
  library: (limit = 50) => j(`/api/library?limit=${limit}`),
  libraryDevice: (id) => j(`/api/library/${id}`),
  libraryBuild: (id, buildId) => j(`/api/library/${id}/${buildId}`),
  assemblyHistory: (limit = 30) => j(`/api/assembly/history?limit=${limit}`),
  assemblyHistoryEntry: (id) => j(`/api/assembly/history/${id}`),
  svgFlatten: (svg, motifW = 60.0) =>
    j("/api/svg/flatten", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ svg, motif_w: motifW }),
    }),
  nlEdit: (yaml, text, selectedRegion = null) =>
    j("/api/nl_edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml, text, selected_region: selectedRegion }),
    }),
  job: (id) => j(`/api/jobs/${id}`),
  async waitJob(id, onLog) {
    for (;;) {
      const job = await this.job(id);
      if (onLog) onLog(job);
      if (job.status !== "running") return job;
      await new Promise((res) => setTimeout(res, 700));
    }
  },
};
