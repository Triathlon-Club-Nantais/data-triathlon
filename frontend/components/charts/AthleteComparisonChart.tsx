"use client";

import { useEffect, useState } from "react";
import { Card, Eyebrow, Input } from "@/components/tcn";
import { useDebounce } from "@/hooks/useDebounce";
import { apiClient } from "@/lib/api/client";
import type { AthleteSearchResult, Participation } from "@/lib/types";
import { commonParticipations, formatDelta } from "@/lib/utils/athlete-comparison";
import { formatDate } from "@/lib/utils/date";

// Chaque barre n'est qu'un simple rectangle de largeur proportionnelle : pas
// besoin du patron SVG « géométrie dans le SVG, texte en HTML » (#480,
// RESP-2), réservé aux tracés continus (Histogram, RankingEvolutionChart).
// Ici la grille CSS suffit et garde les libellés, valeurs et l'écart en HTML
// natif — lisibles à l'écran, pas seulement à la synthèse vocale (#689).
const LABEL_COL = "76px";
const VALUE_COL = "72px";
const BAR_HEIGHT = 14;
const GRID_COLS = `${LABEL_COL} 1fr ${VALUE_COL}`;

// Zéro-paddée façon chrono (« 01:05:45 »), distincte de la durée compacte
// « 1 h 05 min » de `formatDelta` (lib/utils/athlete-comparison.ts) : l'une
// affiche un temps de course absolu, l'autre un écart entre deux temps — pas
// le même besoin, donc pas la même forme ni le même appelant.
function formatSeconds(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

function BarRow({ name, seconds, maxSeconds, color }: { name: string; seconds: number; maxSeconds: number; color: string }) {
  const pct = maxSeconds > 0 ? Math.min(100, (seconds / maxSeconds) * 100) : 0;
  return (
    <div style={{ display: "grid", gridTemplateColumns: GRID_COLS, gap: 8, alignItems: "center", marginBottom: 4 }}>
      <span
        style={{
          fontSize: 12,
          color: "var(--tcn-text-muted)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={name}
      >
        {name}
      </span>
      <span
        style={{
          height: BAR_HEIGHT,
          borderRadius: 4,
          background: "var(--tcn-border-faint)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <span style={{ position: "absolute", inset: 0, width: `${pct}%`, background: color, borderRadius: 4 }} />
      </span>
      <span
        style={{
          fontSize: 12,
          fontVariantNumeric: "tabular-nums",
          color: "var(--tcn-ink)",
          textAlign: "right",
        }}
      >
        {formatSeconds(seconds)}
      </span>
    </div>
  );
}

/**
 * Comparaison visuelle de deux athlètes sur leurs épreuves communes
 * (US6, #466) — une paire de barres par épreuve, temps le plus court en
 * premier. Nom de l'épreuve, temps et écart chiffré sont visibles en clair
 * (#689) : jusque-là seule la longueur des barres portait l'information,
 * réservant tout le reste (temps, nom d'épreuve) à l'`aria-label` et à une
 * liste `sr-only`, invisibles à l'écran. Composant présentationnel pur,
 * testable indépendamment du sélecteur d'athlète qui l'alimente.
 */
export function AthleteComparisonResult({
  mine,
  theirs,
  theirsName,
}: {
  mine: Participation[];
  theirs: Participation[];
  theirsName: string;
}) {
  const common = commonParticipations(mine, theirs);

  if (common.length === 0) {
    return (
      <p className="py-4 text-sm text-[var(--tcn-text-faint)]">
        Aucune épreuve commune avec {theirsName} pour l&apos;instant.
      </p>
    );
  }

  const rows = common.filter((r) => r.mineSeconds != null && r.theirsSeconds != null);
  if (rows.length === 0) {
    return (
      <p className="py-4 text-sm text-[var(--tcn-text-faint)]">
        {common.length} épreuve{common.length > 1 ? "s" : ""} en commun avec {theirsName}, mais aucun temps
        exploitable pour comparer.
      </p>
    );
  }

  const maxSeconds = Math.max(...rows.flatMap((r) => [r.mineSeconds ?? 0, r.theirsSeconds ?? 0]));

  return (
    <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Repère min/max de l'échelle commune à toutes les paires (#689, point 4). */}
      <div style={{ display: "grid", gridTemplateColumns: GRID_COLS, gap: 8 }}>
        <span />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--tcn-text-faint)" }}>
          <span>{formatSeconds(0)}</span>
          <span>{formatSeconds(maxSeconds)}</span>
        </div>
        <span />
      </div>

      {rows.map((r) => {
        const mineSeconds = r.mineSeconds ?? 0;
        const theirsSeconds = r.theirsSeconds ?? 0;
        return (
          <div key={r.courseId}>
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: "var(--tcn-ink)" }}>{r.courseName}</span>
              {r.eventDate && (
                <span style={{ marginLeft: 8, fontSize: 12, color: "var(--tcn-text-faint)" }}>
                  {formatDate(r.eventDate)}
                </span>
              )}
            </div>
            <BarRow name="Vous" seconds={mineSeconds} maxSeconds={maxSeconds} color="var(--tcn-orange)" />
            <BarRow name={theirsName} seconds={theirsSeconds} maxSeconds={maxSeconds} color="var(--tcn-ink-3)" />
            {/* Même grille que `BarRow` et le repère min/max ci-dessus (cellule de
                gauche vide) plutôt qu'un `marginLeft: LABEL_COL` : ce dernier
                ignorait le `gap` de la grille et désalignait l'écart de 8px par
                rapport aux barres (revue de #689). */}
            <div style={{ display: "grid", gridTemplateColumns: GRID_COLS, gap: 8, marginTop: 4 }}>
              <span />
              <p style={{ fontSize: 12, fontWeight: 600, color: "var(--tcn-text-muted)" }}>
                Écart : {formatDelta(mineSeconds, theirsSeconds)}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

type Etat = "idle" | "chargement" | "ok" | "echec";

/**
 * Sélecteur d'un second athlète du club + comparaison sur épreuve commune
 * (US6, « Comment je me compare à un coéquipier ? », #466).
 *
 * Réutilise `GET /athletes/search` (#484, déjà public) plutôt que
 * `listParticipations` filtré : c'est la même route que la palette ⌘K, et
 * `GET /athletes/{id}` rend déjà toutes les participations de l'athlète
 * choisi en un seul appel — pas de nouveau contrat API pour cette US.
 */
export function AthleteComparisonChart({ mine }: { mine: Participation[] }) {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);
  const [results, setResults] = useState<AthleteSearchResult[]>([]);
  const [selected, setSelected] = useState<AthleteSearchResult | null>(null);
  const [theirs, setTheirs] = useState<Participation[]>([]);
  const [etat, setEtat] = useState<Etat>("idle");

  const search = debouncedQuery.trim();

  useEffect(() => {
    if (search.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResults([]);
      return;
    }
    let annule = false;
    apiClient
      .searchAthletes(search)
      .then((data) => {
        if (!annule) setResults(data);
      })
      .catch(() => {
        if (!annule) setResults([]);
      });
    return () => {
      annule = true;
    };
  }, [search]);

  function choisir(athlete: AthleteSearchResult) {
    setSelected(athlete);
    setResults([]);
    setQuery("");
    setEtat("chargement");
    apiClient
      .getAthlete(athlete.id)
      .then((detail) => {
        setTheirs(detail.participations);
        setEtat("ok");
      })
      .catch(() => setEtat("echec"));
  }

  return (
    // Pas de marge inline ici : l'espacement avec les cartes voisines de
    // `/athletes/[id]` vient du `space-y-6` posé par la page (#654) — une
    // marge locale y ferait à nouveau cumuler deux systèmes.
    <Card>
      <Eyebrow>Comparer avec un coéquipier</Eyebrow>

      {!selected && (
        <div style={{ marginTop: 8 }}>
          <Input
            type="search"
            placeholder="Chercher un athlète du club…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Chercher un athlète à comparer"
          />
          {results.length > 0 && (
            <ul style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
              {results.map((athlete) => (
                <li key={athlete.id}>
                  <button
                    type="button"
                    onClick={() => choisir(athlete)}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "6px 8px",
                      borderRadius: 6,
                      fontSize: 14,
                    }}
                    className="tcn-comparaison-lien hover:bg-accent"
                  >
                    {athlete.prenom} {athlete.nom}
                    {athlete.club ? ` · ${athlete.club}` : ""}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {selected && etat === "chargement" && (
        <p className="py-4 text-sm text-[var(--tcn-text-faint)]">Chargement…</p>
      )}

      {selected && etat === "echec" && (
        <p className="py-4 text-sm text-[var(--tcn-text-faint)]">
          Impossible de charger les résultats de {selected.prenom} {selected.nom} pour l&apos;instant.
        </p>
      )}

      {selected && etat === "ok" && (
        <>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
            <span style={{ fontSize: 14, color: "var(--tcn-text-muted)" }}>
              Comparaison avec {selected.prenom} {selected.nom}
            </span>
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                setTheirs([]);
                setEtat("idle");
              }}
              className="tcn-comparaison-lien text-sm font-semibold text-accent-ink hover:underline"
            >
              Changer
            </button>
          </div>
          <AthleteComparisonResult mine={mine} theirs={theirs} theirsName={`${selected.prenom} ${selected.nom}`} />
        </>
      )}
    </Card>
  );
}
