import { useState } from "react";
import { api } from "../api/client.js";
import { EVENT_TYPE_OPTIONS } from "../constants.js";

const EXTENDED_EVENT_TYPE_OPTIONS = [
  { value: "triathlon-s",  label: "Triathlon S (Sprint)" },
  { value: "triathlon-m",  label: "Triathlon M (Olympique)" },
  { value: "triathlon-l",  label: "Triathlon L (Half)" },
  { value: "triathlon-xl", label: "Triathlon XL (Ironman)" },
  { value: "triathlon",    label: "Triathlon (format inconnu)" },
  { value: "duathlon-xs",  label: "Duathlon XS" },
  { value: "duathlon-s",   label: "Duathlon S (Sprint)" },
  { value: "duathlon-m",   label: "Duathlon M" },
  { value: "duathlon-l",   label: "Duathlon L" },
  { value: "duathlon",     label: "Duathlon (format inconnu)" },
  { value: "swimrun-s",    label: "SwimRun S" },
  { value: "swimrun-m",    label: "SwimRun M" },
  { value: "swimrun-l",    label: "SwimRun L" },
  { value: "swimrun",      label: "SwimRun (format inconnu)" },
  { value: "aquathlon",    label: "Aquathlon" },
  { value: "aquarun",      label: "Aquarun" },
  { value: "bike-run",     label: "Bike & Run" },
];

function getSplitFields(eventType) {
  const t = (eventType || "").toLowerCase();

  if (t.startsWith("duathlon")) return [
    { label: "Course 1",  field: "swim_time" },   // slot swim = run1 (pas de natation)
    { label: "T1",        field: "t1_time" },
    { label: "Vélo",      field: "bike_time" },
    { label: "T2",        field: "t2_time" },
    { label: "Course 2",  field: "run_time" },
  ];

  if (t === "bike-run") return [
    { label: "Vélo",   field: "bike_time" },
    { label: "Course", field: "run_time" },
  ];

  if (t === "aquathlon") return [
    { label: "Natation", field: "swim_time" },
    { label: "Course",   field: "run_time" },
  ];

  if (t === "aquarun") return [
    { label: "Natation", field: "swim_time" },
    { label: "T1",       field: "t1_time" },
    { label: "Course",   field: "run_time" },
  ];

  if (t.startsWith("swimrun")) return [
    { label: "Natation", field: "swim_time" },
    { label: "Course",   field: "run_time" },
  ];

  // Triathlon (tous formats) + fallback type inconnu
  return [
    { label: "Natation",      field: "swim_time" },
    { label: "T1",            field: "t1_time" },
    { label: "Vélo",          field: "bike_time" },
    { label: "T2",            field: "t2_time" },
    { label: "Course à pied", field: "run_time" },
  ];
}

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

function isBreizhchrono(url) {
  return url.includes("breizhchrono.com");
}

function isTimepulse(url) {
  return url.includes("timepulse.fr");
}

function isWiclax(url) {
  return url.includes("wiclax-results.com")
    || (url.includes("wiclax.com") && url.includes("G-Live"))
    || url.includes("chronosmetron.com");
}

function needsSearch(url) {
  try {
    const p = new URLSearchParams(new URL(url).search);
    if (isKlikego(url) || isBreizhchrono(url)) return !p.get("search");
    if (isTimepulse(url)) return !p.get("bib") && !p.get("search");
    if (isWiclax(url)) return !p.get("B") && !p.get("b") && !p.get("search") && !p.get("f");
  } catch { /* invalid URL */ }
  return false;
}

function providerHint(url) {
  if (isKlikego(url)) return "Klikego";
  if (isBreizhchrono(url)) return "Breizh Chrono";
  if (isTimepulse(url)) return "TimePulse";
  if (isWiclax(url)) return "Wiclax";
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
  const [candidates, setCandidates] = useState(null);
  const [result, setResult] = useState(null);
  const [edited, setEdited] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [manualMode, setManualMode] = useState(false);

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
    setCandidates(null);
    setSaved(false);
    setManualMode(false);
    try {
      const data = await api.scrape(finalUrl);
      if (data.multiple_matches) {
        setCandidates({ list: data.candidates, url: finalUrl });
      } else {
        setResult(data);
        setEdited({ ...data });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectCandidate(bib) {
    const candidate = candidates.list.find(c => c.bib === bib);
    const savedCandidates = candidates;
    setLoading(true);
    setError("");
    setCandidates(null);
    try {
      const data = await api.scrape(savedCandidates.url, bib);
      if (candidate) {
        if (!data.athlete_name) data.athlete_name = candidate.athlete_name;
        if (!data.athlete_firstname) data.athlete_firstname = candidate.athlete_firstname;
      }
      setResult(data);
      setEdited({ ...data });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function validateEdited() {
    if (!edited.athlete_name?.trim()) return "Le nom de l'athlète est requis.";
    if (!edited.event_name?.trim()) return "Le nom de l'épreuve est requis.";
    if (!edited.event_type) return "Le type d'épreuve est requis.";
    return null;
  }

  async function handleSave() {
    const validationError = validateEdited();
    if (validationError) { setError(validationError); return; }
    setSaving(true);
    setError("");
    try {
      await api.saveResult(edited);
      setSaved(true);
      onSaved?.({ club: edited.club, url: url.trim() });
      // Reset form after short delay so user sees the success message
      setTimeout(() => {
        setUrl("");
        setAthleteName("");
        setResult(null);
        setEdited(null);
        setCandidates(null);
        setSaved(false);
        setManualMode(false);
      }, 2000);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleManualEntry() {
    setManualMode(true);
    setError("");
    const empty = {
      provider: "manuel", source_url: url.trim(),
      athlete_name: "", athlete_firstname: "", club: "", category: "", gender: "",
      bib_number: "", event_name: "", event_date: "", event_type: "",
      rank_overall: null, rank_category: null, rank_gender: null,
      total_time: "", swim_time: "", t1_time: "", bike_time: "", t2_time: "", run_time: "",
      is_relay: false, raw_data: {},
    };
    setResult(empty);
    setEdited({ ...empty });
    // Notify backend
    try { await api.reportPendingProvider(url.trim()); } catch { /* non-blocking */ }
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

      {error && (
        <div style={styles.errorBlock}>
          <p style={styles.error}>{error}</p>
          {!result && url.trim() && (
            <div style={styles.manualHint}>
              <span style={styles.manualHintText}>
                Ce provider n'est pas encore supporté ou le scraping a échoué.
              </span>
              <button style={styles.btnManual} onClick={handleManualEntry}>
                Saisir manuellement <span style={styles.lastResort}>(dernier recours)</span>
              </button>
            </div>
          )}
        </div>
      )}

      {candidates && (
        <div style={styles.candidates}>
          <p style={styles.candidatesTitle}>
            Plusieurs athlètes trouvés — sélectionnez le bon :
          </p>
          {candidates.list.map((c) => (
            <button
              key={c.bib}
              style={styles.candidateBtn}
              onClick={() => handleSelectCandidate(c.bib)}
            >
              <span style={styles.candidateName}>{c.athlete_name} {c.athlete_firstname}</span>
              <span style={styles.candidateMeta}>
                {c.total_time && <span>⏱ {c.total_time}</span>}
                {c.club && <span> · {c.club}</span>}
                <span style={styles.candidateBib}> · Dossard {c.bib}</span>
              </span>
            </button>
          ))}
        </div>
      )}

      {result && edited && (
        <div style={styles.preview}>
          {manualMode && (
            <div style={styles.manualWarning}>
              ⚠️ Saisie manuelle — remplissez tous les champs. Un administrateur sera notifié pour implémenter ce provider.
            </div>
          )}
          <div style={styles.previewHeader}>
            <span style={styles.badge}>
              {manualMode ? "Saisie manuelle" : (PROVIDER_LABELS[result.provider] || result.provider)}
            </span>
            <span style={styles.hint}>{manualMode ? "Remplissez tous les champs" : "Vérifiez et corrigez si besoin"}</span>
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
                {EXTENDED_EVENT_TYPE_OPTIONS.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <Field label="Date (AAAA-MM-JJ)" value={edited.event_date || ""} onChange={(v) => handleField("event_date", v)} />
            <div style={styles.checkboxField}>
              <label style={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={!!edited.is_relay}
                  onChange={(e) => handleField("is_relay", e.target.checked)}
                  style={styles.checkbox}
                />
                Épreuve en relais
              </label>
            </div>
          </div>

          <div style={styles.timesGrid}>
            <TimeField label="Temps total" value={edited.total_time} onChange={(v) => handleField("total_time", v)} />
            {getSplitFields(edited.event_type).map(({ label, field }) => (
              <TimeField key={field} label={label} value={edited[field] || ""} onChange={(v) => handleField(field, v)} />
            ))}
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
  hint: { color: "#718096", fontSize: 13, marginTop: 8 },
  error: { color: "#e53e3e", fontSize: 14, marginBottom: 10 },
  success: { color: "#10b981", fontWeight: 700, marginTop: 16, fontSize: 15 },
  preview: { marginTop: 20, padding: 20, background: "#f7fafc", borderRadius: 10, border: "1px solid #e2e8f0" },
  previewHeader: { display: "flex", alignItems: "center", gap: 12, marginBottom: 18 },
  badge: { background: "#ebf8ff", color: "#2b6cb0", borderRadius: 20, padding: "3px 12px", fontSize: 12, fontWeight: 700 },
  hint: { color: "#718096", fontSize: 13 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 14, marginBottom: 14 },
  timesGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 14, marginBottom: 14 },
  ranksGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 14, marginBottom: 14 },
  fieldLabel: { display: "block", fontSize: 12, fontWeight: 600, color: "#4a5568", marginBottom: 4 },
  checkboxField: { display: "flex", alignItems: "center", paddingTop: 20 },
  checkboxLabel: { display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "#4a5568", cursor: "pointer" },
  checkbox: { width: 16, height: 16, cursor: "pointer" },
  errorBlock: { marginBottom: 10 },
  manualHint: { marginTop: 8, padding: "10px 14px", background: "#fff5f5", border: "1px solid #feb2b2", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" },
  manualHintText: { fontSize: 13, color: "#742a2a", flex: 1 },
  btnManual: { padding: "7px 14px", background: "#fff", border: "1px solid #fc8181", borderRadius: 7, cursor: "pointer", fontSize: 13, color: "#c53030", fontWeight: 600, whiteSpace: "nowrap" },
  lastResort: { fontSize: 11, fontWeight: 400, color: "#e53e3e" },
  manualWarning: { background: "#fffbeb", border: "1px solid #f6e05e", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#744210", marginBottom: 14 },
  candidates: { marginTop: 16, padding: "16px 20px", background: "#fffbeb", border: "1px solid #f6e05e", borderRadius: 10 },
  candidatesTitle: { fontWeight: 700, fontSize: 14, color: "#744210", marginBottom: 12 },
  candidateBtn: { display: "flex", flexDirection: "column", alignItems: "flex-start", width: "100%", padding: "10px 14px", marginBottom: 8, background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, cursor: "pointer", textAlign: "left", transition: "border-color 0.15s" },
  candidateName: { fontWeight: 700, fontSize: 15, color: "#1a202c" },
  candidateMeta: { fontSize: 13, color: "#718096", marginTop: 2 },
  candidateBib: { color: "#a0aec0" },
};
