import { useState } from "react";
import ScrapeForm from "./components/ScrapeForm.jsx";
import ResultsList from "./components/ResultsList.jsx";

export default function App() {
  const [tab, setTab] = useState("add");
  const [refreshKey, setRefreshKey] = useState(0);

  function handleSaved() {
    setRefreshKey((k) => k + 1);
    // Switch to results tab after a short delay so the user sees the success message
    setTimeout(() => setTab("results"), 1200);
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
      </nav>

      <main style={styles.main}>
        {tab === "add" && <ScrapeForm onSaved={handleSaved} />}
        {tab === "results" && <ResultsList refreshKey={refreshKey} />}
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
  main: { maxWidth: 900, margin: "0 auto", padding: "28px 16px" },
};
