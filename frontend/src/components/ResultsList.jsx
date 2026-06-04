import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client.js";
import EventGroupList from "./EventGroupList.jsx";
import { EVENT_TYPE_LABELS } from "../constants.js";

export default function ResultsList({ refreshKey, initialSearch = "" }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState("");
  const [filters, setFilters] = useState({ name: initialSearch, event_type: "", event_name: "", club: "" });
  const [retryTick, setRetryTick] = useState(0);

  // Sync when parent changes globalSearch
  useEffect(() => {
    setFilters(prev => ({ ...prev, name: initialSearch }));
  }, [initialSearch]);

  const load = useCallback(async (f) => {
    setLoading(true);
    setFetchError("");
    try {
      const data = await api.listEvents(f);
      setEvents(data);
    } catch (err) {
      setFetchError(err.message || "Erreur réseau");
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters);
  }, [filters, refreshKey, retryTick, load]);

  function handleFilter(field, value) {
    setFilters((prev) => ({ ...prev, [field]: value }));
  }

  async function handleDeleteAndReload() {
    load(filters);
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Résultats du club</h2>

      <div style={styles.filters}>
        <input
          style={styles.filterInput}
          placeholder="Rechercher par nom…"
          value={filters.name}
          onChange={(e) => handleFilter("name", e.target.value)}
        />
        <select
          style={styles.filterSelect}
          value={filters.event_type}
          onChange={(e) => handleFilter("event_type", e.target.value)}
        >
          <option value="">Tous les types</option>
          {Object.entries(EVENT_TYPE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
        <input
          style={styles.filterInput}
          placeholder="Nom d'épreuve…"
          value={filters.event_name}
          onChange={(e) => handleFilter("event_name", e.target.value)}
        />
        <input
          style={styles.filterInput}
          placeholder="Club…"
          value={filters.club}
          onChange={(e) => handleFilter("club", e.target.value)}
        />
      </div>

      {loading && <p style={styles.loading}>Chargement…</p>}

      {!loading && fetchError && (
        <div style={styles.errorRow}>
          <p style={styles.error}>Erreur : {fetchError}</p>
          <button style={styles.retryBtn} onClick={() => setRetryTick(t => t + 1)}>Réessayer</button>
        </div>
      )}

      {!loading && !fetchError && events.length === 0 && (
        <p style={styles.empty}>Aucun résultat trouvé. Ajoutez-en un ci-dessus !</p>
      )}

      <EventGroupList
        events={events}
        filters={filters}
        onDelete={handleDeleteAndReload}
        highlightTCN
      />
    </div>
  );
}

const styles = {
  container: {},
  title: { fontSize: 20, fontWeight: 700, marginBottom: 18, color: "#1a202c" },
  filters: { display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" },
  filterInput: { flex: 1, minWidth: 160, padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14 },
  filterSelect: { padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14, background: "#fff" },
  loading: { color: "#718096", textAlign: "center", padding: 20 },
  empty: { color: "#a0aec0", textAlign: "center", padding: 40, fontSize: 15 },
  errorRow: { display: "flex", alignItems: "center", gap: 12, marginBottom: 10 },
  error: { color: "#e53e3e", fontSize: 14, margin: 0 },
  retryBtn: { padding: "5px 14px", background: "#e53e3e", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13, fontWeight: 600 },
};
