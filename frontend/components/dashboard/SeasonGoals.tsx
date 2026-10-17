"use client";

import { useId, useState } from "react";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { Button, Card, Eyebrow, MetaPill } from "@/components/tcn";
import { EVENT_TYPE_OPTIONS, eventTypeLabel } from "@/lib/constants";
import { useDeleteSeasonGoal, useHydratedSession, useSaveSeasonGoal, useSeasonGoals } from "@/lib/queries/auth";
import type { SeasonGoal, SeasonGoalWrite } from "@/lib/types";
import { secondsFromHms } from "@/lib/utils/time";

/** Même motif que la saisie manuelle (`ManualResultForm`, `DUREE`). */
const DUREE = /^\d{1,3}:[0-5]\d:[0-5]\d$/;
const MESSAGE_DUREE = "Format attendu H:MM:SS (par exemple 2:30:00).";

/**
 * « Mes objectifs » de l'Accueil (#1373) : privés, pour le seul compte rattaché
 * à sa fiche (#1325). La progression vient du serveur, sur les résultats validés
 * de la saison en cours.
 */
export function SeasonGoals() {
  const session = useHydratedSession();
  const rattache = Boolean(session.data?.athlete);
  const goals = useSeasonGoals(rattache);
  const [edition, setEdition] = useState<SeasonGoal | "nouveau" | null>(null);
  const [aSupprimer, setASupprimer] = useState<SeasonGoal | null>(null);
  const supprimer = useDeleteSeasonGoal();

  if (!rattache) return null;

  return (
    <Card style={{ marginTop: 24 }}>
      <Eyebrow>Mes objectifs</Eyebrow>
      {goals.isPending ? null : goals.error ? (
        <p role="alert" style={{ marginTop: 12 }}>{goals.error.message}</p>
      ) : (
        <>
          {goals.data.length === 0 && edition === null && (
            <p style={{ marginTop: 12, color: "var(--tcn-text-muted)" }}>
              Aucun objectif pour cette saison. Fixez un temps à battre ou un nombre d&apos;épreuves.
            </p>
          )}
          <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0", display: "grid", gap: 12 }}>
            {goals.data.map((goal) => (
              <li key={goal.id} style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
                <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                  <div style={{ fontWeight: 700 }}>{libelle(goal)}</div>
                  <div style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>{progression(goal)}</div>
                </div>
                {goal.reached && <MetaPill accent dot>Atteint</MetaPill>}
                <Button variant="secondary" size="sm" onClick={() => setEdition(goal)}
                  aria-label={`Modifier l'objectif « ${libelle(goal)} »`}>
                  Modifier
                </Button>
                <Button variant="secondary" size="sm" onClick={() => { supprimer.reset(); setASupprimer(goal); }}
                  aria-label={`Supprimer l'objectif « ${libelle(goal)} »`}>
                  Supprimer
                </Button>
              </li>
            ))}
          </ul>
          {edition === null ? (
            <div style={{ marginTop: 16 }}>
              <Button variant="secondary" onClick={() => setEdition("nouveau")}>Ajouter un objectif</Button>
            </div>
          ) : (
            <GoalForm
              key={edition === "nouveau" ? "nouveau" : edition.id}
              goal={edition === "nouveau" ? null : edition}
              onDone={() => setEdition(null)}
            />
          )}
        </>
      )}
      <DangerConfirm
        open={aSupprimer !== null}
        onOpenChange={(ouvert) => !ouvert && setASupprimer(null)}
        titre="Supprimer cet objectif ?"
        description={aSupprimer ? <>« {libelle(aSupprimer)} » sera effacé.</> : null}
        libelleAction="Supprimer l'objectif"
        avertissement={supprimer.error?.message}
        enAttente={supprimer.isPending}
        onConfirm={() => {
          if (aSupprimer) supprimer.mutate(aSupprimer.id, { onSuccess: () => setASupprimer(null) });
        }}
      />
    </Card>
  );
}

function GoalForm({ goal, onDone }: { goal: SeasonGoal | null; onDone: () => void }) {
  const ids = useId();
  const enregistrer = useSaveSeasonGoal();
  const [kind, setKind] = useState<SeasonGoal["kind"]>(goal?.kind ?? "time");
  const [eventType, setEventType] = useState(goal?.event_type ?? "");
  const [cible, setCible] = useState(goal ? (goal.kind === "time" ? hms(goal.target) : String(goal.target)) : "");
  const [erreur, setErreur] = useState<string | null>(null);

  function soumettre(e: React.FormEvent) {
    e.preventDefault();
    let target: number | null;
    if (kind === "time") {
      if (!eventType) return setErreur("Choisissez la discipline et le format du temps à battre.");
      target = DUREE.test(cible.trim()) ? secondsFromHms(cible.trim()) : null;
      if (!target) return setErreur(MESSAGE_DUREE);
    } else {
      target = /^\d+$/.test(cible.trim()) ? Number(cible.trim()) : null;
      if (!target) return setErreur("Le nombre d'épreuves doit être un entier supérieur ou égal à 1.");
    }
    setErreur(null);
    const body: SeasonGoalWrite = { kind, event_type: eventType || null, target };
    enregistrer.mutate({ id: goal?.id ?? null, body }, { onSuccess: onDone });
  }

  const message = erreur ?? enregistrer.error?.message;
  return (
    <form onSubmit={soumettre} style={{ marginTop: 16, display: "grid", gap: 12, maxWidth: 420 }}>
      <fieldset style={{ border: "none", padding: 0, margin: 0, display: "flex", gap: 16, flexWrap: "wrap" }}>
        <legend style={{ fontWeight: 700, marginBottom: 6 }}>Sorte d&apos;objectif</legend>
        <label>
          <input type="radio" name={`${ids}-kind`} checked={kind === "time"} onChange={() => setKind("time")} />{" "}
          Un temps à battre
        </label>
        <label>
          <input type="radio" name={`${ids}-kind`} checked={kind === "count"} onChange={() => setKind("count")} />{" "}
          Nombre d&apos;épreuves
        </label>
      </fieldset>
      <label htmlFor={`${ids}-type`} style={{ fontWeight: 600 }}>Discipline</label>
      <select id={`${ids}-type`} className="tcn-input" value={eventType} onChange={(e) => setEventType(e.target.value)}>
        <option value="">{kind === "count" ? "Toutes disciplines" : "Choisir…"}</option>
        {EVENT_TYPE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      <label htmlFor={`${ids}-cible`} style={{ fontWeight: 600 }}>
        {kind === "time" ? "Temps cible" : "Nombre d'épreuves visé"}
      </label>
      <input
        id={`${ids}-cible`}
        className="tcn-input"
        inputMode={kind === "time" ? "text" : "numeric"}
        placeholder={kind === "time" ? "2:30:00" : "6"}
        value={cible}
        onChange={(e) => setCible(e.target.value)}
        aria-invalid={erreur ? true : undefined}
      />
      {message && <p role="alert" style={{ margin: 0, color: "var(--tcn-danger)", fontSize: 13 }}>{message}</p>}
      <div style={{ display: "flex", gap: 10 }}>
        <Button type="submit" aria-disabled={enregistrer.isPending || undefined}>Enregistrer</Button>
        <Button type="button" variant="secondary" onClick={onDone}>Annuler</Button>
      </div>
    </form>
  );
}

function libelle(goal: SeasonGoal): string {
  const format = goal.event_type ? eventTypeLabel(goal.event_type) : null;
  if (goal.kind === "time") return `${format} en moins de ${hms(goal.target)}`;
  const epreuves = `${goal.target} ${goal.target > 1 ? "épreuves" : "épreuve"}`;
  return format ? `${epreuves} de ${format}` : `${epreuves} cette saison`;
}

function progression(goal: SeasonGoal): string {
  if (goal.kind === "time") return goal.best_time ? `Meilleur temps : ${goal.best_time}` : "Pas encore de temps cette saison";
  return `${goal.count ?? 0} sur ${goal.target}`;
}

function hms(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
