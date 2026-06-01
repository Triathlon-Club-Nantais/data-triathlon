import { useState } from "react";
import { api } from "../api/client.js";
import ResultCard from "./ResultCard.jsx";

const EVENT_TYPES = [
  "triathlon-s",
  "triathlon-m",
  "triathlon-l",
  "triathlon-xl",
  "duathlon",
  "swimrun",
];

const PROVIDER_LABELS = {
  breizhchrono: "Breizh Chrono",
  wiclax: "Wiclax / G-Live",
  klikego: "Klikego",
  timepulse: "TimePulse",
  playwright: "Autre (navigateur)",
};

function isKlikego(url) {
  return url.includes("klikego.com");
}

function isTimepulse(url) {
  return url.includes("timepulse.fr");
}

function needsSearch(url) {
  try {
    const p = new URLSearchParams(new URL(url).search);
    if (isKlikego(url)) return !p.get("search");
    if (isTimepulse(url)) return !p.get("bib") && !p.get("search");
  } catch { /* invalid URL */ }
  return false;
}

function providerHint(url) {
  if (isKlikego(url)) return "Klikego";
  if (isTimepulse(url)) return "TimePulse";
  return "";
}

function injectSearch(url, name) {
  try {
    const u = new URL(url);
    u.searchParams.set("search", name.trim());
    return u.toString();
  } catch { return url; }
}

export default function ScrapeForm({ onSaved }) {
  const [url, setUrl] = useState("");
  const [athleteName, setAthleteName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [edited, setEdited] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const showNameField = needsSearch(url);

  async function handleScrape(e) {
    e.preventDefault();
    if (!url.trim()) return;
    let finalUrl = url.trim();
    if (showNameField && athleteName.trim()) {
      finalUrl = injectSearch(finalUrl, athleteName);
    }
    setLoading(true);
    setError("");
    setResult(null);
    setSaved(false);
    try {
      const data = await api.scrape(finalUrl);
      setResult(data);
      setEdited({ ...data });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      await api.saveResult(edited);
      setSaved(true);
      onSaved?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function handleField(field, value) {
    setEdited((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Ajouter un résultat</h2>

      <form onSubmit={handleScrape} style={styles.form}>
        <label style={styles.label}>Lien de résultat</label>
        <div style={styles.row}>
          <input
            style={styles.input}
            type="url"
            placeholder="https://www.klikego.com/resultats/... ou timepulse.fr/..."
            value={url}
            onChange={(e) => { setUrl(e.target.value); setResult(null); }}
            required
          />
          <button style={styles.btnPrimary} type="submit" disabled={loading}>
            {loading ? "Récupération…" : "Récupérer"}
          </button>
        </div>
        {showNameField && (
          <div style={styles.nameHint}>
            <span style={styles.hintIcon}>ℹ</span>
            <span>{providerHint(url)} — saisissez le nom de l'athlète :</span>
            <input
              style={{ ...styles.input, flex: "0 0 220px" }}
              type="text"
              placeholder="ex: ARNOUX"
              value={athleteName}
              onChange={(e) => setAthleteName(e.target.value)}
              required={showNameField}
            />
          </div>
        )}
      </form>

      {error && <p style={styles.error}>{error}</p>}

      {result && edited && (
        <div style={styles.preview}>
          <div style={styles.previewHeader}>
            <span style={styles.badge}>
              {PROVIDER_LABELS[result.provider] || result.provider}
            </span>
            <span style={styles.hint}>Vérifiez et corrigez si besoin</span>
          </div>

          <div style={styles.grid}>
            <Field label="Nom" value={edited.athlete_name} onChange={(v) => handleField("athlete_name", v)} />
            <Field label="Prénom" value={edited.athlete_firstname} onChange={(v) => handleField("athlete_firstname", v)} />
            <Field label="Club" value={edited.club} onChange={(v) => handleField("club", v)} />
            <Field label="Dossard" value={edited.bib_number} onChange={(v) => handleField("bib_number", v)} />
            <Field label="Catégorie" value={edited.category} onChange={(v) => handleField("category", v)} />
            <Field label="Genre" value={edited.gender} onChange={(v) => handleField("gender", v)} />
          </div>

          <div style={styles.grid}>
            <Field label="Épreuve" value={edited.event_name} onChange={(v) => handleField("event_name", v)} />
            <div>
              <label style={styles.fieldLabel}>Type d'épreuve</label>
              <select
                style={{ ...styles.input, width: "100%" }}
                value={edited.event_type}
                onChange={(e) => handleField("event_type", e.target.value)}
              >
                <option value="">-- choisir --</option>
                {EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <Field label="Date (AAAA-MM-JJ)" value={edited.event_date || ""} onChange={(v) => handleField("event_date", v)} />
          </div>

          <div style={styles.timesGrid}>
            <TimeField label="Temps total" value={edited.total_time} onChange={(v) => handleField("total_time", v)} />
            <TimeField label="Natation" value={edited.swim_time} onChange={(v) => handleField("swim_time", v)} />
            <TimeField label="T1" value={edited.t1_time} onChange={(v) => handleField("t1_time", v)} />
            <TimeField label="Vélo" value={edited.bike_time} onChange={(v) => handleField("bike_time", v)} />
            <TimeField label="T2" value={edited.t2_time} onChange={(v) => handleField("t2_time", v)} />
            <TimeField label="Course à pied" value={edited.run_time} onChange={(v) => handleField("run_time", v)} />
          </div>

          <div style={styles.ranksGrid}>
            <TimeField label="Classement général" value={edited.rank_overall ?? ""} onChange={(v) => handleField("rank_overall", v ? Number(v) : null)} />
            <TimeField label="Classement catégorie" value={edited.rank_category ?? ""} onChange={(v) => handleField("rank_category", v ? Number(v) : null)} />
            <TimeField label="Classement genre" value={edited.rank_gender ?? ""} onChange={(v) => handleField("rank_gender", v ? Number(v) : null)} />
          </div>

          {saved ? (
            <p style={styles.success}>Résultat enregistré !</p>
          ) : (
            <button style={styles.btnSave} onClick={handleSave} disabled={saving}>
              {saving ? "Enregistrement…" : "Enregistrer le résultat"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange }) {
  return (
    <div>
      <label style={styles.fieldLabel}>{label}</label>
      <input
        style={{ ...styles.input, width: "100%" }}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

function TimeField({ label, value, onChange }) {
  return (
    <div>
      <label style={styles.fieldLabel}>{label}</label>
      <input
        style={{ ...styles.inputMono, width: "100%" }}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

const styles = {
  container: { background: "#fff", borderRadius: 12, padding: 28, marginBottom: 28, boxShadow: "0 1px 4px rgba(0,0,0,0.08)" },
  title: { fontSize: 20, fontWeight: 700, marginBottom: 18, color: "#1a202c" },
  form: { marginBottom: 16 },
  label: { display: "block", fontWeight: 600, marginBottom: 6, fontSize: 14 },
  row: { display: "flex", gap: 10 },
  input: { flex: 1, padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14, outline: "none", minWidth: 0 },
  nameHint: { display: "flex", alignItems: "center", gap: 10, marginTop: 10, padding: "10px 14px", background: "#ebf8ff", borderRadius: 8, fontSize: 13, color: "#2b6cb0", flexWrap: "wrap" },
  hintIcon: { fontWeight: 700, fontSize: 16 },
  inputMono: { flex: 1, padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14, fontFamily: "monospace", outline: "none" },
  btnPrimary: { padding: "9px 20px", background: "#3b82f6", color: "#fff", border: "none", borderRadius: 7, fontWeight: 600, cursor: "pointer", fontSize: 14, whiteSpace: "nowrap" },
  btnSave: { marginTop: 20, padding: "11px 24px", background: "#10b981", color: "#fff", border: "none", borderRadius: 7, fontWeight: 700, cursor: "pointer", fontSize: 15 },
  error: { color: "#e53e3e", fontSize: 14, marginBottom: 10 },
  success: { color: "#10b981", fontWeight: 700, marginTop: 16, fontSize: 15 },
  preview: { marginTop: 20, padding: 20, background: "#f7fafc", borderRadius: 10, border: "1px solid #e2e8f0" },
  previewHeader: { display: "flex", alignItems: "center", gap: 12, marginBottom: 18 },
  badge: { background: "#ebf8ff", color: "#2b6cb0", borderRadius: 20, padding: "3px 12px", fontSize: 12, fontWeight: 700 },
  hint: { color: "#718096", fontSize: 13 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 14, marginBottom: 14 },
  timesGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 14, marginBottom: 14 },
  ranksGrid: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 14 },
  fieldLabel: { display: "block", fontSize: 12, fontWeight: 600, color: "#4a5568", marginBottom: 4 },
};
