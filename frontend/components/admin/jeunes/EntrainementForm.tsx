"use client";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GroupesPicker } from "@/components/admin/jeunes/GroupesPicker";
import type { TrainingGroup, TrainingSession } from "@/lib/types";

/**
 * Création **et** correction d'un entraînement (#868) — même formulaire, deux
 * contextes : semé vide pour créer, semé de `entrainement` pour corriger.
 *
 * Seule la date est obligatoire (#868). `start_time`, `location` et `session_type`
 * restent du texte libre — aucune nomenclature n'a été demandée.
 *
 * `groupes` (#1291) : fourni, le formulaire propose les groupes visés et soumet
 * `group_ids` ; absent (liste non chargée), il ne les soumet pas, pour qu'une
 * correction n'efface jamais des groupes qu'elle n'a pas pu montrer.
 */
export function EntrainementForm({
  entrainement,
  soumettre,
  enCours,
  libelleSoumission,
  groupes,
}: {
  entrainement?: TrainingSession;
  soumettre: (champs: {
    date: string;
    start_time: string | null;
    location: string | null;
    session_type: string | null;
    group_ids?: number[];
  }) => Promise<void> | void;
  enCours: boolean;
  libelleSoumission: string;
  groupes?: TrainingGroup[];
}) {
  // Le formulaire de correction s'ouvre par dessus celui de création : des `id`
  // fixes rattacheraient ses libellés aux champs de la page (#876).
  const idPrefix = useId();
  const [date, setDate] = useState(entrainement?.date ?? "");
  const [heure, setHeure] = useState(entrainement?.start_time?.slice(0, 5) ?? "");
  const [lieu, setLieu] = useState(entrainement?.location ?? "");
  const [typeSeance, setTypeSeance] = useState(entrainement?.session_type ?? "");
  const [groupIds, setGroupIds] = useState<number[]>(entrainement?.group_ids ?? []);

  async function onSubmit(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!date) return;
    await soumettre({
      date,
      start_time: heure ? `${heure}:00` : null,
      location: lieu.trim() ? lieu.trim() : null,
      session_type: typeSeance.trim() ? typeSeance.trim() : null,
      ...(groupes ? { group_ids: groupIds } : {}),
    });
  }

  return (
    // Requête de conteneur, pas d'écran : le même formulaire vit en pleine page
    // et dans la fenêtre de séance, étroite, où le lieu se tronquait (#1290).
    <form onSubmit={onSubmit} className="@container">
      <div className="grid grid-cols-2 items-end gap-3 @2xl:grid-cols-[auto_auto_1fr_1fr_auto]">
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-date`}>Date</Label>
          <Input
            id={`${idPrefix}-date`}
            type="date"
            required
            className="@2xl:w-40"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-heure`}>Heure</Label>
          <Input
            id={`${idPrefix}-heure`}
            type="time"
            className="@2xl:w-28"
            value={heure}
            onChange={(e) => setHeure(e.target.value)}
          />
        </div>
        <div className="col-span-2 space-y-1.5 @2xl:col-span-1">
          <Label htmlFor={`${idPrefix}-lieu`}>Lieu</Label>
          <Input
            id={`${idPrefix}-lieu`}
            placeholder="Base nautique"
            value={lieu}
            onChange={(e) => setLieu(e.target.value)}
          />
        </div>
        <div className="col-span-2 space-y-1.5 @2xl:col-span-1">
          <Label htmlFor={`${idPrefix}-type`}>Type de séance</Label>
          <Input
            id={`${idPrefix}-type`}
            placeholder="Natation"
            value={typeSeance}
            onChange={(e) => setTypeSeance(e.target.value)}
          />
        </div>
        {groupes && (
          <div className="col-span-2 @2xl:col-span-5">
            <GroupesPicker groupes={groupes} value={groupIds} onChange={setGroupIds} />
          </div>
        )}
        <Button
          type="submit"
          className="col-span-2 w-fit @2xl:col-span-1"
          disabled={enCours || !date}
        >
          {libelleSoumission}
        </Button>
      </div>
    </form>
  );
}
