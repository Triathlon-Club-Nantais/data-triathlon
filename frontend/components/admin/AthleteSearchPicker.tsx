"use client";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebounce } from "@/hooks/useDebounce";
import { useAdminAthleteSearch } from "@/lib/queries/admin";
import { formatDate } from "@/lib/utils/date";
import type { AdminAthlete } from "@/lib/types";

/**
 * Choisir **la bonne** fiche coureur parmi des quasi-identiques (#117, FR-024).
 *
 * Chaque proposition affiche sa date de naissance et son nombre de résultats,
 * et ce n'est pas de l'ornement : sur nom + prénom + club seuls — tout ce que
 * rend la recherche publique — deux vrais homonymes du même club sont
 * indiscernables. Le geste censé résorber un doublon fusionnerait alors deux
 * personnes distinctes, sans annulation possible.
 */
export function AthleteSearchPicker({
  selectedId,
  onSelect,
  excludeId,
}: {
  selectedId: number | null;
  onSelect: (athlete: AdminAthlete) => void;
  /** Une fiche à ne pas proposer : celle que l'on fusionne, qui sortirait en tête (#908). */
  excludeId?: number;
}) {
  const [saisie, setSaisie] = useState("");
  const recherche = useDebounce(saisie, 300);
  const recue = useAdminAthleteSearch(recherche);
  const { isFetching } = recue;
  const exclue = excludeId !== undefined && (recue.data ?? []).some((athlete) => athlete.id === excludeId);
  const data = recue.data?.filter((athlete) => athlete.id !== excludeId);

  return (
    <div className="space-y-2">
      <Input
        type="search"
        placeholder="Chercher un athlète par nom ou prénom…"
        value={saisie}
        onChange={(evenement) => setSaisie(evenement.target.value)}
      />

      {isFetching && <Skeleton className="h-20 w-full" />}

      {data && data.length === 0 && !exclue && (
        <p className="text-[var(--tcn-text-faint)] text-sm">
          Aucun athlète ne correspond à cette recherche.
        </p>
      )}

      {exclue && (
        <p className="text-[var(--tcn-text-faint)] text-sm">
          La fiche que vous consultez n&apos;est pas proposée : choisissez l&apos;autre.
        </p>
      )}

      {data && data.length > 0 && (
        <ul className="max-h-64 space-y-1 overflow-y-auto">
          {data.map((athlete) => (
            <li key={athlete.id}>
              <button
                type="button"
                onClick={() => onSelect(athlete)}
                aria-pressed={athlete.id === selectedId}
                className={`w-full rounded-md border p-2 text-left text-sm hover:bg-accent ${
                  athlete.id === selectedId ? "border-primary bg-accent" : "border-transparent"
                }`}
              >
                <span className="font-medium">
                  {athlete.nom} {athlete.prenom}
                </span>
                <span className="text-[var(--tcn-text-faint)] block text-xs">
                  {athlete.birth_date ? `Né(e) le ${formatDate(athlete.birth_date)}` : "Date de naissance inconnue"}
                  {athlete.club ? ` · ${athlete.club}` : ""}
                  {" · "}
                  {athlete.participations} résultat{athlete.participations > 1 ? "s" : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
