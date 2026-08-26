"use client";
import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { AthleteSeasonActivity } from "@/lib/types";
import { Card, Input, VousChip } from "@/components/tcn";
import { useSelectedAthlete } from "@/components/layout/AthletePicker";
import { trouverRang } from "@/lib/utils/rang";
import { SEUIL_RAPPEL_POSITION } from "@/lib/club";
import { AthleteSortToggle, SORT_DEFAULT, SORT_PARAM, sortTypeFromParam } from "./AthleteSortToggle";
import { RappelPosition } from "./RappelPosition";

/** Insensible casse/accents, comme la recherche serveur (`core/text.deaccent`, #357). */
function normalise(texte: string): string {
  return texte
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

/**
 * Filtre en mémoire (#382) — même liste déjà chargée que le tri, pas d'aller-retour
 * réseau. Mot à mot comme `name_filter` côté API (#357) : chaque mot du terme doit
 * matcher nom+prénom, sans quoi « Jean Dupont » (ordre naturel) ne trouve rien.
 */
function filterAthletes(athletes: AthleteSeasonActivity[], query: string): AthleteSeasonActivity[] {
  const mots = normalise(query.trim()).split(/\s+/).filter(Boolean);
  if (mots.length === 0) return athletes;
  return athletes.filter((a) => {
    const cible = normalise(`${a.nom} ${a.prenom}`);
    return mots.every((mot) => cible.includes(mot));
  });
}

// Nom vide (import mal renseigné) en fin de tri, pas en tête (Edge Cases du
// spec) : sans ce garde-fou, "" précède tout nom non vide en localeCompare.
function byNomPrenom(a: AthleteSeasonActivity, b: AthleteSeasonActivity): number {
  const aVide = a.nom === "" ? 1 : 0;
  const bVide = b.nom === "" ? 1 : 0;
  if (aVide !== bVide) return aVide - bVide;
  return a.nom.localeCompare(b.nom, "fr") || a.prenom.localeCompare(b.prenom, "fr");
}

/** Tri en mémoire (#274) — la liste est déjà entièrement chargée, cf. research.md. */
function sortAthletes(
  athletes: AthleteSeasonActivity[],
  sort: ReturnType<typeof sortTypeFromParam>,
): AthleteSeasonActivity[] {
  if (sort === "nom") return [...athletes].sort(byNomPrenom);
  // Défaut : nombre d'épreuves décroissant, égalité départagée par nom de famille.
  return [...athletes].sort(
    (a, b) => b.participation_count - a.participation_count || byNomPrenom(a, b),
  );
}

/**
 * Liste des athlètes actifs d'une saison (#274) — nom + nombre d'épreuves.
 * Scope/saison/discipline arrivent déjà filtrés depuis la page. Le tri et la
 * recherche (#382), eux, sont purement client — la liste est déjà entièrement
 * chargée (cf. `sortAthletes`/`filterAthletes`, mêmes limites que `research.md`).
 */
export function AthleteSeasonList({ athletes }: { athletes: AthleteSeasonActivity[] }) {
  const sp = useSearchParams();
  const sort = sortTypeFromParam(sp.get(SORT_PARAM) ?? undefined);
  const [query, setQuery] = useState("");
  // Athlète retenu (#504) : lu inconditionnellement — un hook ne se cale pas
  // derrière le retour anticipé de la liste vide.
  const athleteRetenu = useSelectedAthlete();

  if (athletes.length === 0) {
    return (
      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ padding: 40, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>
          Aucun athlète actif sur cette saison. Essayez une autre saison.
        </div>
      </Card>
    );
  }

  const filtered = filterAthletes(athletes, query);
  const sorted = sortAthletes(filtered, sort);

  // Rang calculé sur la liste **complète**, triée par volume et non filtrée
  // par la recherche — jamais sur `sort` : « 41ᵉ du club » promet un rang de
  // club, cohérent avec le rappel de `/club` (toujours trié par volume,
  // `buildRoster`, aucun bouton de tri) ; le laisser suivre le tri
  // d'affichage ferait mentir le mot « club » dès qu'on bascule sur le tri
  // alphabétique (revue de code, #504).
  const rangComplet = sortAthletes(athletes, SORT_DEFAULT);
  const rang = athleteRetenu
    ? trouverRang(athleteRetenu.id, rangComplet.map((a) => a.id))
    : null;
  const rappelVisible = rang !== null && rang > SEUIL_RAPPEL_POSITION;

  return (
    <div className="space-y-3">
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 12 }}>
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher un athlète (nom, prénom)"
          aria-label="Rechercher un athlète"
          containerStyle={{ maxWidth: 320, flex: 1 }}
        />
        <AthleteSortToggle />
      </div>
      <RappelPosition
        visible={rappelVisible}
        epreuves={rang ? rangComplet[rang - 1].participation_count : 0}
        rang={rang ?? 0}
        hrefAncre={athleteRetenu ? `#athlete-${athleteRetenu.id}` : "#"}
      />
      {/* WCAG 4.1.3 — la recherche change le contenu de la liste sans déplacer
          le focus : sans cette annonce, un lecteur d'écran ne signale ni le
          nombre de résultats ni le basculement vers l'état vide (revue #382). */}
      <p className="sr-only" role="status">
        {sorted.length} athlète{sorted.length > 1 ? "s" : ""} trouvé{sorted.length > 1 ? "s" : ""}
      </p>
      {sorted.length === 0 ? (
        <Card padding={0} style={{ overflow: "hidden" }}>
          <div style={{ padding: 40, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>
            Aucun athlète ne correspond à « {query.trim()} ». Essayez un autre nom.
          </div>
        </Card>
      ) : (
        <Card padding={0} style={{ overflow: "hidden" }}>
          {sorted.map((a) => {
            const moi = athleteRetenu?.id === a.id;
            return (
              <Link
                key={a.id}
                id={`athlete-${a.id}`}
                href={`/athletes/${a.id}`}
                className={moi ? "tcn-rowlink tcn-rowlink--moi" : "tcn-rowlink"}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "14px 26px",
                  borderBottom: "1px solid var(--tcn-border-faint)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}>
                  <span>
                    <span data-testid="athlete-row-nom">{a.nom}</span>{" "}
                    <span style={{ fontWeight: 500, color: "var(--tcn-text-faint)" }}>{a.prenom}</span>
                  </span>
                  {moi && <VousChip />}
                </div>
                <div style={{ fontSize: 14, color: "var(--tcn-text-faint)", fontWeight: 600 }}>
                  <span>{a.participation_count}</span>{" "}
                  <span>épreuve{a.participation_count > 1 ? "s" : ""}</span>
                </div>
              </Link>
            );
          })}
        </Card>
      )}
    </div>
  );
}
