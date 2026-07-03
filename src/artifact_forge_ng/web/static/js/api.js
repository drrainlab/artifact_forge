// Thin API client. Every response is a view model from serialize.py —
// the UI never derives engine truth on its own.
async function j(url, opts) {
  const r = await fetch(url, opts);
  return r.json();
}
export const api = {
  status: () => j("/api/status"),
  catalog: () => j("/api/catalog"),
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
  nlEdit: (yaml, text) =>
    j("/api/nl_edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml, text }),
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
