import { useState, useEffect, useRef } from "react";
import { api } from "../api/client.js";
import { EVENT_TYPE_LABELS } from "../constants.js";

const POLL_MS = 15_000;
const TCN_FILTER = "nantais|TCN";

function timeAgo(isoStr) {
  if (!isoStr) return "";
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60)   return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400)return `il y a ${Math.floor(diff / 3600)} h`;
  return `il y a ${Math.floor(diff / 86400)} j`;
}

export default function ResultsFeed() {
  const [items,   setItems]   = useState([]);
  const [tick,    setTick]    = useState(0);
  const [pulse,   setPulse]   = useState(false);
  const prevIds = useRef(new Set());

  useEffect(() => {
    async function poll() {
      try {
        const data = await api.listResults({ page_size: 20, page: 1, club: TCN_FILTER });
        const newIds = new Set(data.map(r => r.id));
        const hasNew = data.some(r => !prevIds.current.has(r.id));
        if (hasNew) setPulse(true);
        prevIds.current = newIds;
        setItems(data);
      } catch { /* silent */ }
    }

    poll();
    const id = setInterval(() => { poll(); setTick(t => t + 1); }, POLL_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (pulse) {
      const t = setTimeout(() => setPulse(false), 1500);
      return () => clearTimeout(t);
    }
  }, [pulse]);

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <h3 style={styles.title}>Derniers résultats ajoutés</h3>
        <span style={{ ...styles.dot, background: pulse ? "#10b981" : "#94a3b8" }} title="Mise à jour toutes les 15 s" />
      </div>

      {items.length === 0 && <p style={styles.empty}>Aucun résultat encore. Ajoutez-en un !</p>}

      <div style={styles.list}>
        {items.map((r) => {
          const fullName = [r.athlete_firstname, r.athlete_name].filter(Boolean).join(" ");
          const type = EVENT_TYPE_LABELS[r.event_type] || r.event_type || "";

          return (
            <div key={r.id} style={styles.item}>
              <div style={styles.avatar}>
                {(r.athlete_name?.[0] || "?").toUpperCase()}
              </div>
              <div style={styles.info}>
                <div style={styles.row}>
                  <span style={styles.name}>{fullName || "Athlète inconnu"}</span>
                  {r.total_time && <span style={styles.time}>{r.total_time}</span>}
                </div>
                <div style={styles.sub}>
                  <span style={styles.event}>{r.event_name || "Épreuve inconnue"}</span>
                  {type && <span style={styles.typePill}>{type}</span>}
                </div>
              </div>
              <span style={styles.ago}>{timeAgo(r.scraped_at)}</span>
            </div>
          );
        })}
      </div>

      <div style={styles.footer}>
        Mis à jour toutes les 15 s · {items.length} résultat{items.length > 1 ? "s" : ""}
      </div>
    </div>
  );
}

const styles = {
  wrapper: { background: "#fff", borderRadius: 8, padding: "16px 20px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", marginBottom: 16 },
  header:  { display: "flex", alignItems: "center", gap: 10, marginBottom: 12 },
  title:   { fontSize: 13, fontWeight: 700, color: "#1a1a1a", textTransform: "uppercase", letterSpacing: "0.07em", margin: 0, flex: 1 },
  dot:     { width: 10, height: 10, borderRadius: "50%", flexShrink: 0, transition: "background 0.5s" },

  list:  { display: "flex", flexDirection: "column", gap: 8 },
  item:  { display: "flex", alignItems: "center", gap: 12, padding: "8px 10px", borderRadius: 6, background: "#fff8f5", borderLeft: "3px solid #e95d0f" },

  avatar: {
    width: 36, height: 36, borderRadius: "50%", background: "#f0f0f0",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontWeight: 800, fontSize: 15, color: "#1a1a1a", flexShrink: 0,
  },
  info:  { flex: 1, minWidth: 0 },
  row:   { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  name:  { fontWeight: 700, fontSize: 14, color: "#1a1a1a" },
  time:  { fontFamily: "monospace", fontWeight: 700, color: "#e95d0f", fontSize: 13 },
  sub:   { display: "flex", alignItems: "center", gap: 6, marginTop: 2, flexWrap: "wrap" },
  event: { fontSize: 12, color: "#888", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 260 },
  typePill: { background: "#f5f5f5", color: "#555", borderRadius: 10, padding: "1px 7px", fontSize: 11, flexShrink: 0 },
  ago:   { fontSize: 11, color: "#bbb", whiteSpace: "nowrap", flexShrink: 0 },

  empty:  { color: "#bbb", textAlign: "center", padding: 20 },
  footer: { fontSize: 11, color: "#bbb", textAlign: "right", marginTop: 10 },
};
