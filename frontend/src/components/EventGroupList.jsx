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
  const [isOpen, setIsOpen]             = useState(false);
  const [results, setResults]           = useState(null);
  const [loading, setLoading]           = useState(false);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [confirmDelete, setConfirmDelete] = useState(false);

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

  async function handleDeleteEvent(e) {
    e.stopPropagation();
    if (!confirmDelete) { setConfirmDelete(true); return; }
    await api.deleteEvent(g.event_name, g.event_date);
    setConfirmDelete(false);
    onDelete?.();
  }

  const sortedResults = results
    ? [...results].sort((a, b) => {
        if (a.event_type !== b.event_type) return (a.event_type || "").localeCompare(b.event_type || "");
        return (a.rank_overall || 9999) - (b.rank_overall || 9999);
      })
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
            {(g.event_types ?? (g.event_type ? [g.event_type] : [])).map((et) => (
              <span key={et} style={styles.groupType}>
                {EVENT_TYPE_LABELS[et] || et}
              </span>
            ))}
          </div>
        </div>
        <div style={styles.groupRight}>
          <span style={styles.groupCount}>
            {g.total} résultat{g.total > 1 ? "s" : ""}
          </span>
          {highlightTCN && g.tcn_count > 0 && (
            <span style={styles.tcnBadge}>{g.tcn_count} TCN</span>
          )}
          <button
            style={confirmDelete ? styles.deleteBtnConfirm : styles.deleteEventBtn}
            onClick={handleDeleteEvent}
            title={confirmDelete ? "Cliquer pour confirmer la suppression" : "Supprimer toute la compétition"}
          >
            {confirmDelete ? "Confirmer ?" : "Supprimer"}
          </button>
          <span style={styles.chevron}>{isOpen ? "▲" : "▼"}</span>
        </div>
      </button>

      {isOpen && (
        <div style={styles.groupBody}>
          {loading && <p style={styles.loadingInner}>Chargement…</p>}
          {!loading && displayedResults.map((r, i) => {
            const showDivider = g.event_types?.length > 1 && r.event_type !== displayedResults[i - 1]?.event_type;
            return (
              <div key={r.id}>
                {showDivider && (
                  <div style={styles.disciplineHeader}>
                    {EVENT_TYPE_LABELS[r.event_type] || r.event_type}
                  </div>
                )}
                <div style={highlightTCN && isTCN(r.club) ? styles.tcnHighlight : undefined}>
                  <ResultCard result={r} onDelete={() => handleDelete(r.id)} />
                </div>
              </div>
            );
          })}
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

  // Consolidate rows with same (event_name, event_date) across disciplines into one group.
  // The API returns one row per (event_name, event_date, event_type); without merging,
  // React key collisions would silently drop all but one discipline per competition.
  const groupMap = new Map();
  for (const e of events) {
    const key = `${e.event_name}||${e.event_date}`;
    if (!groupMap.has(key)) {
      groupMap.set(key, { ...e, event_types: e.event_type ? [e.event_type] : [] });
    } else {
      const g = groupMap.get(key);
      g.total += e.total;
      g.tcn_count += e.tcn_count;
      if (e.event_type && !g.event_types.includes(e.event_type)) {
        g.event_types.push(e.event_type);
      }
    }
  }
  const consolidated = Array.from(groupMap.values());

  return (
    <div>
      {consolidated.map((g) => (
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
  deleteEventBtn: { padding: "3px 10px", fontSize: 12, fontWeight: 600, color: "#e53e3e", background: "none", border: "1px solid #fed7d7", borderRadius: 5, cursor: "pointer" },
  deleteBtnConfirm: { padding: "3px 10px", fontSize: 12, fontWeight: 700, color: "#fff", background: "#e53e3e", border: "none", borderRadius: 5, cursor: "pointer" },
  groupBody: { paddingTop: 6 },
  disciplineHeader: {
    margin: "14px 0 6px", padding: "6px 12px",
    background: "#fff5f0", borderLeft: "3px solid #e95d0f",
    borderRadius: 4, fontSize: 12, fontWeight: 700,
    color: "#c4500d", letterSpacing: "0.04em", textTransform: "uppercase",
  },
  tcnHighlight: { borderLeft: "3px solid #e95d0f", borderRadius: 4, marginBottom: 2 },
};
