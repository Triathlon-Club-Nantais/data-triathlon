"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProgressionChart, type ProgressionAxis } from "@/components/charts/ProgressionChart";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import {
  useAddProfileMeasurement,
  useDeleteProfileMeasurement,
  useMeasurementEvents,
  useTrainingSessionsOn,
} from "@/lib/queries/admin";
import { formatDate, localToday } from "@/lib/utils/date";
import { formatDuration, parseDuration } from "@/lib/utils/duration";
import type { ProfileMeasurement } from "@/lib/types";

// Une durée n'a pas de plafond naturel : la marge de la courbe ne se rabat sur rien.
const DURATION_AXIS: ProgressionAxis = {
  max: Infinity,
  // La gouttière gauche du graphique tient 40 px : « 7:42 », pas « 7:42,3 ».
  tick: (value) => formatDuration(Math.round(value / 10) * 10),
  label: formatDuration,
  spoken: formatDuration,
  caption: "Durée à chaque test, plus haut, plus rapide.",
  ariaLabel: "Évolution de la durée (plus court, meilleur)",
  emptyTitle: "Pas encore assez de tests",
  emptyDescription: "Trois tests de cette épreuve sont nécessaires pour tracer une progression.",
};

const MIN_TESTS_POUR_COURBE = 3;

/** Les tests chronométrés du jeune (#1365), groupés par épreuve dans l'ordre de l'API. */
export function ProfileMeasurements({
  profileId,
  measurements,
  peutEcrire,
}: {
  profileId: number;
  measurements: ProfileMeasurement[];
  peutEcrire: boolean;
}) {
  const supprimer = useDeleteProfileMeasurement();
  const confirmer = useDangerConfirm();
  // Pas de Map.groupBy : absent de Safari < 17.4, hors des cibles de Next.
  const parEpreuve = new Map<string, ProfileMeasurement[]>();
  for (const test of measurements) {
    parEpreuve.set(test.event, [...(parEpreuve.get(test.event) ?? []), test]);
  }

  async function retirer(test: ProfileMeasurement) {
    if (
      !(await confirmer({
        titre: "Supprimer ce test ?",
        description: `Le test « ${test.event} » du ${formatDate(test.measured_on)} (${formatDuration(test.duration_tenths)}) sera supprimé définitivement.`,
        libelleAction: "Supprimer",
      }))
    ) {
      return;
    }
    try {
      await supprimer.mutateAsync({ id: profileId, measurementId: test.id });
      toast.success("Test supprimé.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card className="space-y-3 p-4">
      <div className="text-lg font-bold">Tests chronométrés</div>

      {peutEcrire && <FormulaireTest profileId={profileId} />}

      {measurements.length === 0 ? (
        <p className="text-[var(--tcn-text-faint)] text-sm">
          Aucun test chronométré pour l&apos;instant.
        </p>
      ) : (
        [...parEpreuve].map(([epreuve, tests]) => (
          <section key={epreuve} className="space-y-2 border-t pt-3 first:border-t-0 first:pt-0">
            <h3 className="font-semibold">{epreuve}</h3>
            {tests.length < MIN_TESTS_POUR_COURBE ? (
              <p className="text-[var(--tcn-text-faint)] text-sm">Courbe à partir de trois tests.</p>
            ) : (
              <ProgressionChart
                axis={DURATION_AXIS}
                points={tests.map((test) => ({
                  id: test.id,
                  eventDate: test.measured_on,
                  value: test.duration_tenths,
                }))}
              />
            )}
            <ul className="divide-border divide-y">
              {tests.map((test) => (
                <li key={test.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <span>
                    {formatDate(test.measured_on)} · {formatDuration(test.duration_tenths)}
                    {test.training_session_id !== null && " · en séance"}
                  </span>
                  {peutEcrire && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="tcn-cible-tactile"
                      aria-label={`Supprimer le test ${epreuve} du ${formatDate(test.measured_on)}`}
                      onClick={() => retirer(test)}
                    >
                      Supprimer
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </Card>
  );
}

function FormulaireTest({ profileId }: { profileId: number }) {
  const ajouter = useAddProfileMeasurement();
  const suggestions = useMeasurementEvents();
  const [date, setDate] = useState(localToday);
  const [epreuve, setEpreuve] = useState("");
  const [duree, setDuree] = useState("");
  const [seance, setSeance] = useState("");
  const [illisible, setIllisible] = useState(false);
  const [epreuveVide, setEpreuveVide] = useState(false);
  const seances = useTrainingSessionsOn(profileId, date);

  async function enregistrer(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    const dixiemes = parseDuration(duree);
    setIllisible(dixiemes === null);
    setEpreuveVide(!epreuve.trim());
    if (dixiemes === null || !epreuve.trim()) return;
    try {
      await ajouter.mutateAsync({
        id: profileId,
        measured_on: date,
        event: epreuve.trim(),
        duration_tenths: dixiemes,
        training_session_id: seance ? Number(seance) : null,
      });
      setEpreuve("");
      setDuree("");
      setSeance("");
      toast.success("Test enregistré.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <form onSubmit={enregistrer} className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="test-date">Date</Label>
        <Input
          id="test-date"
          type="date"
          required
          value={date}
          onChange={(e) => {
            setDate(e.target.value);
            setSeance("");
          }}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="test-epreuve">Épreuve</Label>
        <Input
          id="test-epreuve"
          required
          list="test-epreuves"
          aria-invalid={epreuveVide}
          aria-describedby={epreuveVide ? "test-epreuve-erreur" : undefined}
          value={epreuve}
          onChange={(e) => setEpreuve(e.target.value)}
        />
        {epreuveVide && (
          <p id="test-epreuve-erreur" role="alert" className="text-destructive text-sm">
            Indiquez l&apos;épreuve.
          </p>
        )}
        <datalist id="test-epreuves">
          {(suggestions.data ?? []).map((nom) => (
            <option key={nom} value={nom} />
          ))}
        </datalist>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="test-duree">Durée</Label>
        <Input
          id="test-duree"
          required
          inputMode="decimal"
          aria-invalid={illisible}
          aria-describedby="test-duree-aide"
          value={duree}
          onChange={(e) => setDuree(e.target.value)}
        />
        <p id="test-duree-aide" className="text-[var(--tcn-text-faint)] text-xs">
          En secondes (42,3), min:s (7:42) ou h:min:s (1:02:05)
        </p>
        {illisible && (
          <p role="alert" className="text-destructive text-sm">
            Durée illisible. Exemples : 42,3 ou 7:42.
          </p>
        )}
      </div>
      {(seances.data?.length ?? 0) > 0 && (
        <div className="space-y-1.5">
          <Label htmlFor="test-seance">Séance</Label>
          <select
            id="test-seance"
            className="border-input h-9 min-h-11 w-full rounded-md border bg-transparent px-2 text-sm md:min-h-0"
            value={seance}
            onChange={(e) => setSeance(e.target.value)}
          >
            <option value="">Aucune</option>
            {(seances.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {[item.start_time?.slice(0, 5), item.session_type, item.location]
                  .filter(Boolean)
                  .join(" · ") || `Séance du ${formatDate(item.date)}`}
              </option>
            ))}
          </select>
        </div>
      )}
      <Button type="submit" size="sm" className="tcn-cible-tactile" disabled={ajouter.isPending}>
        Enregistrer le test
      </Button>
    </form>
  );
}
