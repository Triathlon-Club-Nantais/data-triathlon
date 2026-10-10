"use client";
import { useId, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { GroupesPicker } from "@/components/admin/jeunes/GroupesPicker";
import {
  useCreateTrainingRecurrence,
  useDeleteTrainingRecurrence,
  useTrainingRecurrencePreview,
  useTrainingRecurrences,
  useUpdateTrainingRecurrence,
} from "@/lib/queries/admin";
import { formatDate } from "@/lib/utils/date";
import type { TrainingGroup, TrainingRecurrence, TrainingRecurrenceInput } from "@/lib/types";

/** Indexés comme `date.weekday()` côté serveur : 0 = lundi. */
const JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"];

function pluriel(n: number, mot: string): string {
  return `${n} ${mot}${n > 1 ? "s" : ""}`;
}

function decrire(recurrence: TrainingRecurrence): string {
  const heure = recurrence.start_time ? ` à ${recurrence.start_time.slice(0, 5)}` : "";
  const lieu = recurrence.location ? ` · ${recurrence.location}` : "";
  return `Chaque ${JOURS[recurrence.weekday]}${heure}${lieu}, du ${formatDate(recurrence.starts_on)} au ${formatDate(recurrence.ends_on)}`;
}

/**
 * Création et modification d'une récurrence hebdomadaire (#1291, US3). Le
 * nombre de séances est annoncé avant validation (FR-011), par l'aperçu
 * serveur, seul juge de la borne de 53 séances (FR-012).
 */
export function RecurrenceForm({
  recurrence,
  groupes,
  soumettre,
  enCours,
}: {
  recurrence?: TrainingRecurrence;
  groupes: TrainingGroup[];
  soumettre: (champs: TrainingRecurrenceInput) => Promise<void>;
  enCours: boolean;
}) {
  const id = useId();
  const [jour, setJour] = useState(recurrence ? String(recurrence.weekday) : "");
  const [heure, setHeure] = useState(recurrence?.start_time?.slice(0, 5) ?? "");
  const [lieu, setLieu] = useState(recurrence?.location ?? "");
  const [typeSeance, setTypeSeance] = useState(recurrence?.session_type ?? "");
  const [debut, setDebut] = useState(recurrence?.starts_on ?? "");
  const [fin, setFin] = useState(recurrence?.ends_on ?? "");
  const [groupIds, setGroupIds] = useState<number[]>(recurrence?.group_ids ?? []);

  const periode =
    jour !== "" && debut && fin
      ? {
          weekday: Number(jour),
          start_time: null,
          location: null,
          session_type: null,
          starts_on: debut,
          ends_on: fin,
          group_ids: [],
        }
      : null;
  const apercu = useTrainingRecurrencePreview(periode);
  const nombre = apercu.data?.occurrence_count;

  async function onSubmit(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!periode) return;
    await soumettre({
      ...periode,
      start_time: heure ? `${heure}:00` : null,
      location: lieu.trim() || null,
      session_type: typeSeance.trim() || null,
      group_ids: groupIds,
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-jour`}>Jour</Label>
          <select
            id={`${id}-jour`}
            required
            className="border-input h-9 w-full rounded-md border bg-transparent px-2 text-sm"
            value={jour}
            onChange={(e) => setJour(e.target.value)}
          >
            <option value="" disabled>
              Choisir…
            </option>
            {JOURS.map((nom, index) => (
              <option key={nom} value={index}>
                {nom[0].toUpperCase() + nom.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-heure`}>Heure</Label>
          <Input id={`${id}-heure`} type="time" value={heure} onChange={(e) => setHeure(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-debut`}>Du</Label>
          <Input id={`${id}-debut`} type="date" required value={debut} onChange={(e) => setDebut(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-fin`}>Au</Label>
          <Input id={`${id}-fin`} type="date" required value={fin} onChange={(e) => setFin(e.target.value)} />
        </div>
        <div className="col-span-2 space-y-1.5">
          <Label htmlFor={`${id}-lieu`}>Lieu</Label>
          <Input id={`${id}-lieu`} placeholder="Base nautique" value={lieu} onChange={(e) => setLieu(e.target.value)} />
        </div>
        <div className="col-span-2 space-y-1.5">
          <Label htmlFor={`${id}-type`}>Type de séance</Label>
          <Input
            id={`${id}-type`}
            placeholder="Natation"
            value={typeSeance}
            onChange={(e) => setTypeSeance(e.target.value)}
          />
        </div>
      </div>
      <GroupesPicker groupes={groupes} value={groupIds} onChange={setGroupIds} />
      <p aria-live="polite" className="min-h-5 text-sm">
        {apercu.error ? (
          <span className="text-destructive">{apercu.error.message}</span>
        ) : nombre !== undefined ? (
          recurrence ? (
            `La période compte ${pluriel(nombre, "séance")}.`
          ) : (
            `${pluriel(nombre, "séance")} ${nombre > 1 ? "seront créées" : "sera créée"}.`
          )
        ) : (
          ""
        )}
      </p>
      <Button type="submit" disabled={enCours || nombre === undefined}>
        {recurrence ? "Enregistrer" : "Créer les séances"}
      </Button>
    </form>
  );
}

/** Les récurrences du calendrier : liste, création, modification et suppression. */
export function RecurrencesSection({ groupes, peutEcrire }: { groupes: TrainingGroup[]; peutEcrire: boolean }) {
  const { data, isPending, error } = useTrainingRecurrences();
  const creer = useCreateTrainingRecurrence();
  const modifier = useUpdateTrainingRecurrence();
  const supprimer = useDeleteTrainingRecurrence();
  const confirmer = useDangerConfirm();
  const [edition, setEdition] = useState<TrainingRecurrence | "nouvelle" | null>(null);

  async function creerRecurrence(champs: TrainingRecurrenceInput) {
    try {
      const creee = await creer.mutateAsync(champs);
      toast.success(`${pluriel(creee.created_session_count, "séance")} créée${creee.created_session_count > 1 ? "s" : ""}.`);
      setEdition(null);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function modifierRecurrence(id: number, champs: TrainingRecurrenceInput) {
    try {
      await modifier.mutateAsync({ id, champs });
      toast.success("Récurrence modifiée.");
      setEdition(null);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function detruire(recurrence: TrainingRecurrence) {
    const accord = await confirmer({
      titre: "Supprimer la récurrence ?",
      description: `${pluriel(recurrence.upcoming_session_count, "séance")} à venir ${recurrence.upcoming_session_count > 1 ? "seront supprimées" : "sera supprimée"}. Les séances passées, pointées ou modifiées une par une restent au calendrier.`,
      libelleAction: "Supprimer la récurrence",
    });
    if (!accord) return;
    try {
      const bilan = await supprimer.mutateAsync(recurrence.id);
      toast.success(`Récurrence supprimée, ${pluriel(bilan.deleted_session_count, "séance")} retirée${bilan.deleted_session_count > 1 ? "s" : ""}.`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <section aria-labelledby="recurrences" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="recurrences" className="font-heading text-lg font-semibold">
          Séances récurrentes
        </h2>
        {peutEcrire && (
          <Button variant="outline" size="sm" onClick={() => setEdition("nouvelle")}>
            Nouvelle récurrence
          </Button>
        )}
      </div>
      {isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : error ? (
        <p className="text-destructive text-sm">Les récurrences n&apos;ont pas pu être chargées. Réessayez plus tard.</p>
      ) : !data || data.length === 0 ? (
        <p className="text-[var(--tcn-text-faint)] text-sm">
          Aucune récurrence : une récurrence crée d&apos;un geste les séances hebdomadaires d&apos;une période.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {data.map((recurrence) => (
            <Card key={recurrence.id} className="space-y-2 p-4">
              <div className="font-medium">{decrire(recurrence)}</div>
              <div className="text-[var(--tcn-text-faint)] text-sm">
                {pluriel(recurrence.upcoming_session_count, "séance")} à venir
                {recurrence.group_ids.length > 0 &&
                  ` · ${groupes
                    .filter((groupe) => recurrence.group_ids.includes(groupe.id))
                    .map((groupe) => groupe.name)
                    .join(", ")}`}
              </div>
              {peutEcrire && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    aria-label="Modifier la récurrence"
                    onClick={() => setEdition(recurrence)}
                  >
                    Modifier
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    aria-label="Supprimer la récurrence"
                    disabled={supprimer.isPending}
                    onClick={() => detruire(recurrence)}
                  >
                    Supprimer
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {edition !== null && (
        <Dialog open onOpenChange={(ouvert) => !ouvert && setEdition(null)}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>{edition === "nouvelle" ? "Nouvelle récurrence" : "Modifier la récurrence"}</DialogTitle>
              <DialogDescription>
                {edition === "nouvelle"
                  ? "Une séance est créée pour chaque semaine de la période, avec les membres des groupes visés."
                  : "Les changements s'appliquent aux séances à venir dont l'appel n'a pas commencé, sauf celles modifiées une par une."}
              </DialogDescription>
            </DialogHeader>
            {edition === "nouvelle" ? (
              <RecurrenceForm groupes={groupes} soumettre={creerRecurrence} enCours={creer.isPending} />
            ) : (
              <RecurrenceForm
                recurrence={edition}
                groupes={groupes}
                soumettre={(champs) => modifierRecurrence(edition.id, champs)}
                enCours={modifier.isPending}
              />
            )}
          </DialogContent>
        </Dialog>
      )}
    </section>
  );
}
