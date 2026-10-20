async function request(path, options = {}) {
  const response = await fetch(path, options);
  const type = response.headers.get("content-type") || "";
  const body = type.includes("json") ? await response.json() : await response.text();
  if (!response.ok) throw new Error(body?.detail || body || response.statusText);
  return body;
}

export const api = {
  health: () => request("/api/health"),
  model: (profile) => request("/api/model/info?profile=" + encodeURIComponent(profile)),
  metrics: (profile) => request("/api/model/metrics?profile=" + encodeURIComponent(profile)),
  dashboard: () => request("/api/dashboard/summary"),
  history: (filters = {}) => {
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    return request("/api/history" + (query.size ? "?" + query : ""));
  },
  historyDetail: (id) => request("/api/history/" + encodeURIComponent(id)),
  upload: (file, profile) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/analyze/upload?profile=" + encodeURIComponent(profile), { method: "POST", body: form });
  },
  demoSamples: () => request("/api/demo/samples"),
  demoAnalyze: (id) => request("/api/demo/analyze/" + encodeURIComponent(id), { method: "POST" }),
  demoAudio: async (id) => {
    const response = await fetch("/api/demo/audio/" + encodeURIComponent(id));
    if (!response.ok) {
      let detail = response.statusText;
      try { detail = (await response.json()).detail || detail; } catch {}
      throw new Error(detail);
    }
    return response.blob();
  },
  settings: (profile) => request("/api/settings?profile=" + encodeURIComponent(profile)),
  saveSettings: (settings, profile) => request("/api/settings?profile=" + encodeURIComponent(profile), {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings),
  }),
  clearHistory: () => request("/api/history", { method: "DELETE" }),
  socket: () => new WebSocket((location.protocol === "https:" ? "wss" : "ws") + "://" + location.host + "/ws/live"),
};
