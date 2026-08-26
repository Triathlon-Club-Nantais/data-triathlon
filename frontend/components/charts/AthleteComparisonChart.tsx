"use client";

import { useEffect, useState } from "react";
import { scaleLinear } from "d3-scale";
import { Card, Eyebrow, Input } from "@/components/tcn";
import { useDebounce } from "@/hooks/useDebounce";
import { apiClient } from "@/lib/api/client";
import type { AthleteSearchResult, Participation } from "@/lib/types";
import { commonParticipations } from "@/lib/utils/athlete-comparison";
import { formatDate } from "@/lib/utils/date";

// Même système de coordonnées que `ProgressionChart` : SVG à `viewBox` fixe
// étiré à 100%, labels en HTML (#480, RESP-2).
const W = 900;
const BAR_HEIGHT = 22;
const BAR_GAP = 34;
const TOP = 8;
const LEFT = 4;
const RIGHT = 4;
const LABEL_GUTTER = 22;

function formatSeconds(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

/**
 * Comparaison visuelle de deux athlètes sur leurs épreuves communes
 * (US6, #466) — un mini-diagramme en barres par épreuve, temps le plus court
 * en premier. Composant présentationnel pur, testable indépendamment du
 * sélecteur d'athlète qui l'alimente.
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
  const xScale = scaleLinear().domain([0, maxSeconds]).range([0, W - LEFT - RIGHT]);
  const H = TOP + rows.length * (2 * BAR_HEIGHT + BAR_GAP);

  const summary = rows
    .map(
      (r) =>
        `${formatDate(r.eventDate)} : vous ${formatSeconds(r.mineSeconds ?? 0)}, ${theirsName} ${formatSeconds(r.theirsSeconds ?? 0)}`,
    )
    .join(" ; ");

  return (
    <div style={{ position: "relative", paddingBottom: LABEL_GUTTER }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ width: "100%", height: H, display: "block" }}
        role="img"
        aria-label={`Comparaison avec ${theirsName} : ${summary}.`}
      >
        {rows.map((r, index) => {
          const groupTop = TOP + index * (2 * BAR_HEIGHT + BAR_GAP);
          return (
            <g key={r.courseId}>
              <rect
                x={LEFT}
                y={groupTop}
                width={xScale(r.mineSeconds ?? 0)}
                height={BAR_HEIGHT}
                fill="var(--tcn-orange)"
              />
              <rect
                x={LEFT}
                y={groupTop + BAR_HEIGHT + 4}
                width={xScale(r.theirsSeconds ?? 0)}
                height={BAR_HEIGHT}
                fill="var(--tcn-ink-3)"
              />
            </g>
          );
        })}
      </svg>

      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: LABEL_GUTTER }}>
        <span
          aria-hidden
          style={{
            fontSize: 11,
            color: "var(--tcn-text-faint)",
            fontFamily: "var(--tcn-font-body)",
          }}
        >
          <span style={{ color: "var(--tcn-orange)" }}>■</span> Vous ·{" "}
          <span style={{ color: "var(--tcn-ink-3)" }}>■</span> {theirsName}
        </span>
      </div>

      <ul className="sr-only">
        {rows.map((r) => (
          <li key={r.courseId}>
            {r.courseName} ({formatDate(r.eventDate)}) — vous {formatSeconds(r.mineSeconds ?? 0)}, {theirsName}{" "}
            {formatSeconds(r.theirsSeconds ?? 0)}
          </li>
        ))}
      </ul>
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
    <Card style={{ marginTop: 24 }}>
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
