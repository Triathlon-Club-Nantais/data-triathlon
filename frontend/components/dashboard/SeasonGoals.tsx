"use client";

import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { Button, Card, MetaPill } from "@/components/tcn";
import { useDebounce } from "@/hooks/useDebounce";
import { apiClient } from "@/lib/api/client";
import { EVENT_TYPE_OPTIONS, eventTypeLabel } from "@/lib/constants";
import { useDeleteSeasonGoal, useHydratedSession, useSaveSeasonGoal, useSeasonGoals } from "@/lib/queries/auth";
import type { CourseBrief, SeasonGoal, SeasonGoalWrite } from "@/lib/types";
import { currentSeason, seasonLabel } from "@/lib/utils/season";
import { formatDate } from "@/lib/utils/date";
import { hms, joursAvant, libelle, progression } from "@/lib/utils/season-goal";
import { secondsFromHms } from "@/lib/utils/time";

const WRAP = { whiteSpace: "normal", textAlign: "left", height: "auto" } as const;
const CIBLE = { className: "tcn-cible-tactile", style: { display: "flex", alignItems: "center", gap: 8 } } as const;

/** Même motif que la saisie manuelle (`ManualResultForm`, `DUREE`). */
const DUREE = /^\d{1,3}:[0-5]\d:[0-5]\d$/;
const MESSAGE_DUREE = "Format attendu H:MM:SS (par exemple 2:30:00).";

/**
 * « Mes objectifs » de Mon espace (#1373) : privés, pour le seul compte rattaché
 * à sa fiche (#1325). La progression vient du serveur, sur les résultats validés
 * de la saison affichée : la saison choisie si elle est seule, sinon la saison en
 * cours. Une saison passée est en lecture seule (création bornée à la saison en cours).
 */
export function SeasonGoals({ seasons }: { seasons: number[] }) {
  const saison = seasons.length === 1 ? seasons[0] : currentSeason();
  // `key` : changer de saison referme tout formulaire ou confirmation ouverts.
  return <CarteObjectifs key={saison} saison={saison} plusieurs={seasons.length > 1} />;
}

function CarteObjectifs({ saison, plusieurs }: { saison: number; plusieurs: boolean }) {
  const session = useHydratedSession();
  const rattache = Boolean(session.data?.athlete);
  const modifiable = saison === currentSeason();
  const goals = useSeasonGoals(rattache, saison);
  const [edition, setEdition] = useState<SeasonGoal | "nouveau" | null>(null);
  const [aSupprimer, setASupprimer] = useState<SeasonGoal | null>(null);
  const supprimer = useDeleteSeasonGoal();

  if (!rattache) return null;

  return (
    <Card>
      <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>
        Objectifs, {seasonLabel(saison)}
      </h2>
      {plusieurs && (
        <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}>
          Plusieurs saisons sont sélectionnées : les objectifs affichés sont ceux de la saison en cours.
        </p>
      )}
      {goals.isPending ? null : goals.error ? (
        <p role="alert" style={{ marginTop: 12 }}>{goals.error.message}</p>
      ) : (
        <>
          {goals.data.length === 0 && edition === null && (
            <p style={{ marginTop: 12, color: "var(--tcn-text-muted)" }}>
              {modifiable
                ? "Aucun objectif pour cette saison. Fixez un temps à battre, un nombre d'épreuves ou une épreuve cible."
                : "Aucun objectif sur cette saison. Les objectifs se fixent sur la saison en cours."}
            </p>
          )}
          <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0", display: "grid", gap: 12 }}>
            {goals.data.map((goal) => (
              <li key={goal.id} style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
                <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                  <div style={{ fontWeight: 700 }}>{libelle(goal)}</div>
                  <div style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>{progression(goal)}</div>
                </div>
                {goal.major && <MetaPill accent>Majeur</MetaPill>}
                {goal.reached && <MetaPill accent dot>Atteint</MetaPill>}
                {goal.outcome === "missed" && <MetaPill>Non atteint</MetaPill>}
                {modifiable && (
                  <>
                    <Button variant="secondary" size="sm" onClick={() => setEdition(goal)}
                      aria-label={`Modifier l'objectif « ${libelle(goal)} »`}>
                      Modifier
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => { supprimer.reset(); setASupprimer(goal); }}
                      aria-label={`Supprimer l'objectif « ${libelle(goal)} »`}>
                      Supprimer
                    </Button>
                  </>
                )}
              </li>
            ))}
          </ul>
          {!modifiable ? null : edition === null ? (
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
  const [cible, setCible] = useState(goal?.target ? (goal.kind === "time" ? hms(goal.target) : String(goal.target)) : "");
  const [major, setMajor] = useState(goal?.major ?? false);
  const [connue, setConnue] = useState<{ id: number; name: string } | null>(
    goal?.course_id && goal.race_name ? { id: goal.course_id, name: goal.race_name } : null,
  );
  const [libre, setLibre] = useState(goal?.kind === "race" && !goal.course_id);
  const [nom, setNom] = useState(goal?.race_name ?? "");
  const [date, setDate] = useState(goal?.race_date ?? "");
  const [erreur, setErreur] = useState<{ texte: string; champ: string } | null>(null);
  const idErreur = `${ids}-erreur`;
  function echec(texte: string, champ: string) {
    setErreur({ texte, champ });
    document.getElementById(`${ids}-${champ}`)?.focus();
  }
  const invalide = (champ: string) =>
    erreur?.champ === champ ? { "aria-invalid": true as const, "aria-describedby": idErreur } : {};

  function soumettre(e: React.FormEvent) {
    e.preventDefault();
    let target: number | null = null;
    const saisie = cible.trim();
    if (kind === "count") {
      target = /^\d+$/.test(saisie) ? Number(saisie) : null;
      if (!target) return echec("Le nombre d'épreuves doit être un entier supérieur ou égal à 1.", "cible");
    } else if (kind === "time" || saisie) {
      if (!eventType) return echec("Choisissez la discipline et le format du temps à battre.", "type");
      target = DUREE.test(saisie) ? secondsFromHms(saisie) : null;
      if (!target) return echec(MESSAGE_DUREE, "cible");
    }
    const body: SeasonGoalWrite = { kind, event_type: eventType || null, target, major };
    if (kind === "race") {
      if (libre) {
        if (!nom.trim()) return echec("Indiquez le nom de l'épreuve.", "nom");
        if (!date) return echec("Indiquez la date de l'épreuve.", "date");
        body.race_name = nom.trim();
        body.race_date = date;
      } else {
        if (!connue) return echec("Choisissez votre épreuve dans la liste.", connue === null ? "recherche" : "type");
        body.course_id = connue.id;
      }
    }
    setErreur(null);
    enregistrer.mutate({ id: goal?.id ?? null, body }, { onSuccess: onDone });
  }

  const message = erreur?.texte ?? enregistrer.error?.message;
  return (
    <form onSubmit={soumettre} style={{ marginTop: 16, display: "grid", gap: 12, maxWidth: 420 }}>
      <fieldset style={{ border: "none", padding: 0, margin: 0, display: "flex", gap: 16, flexWrap: "wrap" }}>
        <legend style={{ fontWeight: 700, marginBottom: 6 }}>Sorte d&apos;objectif</legend>
        <label {...CIBLE}>
          <input type="radio" name={`${ids}-kind`} checked={kind === "time"} onChange={() => setKind("time")} />
          Un temps à battre
        </label>
        <label {...CIBLE}>
          <input type="radio" name={`${ids}-kind`} checked={kind === "count"} onChange={() => setKind("count")} />
          Nombre d&apos;épreuves
        </label>
        <label {...CIBLE}>
          <input type="radio" name={`${ids}-kind`} checked={kind === "race"} onChange={() => setKind("race")} />
          Une épreuve cible
        </label>
      </fieldset>
      {kind === "race" && (
        <ChoixEpreuve
          prefix={ids}
          invalide={invalide}
          connue={connue}
          onChoisir={(course) => {
            setConnue({ id: course.id, name: course.name });
            if (course.event_type) setEventType(course.event_type);
          }}
          onChanger={() => setConnue(null)}
          libre={libre}
          onLibre={setLibre}
          nom={nom}
          onNom={setNom}
          date={date}
          onDate={setDate}
        />
      )}
      <label htmlFor={`${ids}-type`} style={{ fontWeight: 600 }}>Discipline</label>
      <select id={`${ids}-type`} className="tcn-input" value={eventType} disabled={kind === "race" && connue !== null && !libre} {...invalide("type")} onChange={(e) => setEventType(e.target.value)}>
        <option value="">{kind === "time" ? "Choisir…" : "Toutes disciplines"}</option>
        {EVENT_TYPE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      <label htmlFor={`${ids}-cible`} style={{ fontWeight: 600 }}>
        {kind === "count" ? "Nombre d'épreuves visé" : kind === "race" ? "Temps visé (facultatif)" : "Temps cible"}
      </label>
      <input
        id={`${ids}-cible`}
        className="tcn-input"
        inputMode={kind === "count" ? "numeric" : "text"}
        placeholder={kind === "count" ? "6" : "2:30:00"}
        value={cible}
        onChange={(e) => setCible(e.target.value)}
        {...invalide("cible")}
      />
      <label {...CIBLE}>
        <input type="checkbox" checked={major} onChange={(e) => setMajor(e.target.checked)} />
        Objectif majeur de la saison
      </label>
      {message && <p id={idErreur} role="alert" style={{ margin: 0, color: "var(--tcn-danger)", fontSize: 13 }}>{message}</p>}
      <div style={{ display: "flex", gap: 10 }}>
        <Button type="submit" aria-disabled={enregistrer.isPending || undefined}>Enregistrer</Button>
        <Button type="button" variant="secondary" onClick={onDone}>Annuler</Button>
      </div>
    </form>
  );
}

/** Épreuve cible : recherche parmi les épreuves importées de la saison en cours, sinon saisie libre. */
function ChoixEpreuve(props: {
  prefix: string;
  invalide: (champ: string) => object;
  connue: { id: number; name: string } | null;
  onChoisir: (course: CourseBrief) => void;
  onChanger: () => void;
  libre: boolean;
  onLibre: (libre: boolean) => void;
  nom: string;
  onNom: (nom: string) => void;
  date: string;
  onDate: (date: string) => void;
}) {
  const ids = props.prefix;
  const [saisie, setSaisie] = useState("");
  const recherche = useDebounce(saisie.trim(), 300);
  const debut = currentSeason();
  // Le focus ne suit qu'un geste : à l'ouverture de la sorte, il reste sur la case radio.
  const [focuser, setFocuser] = useState(false);
  const resultats = useQuery({
    queryKey: ["season-goal-course-search", recherche, debut],
    queryFn: () =>
      apiClient.listCourses({
        name: recherche,
        date_from: `${debut}-09-01`,
        date_to: `${debut + 1}-08-31`,
        page_size: 8,
      }),
    enabled: !props.libre && !props.connue && recherche.length > 0,
  });

  const visibles = (resultats.data ?? []).filter((course) => !course.is_relay && course.is_reliable !== false);

  if (props.libre) {
    return (
      <>
        <label htmlFor={`${ids}-nom`} style={{ fontWeight: 600 }}>Nom de l&apos;épreuve</label>
        <input key="nom" id={`${ids}-nom`} className="tcn-input" maxLength={200} autoFocus={focuser} value={props.nom} {...props.invalide("nom")}
          onChange={(e) => props.onNom(e.target.value)} />
        <label htmlFor={`${ids}-date`} style={{ fontWeight: 600 }}>Date de l&apos;épreuve</label>
        <input id={`${ids}-date`} className="tcn-input" type="date" value={props.date} {...props.invalide("date")}
          min={`${debut}-09-01`} max={`${debut + 1}-08-31`} onChange={(e) => props.onDate(e.target.value)} />
        <Button type="button" variant="secondary" size="sm" onClick={() => { setFocuser(true); props.onLibre(false); }}>
          Revenir à la recherche
        </Button>
      </>
    );
  }
  if (props.connue) {
    return (
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
        <strong>{props.connue.name}</strong>
        <Button type="button" variant="secondary" size="sm" autoFocus={focuser} onClick={() => { setFocuser(true); props.onChanger(); }}>Changer d&apos;épreuve</Button>
      </div>
    );
  }
  return (
    <>
      <label htmlFor={`${ids}-recherche`} style={{ fontWeight: 600 }}>Rechercher une épreuve</label>
      <span id={`${ids}-aide`} style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>Saisissez une partie du nom</span>
      <input key="recherche" id={`${ids}-recherche`} className="tcn-input" autoFocus={focuser} value={saisie} aria-describedby={`${ids}-aide`} {...props.invalide("recherche")} onChange={(e) => setSaisie(e.target.value)} />
      <p aria-live="polite" style={{ margin: 0, fontSize: 13, color: "var(--tcn-text-muted)" }}>
        {resultats.isFetching
          ? "Recherche en cours…"
          : resultats.data
            ? visibles.length === 0
              ? "Aucune épreuve de la saison ne correspond."
              : `${visibles.length} ${visibles.length > 1 ? "épreuves trouvées" : "épreuve trouvée"}`
            : ""}
      </p>
      {resultats.error && (
        <p role="alert" style={{ margin: 0, color: "var(--tcn-danger)", fontSize: 13 }}>{resultats.error.message}</p>
      )}
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
        {visibles.map((course) => (
          <li key={course.id} style={{ minWidth: 0 }}>
            <Button type="button" variant="secondary" size="sm" style={WRAP} onClick={() => { setFocuser(true); props.onChoisir(course); }}>
              {course.name}{course.event_date ? `, ${formatDate(course.event_date)}` : ""} ({eventTypeLabel(course.event_type)})
            </Button>
          </li>
        ))}
      </ul>
      <Button type="button" variant="secondary" size="sm" style={WRAP} onClick={() => { setFocuser(true); props.onLibre(true); }}>
        Saisir l&apos;épreuve à la main
      </Button>
    </>
  );
}

// Les libellés vivent dans `lib/utils/season-goal` : la fiche publique (composant serveur) les appelle,
// ce qu'un export d'un module "use client" interdit.
export { hms, joursAvant, libelle, progression };
