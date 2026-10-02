"use client";
import { useState, type ComponentProps } from "react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useAthleteMergeImpact, useMergeAthletes } from "@/lib/queries/admin";
import { formatDate } from "@/lib/utils/date";
import { motCompte } from "@/lib/utils/format";
import type { AthleteMergeSide } from "@/lib/types";

/** Une fiche à présenter : de quoi la reconnaître, rien de plus. */
export type FicheAFusionner = {
  id: number;
  nom: string;
  prenom: string;
  club: string | null;
  participations?: number;
};

/** « NOM Prénom », l'ordre de la recherche admin et de la revue, sur tout le parcours. */
export function nomDe(fiche: { nom: string; prenom: string }): string {
  return [fiche.nom, fiche.prenom].filter(Boolean).join(" ");
}

function CarteFiche({
  fiche,
  choisie,
  onChoisir,
}: {
  fiche: FicheAFusionner;
  choisie: boolean;
  onChoisir: () => void;
}) {
  const details = [
    fiche.club ?? "Sans club",
    fiche.participations === undefined ? null : motCompte(fiche.participations, "résultat"),
    `fiche n° ${fiche.id}`,
  ].filter(Boolean);
  return (
    <button
      type="button"
      role="radio"
      onClick={onChoisir}
      aria-checked={choisie}
      className={`w-full rounded-md border p-3 text-left text-sm hover:bg-accent ${
        choisie ? "border-primary bg-accent" : "border-transparent"
      }`}
    >
      <span className="block font-medium">Garder {nomDe(fiche)}</span>
      <span className="text-[var(--tcn-text-faint)] block text-xs">{details.join(" · ")}</span>
    </button>
  );
}

/**
 * Fusionner deux fiches d'une même personne (#908).
 *
 * **La fiche conservée se choisit**, comme la cible de `MergeCoursesDialog` :
 * rien ne dit laquelle garder, ni l'ordre reçu, ni le nombre de résultats.
 *
 * L'aperçu, chargé à la sélection, porte aussi le refus éventuel : le serveur
 * refuserait la fusion, et l'écran le dit avant le clic, bouton inerte
 * (`frontend/AGENTS.md`, gestes destructifs). La fiche absorbée disparaît sans
 * retour, d'où `DangerConfirm`.
 */
export function MergeAthletesDialog({
  athleteA,
  athleteB,
  open,
  onOpenChange,
  onMerged,
  finalFocus,
}: {
  athleteA: FicheAFusionner;
  athleteB: FicheAFusionner;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
  /** Appelé avec l'id de la fiche conservée, une fois la fusion faite. */
  onMerged?: (keptId: number) => void;
  /** Où rendre le focus à la fermeture, quand le déclencheur a disparu entre-temps. */
  finalFocus?: ComponentProps<typeof DangerConfirm>["finalFocus"];
}) {
  const [gardeeId, setGardeeId] = useState<number | null>(null);
  const absorbee = gardeeId === null ? null : gardeeId === athleteA.id ? athleteB : athleteA;
  const gardee = gardeeId === null ? null : gardeeId === athleteA.id ? athleteA : athleteB;

  const impact = useAthleteMergeImpact(gardeeId, absorbee?.id ?? null);
  const fusion = useMergeAthletes();
  const refus = impact.data?.blocking_label ?? null;

  async function confirmer() {
    if (gardee === null || absorbee === null) return;
    try {
      await fusion.mutateAsync({ keptId: gardee.id, absorbedId: absorbee.id });
      // Par numéro : deux homonymes ont le même nom, et le toast dirait « X dans X ».
      toast.success(`La fiche n° ${absorbee.id} a été fusionnée dans la fiche n° ${gardee.id} (${nomDe(gardee)}).`);
      onOpenChange(false);
      onMerged?.(gardee.id);
    } catch (erreur) {
      toast.error((erreur as Error).message);
      // Un refus apparu depuis l'aperçu doit s'afficher ici, bouton inerte.
      impact.refetch();
    }
  }

  return (
    <DangerConfirm
      open={open}
      onOpenChange={onOpenChange}
      finalFocus={finalFocus}
      titre="Fusionner ces deux fiches ?"
      description={
        <>
          Choisissez la fiche à conserver. L&apos;autre est supprimée : ses résultats,
          ses validations de saison, son bénévolat et son compte membre passent sur la
          fiche conservée.
        </>
      }
      actionBloquee={!impact.data || refus !== null}
      libelleAction={fusion.isPending ? "Fusion en cours…" : "Fusionner"}
      enAttente={fusion.isPending}
      onConfirm={confirmer}
    >
      <div role="radiogroup" aria-label="Fiche à conserver" className="space-y-2">
        <CarteFiche fiche={athleteA} choisie={gardeeId === athleteA.id} onChoisir={() => setGardeeId(athleteA.id)} />
        <CarteFiche fiche={athleteB} choisie={gardeeId === athleteB.id} onChoisir={() => setGardeeId(athleteB.id)} />
      </div>

      {gardeeId !== null && impact.isLoading && <Skeleton className="h-16 w-full" />}

      {gardeeId !== null && impact.error && (
        <div className="space-y-2">
          <p className="text-sm text-destructive">
            L&apos;ampleur de la fusion n&apos;a pas pu être chiffrée. Par prudence, la
            fusion n&apos;est pas activée.
          </p>
          <button
            type="button"
            onClick={() => impact.refetch()}
            className="min-h-11 rounded-md border px-3 text-sm hover:bg-accent"
          >
            Réessayer
          </button>
        </div>
      )}

      {refus && (
        <div role="alert" className="space-y-1 text-sm text-destructive">
          <p className="font-medium">Fusion impossible</p>
          <p>{refus}</p>
        </div>
      )}

      {impact.data && (
        <ul aria-label="Dates de naissance" className="space-y-1 text-sm">
          {[impact.data.kept, impact.data.absorbed].map((fiche: AthleteMergeSide) => (
            <li key={fiche.id}>
              {nomDe(fiche)} (n° {fiche.id}) :{" "}
              {fiche.birth_date ? `né(e) le ${formatDate(fiche.birth_date)}` : "date de naissance inconnue"}
            </li>
          ))}
        </ul>
      )}

      {impact.data && refus === null && (
        <ul aria-label="Ce que la fusion déplace" className="space-y-1 text-sm">
          <li>
            <strong>{motCompte(impact.data.moves.participations, "résultat")}</strong> et{" "}
            {motCompte(impact.data.moves.teammates, "place")} d&apos;équipier de relais passeront sur la
            fiche conservée.
          </li>
          {impact.data.moves.season_validations > 0 && (
            <li>{motCompte(impact.data.moves.season_validations, "validation")} de saison.</li>
          )}
          {impact.data.moves.volunteer_actions > 0 && (
            <li>{motCompte(impact.data.moves.volunteer_actions, "action")} bénévole.</li>
          )}
          {impact.data.moves.users > 0 && (
            <li>{motCompte(impact.data.moves.users, "compte")} membre lié à la fiche absorbée.</li>
          )}
          {impact.data.alias_added && (
            <li>
              La graphie « {nomDe(impact.data.absorbed)} » sera reconnue comme celle de la fiche conservée
              lors des prochains imports.
            </li>
          )}
        </ul>
      )}
    </DangerConfirm>
  );
}
