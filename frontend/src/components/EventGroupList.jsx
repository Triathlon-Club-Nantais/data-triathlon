import { useState } from "react";
import ResultCard from "./ResultCard.jsx";

const EVENT_TYPE_LABELS = {
  "triathlon-s":  "Triathlon S",
  "triathlon-m":  "Triathlon M",
  "triathlon-l":  "Triathlon L",
  "triathlon-xl": "Triathlon XL",
  "duathlon-xs":  "Duathlon XS",
  "duathlon-s":   "Duathlon S",
  "duathlon-m":   "Duathlon M",
  "duathlon-l":   "Duathlon L",
  "duathlon":     "Duathlon",
  "swimrun-s":    "SwimRun S",
  "swimrun-m":    "SwimRun M",
  "swimrun-l":    "SwimRun L",
  "swimrun":      "SwimRun",
  "aquathlon":    "Aquathlon",
  "aquarun":      "Aquarun",
  "bike-run":     "Bike & Run",
};

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

function groupByEvent(results) {
  const map = {};
  for (const r of results) {
    const key = `${r.event_name}||${r.event_date || ""}`;
    if (!map[key]) map[key] = {
      event_name: r.event_name,
      event_date: r.event_date,
      event_type: r.event_type,
      results: [],
    };
    map[key].results.push(r);
  }
  return Object.values(map).sort((a, b) =>
    (b.event_date || "").localeCompare(a.event_date || "")
  );
}

export default function EventGroupList({ results, onDelete, highlightTCN = false, defaultOpen = false }) {
  const groups = groupByEvent(results);
  const [openGroups, setOpenGroups] = useState(() => {
    if (!defaultOpen) return {};
    const init = {};
    groups.forEach(g => { init[`${g.event_name}||${g.event_date}`] = true; });
    return init;
  });

  function toggle(key) {
    setOpenGroups(prev => ({ ...prev, [key]: !prev[key] }));
  }

  if (groups.length === 0) return null;

  return (
    <div>
      {groups.map((g) => {
        const key = `${g.event_name}||${g.event_date}`;
        const isOpen = !!openGroups[key];
        const tcnCount = highlightTCN ? g.results.filter(r => isTCN(r.club)).length : 0;

        return (
          <div key={key} style={styles.group}>
            <button style={styles.groupHeader} onClick={() => toggle(key)}>
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
                  {g.results.length} résultat{g.results.length > 1 ? "s" : ""}
                </span>
                {highlightTCN && tcnCount > 0 && (
                  <span style={styles.tcnBadge}>{tcnCount} TCN</span>
                )}
                <span style={styles.chevron}>{isOpen ? "▲" : "▼"}</span>
              </div>
            </button>

            {isOpen && (
              <div style={styles.groupBody}>
                {g.results
                  .sort((a, b) => (a.rank_overall || 9999) - (b.rank_overall || 9999))
                  .map((r) => (
                    <div
                      key={r.id}
                      style={highlightTCN && isTCN(r.club) ? styles.tcnHighlight : undefined}
                    >
                      <ResultCard result={r} onDelete={onDelete} />
                    </div>
                  ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const styles = {
  group: { marginBottom: 10 },
  groupHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    width: "100%", padding: "14px 18px", background: "#fff",
    border: "1px solid #e2e8f0", borderRadius: 10,
    cursor: "pointer", textAlign: "left", gap: 12,
    boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
  },
  groupLeft: { flex: 1, minWidth: 0 },
  groupName: { fontWeight: 700, fontSize: 15, color: "#1a202c", display: "block" },
  groupMeta: { display: "flex", gap: 10, marginTop: 4, alignItems: "center", flexWrap: "wrap" },
  groupDate: { fontSize: 13, color: "#718096" },
  groupType: { background: "#f0fff4", color: "#276749", borderRadius: 10, padding: "1px 8px", fontSize: 12, fontWeight: 600 },
  groupRight: { display: "flex", alignItems: "center", gap: 10, flexShrink: 0 },
  groupCount: { fontSize: 13, color: "#a0aec0", whiteSpace: "nowrap" },
  tcnBadge: { background: "#ebf8ff", color: "#2b6cb0", borderRadius: 20, padding: "2px 10px", fontSize: 12, fontWeight: 700 },
  chevron: { fontSize: 11, color: "#a0aec0" },
  groupBody: { paddingTop: 6 },
  tcnHighlight: { borderLeft: "3px solid #3b82f6", borderRadius: 4, marginBottom: 2 },
};
