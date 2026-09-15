"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateEntrainement } from "@/lib/queries/admin";

/**
 * La note de séance (#869, US3) — texte libre rattaché à l'entraînement
 * entier, rapport de l'encadrant. Distincte du journal de bord d'un jeune
 * (`AjouterNoteJeuneDialog`, réutilise #867).
 *
 * Une soumission vide ou blanche **n'écrit rien** — « pas de note » se dit
 * en n'appelant jamais le `PATCH`, jamais en envoyant `""` : voir
 * `data-model.md` §Validation de la feature.
 */
export function NoteSeanceForm({
  entrainementId,
  note,
  peutEcrire,
}: {
  entrainementId: number;
  note: string;
  peutEcrire: boolean;
}) {
  const [valeur, setValeur] = useState(note);
  const modifier = useUpdateEntrainement();

  async function enregistrer(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!valeur.trim()) return;
    try {
      await modifier.mutateAsync({ id: entrainementId, champs: { note: valeur } });
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
      <Button type="submit" size="sm" disabled={modifier.isPending || !valeur.trim()}>
        Enregistrer la note
      </Button>
    </form>
  );
}
