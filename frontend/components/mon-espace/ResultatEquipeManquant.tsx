"use client";

import { useState } from "react";
import { Alert, AnnonceStatut, Button, Card, Eyebrow, Input } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyResultClaims, useMyTeamResults, useRequestResultClaim } from "@/lib/queries/auth";
import type { TeamResult } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";
import { ordinalFr } from "@/lib/utils/format";

const MIN_CARACTERES = 3;
const texteDiscret = { margin: 0, fontSize: 13, lineHeight: 1.45, color: "var(--tcn-text-muted)" } as const;

/** Un relais, swimrun ou raid absent de mes résultats : je le retrouve par son nom d'équipe et je demande à le rejoindre (#1739). */
export function ResultatEquipeManquant() {
  const [saisie, setSaisie] = useState("");
  const [recherche, setRecherche] = useState("");
  const active = recherche.length >= MIN_CARACTERES;
  const resultats = useMyTeamResults(recherche, active);
  const demandes = useMyResultClaims(true);
  const demander = useRequestResultClaim();
  const assez = saisie.trim().length >= MIN_CARACTERES;

  function ligne(equipe: TeamResult) {
    const demande = demandes.data?.find((d) => d.kind === "team" && d.participation_id === equipe.participation_id);
    const details = [
      equipe.course_name,
      equipe.event_date && formatDate(equipe.event_date),
      equipe.rank_overall !== null && ordinalFr(equipe.rank_overall),
      equipe.total_time,
    ].filter(Boolean);
    return (
      <li key={equipe.participation_id} style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
        <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "var(--tcn-ink)" }}>{equipe.team_name}</p>
        <p style={texteDiscret}>{details.join(" · ")}</p>
        {equipe.teammates.length > 0 && <p style={texteDiscret}>{equipe.teammates.join(", ")}</p>}
        {demande?.status === "pending" ? (
          <p style={texteDiscret}>Demande envoyée, le club va vérifier.</p>
        ) : (
          <>
            {demande?.status === "rejected" && <p style={texteDiscret}>Demande refusée par le club.</p>}
            <Button
              variant="secondary"
              size="sm"
              aria-label={`C'était mon équipe : ${equipe.team_name}, ${equipe.course_name}`}
              aria-disabled={demander.isPending || undefined}
              onClick={() => {
                if (!demander.isPending) demander.mutate({ participationId: equipe.participation_id, kind: "team" });
              }}
            >
              C&apos;était mon équipe
            </Button>
          </>
        )}
      </li>
    );
  }

  return (
    <Card padding={20}>
      <Eyebrow>Un résultat d&apos;équipe manque ?</Eyebrow>
      <p style={{ ...texteDiscret, margin: "12px 0 0", fontSize: 14 }}>Swimrun, raid, relais : cherchez le nom de votre équipe.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (assez) setRecherche(saisie.trim());
        }}
        style={{ margin: "12px 0 0", display: "flex", flexDirection: "column", gap: 8 }}
      >
        <label htmlFor="resultat-equipe-nom" style={{ fontSize: 13, fontWeight: 600, color: "var(--tcn-ink)" }}>
          Nom de l&apos;équipe
        </label>
        <Input id="resultat-equipe-nom" value={saisie} onChange={(e) => setSaisie(e.target.value)} autoComplete="off" />
        <Button type="submit" variant="secondary" aria-disabled={!assez || undefined}>
          Chercher
        </Button>
      </form>
      <AnnonceStatut texte={active && resultats.data ? `${resultats.data.length} résultat(s) d'équipe` : ""} busy={active && resultats.isPending} />
      {active && resultats.isPending && <Skeleton data-testid="squelette-equipes" className="mt-3 h-16 w-full rounded-lg" />}
      {active && resultats.data && resultats.data.length === 0 && (
        <p style={{ ...texteDiscret, margin: "12px 0 0", fontSize: 14 }}>{`Aucun résultat d'équipe ne correspond à « ${recherche} ».`}</p>
      )}
      {active && resultats.data && resultats.data.length > 0 && (
        <ul style={{ margin: "12px 0 0", padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 16 }}>
          {resultats.data.map(ligne)}
        </ul>
      )}
      {demander.error && (
        <div role="alert" style={{ marginTop: 12 }}>
          <Alert status="error" title="Demande non envoyée">
            {demander.error.message}
          </Alert>
        </div>
      )}
    </Card>
  );
}
