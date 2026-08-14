"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { AthleteSeasonActivity } from "@/lib/types";
import { Card } from "@/components/tcn";
import { AthleteSortToggle, SORT_PARAM, sortTypeFromParam } from "./AthleteSortToggle";

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
 * Ne filtre pas : la liste arrive déjà scopée club/saison depuis la page. Le
 * tri, lui, est purement client (`?sort=`, cf. `AthleteSortToggle`).
 */
export function AthleteSeasonList({ athletes }: { athletes: AthleteSeasonActivity[] }) {
  const sp = useSearchParams();
  const sort = sortTypeFromParam(sp.get(SORT_PARAM) ?? undefined);

  if (athletes.length === 0) {
    return (
      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ padding: 40, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>
          Aucun athlète actif sur cette saison.
        </div>
      </Card>
    );
  }

  const sorted = sortAthletes(athletes, sort);

  return (
    <div className="space-y-3">
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <AthleteSortToggle />
      </div>
      <Card padding={0} style={{ overflow: "hidden" }}>
        {sorted.map((a) => (
          <Link
            key={a.id}
            href={`/athletes/${a.id}`}
            className="tcn-rowlink"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "14px 26px",
              borderBottom: "1px solid var(--tcn-border-faint)",
            }}
          >
            <div style={{ fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}>
              <span data-testid="athlete-row-nom">{a.nom}</span>{" "}
              <span style={{ fontWeight: 500, color: "var(--tcn-text-muted)" }}>{a.prenom}</span>
            </div>
            <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>
              <span>{a.participation_count}</span>{" "}
              <span>épreuve{a.participation_count > 1 ? "s" : ""}</span>
            </div>
          </Link>
        ))}
      </Card>
    </div>
  );
}
