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
  scrape: (url) =>
    request("/scrape", {
      method: "POST",
      body: JSON.stringify({ url }),
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

  deleteResult: (id) =>
    request(`/results/${id}`, { method: "DELETE" }),

  importEvent: (url) =>
    request("/scrape/event", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
};
