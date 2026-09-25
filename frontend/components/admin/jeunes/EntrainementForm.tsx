"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { TrainingSession } from "@/lib/types";

/**
 * Création **et** correction d'un entraînement (#868) — même formulaire, deux
 * contextes : semé vide pour créer, semé de `entrainement` pour corriger.
 *
 * Seule la date est obligatoire (#868). `start_time`, `location` et `session_type`
 * restent du texte libre — aucune nomenclature n'a été demandée.
 */
export function EntrainementForm({
  entrainement,
  soumettre,
  enCours,
  libelleSoumission,
}: {
  entrainement?: TrainingSession;
  soumettre: (champs: {
    date: string;
    start_time: string | null;
    location: string | null;
    session_type: string | null;
  }) => Promise<void> | void;
  enCours: boolean;
  libelleSoumission: string;
}) {
  const [date, setDate] = useState(entrainement?.date ?? "");
  const [heure, setHeure] = useState(entrainement?.start_time?.slice(0, 5) ?? "");
  const [lieu, setLieu] = useState(entrainement?.location ?? "");
  const [typeSeance, setTypeSeance] = useState(entrainement?.session_type ?? "");

  async function onSubmit(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!date) return;
    await soumettre({
      date,
      start_time: heure ? `${heure}:00` : null,
      location: lieu.trim() ? lieu.trim() : null,
      session_type: typeSeance.trim() ? typeSeance.trim() : null,
    });
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
      <div className="space-y-1.5">
        <Label htmlFor="entrainement-date">Date</Label>
        <Input
          id="entrainement-date"
          type="date"
          required
          className="w-40"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="entrainement-heure">Heure</Label>
        <Input
          id="entrainement-heure"
          type="time"
          className="w-28"
          value={heure}
          onChange={(e) => setHeure(e.target.value)}
        />
      </div>
      <div className="flex-1 space-y-1.5">
        <Label htmlFor="entrainement-lieu">Lieu</Label>
        <Input
          id="entrainement-lieu"
          placeholder="Base nautique"
          value={lieu}
          onChange={(e) => setLieu(e.target.value)}
        />
      </div>
      <div className="flex-1 space-y-1.5">
        <Label htmlFor="entrainement-type">Type de séance</Label>
        <Input
          id="entrainement-type"
          placeholder="Natation"
          value={typeSeance}
          onChange={(e) => setTypeSeance(e.target.value)}
        />
      </div>
      <Button type="submit" disabled={enCours || !date}>
        {libelleSoumission}
      </Button>
    </form>
  );
}
