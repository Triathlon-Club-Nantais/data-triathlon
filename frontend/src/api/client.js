const BASE = (import.meta.env.VITE_API_URL || "") + "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Erreur réseau");
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  scrape: (url, bib = null) =>
    request("/scrape", {
      method: "POST",
      body: JSON.stringify({ url, bib }),
    }),

  saveResult: (data) =>
    request("/results", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listResults: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params.set(k, v);
    });
    const qs = params.toString();
    return request(`/results${qs ? `?${qs}` : ""}`);
  },

  listEvents: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params.set(k, v);
    });
    const qs = params.toString();
    return request(`/results/events${qs ? `?${qs}` : ""}`);
  },

  listResultsByEvent: (eventName, eventDate) => {
    const params = new URLSearchParams({ event_name: eventName, page_size: 500 });
    if (eventDate) params.set("date_from", eventDate);
    if (eventDate) params.set("date_to", eventDate);
    return request(`/results?${params.toString()}`);
  },

  deleteResult: (id) =>
    request(`/results/${id}`, { method: "DELETE" }),

  importEvent: (url) =>
    request("/scrape/event", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  importEventStream: async function* (url) {
    const res = await fetch(`${BASE}/scrape/event/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error("Erreur lors du démarrage de l'import");
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const part of parts) {
        if (part.startsWith("data: ")) {
          try { yield JSON.parse(part.slice(6)); } catch { /* ignore */ }
        }
      }
    }
  },

  reportPendingProvider: (url) =>
    request("/admin/pending-providers", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  listPendingProviders: () => request("/admin/pending-providers"),

  getStats: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    const qs = params.toString();
    return request(`/stats${qs ? `?${qs}` : ""}`);
  },

  getEventsGeo: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    const qs = params.toString();
    return request(`/stats/events-geo${qs ? `?${qs}` : ""}`);
  },

  markProviderHandled: (id) =>
    request(`/admin/pending-providers/${id}`, { method: "DELETE" }),
};
