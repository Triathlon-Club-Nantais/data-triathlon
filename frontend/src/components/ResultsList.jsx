import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client.js";
import EventGroupList from "./EventGroupList.jsx";

const EVENT_TYPES = [
  "triathlon-s",
  "triathlon-m",
  "triathlon-l",
  "triathlon-xl",
  "duathlon-xs",
  "duathlon-s",
  "duathlon-m",
  "duathlon-l",
  "duathlon",
  "swimrun-s",
  "swimrun-m",
  "swimrun-l",
  "swimrun",
  "aquathlon",
  "aquarun",
  "bike-run",
];

export default function ResultsList({ refreshKey }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ name: "", event_type: "", event_name: "", club: "" });
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const load = useCallback(async (f, p) => {
    setLoading(true);
    try {
      const data = await api.listResults({ ...f, page: p, page_size: PAGE_SIZE });
      setResults(data);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters, page);
  }, [filters, page, refreshKey, load]);

  function handleFilter(field, value) {
    setFilters((prev) => ({ ...prev, [field]: value }));
    setPage(1);
  }

  async function handleDelete(id) {
    if (!window.confirm("Supprimer ce résultat ?")) return;
    await api.deleteResult(id);
    load(filters, page);
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
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
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

      {!loading && results.length === 0 && (
        <p style={styles.empty}>Aucun résultat trouvé. Ajoutez-en un ci-dessus !</p>
      )}

      <EventGroupList results={results} onDelete={handleDelete} highlightTCN />

      {results.length === PAGE_SIZE && (
        <div style={styles.pagination}>
          {page > 1 && (
            <button style={styles.pageBtn} onClick={() => setPage((p) => p - 1)}>
              ← Précédent
            </button>
          )}
          <span style={styles.pageInfo}>Page {page}</span>
          <button style={styles.pageBtn} onClick={() => setPage((p) => p + 1)}>
            Suivant →
          </button>
        </div>
      )}
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
  pagination: { display: "flex", justifyContent: "center", alignItems: "center", gap: 16, marginTop: 20 },
  pageBtn: { padding: "8px 18px", background: "#3b82f6", color: "#fff", border: "none", borderRadius: 7, cursor: "pointer", fontWeight: 600 },
  pageInfo: { color: "#718096", fontSize: 14 },
};
