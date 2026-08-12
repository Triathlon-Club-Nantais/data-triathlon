"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button, MetaPill, Modal } from "@/components/tcn";
import { useSwitchCourseSource } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { providerLabel } from "@/lib/constants";
import type { CourseSource } from "@/lib/types";

const TITRE_LIEN = "Ouvrir les résultats du chronométreur dans un nouvel onglet";

/**
 * Sources d'une épreuve, en tête de la page course. Lecture publique (D4 de
 * l'epic #275) : le rendu ne dépend jamais de la session. Seul le bouton
 * « Activer » — et la confirmation qu'il ouvre — l'exige, via `courses:sources`.
 *
 * Une seule source : rendu identique à l'ancien affichage sur
 * `course.source_url` (#279), aucune mention active/passive — il n'y a rien à
 * choisir. Le geste de bascule lui-même n'a de sens qu'à partir de deux.
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

  if (sources.length === 0) return null;

  if (sources.length === 1) {
    const [source] = sources;
    return (
      <MetaPill label="Source" href={source.url} title={TITRE_LIEN}>
        {providerLabel(source.provider)}
        <span aria-hidden="true">↗</span>
      </MetaPill>
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
        </span>
      ))}

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
