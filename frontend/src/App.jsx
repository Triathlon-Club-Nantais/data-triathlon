import { useState, useEffect, useRef } from "react";
import ScrapeForm from "./components/ScrapeForm.jsx";
import ResultsList from "./components/ResultsList.jsx";
import ClubView from "./components/ClubView.jsx";
import AdminView from "./components/AdminView.jsx";
import DashboardView from "./components/DashboardView.jsx";
import { api } from "./api/client.js";

export default function App() {
  const [tab, setTab] = useState("add");
  const [refreshKey, setRefreshKey] = useState(0);
  const [clubFilter, setClubFilter] = useState(() => {
    const stored = localStorage.getItem("tcn_club_filter");
    // Normalize old full-name filters to keywords matching all TCN club name variants:
    // "TRIATHLON CLUB NANTAIS", "TRI CLUB NANTAIS", "TCN", etc.
    if (!stored || stored.toLowerCase().includes("nantais") || stored.toUpperCase() === "TCN") {
      return "nantais|TCN";
    }
    return stored;
  });
  const [importStatus, setImportStatus] = useState(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [globalSearch, setGlobalSearch] = useState("");
  const searchRef = useRef(null);

  useEffect(() => {
    api.listPendingProviders()
      .then((data) => setPendingCount(data.length))
      .catch(() => {});
  }, []);

  async function handleSaved({ club, url }) {
    setRefreshKey((k) => k + 1);
    if (!url) return;
    setImportStatus({ phase: "scraping", message: "Récupération des participants…" });
    try {
      for await (const evt of api.importEventStream(url)) {
        setImportStatus(evt);
        if (evt.phase === "done") {
          setRefreshKey((k) => k + 1);
          setTab("club");
        }
      }
    } catch {
      setImportStatus({ phase: "error", message: "Import indisponible pour ce provider." });
    }
  }

  return (
    <div style={styles.root}>
      <header style={styles.header} className="app-header">
        <div style={styles.logo}>
          <span style={styles.logoIcon}>🏊</span>
          <span style={styles.logoIcon}>🚴</span>
          <span style={styles.logoIcon}>🏃</span>
          <span style={styles.logoText}>Triathlon Club — Résultats</span>
        </div>
        <form
          className="global-search"
          onSubmit={(e) => { e.preventDefault(); if (globalSearch.trim()) { setTab("results"); } }}
        >
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="white" strokeWidth="2.5">
            <circle cx="8.5" cy="8.5" r="5.5"/><path d="M14 14l4 4"/>
          </svg>
          <input
            ref={searchRef}
            placeholder="Rechercher un athlète…"
            value={globalSearch}
            onChange={(e) => { setGlobalSearch(e.target.value); if (e.target.value) setTab("results"); }}
          />
          {globalSearch && (
            <button type="button" onClick={() => { setGlobalSearch(""); searchRef.current?.focus(); }}
              style={{ background: "none", border: "none", color: "rgba(255,255,255,0.7)", cursor: "pointer", padding: 0, fontSize: 16, lineHeight: 1 }}>
              ×
            </button>
          )}
        </form>
      </header>

      <nav style={styles.nav} className="app-nav">
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
          style={{ ...styles.tab, ...(tab === "dashboard" ? styles.tabActive : {}) }}
          onClick={() => setTab("dashboard")}
        >
          Dashboard
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

      {importStatus && <ImportBanner status={importStatus} onClose={() => setImportStatus(null)} />}

      <main style={styles.main} className="app-main">
        {tab === "add"       && <ScrapeForm onSaved={handleSaved} />}
        {tab === "results"   && <ResultsList refreshKey={refreshKey} initialSearch={globalSearch} />}
        {tab === "club"      && <ClubView refreshKey={refreshKey} club={clubFilter} />}
        {tab === "dashboard" && <DashboardView />}
        {tab === "admin" && (
          <AdminView onCountChange={(n) => setPendingCount(n)} />
        )}
      </main>
    </div>
  );
}

function ImportBanner({ status, onClose }) {
  const { phase, total, imported = 0, skipped = 0, progress = 0, message } = status;
  const pct = total ? Math.round((progress / total) * 100) : 0;

  return (
    <div style={bannerStyles.wrapper}>
      <div style={bannerStyles.content}>
        {phase === "scraping" && <><span style={bannerStyles.spin}>⏳</span> {message}</>}
        {phase === "saving" && (
          <>
            <span>⬇️ Import en cours…</span>
            <div style={bannerStyles.barTrack}>
              <div style={{ ...bannerStyles.barFill, width: `${pct}%` }} />
            </div>
            <span style={bannerStyles.counter}>{imported} importé{imported !== 1 ? "s" : ""} · {skipped} déjà présent{skipped !== 1 ? "s" : ""} · {progress}/{total}</span>
          </>
        )}
        {phase === "done" && <>✅ {imported} participant{imported !== 1 ? "s" : ""} importé{imported !== 1 ? "s" : ""}, {skipped} déjà présent{skipped !== 1 ? "s" : ""}.</>}
        {phase === "error" && <>⚠️ {message}</>}
      </div>
      {(phase === "done" || phase === "error") && (
        <button onClick={onClose} style={bannerStyles.close}>×</button>
      )}
    </div>
  );
}

const bannerStyles = {
  wrapper: { background: "#fff5f0", borderBottom: "1px solid #ffd5bf", padding: "10px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 },
  content: { display: "flex", alignItems: "center", gap: 12, fontSize: 14, fontWeight: 600, color: "#c4500d", flex: 1 },
  barTrack: { flex: "1 1 120px", maxWidth: 220, height: 6, background: "#ffd5bf", borderRadius: 3, overflow: "hidden" },
  barFill:  { height: "100%", background: "#e95d0f", borderRadius: 3, transition: "width 0.3s" },
  counter:  { fontSize: 12, color: "#888", fontWeight: 400, whiteSpace: "nowrap" },
  close:    { background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#aaa", padding: "0 4px", lineHeight: 1 },
  spin:     {},
};

const styles = {
  root: { minHeight: "100vh", background: "#f5f5f5" },
  header: { background: "#1a1a1a", padding: "14px 24px", display: "flex", alignItems: "center", gap: 16 },
  logo: { display: "flex", alignItems: "center", gap: 8 },
  logoIcon: { fontSize: 22 },
  logoText: { color: "#fff", fontWeight: 800, fontSize: 20, marginLeft: 8, letterSpacing: "-0.01em" },
  nav: { background: "#fff", borderBottom: "2px solid #e8e8e8", padding: "0 24px", display: "flex", gap: 4 },
  tab: { padding: "14px 20px", border: "none", background: "none", cursor: "pointer", fontSize: 15, color: "#6b6b6b", fontWeight: 600, borderBottom: "3px solid transparent", marginBottom: -2 },
  tabActive: { color: "#e95d0f", borderBottomColor: "#e95d0f" },
  badge: { position: "absolute", top: 8, right: 4, background: "#e95d0f", color: "#fff", borderRadius: "50%", width: 18, height: 18, fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" },
  main: { maxWidth: 900, margin: "0 auto", padding: "28px 16px" },
};
