"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAddProfileLogEntry } from "@/lib/queries/admin";

/**
 * Note sur un jeune, pendant l'appel (#869, US3) — délègue **tel quel** au
 * journal de bord déjà posé par #867 (`POST /admin/profiles/{id}/log-entries`,
 * `useAddProfileLogEntry`) : aucun second mécanisme de notes, cf.
 * `research.md` D3 de la feature.
 */
export function AjouterNoteJeuneDialog({
  profileId,
  jeuneNom,
  open,
  onOpenChange,
}: {
  profileId: number;
  jeuneNom: string;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [texte, setTexte] = useState("");
  const ajouter = useAddProfileLogEntry();

  async function enregistrer(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!texte.trim()) return;
    try {
      await ajouter.mutateAsync({ id: profileId, text: texte.trim() });
      toast.success("Note ajoutée au journal de bord.");
      setTexte("");
      onOpenChange(false);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Note pour {jeuneNom}</DialogTitle>
          <DialogDescription>
            Versée au journal de bord de son profil, datée d&apos;aujourd&apos;hui.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={enregistrer} className="space-y-2">
          <Label htmlFor="appel-note-jeune">Note</Label>
          <Textarea
            id="appel-note-jeune"
            value={texte}
            onChange={(e) => setTexte(e.target.value)}
            placeholder="Ce qui vaut la peine d'être noté après cette séance."
          />
          <Button type="submit" size="sm" disabled={ajouter.isPending || !texte.trim()}>
            Enregistrer
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
