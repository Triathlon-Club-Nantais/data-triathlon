import { useState, useEffect, useMemo } from "react";
import { api } from "../api/client.js";
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

export default function ClubView({ refreshKey, club }) {
  const [allResults, setAllResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState("");
  const [nameFilter, setNameFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    setFetchError("");
    const params = { page_size: 1000 };
    if (club) params.club = club;
    api.listResults(params)
      .then((data) => setAllResults(data || []))
      .catch((err) => { setFetchError(err.message || "Erreur inconnue"); setAllResults([]); })
      .finally(() => setLoading(false));
  }, [refreshKey, club]);

  // --- Stats ---
  const stats = useMemo(() => {
    if (!allResults.length) return null;

    const athleteSet = new Set(
      allResults.map((r) => `${r.athlete_name}||${r.athlete_firstname}`)
    );

    const byType = allResults.reduce((acc, r) => {
      const t = r.event_type || "inconnu";
      acc[t] = (acc[t] || 0) + 1;
      return acc;
    }, {});

    const byAthlete = allResults.reduce((acc, r) => {
      const key = `${r.athlete_firstname} ${r.athlete_name}`.trim() || "Inconnu";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const topAthletes = Object.entries(byAthlete)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);

    const bestRankings = allResults
      .filter((r) => r.rank_overall)
      .sort((a, b) => a.rank_overall - b.rank_overall)
      .slice(0, 10);

    const topType = Object.entries(byType).sort((a, b) => b[1] - a[1])[0];

    return { total: allResults.length, athletes: athleteSet.size, byType, topAthletes, bestRankings, topType };
  }, [allResults]);

  // --- Filtered list ---
  const filtered = useMemo(() => {
    return allResults.filter((r) => {
      const name = `${r.athlete_name} ${r.athlete_firstname}`.toLowerCase();
      if (nameFilter && !name.includes(nameFilter.toLowerCase())) return false;
      if (typeFilter && r.event_type !== typeFilter) return false;
      return true;
    });
  }, [allResults, nameFilter, typeFilter]);

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>{club || "Club TCN"}</h2>

      {fetchError && <p style={styles.error}>Erreur : {fetchError}</p>}
      {loading && <p style={styles.loading}>Chargement…</p>}

      {!loading && !allResults.length && !fetchError && (
        <p style={styles.empty}>
          {club
            ? `Aucun résultat trouvé pour « ${club} ».`
            : "Ajoutez un résultat pour voir les statistiques du club."}
        </p>
      )}

      {!loading && !!allResults.length && (<>

      {/* Summary cards */}
      {stats && (
        <div style={styles.statRow}>
          <StatCard label="Résultats" value={stats.total} color="#3b82f6" />
          <StatCard label="Athlètes" value={stats.athletes} color="#10b981" />
          {stats.topType && (
            <StatCard
              label="Épreuve favorite"
              value={EVENT_TYPE_LABELS[stats.topType[0]] || stats.topType[0]}
              sub={`${stats.topType[1]} participations`}
              color="#f59e0b"
            />
          )}
        </div>
      )}

      {/* Top athletes + Best rankings */}
      {stats && (
        <div style={styles.twoCol}>
          <div style={styles.panel}>
            <h3 style={styles.panelTitle}>Top athlètes</h3>
            {stats.topAthletes.map(([name, count], i) => (
              <div key={name} style={styles.rankRow}>
                <span style={styles.rankPos}>{i + 1}</span>
                <span style={styles.rankName}>{name}</span>
                <span style={styles.rankCount}>{count} résultat{count > 1 ? "s" : ""}</span>
              </div>
            ))}
          </div>
          <div style={styles.panel}>
            <h3 style={styles.panelTitle}>Meilleurs classements généraux</h3>
            {stats.bestRankings.length === 0 && (
              <p style={styles.emptyPanel}>Aucun classement disponible.</p>
            )}
            {stats.bestRankings.map((r) => (
              <div key={r.id} style={styles.rankRow}>
                <span style={{ ...styles.rankPos, color: "#f59e0b" }}>{r.rank_overall}e</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={styles.rankName}>
                    {r.athlete_firstname} {r.athlete_name}
                  </div>
                  <div style={styles.rankSub}>{r.event_name}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Type breakdown pills */}
      {stats && (
        <div style={styles.pills}>
          {Object.entries(stats.byType)
            .sort((a, b) => b[1] - a[1])
            .map(([type, count]) => (
              <span key={type} style={styles.pill}>
                {EVENT_TYPE_LABELS[type] || type} <strong>{count}</strong>
              </span>
            ))}
        </div>
      )}

      {/* Filters */}
      <div style={styles.filters}>
        <input
          style={styles.filterInput}
          placeholder="Rechercher par nom…"
          value={nameFilter}
          onChange={(e) => setNameFilter(e.target.value)}
        />
        <select
          style={styles.filterSelect}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">Tous les types</option>
          {Object.entries(EVENT_TYPE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
        <span style={styles.filterCount}>{filtered.length} résultat{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Results list */}
      {filtered.length === 0 && (
        <p style={styles.empty}>Aucun résultat correspond aux filtres.</p>
      )}
      {filtered.map((r) => (
        <ResultCard key={r.id} result={r} />
      ))}
      </>)}
    </div>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{ ...styles.statCard, borderTopColor: color }}>
      <div style={{ ...styles.statValue, color }}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
      {sub && <div style={styles.statSub}>{sub}</div>}
    </div>
  );
}

const styles = {
  container: {},
  title: { fontSize: 22, fontWeight: 800, color: "#1a202c", marginBottom: 20 },
  loading: { color: "#718096", textAlign: "center", padding: 40 },
  empty: { color: "#a0aec0", textAlign: "center", padding: 40, fontSize: 15 },
  error: { color: "#e53e3e", fontSize: 14, marginBottom: 10 },

  statRow: { display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" },
  statCard: { flex: "1 1 160px", background: "#fff", borderRadius: 10, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.08)", borderTop: "4px solid #ccc" },
  statValue: { fontSize: 28, fontWeight: 800, lineHeight: 1 },
  statLabel: { fontSize: 13, color: "#718096", marginTop: 4, fontWeight: 600 },
  statSub: { fontSize: 12, color: "#a0aec0", marginTop: 2 },

  twoCol: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 },
  panel: { background: "#fff", borderRadius: 10, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.08)" },
  panelTitle: { fontSize: 14, fontWeight: 700, color: "#4a5568", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.05em" },
  rankRow: { display: "flex", alignItems: "center", gap: 10, paddingBottom: 8, marginBottom: 8, borderBottom: "1px solid #f0f4f8" },
  rankPos: { fontSize: 18, fontWeight: 800, color: "#3b82f6", minWidth: 28, textAlign: "right" },
  rankName: { flex: 1, fontWeight: 600, fontSize: 14, color: "#2d3748", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  rankCount: { fontSize: 12, color: "#a0aec0", whiteSpace: "nowrap" },
  rankSub: { fontSize: 12, color: "#a0aec0", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  emptyPanel: { color: "#a0aec0", fontSize: 13 },

  pills: { display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 },
  pill: { background: "#ebf8ff", color: "#2b6cb0", borderRadius: 20, padding: "4px 12px", fontSize: 13 },

  filters: { display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" },
  filterInput: { flex: 1, minWidth: 160, padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14 },
  filterSelect: { padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14, background: "#fff" },
  filterCount: { fontSize: 13, color: "#718096", whiteSpace: "nowrap" },
};
