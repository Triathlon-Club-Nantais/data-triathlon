"use client";
import { useEffect, useState } from "react";
import { Loader2, RotateCw } from "lucide-react";
import { toast } from "sonner";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { Button, MetaPill, Modal } from "@/components/tcn";
import { Progress } from "@/components/ui/progress";
import { useRescrapeStream, type RescrapeState } from "@/hooks/useRescrapeStream";
import { useSwitchSourceStream } from "@/hooks/useSwitchSourceStream";
import { apiClient } from "@/lib/api/client";
import { useSession } from "@/lib/queries/auth";
import { providerLabel } from "@/lib/constants";
import type { CourseSource } from "@/lib/types";

const TITRE_LIEN = "Ouvrir les résultats du chronométreur dans un nouvel onglet";

/**
 * Le message de fin de re-scrape doit rester vrai même quand rien n'a changé
 * — le cas le plus fréquent sur une épreuve déjà à jour, et celui qui a
 * dérouté un administrateur lisant « 0 ajoutés, 0 mis à jour » comme un échec
 * plutôt que comme une confirmation (aucune régression : `imported`/`updated`
 * à 0 est le comportement attendu de l'upsert quand la source n'a rien de
 * neuf à publier, cf. `_merge_fields` côté backend).
 */
function messageFinRescrape(state: RescrapeState): string {
  if (state.imported === 0 && state.updated === 0) {
    return state.total > 0
      ? `Déjà à jour — ${state.total} participant${state.total > 1 ? "s" : ""} vérifié${state.total > 1 ? "s" : ""}, aucun changement chez le chronométreur.`
      : "Déjà à jour, aucun changement chez le chronométreur.";
  }
  const parts: string[] = [];
  if (state.imported > 0) parts.push(`${state.imported} ajouté${state.imported > 1 ? "s" : ""}`);
  if (state.updated > 0) parts.push(`${state.updated} mis à jour`);
  return `Résultats à jour : ${parts.join(", ")} (sur ${state.total} participants).`;
}

/**
 * Sources d'une épreuve, en tête de la page course. Lecture publique (D4 de
 * l'epic #275) : le rendu ne dépend jamais de la session. Seuls le bouton
 * « Activer » et le bouton « Re-scraper » — et les gestes qu'ils ouvrent —
 * l'exigent, via `courses:sources` (#285, #118).
 *
 * Une seule source : rendu identique à l'ancien affichage sur
 * `course.source_url` (#279), aucune mention active/passive — il n'y a rien à
 * choisir. Le geste de bascule lui-même n'a de sens qu'à partir de deux ; le
 * re-scrape, lui, cible toujours l'unique source, active par construction.
 */
export function CourseSourcesPanel({
  courseId,
  initialSources,
}: {
  courseId: number;
  initialSources: CourseSource[];
}) {
  const [sources, setSources] = useState(initialSources);
  const [cible, setCible] = useState<CourseSource | null>(null);
  const [pourSuppression, setPourSuppression] = useState<CourseSource | null>(null);
  const [suppressionEnCours, setSuppressionEnCours] = useState(false);
  const session = useSession();
  const peutBasculer = session.data?.permissions.includes("courses:sources") ?? false;
  const bascule = useSwitchSourceStream();
  const rescrape = useRescrapeStream();

  async function confirmerSuppression() {
    if (!pourSuppression) return;
    const source = pourSuppression;
    setSuppressionEnCours(true);
    try {
      await apiClient.deleteCourseSource(courseId, source.id);
      setSources((actuelles) => actuelles.filter((s) => s.id !== source.id));
      toast.success(`${providerLabel(source.provider)} a été retirée des sources de l'épreuve.`);
      setPourSuppression(null);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    } finally {
      setSuppressionEnCours(false);
    }
  }

  // Notifie en fin de flux plutôt qu'à chaque `await` — `start()` ne rejette
  // jamais (le hook capture ses propres erreurs dans `state.error`, patron
  // `useImportStream`), donc un simple `try/catch` autour de `start()` ne
  // verrait jamais l'échec.
  useEffect(() => {
    if (rescrape.state.phase === "done") {
      toast.success(messageFinRescrape(rescrape.state));
    } else if (rescrape.state.phase === "error" && rescrape.state.error) {
      toast.error(rescrape.state.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rescrape.state.phase]);

  if (sources.length === 0) return null;

  const boutonRescraper = peutBasculer && (
    <Button
      size="sm"
      variant="secondary"
      aria-label="Re-scraper cette épreuve"
      disabled={rescrape.state.running}
      onClick={() => rescrape.start(courseId)}
      icon={
        rescrape.state.running ? (
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        ) : (
          <RotateCw size={14} aria-hidden="true" />
        )
      }
    >
      {rescrape.state.running ? "Re-scrape en cours…" : "Re-scraper"}
    </Button>
  );

  const pctRescrape =
    rescrape.state.total > 0
      ? Math.round((rescrape.state.progress / rescrape.state.total) * 100)
      : 0;

  // Carte neutre (ni succès ni erreur — l'un ou l'autre part en toast à la
  // fin) pendant que le re-scrape tourne. Mêmes tokens que `tcn/Alert` pour
  // rester dans le même langage visuel, sans en détourner les couleurs
  // sémantiques pour un état qui n'est encore ni l'un ni l'autre.
  const progressionRescrape = rescrape.state.running && (
    <div
      role="status"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        marginTop: 10,
        padding: "12px 16px",
        background: "var(--tcn-surface-sunk)",
        border: "1.5px solid var(--tcn-border)",
        borderRadius: "var(--tcn-radius-xl)",
        fontSize: 13,
        color: "var(--tcn-text-body)",
      }}
    >
      <Loader2 size={16} className="animate-spin" style={{ flex: "none", color: "var(--tcn-orange)" }} aria-hidden="true" />
      {rescrape.state.phase === "scraping" && <span>{rescrape.state.message}</span>}
      {rescrape.state.phase === "saving" && (
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span>Enregistrement des résultats…</span>
            <span style={{ color: "var(--tcn-text-muted)" }}>
              {rescrape.state.progress}/{rescrape.state.total}
            </span>
          </div>
          <Progress value={pctRescrape} />
        </div>
      )}
    </div>
  );

  if (sources.length === 1) {
    const [source] = sources;
    return (
      <>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <MetaPill label="Source" href={source.url} title={TITRE_LIEN}>
            {providerLabel(source.provider)}
            <span aria-hidden="true">↗</span>
          </MetaPill>
          {boutonRescraper}
        </span>
        {progressionRescrape}
      </>
    );
  }

  // Réagit dans le gestionnaire d'événement, pas dans un `useEffect` sur
  // `bascule.state.phase` : `start()` rend le dénouement du flux (patron
  // `useSwitchSourceStream`), ce qui évite le `setState` synchrone en effet
  // que React déconseille (cascading renders).
  async function confirmer() {
    if (!cible) return;
    const label = providerLabel(cible.provider);
    const resultat = await bascule.start(courseId, cible.id);
    if (resultat?.phase === "done") {
      setSources(resultat.sources);
      toast.success(`${label} est désormais la source active — résultats remplacés.`);
      setCible(null);
      bascule.reset();
    } else if (resultat?.phase === "error") {
      toast.error(resultat.message);
    }
  }

  // Même carte neutre que `progressionRescrape`, mais rendue **dans** la
  // modale de confirmation (#624) : celle-ci reste ouverte tant que le flux
  // tourne, contrairement au re-scrape qui n'a pas de confirmation.
  const progressionBascule = bascule.state.running && (
    <div
      role="status"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        marginTop: 14,
        padding: "12px 16px",
        background: "var(--tcn-surface-sunk)",
        border: "1.5px solid var(--tcn-border)",
        borderRadius: "var(--tcn-radius-xl)",
        fontSize: 13,
        color: "var(--tcn-text-body)",
      }}
    >
      <Loader2 size={16} className="animate-spin" style={{ flex: "none", color: "var(--tcn-orange)" }} aria-hidden="true" />
      {bascule.state.phase === "scraping" && <span>{bascule.state.message}</span>}
      {bascule.state.phase === "saving" && (
        <span>
          Enregistrement de {bascule.state.total} participant{bascule.state.total > 1 ? "s" : ""}…
        </span>
      )}
    </div>
  );

  return (
    <>
      {sources.map((source) => (
        <span key={source.id} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <MetaPill
            label={source.is_active ? "Source active" : "Autre source"}
            href={source.url}
            accent={source.is_active}
            title={TITRE_LIEN}
          >
            {providerLabel(source.provider)}
            <span aria-hidden="true">↗</span>
          </MetaPill>
          {peutBasculer && !source.is_active && (
            <Button
              size="sm"
              variant="secondary"
              aria-label={`Activer ${providerLabel(source.provider)} comme source active`}
              onClick={() => setCible(source)}
            >
              Activer
            </Button>
          )}
          {/* Jamais sur l'active : l'index partiel autorise zéro active, mais
              une épreuve sans active n'est plus scrapée (#282) ni affichée
              avec sa source (#279) — refusé côté serveur, non proposé ici. */}
          {peutBasculer && !source.is_active && (
            <Button
              size="sm"
              variant="secondary"
              aria-label={`Supprimer ${providerLabel(source.provider)} des sources`}
              onClick={() => setPourSuppression(source)}
            >
              Supprimer
            </Button>
          )}
          {/* Le re-scrape cible toujours l'active (Assumptions, spec.md) —
              le bouton ne rejoint donc que sa pill, jamais celle d'une passive. */}
          {source.is_active && boutonRescraper}
        </span>
      ))}
      {progressionRescrape}

      {cible && (
        <Modal
          eyebrow="Sources de l'épreuve"
          title="Basculer la source active ?"
          onClose={() => {
            if (bascule.state.running) return;
            setCible(null);
            bascule.reset();
          }}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <Button
                variant="ghost"
                onClick={() => {
                  setCible(null);
                  bascule.reset();
                }}
                disabled={bascule.state.running}
              >
                Annuler
              </Button>
              <Button variant="destructive" onClick={confirmer} disabled={bascule.state.running}>
                {bascule.state.running ? "Bascule en cours…" : "Basculer"}
              </Button>
            </div>
          }
        >
          <p style={{ color: "var(--tcn-text-body)", fontSize: 14, lineHeight: 1.5, margin: 0 }}>
            {providerLabel(cible.provider)} va relancer un scrape complet de cette épreuve et
            remplacer l&apos;intégralité des résultats actuellement affichés.
          </p>
          {progressionBascule}
        </Modal>
      )}

      {/* Déclaratif, pas `useDangerConfirm()` : ce panneau se rend aussi sur
          la page publique de l'épreuve, hors de tout `DangerConfirmProvider`
          (monté seulement sous `/admin` et `/benevoles`). */}
      <DangerConfirm
        open={pourSuppression !== null}
        onOpenChange={(ouvert) => {
          if (!ouvert && !suppressionEnCours) setPourSuppression(null);
        }}
        titre={
          pourSuppression
            ? `Supprimer la source ${providerLabel(pourSuppression.provider)} ?`
            : ""
        }
        description="Cette action est irréversible. Elle n'affecte aucun résultat déjà importé — seule la référence à ce chronométreur disparaît."
        enAttente={suppressionEnCours}
        onConfirm={confirmerSuppression}
      />
    </>
  );
}
