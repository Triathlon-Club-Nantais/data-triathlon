import { useState, useEffect } from "react";
import ScrapeForm from "./components/ScrapeForm.jsx";
import ResultsList from "./components/ResultsList.jsx";
import ClubView from "./components/ClubView.jsx";
import AdminView from "./components/AdminView.jsx";
import { api } from "./api/client.js";

export default function App() {
  const [tab, setTab] = useState("add");
  const [refreshKey, setRefreshKey] = useState(0);
  const [clubFilter, setClubFilter] = useState(
    () => localStorage.getItem("tcn_club_filter") || "TRIATHLON CLUB NANTAIS"
  );
  const [importStatus, setImportStatus] = useState(null);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    api.listPendingProviders()
      .then((data) => setPendingCount(data.length))
      .catch(() => {});
  }, []);

  function handleSaved({ club, url }) {
    setRefreshKey((k) => k + 1);
    if (club) {
      setClubFilter(club);
      localStorage.setItem("tcn_club_filter", club);
    }
    if (url) {
      setImportStatus("loading");
      api.importEvent(url)
        .then((r) => {
          setImportStatus(r);
          setRefreshKey((k) => k + 1);
          setTab("club");
        })
        .catch(() => setImportStatus("error"));
    }
  }

  return (
    <div style={styles.root}>
      <header style={styles.header}>
        <div style={styles.logo}>
          <span style={styles.logoIcon}>🏊</span>
          <span style={styles.logoIcon}>🚴</span>
          <span style={styles.logoIcon}>🏃</span>
          <span style={styles.logoText}>Triathlon Club — Résultats</span>
        </div>
      </header>

      <nav style={styles.nav}>
        <button
          style={{ ...styles.tab, ...(tab === "add" ? styles.tabActive : {}) }}
          onClick={() => setTab("add")}
        >
          Ajouter un résultat
        </button>
        <button
          style={{ ...styles.tab, ...(tab === "results" ? styles.tabActive : {}) }}
          onClick={() => setTab("results")}
        >
          Tous les résultats
        </button>
        <button
          style={{ ...styles.tab, ...(tab === "club" ? styles.tabActive : {}) }}
          onClick={() => setTab("club")}
        >
          Club TCN
        </button>
        <button
          style={{ ...styles.tab, ...(tab === "admin" ? styles.tabActive : {}), marginLeft: "auto", position: "relative" }}
          onClick={() => setTab("admin")}
        >
          Admin
          {pendingCount > 0 && (
            <span style={styles.badge}>{pendingCount}</span>
          )}
        </button>
      </nav>

      {importStatus && (
        <div style={styles.importBanner}>
          {importStatus === "loading" && "⏳ Import de l'épreuve en cours…"}
          {importStatus === "error" && "⚠️ Import de l'épreuve indisponible pour ce provider."}
          {importStatus?.imported !== undefined && (
            `✅ ${importStatus.imported} participant${importStatus.imported !== 1 ? "s" : ""} importé${importStatus.imported !== 1 ? "s" : ""}, ${importStatus.skipped} déjà présent${importStatus.skipped !== 1 ? "s" : ""}.`
          )}
        </div>
      )}

      <main style={styles.main}>
        {tab === "add" && <ScrapeForm onSaved={handleSaved} />}
        {tab === "results" && <ResultsList refreshKey={refreshKey} />}
        {tab === "club" && <ClubView refreshKey={refreshKey} club={clubFilter} />}
        {tab === "admin" && (
          <AdminView onCountChange={(n) => setPendingCount(n)} />
        )}
      </main>
    </div>
  );
}

const styles = {
  root: { minHeight: "100vh", background: "#f0f4f8" },
  header: { background: "#1e3a5f", padding: "16px 24px", display: "flex", alignItems: "center" },
  logo: { display: "flex", alignItems: "center", gap: 8 },
  logoIcon: { fontSize: 22 },
  logoText: { color: "#fff", fontWeight: 800, fontSize: 20, marginLeft: 8 },
  nav: { background: "#fff", borderBottom: "2px solid #e2e8f0", padding: "0 24px", display: "flex", gap: 4 },
  tab: { padding: "14px 20px", border: "none", background: "none", cursor: "pointer", fontSize: 15, color: "#718096", fontWeight: 600, borderBottom: "3px solid transparent", marginBottom: -2 },
  tabActive: { color: "#3b82f6", borderBottomColor: "#3b82f6" },
  badge: { position: "absolute", top: 8, right: 4, background: "#e53e3e", color: "#fff", borderRadius: "50%", width: 18, height: 18, fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" },
  main: { maxWidth: 900, margin: "0 auto", padding: "28px 16px" },
  importBanner: { background: "#ebf8ff", color: "#2b6cb0", padding: "10px 24px", fontSize: 14, fontWeight: 600, borderBottom: "1px solid #bee3f8" },
};
