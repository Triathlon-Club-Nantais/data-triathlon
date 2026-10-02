"use client";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { MergeAthletesDialog, nomDe } from "@/components/admin/MergeAthletesDialog";
import { useIdentityReview, useIgnoreIdentityPair } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import { motCompte } from "@/lib/utils/format";
import type { IdentityReviewAthlete, IdentityReviewCandidate } from "@/lib/types";

const REFUS = { sujet: "cas d'identité", action: "consulter les cas d'identité des athlètes" };

function LigneFiche({ fiche }: { fiche: IdentityReviewAthlete }) {
  const details = [
    fiche.club ?? "Sans club",
    fiche.gender === "F" ? "Femme" : fiche.gender === "M" ? "Homme" : null,
    fiche.categories.length > 0 ? fiche.categories.join(", ") : null,
    motCompte(fiche.participations, "résultat"),
    fiche.homonym_rank > 0 ? `homonyme n° ${fiche.homonym_rank}` : null,
  ].filter(Boolean);
  return (
    <div className="text-sm">
      <Link href={`/athletes/${fiche.id}`} className="font-medium underline underline-offset-2">
        {nomDe(fiche)}
      </Link>
      <span className="text-[var(--tcn-text-faint)]"> · {details.join(" · ")}</span>
    </div>
  );
}

function Conflits({ candidate }: { candidate: IdentityReviewCandidate }) {
  if (candidate.conflicts.length === 0) return null;
  const noms = new Map(candidate.athletes.map((fiche) => [fiche.id, nomDe(fiche)]));
  const total = candidate.conflicts.length;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">
        {total} épreuve{total > 1 ? "s" : ""} en conflit
      </p>
      {candidate.conflicts.map((conflit) => (
        <div key={conflit.course_id} className="text-sm">
          <p className="font-medium">
            {conflit.course_name}
            {conflit.event_date ? ` · ${formatDate(conflit.event_date)}` : ""}
          </p>
          <ul className="text-[var(--tcn-text-faint)] text-xs">
            {conflit.entries.map((ligne) => (
              <li key={ligne.participation_id}>
                {ligne.bib ? `Dossard ${ligne.bib}` : "Sans dossard"}
                {ligne.category ? ` · ${ligne.category}` : ""}
                {ligne.total_time ? ` · ${ligne.total_time}` : ""}
                {candidate.athletes.length > 1 ? ` · ${noms.get(ligne.athlete_id)}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function CarteCas({
  candidate,
  peutFusionner,
}: {
  candidate: IdentityReviewCandidate;
  peutFusionner: boolean;
}) {
  const [fusionOuverte, setFusionOuverte] = useState(false);
  const ecarter = useIgnoreIdentityPair();
  const confirmer = useDangerConfirm();
  const [ficheA, ficheB] = candidate.athletes;
  const paire = ficheB !== undefined;
  const noms = candidate.athletes.map(nomDe).join(" et ");

  /** Geste neutre (#499) : rien n'est détruit, une suggestion sort de la liste. */
  async function ecarterLaPaire() {
    if (!ficheB) return;
    if (
      !(await confirmer({
        titre: "Écarter cette paire ?",
        description:
          "Vous jugez ces deux fiches distinctes : la paire ne reviendra plus dans cette liste. Aucune donnée n'est modifiée.",
        libelleAction: "Écarter",
        actionNeutre: true,
      }))
    ) {
      return;
    }
    try {
      await ecarter.mutateAsync({ athleteIdA: ficheA.id, athleteIdB: ficheB.id });
      toast.success("Paire écartée : elle ne reviendra plus dans cette liste.");
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <article aria-labelledby={`cas-${candidate.reason}-${ficheA.id}-${ficheB?.id ?? ""}`}>
      <Card>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <h2 id={`cas-${candidate.reason}-${ficheA.id}-${ficheB?.id ?? ""}`} className="text-base font-semibold">
                {noms}
              </h2>
              <Badge variant="secondary">{candidate.reason_label}</Badge>
            </div>
            {paire && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="min-h-11"
                  onClick={ecarterLaPaire}
                  disabled={ecarter.isPending}
                  aria-label={`Écarter la paire ${noms}`}
                >
                  {ecarter.isPending ? "Mise à l'écart…" : "Écarter"}
                </Button>
                {peutFusionner && (
                  <Button
                    size="sm"
                    variant="destructive"
                    className="min-h-11"
                    onClick={() => setFusionOuverte(true)}
                    aria-label={`Fusionner ${noms}`}
                  >
                    Fusionner
                  </Button>
                )}
              </div>
            )}
          </div>
          <div className="space-y-1">
            {candidate.athletes.map((fiche) => (
              <LigneFiche key={fiche.id} fiche={fiche} />
            ))}
          </div>
          <Conflits candidate={candidate} />
          {!paire && (
            <p className="text-[var(--tcn-text-faint)] text-xs">
              Deux personnes partagent cette fiche : ouvrez-la et réattribuez les résultats de l&apos;autre
              athlète à sa propre fiche.
            </p>
          )}
        </CardContent>
      </Card>

      {fusionOuverte && ficheB && (
        <MergeAthletesDialog athleteA={ficheA} athleteB={ficheB} open onOpenChange={setFusionOuverte} />
      )}
    </article>
  );
}

/**
 * Les cas d'identité qu'un admin tranche (#908, #967) : deux dossards sur une
 * même fiche, homonymes du club, paires inversées ou concaténées que la reprise
 * ne fusionne pas, fiches recréées sur une graphie fusionnée.
 *
 * Lecture et écart derrière `athletes:write`. La fusion demande en plus
 * `athletes:read` (l'aperçu montre des fiches gardées) : sans lui, le bouton
 * n'est pas offert plutôt que de finir en 403 (gardes d'écriture,
 * `frontend/AGENTS.md`). Un cas à une seule fiche ne s'écarte pas : il se règle
 * par réattribution, depuis la fiche.
 */
export function AthleteIdentityReviewTable() {
  const { data, isLoading, error } = useIdentityReview();
  const session = useSession();
  const pouvoirs = session.data?.permissions ?? [];
  const peutFusionner = pouvoirs.includes("athletes:write") && pouvoirs.includes("athletes:read");

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (!data || data.candidates.length === 0) {
    return (
      <EmptyState
        title="Aucun cas d'identité à trancher"
        description="Aucune fiche ne porte deux dossards d'une même épreuve, et aucune paire de fiches ne semble désigner la même personne."
      />
    );
  }

  return (
    <div className="space-y-3">
      {data.candidates.map((candidate) => (
        <CarteCas
          key={`${candidate.reason}-${candidate.athletes.map((fiche) => fiche.id).join("-")}`}
          candidate={candidate}
          peutFusionner={peutFusionner}
        />
      ))}
    </div>
  );
}
