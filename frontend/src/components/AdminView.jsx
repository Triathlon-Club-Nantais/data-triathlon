import { useState, useEffect } from "react";
import { api } from "../api/client.js";

function timeAgo(isoStr) {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "aujourd'hui";
  if (days === 1) return "hier";
  if (days < 30) return `il y a ${days} j`;
  return `il y a ${Math.floor(days / 30)} mois`;
}

export default function AdminView({ onCountChange }) {
  const [pending, setPending] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const data = await api.listPendingProviders();
      setPending(data);
      onCountChange?.(data.length);
    } catch {
      setPending([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleHandle(id) {
    await api.markProviderHandled(id);
    load();
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Administration</h2>

      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Providers non supportés signalés</h3>
        <p style={styles.desc}>
          Ces URLs ont été soumises par des utilisateurs dont le scraping a échoué.
          Elles ont utilisé la saisie manuelle comme dernier recours.
          Implémentez le provider correspondant puis marquez comme traité.
        </p>

        {loading && <p style={styles.loading}>Chargement…</p>}

        {!loading && pending.length === 0 && (
          <p style={styles.empty}>Aucun provider en attente. ✅</p>
        )}

        {pending.map((p) => (
          <div key={p.id} style={styles.card}>
            <div style={styles.cardLeft}>
              <span style={styles.domain}>{p.provider_hint || "domaine inconnu"}</span>
              <a href={p.url} target="_blank" rel="noopener noreferrer" style={styles.url}>
                {p.url.length > 80 ? p.url.slice(0, 80) + "…" : p.url}
              </a>
              <span style={styles.date}>Signalé {timeAgo(p.reported_at)}</span>
            </div>
            <button style={styles.handleBtn} onClick={() => handleHandle(p.id)}>
              Marquer traité
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  container: { maxWidth: 800, margin: "0 auto" },
  title: { fontSize: 22, fontWeight: 800, color: "#1a202c", marginBottom: 20 },
  section: { background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.08)" },
  sectionTitle: { fontSize: 16, fontWeight: 700, color: "#2d3748", marginBottom: 8 },
  desc: { fontSize: 13, color: "#718096", marginBottom: 20, lineHeight: 1.6 },
  loading: { color: "#718096", textAlign: "center", padding: 20 },
  empty: { color: "#10b981", fontWeight: 600, padding: "12px 0" },
  card: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "14px 0", borderBottom: "1px solid #f0f4f8" },
  cardLeft: { flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 },
  domain: { fontWeight: 700, fontSize: 14, color: "#e53e3e" },
  url: { fontSize: 12, color: "#3b82f6", wordBreak: "break-all", textDecoration: "none" },
  date: { fontSize: 11, color: "#a0aec0" },
  handleBtn: { padding: "6px 14px", background: "#10b981", color: "#fff", border: "none", borderRadius: 7, cursor: "pointer", fontSize: 13, fontWeight: 600, whiteSpace: "nowrap" },
};
