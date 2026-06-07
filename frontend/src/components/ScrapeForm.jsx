import { useState, useEffect } from "react";
import { api } from "../api/client.js";
import { EVENT_TYPE_LABELS } from "../constants.js";

// ── Provider detection ────────────────────────────────────────────────────────

const PROVIDERS = [
  {
    id: "breizhchrono",
    label: "Breizh Chrono",
    color: "#0055a4",
    match: (u) => u.includes("breizhchrono.com") && !u.includes("live.breizhchrono.com"),
    guide: {
      steps: [
        "Rends-toi sur resultats.breizhchrono.com",
        "Recherche ta course par nom",
        "Clique sur ta discipline (ex : Triathlon Distance Olympique)",
        "Copie l'URL complète depuis la barre d'adresse",
      ],
      example: "https://resultats.breizhchrono.com/resultats-courses/nom-de-la-course-12345/triathlon-sprint",
      warning: null,
    },
  },
  {
    id: "breizhchrono-live",
    label: "Breizh Chrono (live)",
    color: "#e53e3e",
    match: (u) => u.includes("live.breizhchrono.com"),
    guide: null,
    unsupported: true,
    unsupportedMsg:
      "Les liens live.breizhchrono.com ne sont pas supportés. Reviens quand les résultats définitifs sont publiés sur resultats.breizhchrono.com.",
  },
  {
    id: "wiclax",
    label: "Wiclax / ChronoSmetron",
    color: "#2b6cb0",
    match: (u) =>
      u.includes("wiclax-results.com") ||
      u.includes("chronosmetron.com") ||
      (u.includes("wiclax.com") && u.includes("G-Live")),
    guide: {
      steps: [
        "Ouvre le lien de résultats envoyé par l'organisateur",
        "Assure-toi d'être sur la page générale des résultats (pas ton résultat individuel)",
        "Copie l'URL depuis la barre d'adresse",
      ],
      example: "https://chronosmetron.wiclax-results.com/G-Live/g-live.html?f=../Mon-Triathlon-2025/Triathlon.clax",
      warning: "Si l'URL contient &B=XXXX, retire ce paramètre — il pointe vers un athlète spécifique.",
    },
  },
  {
    id: "klikego",
    label: "Klikego",
    color: "#276749",
    match: (u) => u.includes("klikego.com"),
    guide: {
      steps: [
        "Rends-toi sur klikego.com",
        "Recherche ta course",
        "Clique sur l'épreuve correspondante",
        "Copie l'URL de la page résultats",
      ],
      example: "https://www.klikego.com/resultats/nom-de-la-course/12345?heat=triathlon-m",
      warning: null,
    },
  },
  {
    id: "timepulse",
    label: "TimePulse",
    color: "#744210",
    match: (u) => u.includes("timepulse.fr"),
    guide: {
      steps: [
        "Rends-toi sur timepulse.fr",
        "Trouve ta course dans la liste des événements",
        "Copie l'URL de la page résultats",
      ],
      example: "https://www.timepulse.fr/resultats/12345",
      warning: null,
    },
  },
  {
    id: "prolivesport",
    label: "ProLiveSport",
    color: "#553c9a",
    match: (u) => u.includes("prolivesport.fr"),
    guide: {
      steps: [
        "Rends-toi sur prolivesport.fr",
        "Trouve ta compétition et clique dessus",
        "Copie l'URL de la page (format : prolivesport.fr/result/1079)",
      ],
      example: "https://www.prolivesport.fr/result/1079",
      warning: null,
    },
  },
  {
    id: "sportinnovation",
    label: "Sport Innovation",
    color: "#2c5282",
    match: (u) => u.includes("sportinnovation.fr"),
    guide: {
      steps: [
        "Rends-toi sur sportinnovation.fr",
        "Trouve ta course dans le calendrier",
        "Copie l'URL de la page résultats",
      ],
      example: "https://www.sportinnovation.fr/resultats/nom-course",
      warning: null,
    },
  },
];

function detectProvider(url) {
  if (!url || !url.startsWith("http")) return null;
  return PROVIDERS.find((p) => p.match(url)) || null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(d) {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString("fr-FR", {
      day: "2-digit", month: "short", year: "numeric",
    });
  } catch { return d; }
}

const MANUAL_EMPTY = {
  provider: "manuel", source_url: "",
  athlete_name: "", athlete_firstname: "", club: "", category: "", gender: "",
  bib_number: "", event_name: "", event_date: "", event_type: "",
  rank_overall: null, rank_category: null, rank_gender: null,
  total_time: "", swim_time: "", t1_time: "", bike_time: "", t2_time: "", run_time: "",
  is_relay: false, raw_data: {},
};

const EXTENDED_EVENT_TYPE_OPTIONS = [
  { value: "triathlon-s",  label: "Triathlon S (Sprint)" },
  { value: "triathlon-m",  label: "Triathlon M (Olympique)" },
  { value: "triathlon-l",  label: "Triathlon L (Half)" },
  { value: "triathlon-xl", label: "Triathlon XL (Ironman)" },
  { value: "triathlon",    label: "Triathlon (format inconnu)" },
  { value: "duathlon-xs",  label: "Duathlon XS" },
  { value: "duathlon-s",   label: "Duathlon S" },
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
    { label: "Course 1", field: "swim_time" },
    { label: "T1",       field: "t1_time" },
    { label: "Vélo",     field: "bike_time" },
    { label: "T2",       field: "t2_time" },
    { label: "Course 2", field: "run_time" },
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
  return [
    { label: "Natation",      field: "swim_time" },
    { label: "T1",            field: "t1_time" },
    { label: "Vélo",          field: "bike_time" },
    { label: "T2",            field: "t2_time" },
    { label: "Course à pied", field: "run_time" },
  ];
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ScrapeForm({ onSaved }) {
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState(null);
  const [manualMode, setManualMode] = useState(false);
  const [edited, setEdited] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveAttempted, setSaveAttempted] = useState(false);
  const [error, setError] = useState("");
  const [recentResults, setRecentResults] = useState([]);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    api.listResults({ page_size: 5, page: 1, club: "nantais|TCN" })
      .then(setRecentResults)
      .catch(() => {});
  }, [saved]);

  function handleUrlChange(val) {
    setUrl(val);
    setError("");
    setManualMode(false);
    setEdited(null);
    setSaved(false);
    setPreview(null);
    setProvider(detectProvider(val));
  }

  async function handlePreview() {
    if (!url.trim() || !provider || provider.unsupported) return;
    setPreviewLoading(true);
    setError("");
    try {
      const data = await api.previewImport(url.trim());
      setPreview(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setPreviewLoading(false);
    }
  }

  function handleImport(e) {
    e?.preventDefault();
    if (!url.trim() || !provider || provider.unsupported) return;
    onSaved?.({ url: url.trim() });
    setUrl("");
    setProvider(null);
    setPreview(null);
  }

  function handleManualEntry() {
    setManualMode(true);
    setEdited({ ...MANUAL_EMPTY, source_url: url.trim() });
    setError("");
    try { api.reportPendingProvider(url.trim()); } catch { /* non-blocking */ }
  }

  function handleField(field, value) {
    setEdited((prev) => ({ ...prev, [field]: value }));
  }

  function validateEdited() {
    if (!edited.athlete_name?.trim()) return "Le nom de l'athlète est requis.";
    if (!edited.event_name?.trim()) return "Le nom de l'épreuve est requis.";
    if (!edited.event_type) return "Le type d'épreuve est requis.";
    return null;
  }

  async function handleSave() {
    setSaveAttempted(true);
    const err = validateEdited();
    if (err) { setError(err); return; }
    setSaving(true);
    setError("");
    try {
      await api.saveResult(edited);
      setSaved(true);
      onSaved?.({ club: edited.club, url: null });
      setTimeout(() => {
        setUrl("");
        setProvider(null);
        setManualMode(false);
        setEdited(null);
        setSaved(false);
        setSaveAttempted(false);
      }, 2000);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const showRecent = !provider && !manualMode && !url.trim() && recentResults.length > 0;

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Ajouter des résultats</h2>

      {/* URL input */}
      <form onSubmit={handleImport} style={styles.form}>
        <label style={styles.label}>Lien de résultat</label>
        <div style={styles.row}>
          <input
            style={styles.input}
            type="url"
            placeholder="Colle ici l'URL de ta course (Breizh Chrono, Wiclax, Klikego…)"
            value={url}
            onChange={(e) => handleUrlChange(e.target.value)}
          />
        </div>
      </form>

      {error && <p style={styles.error}>{error}</p>}

      {/* Provider détecté → guide + bouton import */}
      {provider && !manualMode && !saved && (
        <ProviderGuide
          provider={provider}
          onPreview={handlePreview}
          onImport={handleImport}
          onBack={() => setPreview(null)}
          url={url}
          preview={preview}
          previewLoading={previewLoading}
        />
      )}

      {/* Aucun provider reconnu → proposer saisie manuelle */}
      {url.trim() && !provider && !manualMode && (
        <div style={styles.unknownBlock}>
          <p style={styles.unknownText}>
            Ce provider n'est pas encore supporté automatiquement.
          </p>
          <button style={styles.btnManual} onClick={handleManualEntry}>
            Saisir manuellement <span style={styles.lastResort}>(dernier recours)</span>
          </button>
        </div>
      )}

      {/* Formulaire de saisie manuelle */}
      {manualMode && edited && (
        <ManualForm
          edited={edited}
          saving={saving}
          saved={saved}
          saveAttempted={saveAttempted}
          error={error}
          onField={handleField}
          onSave={handleSave}
        />
      )}

      {/* Derniers résultats TCN */}
      {showRecent && (
        <div style={recentStyles.wrapper}>
          <p style={recentStyles.title}>Derniers résultats ajoutés</p>
          {recentResults.map((r) => {
            const name = [r.athlete_firstname, r.athlete_name].filter(Boolean).join(" ");
            return (
              <div key={r.id} style={recentStyles.item}>
                <div style={recentStyles.avatar}>{(r.athlete_name?.[0] || "?").toUpperCase()}</div>
                <div style={recentStyles.info}>
                  <span style={recentStyles.name}>{name || "Inconnu"}</span>
                  <span style={recentStyles.sub}>
                    {r.event_name}
                    {r.event_type && (
                      <span style={recentStyles.pill}>
                        {EVENT_TYPE_LABELS[r.event_type] || r.event_type}
                      </span>
                    )}
                  </span>
                </div>
                {r.total_time && <span style={recentStyles.time}>{r.total_time}</span>}
                <span style={recentStyles.date}>{formatDate(r.event_date)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── ProviderGuide ─────────────────────────────────────────────────────────────

function ProviderGuide({ provider, onPreview, onImport, onBack, url, preview, previewLoading }) {
  if (provider.unsupported) {
    return (
      <div style={{ ...guideStyles.wrapper, borderColor: "#feb2b2", background: "#fff5f5" }}>
        <div style={guideStyles.header}>
          <span style={{ ...guideStyles.badge, background: provider.color }}>{provider.label}</span>
          <span style={{ ...guideStyles.status, color: "#e53e3e" }}>Non supporté</span>
        </div>
        <p style={{ margin: 0, fontSize: 14, color: "#742a2a" }}>{provider.unsupportedMsg}</p>
      </div>
    );
  }

  const { guide } = provider;
  const urlOk = url.trim().startsWith("http") && url.length > 20;

  return (
    <div style={guideStyles.wrapper}>
      <div style={guideStyles.header}>
        <span style={{ ...guideStyles.badge, background: provider.color }}>{provider.label}</span>
        <span style={guideStyles.status}>Provider reconnu</span>
      </div>

      {/* Guide : affiché seulement si pas encore de preview */}
      {!preview && (
        <div style={guideStyles.stepsBlock}>
          <p style={guideStyles.stepsTitle}>Comment trouver l'URL :</p>
          <ol style={guideStyles.stepsList}>
            {guide.steps.map((s, i) => <li key={i} style={guideStyles.step}>{s}</li>)}
          </ol>
          <p style={guideStyles.example}>
            <span style={guideStyles.exampleLabel}>Exemple : </span>
            <code style={guideStyles.exampleCode}>{guide.example}</code>
          </p>
          {guide.warning && <p style={guideStyles.warning}>⚠ {guide.warning}</p>}
        </div>
      )}

      {/* Étape 1 : bouton Vérifier */}
      {!preview && (
        <div style={guideStyles.importBlock}>
          <button
            style={{ ...guideStyles.btnImport, opacity: urlOk && !previewLoading ? 1 : 0.5 }}
            onClick={onPreview}
            disabled={!urlOk || previewLoading}
          >
            {previewLoading ? "Vérification…" : "Vérifier la compétition"}
          </button>
          {!urlOk && <p style={guideStyles.urlHint}>L'URL semble incomplète — suis les étapes ci-dessus.</p>}
        </div>
      )}

      {/* Étape 2 : récapitulatif + confirmation */}
      {preview && <EventPreviewCard preview={preview} onImport={onImport} onBack={onBack} />}
    </div>
  );
}

function EventPreviewCard({ preview, onImport, onBack }) {
  const { event_name, event_date, races = [] } = preview;
  const totalCount = races.reduce((s, r) => s + (r.count ?? 0), 0);

  function formatDate(d) {
    if (!d) return "";
    const m = String(d).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString("fr-FR") : d;
  }

  return (
    <div style={previewCardStyles.wrapper}>
      <p style={previewCardStyles.title}>✅ Compétition trouvée</p>
      <p style={previewCardStyles.eventName}>{event_name || "—"}</p>
      {event_date && <p style={previewCardStyles.date}>📅 {formatDate(event_date)}</p>}

      {races.length > 0 && (
        <div style={previewCardStyles.races}>
          {races.map((r, i) => (
            <div key={i} style={previewCardStyles.raceRow}>
              <span style={previewCardStyles.raceLabel}>{r.label}</span>
              {r.count != null && (
                <span style={previewCardStyles.raceCount}>{r.count} participants</span>
              )}
            </div>
          ))}
        </div>
      )}

      {totalCount > 0 && (
        <p style={previewCardStyles.total}>{totalCount} participants au total</p>
      )}

      <p style={previewCardStyles.info}>
        Les membres TCN présents seront automatiquement ajoutés.
      </p>

      <div style={previewCardStyles.actions}>
        <button style={previewCardStyles.btnBack} onClick={onBack}>← Modifier l'URL</button>
        <button style={previewCardStyles.btnConfirm} onClick={onImport}>Importer la compétition</button>
      </div>
    </div>
  );
}

// ── ManualForm ────────────────────────────────────────────────────────────────

function ManualForm({ edited, saving, saved, saveAttempted, error, onField, onSave }) {
  return (
    <div style={styles.preview}>
      <div style={styles.manualWarning}>
        ⚠ Saisie manuelle — remplissez tous les champs. Un administrateur sera notifié.
      </div>

      <div style={styles.grid}>
        <Field label="Nom"       value={edited.athlete_name}      onChange={(v) => onField("athlete_name", v)} />
        <Field label="Prénom"    value={edited.athlete_firstname}  onChange={(v) => onField("athlete_firstname", v)} />
        <Field label="Club"      value={edited.club}               onChange={(v) => onField("club", v)} />
        <Field label="Dossard"   value={edited.bib_number}         onChange={(v) => onField("bib_number", v)} />
        <Field label="Catégorie" value={edited.category}           onChange={(v) => onField("category", v)} />
        <Field label="Genre"     value={edited.gender}             onChange={(v) => onField("gender", v)} />
      </div>

      <div style={styles.grid}>
        <Field label="Épreuve" value={edited.event_name} onChange={(v) => onField("event_name", v)} />
        <div>
          <label style={styles.fieldLabel}>
            Type d'épreuve <span style={styles.required}>*</span>
          </label>
          <select
            style={{
              ...styles.input, width: "100%",
              borderColor: saveAttempted && !edited.event_type ? "#e53e3e" : undefined,
              boxShadow: saveAttempted && !edited.event_type ? "0 0 0 2px rgba(229,62,62,0.2)" : undefined,
            }}
            value={edited.event_type}
            onChange={(e) => onField("event_type", e.target.value)}
          >
            <option value="">-- choisir --</option>
            {EXTENDED_EVENT_TYPE_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          {saveAttempted && !edited.event_type && (
            <span style={styles.fieldError}>Sélectionnez un format avant d'enregistrer.</span>
          )}
        </div>
        <Field label="Date (AAAA-MM-JJ)" value={edited.event_date || ""} onChange={(v) => onField("event_date", v)} />
        <div style={styles.checkboxField}>
          <label style={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={!!edited.is_relay}
              onChange={(e) => onField("is_relay", e.target.checked)}
              style={styles.checkbox}
            />
            Épreuve en relais
          </label>
        </div>
      </div>

      <div style={styles.timesGrid}>
        <TimeField label="Temps total" value={edited.total_time} onChange={(v) => onField("total_time", v)} />
        {getSplitFields(edited.event_type).map(({ label, field }) => (
          <TimeField key={field} label={label} value={edited[field] || ""} onChange={(v) => onField(field, v)} />
        ))}
      </div>

      <div style={styles.ranksGrid}>
        <TimeField label="Classement général"  value={edited.rank_overall  ?? ""} onChange={(v) => onField("rank_overall",  v ? Number(v) : null)} />
        <TimeField label="Classement catégorie" value={edited.rank_category ?? ""} onChange={(v) => onField("rank_category", v ? Number(v) : null)} />
        <TimeField label="Classement genre"    value={edited.rank_gender   ?? ""} onChange={(v) => onField("rank_gender",   v ? Number(v) : null)} />
      </div>

      {error && <p style={styles.error}>{error}</p>}
      {saved ? (
        <p style={styles.success}>Résultat enregistré !</p>
      ) : (
        <button style={styles.btnSave} onClick={onSave} disabled={saving}>
          {saving ? "Enregistrement…" : "Enregistrer le résultat"}
        </button>
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
        aria-label={label}
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
        aria-label={label}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const guideStyles = {
  wrapper: {
    marginTop: 16, padding: 20, background: "#f0fff4",
    border: "1px solid #9ae6b4", borderRadius: 10,
  },
  header: { display: "flex", alignItems: "center", gap: 10, marginBottom: 16 },
  badge: {
    color: "#fff", borderRadius: 20, padding: "3px 12px",
    fontSize: 12, fontWeight: 700,
  },
  status: { fontSize: 13, color: "#276749", fontWeight: 600 },
  stepsBlock: { marginBottom: 16 },
  stepsTitle: { fontSize: 13, fontWeight: 700, color: "#2d3748", marginBottom: 8 },
  stepsList: { margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 6 },
  step: { fontSize: 13, color: "#4a5568", lineHeight: 1.5 },
  example: { marginTop: 10, fontSize: 12, color: "#718096" },
  exampleLabel: { fontWeight: 600 },
  exampleCode: {
    background: "#edf2f7", padding: "2px 6px", borderRadius: 4,
    fontSize: 11, wordBreak: "break-all",
  },
  warning: {
    marginTop: 8, fontSize: 12, color: "#744210",
    background: "#fffbeb", padding: "6px 10px", borderRadius: 6,
  },
  importBlock: { borderTop: "1px solid #c6f6d5", paddingTop: 14, display: "flex", flexDirection: "column", gap: 8 },
  importInfo: { fontSize: 13, color: "#276749", margin: 0 },
  btnImport: {
    padding: "11px 24px", background: "#276749", color: "#fff",
    border: "none", borderRadius: 7, fontWeight: 700, cursor: "pointer",
    fontSize: 15, alignSelf: "flex-start", transition: "opacity 0.15s",
  },
  urlHint: { fontSize: 12, color: "#718096", margin: 0 },
};

const previewCardStyles = {
  wrapper: { marginTop: 12, padding: "16px 18px", background: "#f7fafc", border: "1px solid #bee3f8", borderRadius: 8 },
  title: { margin: "0 0 6px", fontSize: 13, fontWeight: 700, color: "#2b6cb0" },
  eventName: { margin: "0 0 4px", fontSize: 16, fontWeight: 800, color: "#1a202c" },
  date: { margin: "0 0 12px", fontSize: 13, color: "#4a5568" },
  races: { display: "flex", flexDirection: "column", gap: 4, marginBottom: 10 },
  raceRow: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 10px", background: "#ebf8ff", borderRadius: 5 },
  raceLabel: { fontSize: 13, fontWeight: 700, color: "#2c5282" },
  raceCount: { fontSize: 12, color: "#4a5568" },
  total: { margin: "4px 0 8px", fontSize: 13, fontWeight: 600, color: "#276749" },
  info: { margin: "0 0 14px", fontSize: 12, color: "#718096" },
  actions: { display: "flex", gap: 10 },
  btnBack: { padding: "8px 14px", background: "none", border: "1px solid #cbd5e0", borderRadius: 6, fontSize: 13, cursor: "pointer", color: "#4a5568" },
  btnConfirm: { padding: "10px 22px", background: "#276749", color: "#fff", border: "none", borderRadius: 7, fontWeight: 700, cursor: "pointer", fontSize: 14 },
};

const recentStyles = {
  wrapper: { marginTop: 24, borderTop: "1px solid #f0f0f0", paddingTop: 18 },
  title: { fontSize: 12, fontWeight: 700, color: "#aaa", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12 },
  item: { display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: "1px solid #f5f5f5" },
  avatar: { width: 32, height: 32, borderRadius: "50%", background: "#f0f0f0", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 13, color: "#1a1a1a", flexShrink: 0 },
  info: { flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 },
  name: { fontWeight: 700, fontSize: 14, color: "#1a1a1a" },
  sub: { fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6, overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" },
  pill: { background: "#fff5f0", color: "#e95d0f", borderRadius: 10, padding: "0 7px", fontSize: 11, fontWeight: 600, flexShrink: 0 },
  time: { fontFamily: "monospace", fontWeight: 700, color: "#e95d0f", fontSize: 13, flexShrink: 0 },
  date: { fontSize: 11, color: "#bbb", whiteSpace: "nowrap", flexShrink: 0 },
};

const styles = {
  container: { background: "#fff", borderRadius: 12, padding: 28, marginBottom: 28, boxShadow: "0 1px 4px rgba(0,0,0,0.08)" },
  title: { fontSize: 20, fontWeight: 700, marginBottom: 18, color: "#1a1a1a" },
  form: { marginBottom: 16 },
  label: { display: "block", fontWeight: 600, marginBottom: 6, fontSize: 14 },
  row: { display: "flex", gap: 10 },
  input: { flex: 1, padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14, outline: "none", minWidth: 0 },
  inputMono: { flex: 1, padding: "9px 12px", border: "1px solid #cbd5e0", borderRadius: 7, fontSize: 14, fontFamily: "monospace", outline: "none" },
  error: { color: "#e53e3e", fontSize: 14, marginBottom: 10, marginTop: 0 },
  success: { color: "#276749", fontWeight: 700, marginTop: 16, fontSize: 15 },
  unknownBlock: { marginTop: 12, padding: "14px 16px", background: "#fff5f5", border: "1px solid #feb2b2", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" },
  unknownText: { fontSize: 13, color: "#742a2a", margin: 0, flex: 1 },
  btnManual: { padding: "7px 14px", background: "#fff", border: "1px solid #fc8181", borderRadius: 7, cursor: "pointer", fontSize: 13, color: "#c53030", fontWeight: 600, whiteSpace: "nowrap" },
  lastResort: { fontSize: 11, fontWeight: 400, color: "#e53e3e" },
  preview: { marginTop: 20, padding: 20, background: "#fafafa", borderRadius: 10, border: "1px solid #ebebeb" },
  manualWarning: { background: "#fffbeb", border: "1px solid #f6e05e", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#744210", marginBottom: 14 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 14, marginBottom: 14 },
  timesGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 14, marginBottom: 14 },
  ranksGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 14, marginBottom: 14 },
  fieldLabel: { display: "block", fontSize: 12, fontWeight: 600, color: "#4a5568", marginBottom: 4 },
  required: { color: "#e53e3e" },
  fieldError: { display: "block", fontSize: 11, color: "#e53e3e", marginTop: 4 },
  checkboxField: { display: "flex", alignItems: "center", paddingTop: 20 },
  checkboxLabel: { display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "#4a5568", cursor: "pointer" },
  checkbox: { width: 16, height: 16, cursor: "pointer" },
  btnSave: { marginTop: 20, padding: "11px 24px", background: "#1a1a1a", color: "#fff", border: "none", borderRadius: 7, fontWeight: 700, cursor: "pointer", fontSize: 15 },
};
