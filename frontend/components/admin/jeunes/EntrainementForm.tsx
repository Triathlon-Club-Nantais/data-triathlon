"use client";
import { useId, useState } from "react";
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
  // Le formulaire de correction s'ouvre par dessus celui de création : des `id`
  // fixes rattacheraient ses libellés aux champs de la page (#876).
  const idPrefix = useId();
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
        <Label htmlFor={`${idPrefix}-date`}>Date</Label>
        <Input
          id={`${idPrefix}-date`}
          type="date"
          required
          className="w-40"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-heure`}>Heure</Label>
        <Input
          id={`${idPrefix}-heure`}
          type="time"
          className="w-28"
          value={heure}
          onChange={(e) => setHeure(e.target.value)}
        />
      </div>
      <div className="flex-1 space-y-1.5">
        <Label htmlFor={`${idPrefix}-lieu`}>Lieu</Label>
        <Input
          id={`${idPrefix}-lieu`}
          placeholder="Base nautique"
          value={lieu}
          onChange={(e) => setLieu(e.target.value)}
        />
      </div>
      <div className="flex-1 space-y-1.5">
        <Label htmlFor={`${idPrefix}-type`}>Type de séance</Label>
        <Input
          id={`${idPrefix}-type`}
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
