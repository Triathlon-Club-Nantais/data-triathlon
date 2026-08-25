"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useReassignParticipation } from "@/lib/queries/admin";
import type { AdminAthlete, Participation } from "@/lib/types";
import { AthleteSearchPicker } from "./AthleteSearchPicker";

/**
 * Rattacher un résultat au bon coureur (#117, US2).
 *
 * Le bouton reste inerte tant qu'aucune fiche n'est choisie : ce geste déplace
 * un résultat et peut détruire la fiche d'origine au passage, sans annulation.
 * Un clic par inadvertance ne doit rien pouvoir déclencher.
 */
export function ReassignParticipationDialog({
  participation,
  open,
  onOpenChange,
}: {
  participation: Participation;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [cible, setCible] = useState<AdminAthlete | null>(null);
  const rattachement = useReassignParticipation();

  async function confirmer() {
    if (!cible) return;
    try {
      await rattachement.mutateAsync({
        participationId: participation.id,
        athleteId: cible.id,
      });
      toast.success(`Résultat rattaché à ${cible.nom} ${cible.prenom}.`);
      onOpenChange(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rattacher ce résultat à un autre coureur</DialogTitle>
          <DialogDescription>
            {participation.course.name} — actuellement au nom de{" "}
            {participation.athlete?.nom} {participation.athlete?.prenom}. Le
            rattachement est <strong>irréversible</strong> ; si la fiche d&apos;origine
            n&apos;a plus aucun résultat, elle sera supprimée.
          </DialogDescription>
        </DialogHeader>

        <AthleteSearchPicker selectedId={cible?.id ?? null} onSelect={setCible} />

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Renoncer
          </Button>
          <Button onClick={confirmer} disabled={!cible || rattachement.isPending}>
            Rattacher
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
