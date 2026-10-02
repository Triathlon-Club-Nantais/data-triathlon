"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Modal } from "@/components/tcn";
import { AthleteSearchPicker } from "@/components/admin/AthleteSearchPicker";
import { MergeAthletesDialog, nomDe, type FicheAFusionner } from "@/components/admin/MergeAthletesDialog";
import type { AdminAthlete } from "@/lib/types";

/**
 * Après une fusion, la page suit la fiche conservée : rester sur une fiche
 * absorbée montrerait une page qui n'existe plus.
 */
export function useSuivreLaFicheConservee(ficheCourante: number) {
  const router = useRouter();
  return (gardeeId: number) => {
    if (gardeeId === ficheCourante) router.refresh();
    else router.push(`/athletes/${gardeeId}`);
  };
}

/**
 * « Fusionner avec une autre fiche », depuis la page publique d'un athlète (#908).
 *
 * Deux temps : trouver l'autre fiche (la recherche admin, seule à montrer date
 * de naissance et nombre de résultats, d'où `athletes:read` en plus de
 * `athletes:write`), puis choisir celle qu'on garde dans `MergeAthletesDialog`.
 * La fiche consultée n'est pas proposée. Le focus revient au bouton, la
 * recherche ayant disparu entre-temps. L'appelant décide de la visibilité.
 */
export function AthleteMergeAction({ athlete }: { athlete: FicheAFusionner }) {
  const [recherche, setRecherche] = useState(false);
  const [autre, setAutre] = useState<AdminAthlete | null>(null);
  const declencheur = useRef<HTMLButtonElement>(null);
  const suivre = useSuivreLaFicheConservee(athlete.id);
  const nom = nomDe(athlete);

  function choisir(fiche: AdminAthlete) {
    setAutre(fiche);
    setRecherche(false);
  }

  return (
    <>
      <Button
        ref={declencheur}
        variant="secondary"
        onClick={() => setRecherche(true)}
        aria-label={`Fusionner avec une autre fiche : ${nom}`}
      >
        Fusionner avec une autre fiche
      </Button>

      {recherche && (
        <Modal
          eyebrow="Fiche athlète"
          title="Fusionner avec une autre fiche"
          onClose={() => setRecherche(false)}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <Button variant="ghost" onClick={() => setRecherche(false)}>
                Annuler
              </Button>
            </div>
          }
        >
          <p style={{ margin: "0 0 12px", fontSize: 14, color: "var(--tcn-text-muted)" }}>
            Cherchez l&apos;autre fiche de {nom}. Vous choisirez ensuite celle que vous conservez.
          </p>
          <AthleteSearchPicker selectedId={autre?.id ?? null} onSelect={choisir} excludeId={athlete.id} />
        </Modal>
      )}

      {autre && (
        <MergeAthletesDialog
          athleteA={athlete}
          athleteB={autre}
          open
          onOpenChange={(ouvert) => !ouvert && setAutre(null)}
          onMerged={suivre}
          finalFocus={declencheur}
        />
      )}
    </>
  );
}
