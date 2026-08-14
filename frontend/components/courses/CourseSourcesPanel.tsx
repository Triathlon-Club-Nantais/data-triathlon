"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button, MetaPill, Modal } from "@/components/tcn";
import { Progress } from "@/components/ui/progress";
import { useRescrapeStream } from "@/hooks/useRescrapeStream";
import { useSwitchCourseSource } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { providerLabel } from "@/lib/constants";
import type { CourseSource } from "@/lib/types";

const TITRE_LIEN = "Ouvrir les résultats du chronométreur dans un nouvel onglet";

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
  const session = useSession();
  const peutBasculer = session.data?.permissions.includes("courses:sources") ?? false;
  const bascule = useSwitchCourseSource();
  const rescrape = useRescrapeStream();

  // Notifie en fin de flux plutôt qu'à chaque `await` — `start()` ne rejette
  // jamais (le hook capture ses propres erreurs dans `state.error`, patron
  // `useImportStream`), donc un simple `try/catch` autour de `start()` ne
  // verrait jamais l'échec.
  useEffect(() => {
    if (rescrape.state.phase === "done") {
      toast.success(
        `Résultats à jour : ${rescrape.state.imported} ajoutés, ${rescrape.state.updated} mis à jour.`,
      );
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
    >
      {rescrape.state.running ? "Re-scrape en cours…" : "Re-scraper"}
    </Button>
  );

  const pctRescrape =
    rescrape.state.total > 0
      ? Math.round((rescrape.state.progress / rescrape.state.total) * 100)
      : 0;

  const progressionRescrape = rescrape.state.phase !== "idle" && (
    <div style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>
      {rescrape.state.phase === "scraping" && <p>{rescrape.state.message}</p>}
      {rescrape.state.phase === "saving" && (
        <>
          <p>
            Enregistrement… {rescrape.state.progress}/{rescrape.state.total}
          </p>
          <Progress value={pctRescrape} />
        </>
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

  async function confirmer() {
    if (!cible) return;
    try {
      const misesAJour = await bascule.mutateAsync({ courseId, sourceId: cible.id });
      setSources(misesAJour);
      toast.success(`${providerLabel(cible.provider)} est désormais la source active — résultats remplacés.`);
      setCible(null);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

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
          onClose={() => (bascule.isPending ? null : setCible(null))}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <Button variant="ghost" onClick={() => setCible(null)} disabled={bascule.isPending}>
                Annuler
              </Button>
              <Button onClick={confirmer} disabled={bascule.isPending}>
                {bascule.isPending ? "Bascule en cours…" : "Basculer"}
              </Button>
            </div>
          }
        >
          <p style={{ color: "var(--tcn-text-body)", fontSize: 14, lineHeight: 1.5, margin: 0 }}>
            {providerLabel(cible.provider)} va relancer un scrape complet de cette épreuve et
            remplacer l&apos;intégralité des résultats actuellement affichés. L&apos;opération est
            bloquante et peut prendre plusieurs secondes.
          </p>
        </Modal>
      )}
    </>
  );
}
