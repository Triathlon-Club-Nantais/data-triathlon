"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Entrainement } from "@/lib/types";

/**
 * Création **et** correction d'un entraînement (#868) — même formulaire, deux
 * contextes : semé vide pour créer, semé de `entrainement` pour corriger.
 *
 * Seule la date est obligatoire (#868). `heure_debut`, `lieu` et `type_seance`
 * restent du texte libre — aucune nomenclature n'a été demandée.
 */
export function EntrainementForm({
  entrainement,
  soumettre,
  enCours,
  libelleSoumission,
}: {
  entrainement?: Entrainement;
  soumettre: (champs: {
    date: string;
    heure_debut: string | null;
    lieu: string | null;
    type_seance: string | null;
  }) => Promise<void> | void;
  enCours: boolean;
  libelleSoumission: string;
}) {
  const [date, setDate] = useState(entrainement?.date ?? "");
  const [heure, setHeure] = useState(entrainement?.heure_debut?.slice(0, 5) ?? "");
  const [lieu, setLieu] = useState(entrainement?.lieu ?? "");
  const [typeSeance, setTypeSeance] = useState(entrainement?.type_seance ?? "");

  async function onSubmit(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!date) return;
    await soumettre({
      date,
      heure_debut: heure ? `${heure}:00` : null,
      lieu: lieu.trim() ? lieu.trim() : null,
      type_seance: typeSeance.trim() ? typeSeance.trim() : null,
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
