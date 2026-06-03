import { useState, useEffect, useMemo } from "react";
import { api } from "../api/client.js";
import ResultCard from "./ResultCard.jsx";
import EventGroupList from "./EventGroupList.jsx";
import { EVENT_TYPE_LABELS } from "../constants.js";

function formatDate(dateStr) {
  if (!dateStr) return "";
  try {
    return new Date(dateStr).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
  } catch { return dateStr; }
}

export default function ClubView({ refreshKey, club }) {
  const [allResults, setAllResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState("");
  const [eventFilter, setEventFilter] = useState("");
  const [yearFilter, setYearFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [modalAthlete, setModalAthlete] = useState(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [typeFilter, setTypeFilter] = useState("");
  const [openAthlete, setOpenAthlete] = useState(null);

  useEffect(() => {
    setLoading(true);
    setFetchError("");
    const params = { page_size: 1000 };
    if (club) params.club = club;
    api.listResults(params)
      .then((data) => setAllResults(data || []))
      .catch((err) => { setFetchError(err.message || "Erreur inconnue"); setAllResults([]); })
      .finally(() => setLoading(false));
  }, [refreshKey, club, refreshTick]);

  const stats = useMemo(() => {
    if (!allResults.length) return null;

    const athleteSet = new Set(allResults.map(r => `${r.athlete_name}||${r.athlete_firstname}`));
    const eventSet = new Set(allResults.map(r => r.event_name).filter(Boolean));

    const byYear = allResults.reduce((acc, r) => {
      const y = r.event_date?.slice(0, 4) || null;
      if (y) acc[y] = (acc[y] || 0) + 1;
      return acc;
    }, {});
    const activeSeason = Object.entries(byYear).sort((a, b) => b[1] - a[1])[0]?.[0];

    const byType = allResults.reduce((acc, r) => {
      const t = r.event_type || "inconnu";
      acc[t] = (acc[t] || 0) + 1;
      return acc;
    }, {});

    // Activité récente — 6 derniers par date d'épreuve
    const recent = [...allResults]
      .filter(r => r.event_date)
      .sort((a, b) => b.event_date.localeCompare(a.event_date))
      .slice(0, 6);

    // Épreuves collectives — grouper par event_name+date, garder celles avec 2+ membres
    const byEvent = allResults.reduce((acc, r) => {
      const key = `${r.event_name}||${r.event_date || ""}`;
      if (!acc[key]) acc[key] = { event_name: r.event_name, event_date: r.event_date, event_type: r.event_type, members: [] };
      const name = `${r.athlete_firstname} ${r.athlete_name}`.trim();
      if (name && !acc[key].members.includes(name)) acc[key].members.push(name);
      return acc;
    }, {});
    const collective = Object.values(byEvent)
      .filter(e => e.members.length >= 2)
      .sort((a, b) => (b.event_date || "").localeCompare(a.event_date || ""));

    // Progression par athlète — déduplique par event_name+bib_number
    const byAthlete = allResults.reduce((acc, r) => {
      const key = `${r.athlete_name}||${r.athlete_firstname}`;
      if (!acc[key]) acc[key] = {
        name: `${r.athlete_firstname} ${r.athlete_name}`.trim() || "Inconnu",
        results: [],
        seenEvents: new Set(),
        bests: {},
      };
      const dedupKey = `${r.event_name}||${r.bib_number || r.id}`;
      if (acc[key].seenEvents.has(dedupKey)) return acc;
      acc[key].seenEvents.add(dedupKey);
      acc[key].results.push(r);
      if (r.event_type && r.total_time) {
        if (!acc[key].bests[r.event_type] || r.total_time < acc[key].bests[r.event_type])
          acc[key].bests[r.event_type] = r.total_time;
      }
      return acc;
    }, {});
    const athletes = Object.values(byAthlete).sort((a, b) => b.results.length - a.results.length);

    return { total: allResults.length, athleteCount: athleteSet.size, eventCount: eventSet.size, activeSeason, recent, collective, athletes, byType };
  }, [allResults]);

  const availableYears = useMemo(() => {
    const years = [...new Set(allResults.map(r => r.event_date?.slice(0, 4)).filter(Boolean))];
    return years.sort((a, b) => b.localeCompare(a));
  }, [allResults]);

  const filtered = useMemo(() => {
    return allResults.filter((r) => {
      if (eventFilter && !r.event_name?.toLowerCase().includes(eventFilter.toLowerCase())) return false;
      if (yearFilter && r.event_date?.slice(0, 4) !== yearFilter) return false;
      if (typeFilter && r.event_type !== typeFilter) return false;
      return true;
    });
  }, [allResults, eventFilter, yearFilter, typeFilter]);

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>{club || "Club TCN"}</h2>

      {fetchError && (
        <div style={styles.errorRow}>
          <p style={styles.error}>Erreur : {fetchError}</p>
          <button style={styles.retryBtn} onClick={() => setRefreshTick(t => t + 1)}>Réessayer</button>
        </div>
      )}
      {loading && <p style={styles.loading}>Chargement…</p>}

      {!loading && !allResults.length && !fetchError && (
        <p style={styles.empty}>
          {club ? `Aucun résultat trouvé pour « ${club} ».` : "Ajoutez un résultat pour voir les statistiques du club."}
        </p>
      )}

      {!loading && !!allResults.length && stats && (<>

        {/* Chiffres clés */}
        <div style={styles.statRow}>
          <StatCard label="Résultats" value={stats.total} color="#3b82f6" />
          <StatCard label="Athlètes" value={stats.athleteCount} color="#10b981" />
          <StatCard label="Épreuves couvertes" value={stats.eventCount} color="#8b5cf6" />
          {stats.activeSeason && (
            <StatCard label="Saison la + active" value={stats.activeSeason} color="#f59e0b" />
          )}
        </div>

        {/* Timeline des épreuves */}
        <div style={styles.panel}>
          <h3 style={styles.panelTitle}>Dernières épreuves</h3>
          {stats.collective.length === 0 && (
            <p style={styles.emptyPanel}>Aucune épreuve avec 2+ membres pour l'instant.</p>
          )}
          <div style={styles.timeline}>
            {stats.collective.map((e) => (
              <div key={`${e.event_name}||${e.event_date}`} style={styles.timelineItem}>
                <div style={styles.timelineDot} />
                <div style={styles.timelineContent}>
                  <div style={styles.timelineHeader}>
                    <span style={styles.collectiveName}>{e.event_name}</span>
                    <span style={styles.collectiveBadge}>{e.members.length} membre{e.members.length > 1 ? "s" : ""}</span>
                  </div>
                  {e.event_date && <span style={styles.collectiveDate}>{formatDate(e.event_date)}</span>}
                  <div style={styles.memberChips}>
                    {e.members.map((m) => {
                      const athleteData = stats.athletes.find(a => a.name === m);
                      return (
                        <button
                          key={m}
                          style={styles.memberChip}
                          onClick={() => athleteData && setModalAthlete(athleteData)}
                          title={`Voir les résultats de ${m}`}
                        >
                          {m}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Répartition par type */}
        <div style={styles.pills}>
          {Object.entries(stats.byType)
            .sort((a, b) => b[1] - a[1])
            .map(([type, count]) => (
              <span key={type} style={styles.pill}>
                {EVENT_TYPE_LABELS[type] || type} <strong>{count}</strong>
              </span>
            ))}
        </div>

        {/* Athlètes du club */}
        <div style={styles.panel}>
          <h3 style={styles.panelTitle}>Athlètes du club</h3>
          {stats.athletes.map((athlete) => (
            <div key={athlete.name} style={styles.athleteRow}>
              <button
                style={styles.athleteBtn}
                onClick={() => setOpenAthlete(openAthlete === athlete.name ? null : athlete.name)}
              >
                <div style={styles.athleteBtnLeft}>
                  <span style={styles.athleteBtnName}>{athlete.name}</span>
                  {Object.keys(athlete.bests).length > 0 && (
                    <div style={styles.athleteInlineBests}>
                      {Object.entries(athlete.bests).map(([type, time]) => (
                        <span key={type} style={styles.athleteInlinePill}>
                          {EVENT_TYPE_LABELS[type] || type} · <strong>{time}</strong>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <span style={styles.athleteBtnMeta}>
                  {athlete.results.length} résultat{athlete.results.length > 1 ? "s" : ""}
                </span>
                <span style={styles.athleteChevron}>{openAthlete === athlete.name ? "▲" : "▼"}</span>
              </button>

              {openAthlete === athlete.name && (
                <div style={styles.athleteDetail}>
                  {athlete.results
                    .sort((a, b) => (b.event_date || "").localeCompare(a.event_date || ""))
                    .map((r) => (
                      <div key={r.id} style={styles.athleteResult}>
                        <span style={styles.feedDate}>{formatDate(r.event_date)}</span>
                        <span style={styles.feedEvent}>{r.event_name}</span>
                        {r.total_time && <span style={styles.athleteTime}>{r.total_time}</span>}
                        {r.rank_overall && <span style={styles.athleteRank}>{r.rank_overall}e</span>}
                      </div>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Section compétitions */}
        <div style={styles.sectionHeader}>
          <h3 style={styles.sectionTitle}>Compétitions</h3>
        </div>
        <div style={styles.filters}>
          <input
            style={styles.filterInput}
            placeholder="Rechercher une compétition…"
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
          />
          <select
            style={styles.filterSelect}
            value={yearFilter}
            onChange={(e) => setYearFilter(e.target.value)}
          >
            <option value="">Toutes les saisons</option>
            {availableYears.map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
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
        </div>

        {filtered.length === 0 && <p style={styles.empty}>Aucun résultat correspond aux filtres.</p>}
        <EventGroupList results={filtered} />

      </>)}

      {/* Modale athlète */}
      {modalAthlete && (
        <div style={styles.modalOverlay} onClick={() => setModalAthlete(null)}>
          <div style={styles.modalBox} onClick={e => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <span style={styles.modalTitle}>{modalAthlete.name}</span>
              <button style={styles.modalClose} onClick={() => setModalAthlete(null)}>✕</button>
            </div>
            {Object.keys(modalAthlete.bests).length > 0 && (
              <div style={styles.bestsRow}>
                {Object.entries(modalAthlete.bests).map(([type, time]) => (
                  <span key={type} style={styles.bestPill}>
                    {EVENT_TYPE_LABELS[type] || type} · <strong>{time}</strong>
                  </span>
                ))}
              </div>
            )}
            <div style={styles.modalResults}>
              {modalAthlete.results
                .sort((a, b) => (b.event_date || "").localeCompare(a.event_date || ""))
                .map((r) => <ResultCard key={r.id} result={r} />)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div style={{ ...styles.statCard, borderTopColor: color }}>
      <div style={{ ...styles.statValue, color }}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  );
}

const styles = {
  container: {},
  title: { fontSize: 22, fontWeight: 800, color: "#1a202c", marginBottom: 20 },
  loading: { color: "#718096", textAlign: "center", padding: 40 },
  empty: { color: "#a0aec0", textAlign: "center", padding: 40, fontSize: 15 },
  errorRow: { display: "flex", alignItems: "center", gap: 12, marginBottom: 10 },
  error: { color: "#e53e3e", fontSize: 14, margin: 0 },
  retryBtn: { padding: "5px 14px", background: "#e53e3e", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13, fontWeight: 600 },

  statRow: { display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" },
  statCard: { flex: "1 1 140px", background: "#fff", borderRadius: 10, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.08)", borderTop: "4px solid #ccc" },
  statValue: { fontSize: 28, fontWeight: 800, lineHeight: 1 },
  statLabel: { fontSize: 13, color: "#718096", marginTop: 4, fontWeight: 600 },

  twoCol: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 },
  panel: { background: "#fff", borderRadius: 10, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.08)", marginBottom: 16 },
  panelTitle: { fontSize: 14, fontWeight: 700, color: "#4a5568", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.05em" },
  emptyPanel: { color: "#a0aec0", fontSize: 13 },

  feedDate: { fontSize: 11, color: "#a0aec0", whiteSpace: "nowrap", paddingTop: 2, minWidth: 72 },
  feedEvent: { fontSize: 12, color: "#718096", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },

  timeline: { position: "relative", paddingLeft: 20 },
  timelineItem: { position: "relative", paddingBottom: 20, paddingLeft: 16, borderLeft: "2px solid #e2e8f0" },
  timelineDot: { position: "absolute", left: -7, top: 4, width: 12, height: 12, borderRadius: "50%", background: "#3b82f6", border: "2px solid #fff", boxShadow: "0 0 0 2px #3b82f6" },
  timelineContent: { paddingBottom: 4 },
  timelineHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" },
  collectiveName: { fontWeight: 700, fontSize: 15, color: "#1a202c" },
  collectiveBadge: { background: "#ebf8ff", color: "#2b6cb0", borderRadius: 20, padding: "2px 10px", fontSize: 11, fontWeight: 700, whiteSpace: "nowrap" },
  collectiveDate: { fontSize: 12, color: "#a0aec0", display: "block", marginTop: 2, marginBottom: 6 },
  memberChips: { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 },
  memberChip: { background: "#f7fafc", border: "1px solid #e2e8f0", borderRadius: 20, padding: "3px 12px", fontSize: 12, fontWeight: 600, color: "#2d3748", cursor: "pointer", transition: "background 0.15s" },

  athleteRow: { borderBottom: "1px solid #f0f4f8", marginBottom: 4 },
  athleteBtn: { display: "flex", alignItems: "center", width: "100%", background: "none", border: "none", padding: "10px 0", cursor: "pointer", textAlign: "left", gap: 8 },
  athleteBtnLeft: { flex: 1, minWidth: 0 },
  athleteBtnName: { fontWeight: 700, fontSize: 14, color: "#2d3748", display: "block" },
  athleteInlineBests: { display: "flex", flexWrap: "wrap", gap: 4, marginTop: 3 },
  athleteInlinePill: { background: "#f0fff4", color: "#276749", borderRadius: 20, padding: "2px 8px", fontSize: 11 },
  athleteBtnMeta: { fontSize: 12, color: "#a0aec0", whiteSpace: "nowrap" },
  athleteChevron: { fontSize: 11, color: "#a0aec0" },
  athleteDetail: { paddingBottom: 12, paddingLeft: 4 },
  athleteResult: { display: "flex", gap: 10, alignItems: "center", padding: "5px 0", fontSize: 13 },
  athleteTime: { fontWeight: 700, color: "#2d3748", fontFamily: "monospace" },
  athleteRank: { color: "#f59e0b", fontWeight: 700, fontSize: 12 },

  pills: { display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 },
  pill: { background: "#ebf8ff", color: "#2b6cb0", borderRadius: 20, padding: "4px 12px", fontSize: 13 },

  sectionHeader: { display: "flex", alignItems: "center", marginBottom: 12, marginTop: 8 },
  sectionTitle: { fontSize: 16, fontWeight: 700, color: "#2d3748", textTransform: "uppercase", letterSpacing: "0.05em" },
  filters: { display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" },
  filterInput: { flex: 1, minWidth: 160, padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14 },
  filterSelect: { padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14, background: "#fff" },
  filterCount: { fontSize: 13, color: "#718096", whiteSpace: "nowrap" },

  modalOverlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 1000, display: "flex", alignItems: "flex-start", justifyContent: "center", paddingTop: 60, paddingBottom: 40 },
  modalBox: { background: "#f0f4f8", borderRadius: 14, width: "100%", maxWidth: 720, maxHeight: "80vh", overflowY: "auto", boxShadow: "0 8px 32px rgba(0,0,0,0.2)", padding: 24 },
  modalHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  modalTitle: { fontSize: 20, fontWeight: 800, color: "#1a202c" },
  modalClose: { background: "none", border: "none", fontSize: 18, cursor: "pointer", color: "#718096", padding: "4px 8px" },
  modalResults: { marginTop: 12 },
};
