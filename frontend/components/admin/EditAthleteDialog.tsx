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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUpdateAthlete } from "@/lib/queries/admin";
import type { AdminAthlete } from "@/lib/types";

/**
 * Corriger l'identité d'un coureur (#117, US3).
 *
 * Le triplet nom / prénom / date de naissance, et rien d'autre : c'est aussi la
 * clé qui empêche les doublons. Le club n'est pas éditable ici — il est porté
 * par chaque résultat, au moment de la course.
 *
 * En cas de conflit, **la saisie n'est pas vidée** : l'administrateur doit
 * pouvoir corriger sa correction sans tout retaper.
 */
export function EditAthleteDialog({
  athlete,
  open,
  onOpenChange,
}: {
  athlete: AdminAthlete;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [nom, setNom] = useState(athlete.nom);
  const [prenom, setPrenom] = useState(athlete.prenom);
  const [naissance, setNaissance] = useState(athlete.birth_date ?? "");
  const correction = useUpdateAthlete();

  async function enregistrer() {
    try {
      await correction.mutateAsync({
        id: athlete.id,
        champs: {
          nom,
          prenom,
          birth_date: naissance === "" ? null : naissance,
        },
      });
      toast.success("Fiche coureur corrigée.");
      onOpenChange(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Corriger la fiche coureur</DialogTitle>
          <DialogDescription>
            Ces trois champs identifient un coureur de manière unique. Son historique
            de résultats n&apos;est pas touché.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="athlete-nom">Nom</Label>
            <Input id="athlete-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="athlete-prenom">Prénom</Label>
            <Input
              id="athlete-prenom"
              value={prenom}
              onChange={(e) => setPrenom(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="athlete-naissance">Date de naissance</Label>
            <Input
              id="athlete-naissance"
              type="date"
              value={naissance}
              onChange={(e) => setNaissance(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Renoncer
          </Button>
          <Button onClick={enregistrer} disabled={correction.isPending}>
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
