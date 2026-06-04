import { useState, useEffect } from "react";
import ResultCard from "./ResultCard.jsx";
import { EVENT_TYPE_LABELS } from "../constants.js";
import { api } from "../api/client.js";

function formatDate(d) {
  if (!d) return "";
  const m = String(d).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString("fr-FR");
  return String(d);
}

function isTCN(club) {
  if (!club) return false;
  const c = club.toUpperCase();
  return c.includes("NANTAIS") || c === "TCN" || c.includes("TRIATHLON CLUB NANTAIS");
}

const PAGE_SIZE = 50; // résultats rendus par tranche

function EventGroup({ g, onDelete, highlightTCN, filters }) {
  const [isOpen, setIsOpen]       = useState(false);
  const [results, setResults]     = useState(null);
  const [loading, setLoading]     = useState(false);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  async function toggle() {
    if (!isOpen && results === null) {
      setLoading(true);
      try {
        const params = { event_name: g.event_name, page_size: 5000 };
        if (g.event_date) {
          params.date_from = g.event_date;
          params.date_to   = g.event_date;
        }
        if (filters?.name) params.name = filters.name;
        if (filters?.club) params.club = filters.club;
        const data = await api.listResults(params);
        setResults(data);
        setVisibleCount(PAGE_SIZE); // reset pagination on each open
      } catch (e) {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }
    setIsOpen(prev => !prev);
  }

  async function handleDelete(id) {
    if (!window.confirm("Supprimer ce résultat ?")) return;
    await api.deleteResult(id);
    const params = { event_name: g.event_name, page_size: 5000 };
    if (g.event_date) { params.date_from = g.event_date; params.date_to = g.event_date; }
    const data = await api.listResults(params);
    setResults(data);
    onDelete?.();
  }

  const sortedResults = results
    ? [...results].sort((a, b) => (a.rank_overall || 9999) - (b.rank_overall || 9999))
    : [];
  const displayedResults = sortedResults.slice(0, visibleCount);
  const hasMore = sortedResults.length > visibleCount;

  return (
    <div style={styles.group}>
      <button style={styles.groupHeader} onClick={toggle}>
        <div style={styles.groupLeft}>
          <span style={styles.groupName}>{g.event_name || "Épreuve inconnue"}</span>
          <div style={styles.groupMeta}>
            {g.event_date && <span style={styles.groupDate}>{formatDate(g.event_date)}</span>}
            {g.event_type && (
              <span style={styles.groupType}>
                {EVENT_TYPE_LABELS[g.event_type] || g.event_type}
              </span>
            )}
          </div>
        </div>
        <div style={styles.groupRight}>
          <span style={styles.groupCount}>
            {g.total} résultat{g.total > 1 ? "s" : ""}
          </span>
          {highlightTCN && g.tcn_count > 0 && (
            <span style={styles.tcnBadge}>{g.tcn_count} TCN</span>
          )}
          <span style={styles.chevron}>{isOpen ? "▲" : "▼"}</span>
        </div>
      </button>

      {isOpen && (
        <div style={styles.groupBody}>
          {loading && <p style={styles.loadingInner}>Chargement…</p>}
          {!loading && displayedResults.map((r) => (
            <div
              key={r.id}
              style={highlightTCN && isTCN(r.club) ? styles.tcnHighlight : undefined}
            >
              <ResultCard result={r} onDelete={() => handleDelete(r.id)} />
            </div>
          ))}
          {!loading && hasMore && (
            <button
              style={styles.loadMoreBtn}
              onClick={() => setVisibleCount(c => c + PAGE_SIZE)}
            >
              Afficher {Math.min(PAGE_SIZE, sortedResults.length - visibleCount)} résultats de plus
              <span style={styles.loadMoreCount}> ({visibleCount}/{sortedResults.length})</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function EventGroupList({ events = [], onDelete, highlightTCN = false, filters }) {
  if (!events.length) return null;

  return (
    <div>
      {events.map((g) => (
        <EventGroup
          key={`${g.event_name}||${g.event_date}`}
          g={g}
          onDelete={onDelete}
          highlightTCN={highlightTCN}
          filters={filters}
        />
      ))}
    </div>
  );
}

const styles = {
  group: { marginBottom: 10 },
  loadMoreBtn: {
    display: "block", width: "100%", marginTop: 8, padding: "10px 0",
    background: "#fafafa", border: "1px dashed #ddd", borderRadius: 6,
    cursor: "pointer", fontSize: 13, color: "#555", fontWeight: 600,
  },
  loadMoreCount: { fontWeight: 400, color: "#aaa" },
  groupHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    width: "100%", padding: "14px 18px", background: "#fff",
    border: "1px solid #ebebeb", borderRadius: 8,
    cursor: "pointer", textAlign: "left", gap: 12,
    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
  },
  groupLeft: { flex: 1, minWidth: 0 },
  groupName: { fontWeight: 700, fontSize: 15, color: "#1a1a1a", display: "block" },
  groupMeta: { display: "flex", gap: 10, marginTop: 4, alignItems: "center", flexWrap: "wrap" },
  groupDate: { fontSize: 13, color: "#888" },
  groupType: { background: "#fff5f0", color: "#c4500d", borderRadius: 10, padding: "1px 8px", fontSize: 12, fontWeight: 600 },
  groupRight: { display: "flex", alignItems: "center", gap: 10, flexShrink: 0 },
  groupCount: { fontSize: 13, color: "#aaa", whiteSpace: "nowrap" },
  tcnBadge: { background: "#fff5f0", color: "#e95d0f", borderRadius: 20, padding: "2px 10px", fontSize: 12, fontWeight: 700 },
  chevron: { fontSize: 11, color: "#bbb" },
  groupBody: { paddingTop: 6 },
  tcnHighlight: { borderLeft: "3px solid #e95d0f", borderRadius: 4, marginBottom: 2 },
};
