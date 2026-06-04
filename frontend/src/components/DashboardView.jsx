import { useState, useEffect } from "react";
import { api } from "../api/client.js";
import { EVENT_TYPE_LABELS } from "../constants.js";
import ResultsFeed from "./ResultsFeed.jsx";

const TCN_FILTER = "nantais|TCN";
const SPORT_ICONS = {
  "triathlon":    "🏊🚴🏃",
  "duathlon":     "🏃🚴🏃",
  "swimrun":      "🏊🏃",
  "aquathlon":    "🏊🏃",
  "aquarun":      "🏊🏃",
  "bike-run":     "🚴🏃",
};

function getSportIcon(type) {
  const base = Object.keys(SPORT_ICONS).find(k => (type || "").startsWith(k));
  return SPORT_ICONS[base] || "🏅";
}


export default function DashboardView() {
  const [stats,   setStats]   = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getStats({ club: TCN_FILTER })
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      {/* Chiffres clés */}
      {loading && <p style={styles.loading}>Chargement…</p>}
      {!loading && stats && (
        <>
          <div style={styles.kpiRow}>
            <KPI value={stats.total}    label="Résultats"          color="#e95d0f" icon="📋" />
            <KPI value={stats.athletes} label="Athlètes actifs"    color="#1a1a1a" icon="🏅" />
            <KPI value={stats.events}   label="Épreuves couvertes" color="#c6c7c8" icon="📍" />
          </div>

          {/* Répartition par sport */}
          <div style={styles.panel}>
            <span style={styles.panelTitle}>Répartition par discipline</span>
            <div style={styles.sportGrid}>
              {Object.entries(stats.by_type)
                .slice(0, 12)
                .map(([type, count]) => (
                  <div key={type} style={styles.sportCard}>
                    <span style={styles.sportIcon}>{getSportIcon(type)}</span>
                    <span style={styles.sportCount}>{count}</span>
                    <span style={styles.sportLabel}>{EVENT_TYPE_LABELS[type] || type}</span>
                  </div>
                ))
              }
            </div>
          </div>
        </>
      )}

      {/* Feed temps réel */}
      <ResultsFeed />
    </div>
  );
}

function KPI({ value, label, color, icon }) {
  return (
    <div style={{ ...styles.kpi, borderTopColor: color }}>
      <span style={styles.kpiIcon}>{icon}</span>
      <div style={{ ...styles.kpiValue, color }}>{value ?? "—"}</div>
      <div style={styles.kpiLabel}>{label}</div>
    </div>
  );
}

const styles = {
  loading: { textAlign: "center", color: "#888", padding: 40 },

  kpiRow:  { display: "flex", gap: 14, marginBottom: 16, flexWrap: "wrap" },
  kpi:     { flex: "1 1 120px", background: "#fff", borderRadius: 8, padding: "16px 18px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", borderTop: "4px solid #ccc", textAlign: "center" },
  kpiIcon: { fontSize: 22, display: "block", marginBottom: 6 },
  kpiValue:{ fontSize: 32, fontWeight: 800, lineHeight: 1 },
  kpiLabel:{ fontSize: 12, color: "#888", marginTop: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" },

  panel:      { background: "#fff", borderRadius: 8, padding: "16px 20px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", marginBottom: 16 },
  panelHeader:{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  panelTitle: { fontSize: 13, fontWeight: 700, color: "#1a1a1a", textTransform: "uppercase", letterSpacing: "0.07em" },
  panelSub:   { fontSize: 12, color: "#aaa" },

  sportGrid:  { display: "flex", flexWrap: "wrap", gap: 10, marginTop: 10 },
  sportCard:  { display: "flex", flexDirection: "column", alignItems: "center", background: "#fafafa", borderRadius: 8, padding: "12px 14px", minWidth: 80, gap: 4, border: "1px solid #ebebeb" },
  sportIcon:  { fontSize: 20 },
  sportCount: { fontSize: 22, fontWeight: 800, color: "#e95d0f" },
  sportLabel: { fontSize: 11, color: "#888", textAlign: "center" },

  empty: { color: "#aaa", textAlign: "center", padding: 20 },
};
