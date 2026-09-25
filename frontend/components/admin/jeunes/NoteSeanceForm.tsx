"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateTrainingSession } from "@/lib/queries/admin";

/**
 * La note de séance (#869, US3) — texte libre rattaché à l'entraînement
 * entier, rapport de l'encadrant. Distincte du journal de bord d'un jeune
 * (`AjouterNoteJeuneDialog`, réutilise #867).
 *
 * Une soumission blanche sur une séance sans note **n'écrit rien**. Sur une
 * note déjà enregistrée, elle l'efface en envoyant `""`, la forme que prend
 * « pas de note » côté modèle (`TrainingSession.note`, `NOT NULL`).
 */
export function NoteSeanceForm({
  sessionId,
  note,
  peutEcrire,
}: {
  sessionId: number;
  note: string;
  peutEcrire: boolean;
}) {
  const [valeur, setValeur] = useState(note);
  const modifier = useUpdateTrainingSession();

  const vide = !valeur.trim();
  const rienAEnregistrer = vide && !note.trim();

  async function enregistrer(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (rienAEnregistrer) return;
    try {
      await modifier.mutateAsync({ id: sessionId, champs: { note: vide ? "" : valeur } });
      toast.success("Note de séance enregistrée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  if (!peutEcrire) {
    if (!note) return null;
    return (
      <div className="space-y-1">
        <div className="font-medium">Note de séance</div>
        <p className="whitespace-pre-wrap text-sm">{note}</p>
      </div>
    );
  }

  return (
    <form onSubmit={enregistrer} className="space-y-2">
      <Label htmlFor="appel-note-seance">Note de séance</Label>
      <Textarea
        id="appel-note-seance"
        value={valeur}
        onChange={(e) => setValeur(e.target.value)}
        placeholder="Observations sur la séance, incidents à signaler…"
      />
      <Button type="submit" size="sm" disabled={modifier.isPending || rienAEnregistrer}>
        Enregistrer la note
      </Button>
    </form>
  );
}
