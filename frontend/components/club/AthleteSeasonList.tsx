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

/** Statut de validation (#709, FR-014) — filtre client, comme le tri (research.md). */
type FiltreValidation = "tous" | "valides" | "non_valides";

function filterByValidation(
  athletes: AthleteSeasonActivity[],
  filtre: FiltreValidation,
): AthleteSeasonActivity[] {
  if (filtre === "valides") return athletes.filter((a) => a.season_validated === true);
  if (filtre === "non_valides") return athletes.filter((a) => a.season_validated === false);
  return athletes;
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
  // Défaut : total réel d'épreuves décroissant (#709), égalité départagée par nom de famille.
  return [...athletes].sort((a, b) => b.total_count - a.total_count || byNomPrenom(a, b));
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
  // #709 — le statut de validation n'est significatif que sur une saison
  // unique (research.md D9) : l'API rend `season_validated` uniforme (`null`
  // pour tous, ou non-`null` pour tous) selon `seasons`, jamais mixte.
  const singleSeason = athletes[0]?.season_validated !== null;
  const [filtreValidation, setFiltreValidation] = useState<FiltreValidation>("tous");
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

  const filtered = filterByValidation(filterAthletes(athletes, query), singleSeason ? filtreValidation : "tous");
  const sorted = sortAthletes(filtered, sort);

  // Rang calculé sur la liste **complète**, triée par volume et non filtrée
  // par la recherche — jamais sur `sort` : « 41ᵉ du club » promet un rang de
  // club, cohérent avec l'ordre de `club_roster` (backend, #581), toujours
  // trié par volume ; le laisser suivre le tri d'affichage ferait mentir le
  // mot « club » dès qu'on bascule sur le tri alphabétique (revue de code,
  // #504). Le rappel de `/club` lui-même reste générique, sans numéro de
  // rang : son roster arrive déjà plafonné côté SQL, `RosterApercu` n'a donc
  // pas de liste complète où chercher un rang au-delà de l'aperçu.
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
          icon={<span>⌕</span>}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher un athlète (nom, prénom)"
          aria-label="Rechercher un athlète"
          containerStyle={{ maxWidth: 320, flex: 1 }}
        />
        <AthleteSortToggle />
        {singleSeason && (
          <div role="radiogroup" aria-label="Statut de validation" style={{ display: "inline-flex", gap: 8 }}>
            {(
              [
                ["tous", "Tous"],
                ["valides", "Validées"],
                ["non_valides", "Non validées"],
              ] as [FiltreValidation, string][]
            ).map(([valeur, libelle]) => (
              <label key={valeur} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 13 }}>
                <input
                  type="radio"
                  name="filtre-validation"
                  value={valeur}
                  checked={filtreValidation === valeur}
                  onChange={() => setFiltreValidation(valeur)}
                />
                {libelle}
              </label>
            ))}
          </div>
        )}
      </div>
      <RappelPosition
        visible={rappelVisible}
        epreuves={rang ? rangComplet[rang - 1].total_count : 0}
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
                  {singleSeason && a.season_validated && (
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: "var(--tcn-orange)",
                        border: "1px solid var(--tcn-orange)",
                        borderRadius: 6,
                        padding: "1px 6px",
                      }}
                    >
                      Saison validée
                    </span>
                  )}
                </div>
                <div style={{ textAlign: "right" }}>
                  <div
                    data-testid="athlete-row-total"
                    style={{ fontSize: 14, color: "var(--tcn-text-faint)", fontWeight: 600 }}
                  >
                    <span>{a.total_count}</span>{" "}
                    <span>épreuve{a.total_count > 1 ? "s" : ""}</span>
                  </div>
                  {(a.validated_count !== a.total_count ||
                    a.club_affiliated_count !== a.total_count) && (
                    // #709 — le détail n'apparaît que si les compteurs divergent
                    // (FR-004) : pas de bruit répété sur les 315 lignes du cas
                    // courant, où la donnée source est complète.
                    <div
                      data-testid="athlete-row-detail"
                      style={{ fontSize: 12, color: "var(--tcn-text-faint)" }}
                    >
                      dont {a.validated_count} validée{a.validated_count > 1 ? "s" : ""} ·{" "}
                      {a.club_affiliated_count} affiliée{a.club_affiliated_count > 1 ? "s" : ""} club
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
        </Card>
      )}
    </div>
  );
}
