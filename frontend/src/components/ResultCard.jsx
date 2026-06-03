import { useState } from "react";
import { EVENT_TYPE_LABELS } from "../constants.js";

function formatDate(d) {
  if (!d) return "";
  const m = String(d).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString("fr-FR");
  return String(d);
}

function timeAgo(isoStr) {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "aujourd'hui";
  if (days === 1) return "hier";
  if (days < 30) return `il y a ${days} j`;
  if (days < 365) return `il y a ${Math.floor(days / 30)} mois`;
  return `il y a ${Math.floor(days / 365)} an${Math.floor(days / 365) > 1 ? "s" : ""}`;
}

export default function ResultCard({ result, onDelete }) {
  const [confirming, setConfirming] = useState(false);
  const fullName = [result.athlete_firstname, result.athlete_name].filter(Boolean).join(" ");

  function handleDeleteClick() {
    if (confirming) {
      onDelete(result.id);
    } else {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 3000);
    }
  }

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div>
          <div style={styles.name}>{fullName || "Athlète inconnu"}</div>
          <div style={styles.sub}>
            {result.club && <span style={styles.club}>{result.club}</span>}
            {result.category && <span style={styles.cat}>{result.category}</span>}
            {result.gender && <span style={styles.gender}>{result.gender}</span>}
          </div>
        </div>
        <div style={styles.headerRight}>
          {result.total_time && (
            <div style={styles.totalTime}>{result.total_time}</div>
          )}
          {onDelete && (
            <button
              style={confirming ? styles.deleteBtnConfirm : styles.deleteBtn}
              onClick={handleDeleteClick}
              title={confirming ? "Cliquer pour confirmer" : "Supprimer"}
            >
              {confirming ? "Confirmer ?" : "×"}
            </button>
          )}
        </div>
      </div>

      <div style={styles.eventRow}>
        <span style={styles.eventName}>{result.event_name || "Épreuve inconnue"}</span>
        {result.event_type && (
          <span style={styles.eventType}>
            {EVENT_TYPE_LABELS[result.event_type] || result.event_type}
          </span>
        )}
        {result.event_date && (
          <span style={styles.eventDate}>{formatDate(result.event_date)}</span>
        )}
        {result.bib_number && (
          <span style={styles.bib}>#{result.bib_number}</span>
        )}
        {result.is_relay && (
          <span style={styles.relay}>Relais</span>
        )}
      </div>

      {(result.rank_overall || result.rank_category || result.rank_gender) && (
        <div style={styles.ranks}>
          {result.rank_overall && (
            <div style={styles.rankItem}>
              <span style={styles.rankLabel}>Général</span>
              <span style={styles.rankValue}>{result.rank_overall}e</span>
            </div>
          )}
          {result.rank_gender && (
            <div style={styles.rankItem}>
              <span style={styles.rankLabel}>Genre</span>
              <span style={styles.rankValue}>{result.rank_gender}e</span>
            </div>
          )}
          {result.rank_category && (
            <div style={styles.rankItem}>
              <span style={styles.rankLabel}>Catégorie</span>
              <span style={styles.rankValue}>{result.rank_category}e</span>
            </div>
          )}
        </div>
      )}

      {(result.swim_time || result.bike_time || result.run_time) && (
        <div style={styles.splits}>
          <SplitsForSport result={result} />
        </div>
      )}

      <div style={styles.footer}>
        <a href={result.source_url} target="_blank" rel="noopener noreferrer" style={styles.sourceLink}>
          Source ({result.provider})
        </a>
        {result.scraped_at && (
          <span style={styles.addedAt}>Ajouté {timeAgo(result.scraped_at)}</span>
        )}
      </div>
    </div>
  );
}

function SplitsForSport({ result }) {
  const type = result.event_type || "";

  if (type.startsWith("duathlon")) {
    return (
      <>
        <Split label="Course 1" time={result.swim_time} color="#10b981" />
        <Split label="T1"       time={result.t1_time}   color="#94a3b8" small />
        <Split label="Vélo"     time={result.bike_time} color="#f59e0b" />
        <Split label="T2"       time={result.t2_time}   color="#94a3b8" small />
        <Split label="Course 2" time={result.run_time}  color="#10b981" />
      </>
    );
  }

  if (type === "bike-run") {
    return (
      <>
        <Split label="Vélo"   time={result.bike_time} color="#f59e0b" />
        <Split label="Course" time={result.run_time}  color="#10b981" />
      </>
    );
  }

  if (type === "aquathlon") {
    return (
      <>
        <Split label="Natation" time={result.swim_time} color="#3b82f6" />
        <Split label="Course"   time={result.run_time}  color="#10b981" />
      </>
    );
  }

  if (type === "aquarun") {
    return (
      <>
        <Split label="Natation" time={result.swim_time} color="#3b82f6" />
        <Split label="T1"       time={result.t1_time}   color="#94a3b8" small />
        <Split label="Course"   time={result.run_time}  color="#10b981" />
      </>
    );
  }

  return (
    <>
      <Split label="Natation" time={result.swim_time} color="#3b82f6" />
      <Split label="T1"       time={result.t1_time}   color="#94a3b8" small />
      <Split label="Vélo"     time={result.bike_time} color="#f59e0b" />
      <Split label="T2"       time={result.t2_time}   color="#94a3b8" small />
      <Split label="Course"   time={result.run_time}  color="#10b981" />
    </>
  );
}

function Split({ label, time, color, small }) {
  if (!time) return null;
  return (
    <div style={{ ...styles.split, opacity: small ? 0.6 : 1 }}>
      <span style={{ ...styles.splitLabel, color }}>{label}</span>
      <span style={styles.splitTime}>{time}</span>
    </div>
  );
}

const styles = {
  card: { background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,0.08)", marginBottom: 14 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 },
  name: { fontWeight: 700, fontSize: 18, color: "#1a202c" },
  sub: { display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" },
  club: { fontSize: 13, color: "#4a5568" },
  cat: { fontSize: 12, background: "#ebf8ff", color: "#2b6cb0", borderRadius: 10, padding: "1px 8px", fontWeight: 600 },
  gender: { fontSize: 12, background: "#faf5ff", color: "#6b46c1", borderRadius: 10, padding: "1px 8px", fontWeight: 600 },
  headerRight: { display: "flex", alignItems: "center", gap: 12 },
  totalTime: { fontFamily: "monospace", fontSize: 22, fontWeight: 800, color: "#1a202c" },
  deleteBtn: { background: "none", border: "none", cursor: "pointer", fontSize: 22, color: "#a0aec0", lineHeight: 1, padding: "0 4px" },
  deleteBtnConfirm: { background: "#fff5f5", border: "1px solid #fc8181", borderRadius: 6, cursor: "pointer", fontSize: 12, color: "#c53030", fontWeight: 700, padding: "4px 8px" },
  eventRow: { display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid #e2e8f0" },
  eventName: { fontWeight: 600, fontSize: 14, color: "#2d3748" },
  eventType: { background: "#f0fff4", color: "#276749", borderRadius: 10, padding: "2px 8px", fontSize: 12, fontWeight: 600 },
  eventDate: { color: "#718096", fontSize: 13 },
  bib: { color: "#718096", fontSize: 13 },
  relay: { background: "#fff5f5", color: "#c53030", borderRadius: 10, padding: "2px 8px", fontSize: 12, fontWeight: 700 },
  ranks: { display: "flex", gap: 20, marginBottom: 12 },
  rankItem: { display: "flex", flexDirection: "column", alignItems: "center" },
  rankLabel: { fontSize: 11, color: "#a0aec0", fontWeight: 600, textTransform: "uppercase" },
  rankValue: { fontSize: 20, fontWeight: 800, color: "#2d3748" },
  splits: { display: "flex", gap: 8, flexWrap: "wrap", background: "#f7fafc", borderRadius: 8, padding: "10px 14px", marginBottom: 10 },
  split: { display: "flex", flexDirection: "column", alignItems: "center", minWidth: 60 },
  splitLabel: { fontSize: 11, fontWeight: 700, textTransform: "uppercase" },
  splitTime: { fontSize: 14, fontFamily: "monospace", fontWeight: 600, color: "#2d3748" },
  footer: { marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "center" },
  sourceLink: { fontSize: 12, color: "#a0aec0", textDecoration: "none" },
  addedAt: { fontSize: 11, color: "#cbd5e0" },
};
