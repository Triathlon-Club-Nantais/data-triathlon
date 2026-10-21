"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Alert, AnnonceStatut, Button, Card, Eyebrow, Input } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyResultClaims, useMyTeamResults, useRequestResultClaim } from "@/lib/queries/auth";
import type { TeamResult } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";
import { motCompte, ordinalFr } from "@/lib/utils/format";

const MIN_CARACTERES = 3;
const MAX_CARACTERES = 80;
const PLAFOND_RESULTATS = 10;
const texteDiscret = { margin: 0, fontSize: 13, lineHeight: 1.45, color: "var(--tcn-text-muted)" } as const;

/** Un relais, swimrun ou raid absent de mes résultats : je le retrouve par son nom d'équipe et je demande à le rejoindre (#1773). */
export function ResultatEquipeManquant() {
  const [saisie, setSaisie] = useState("");
  const [recherche, setRecherche] = useState("");
  const active = recherche.length >= MIN_CARACTERES;
  const resultats = useMyTeamResults(recherche, active);
  const demandes = useMyResultClaims(true);
  const demander = useRequestResultClaim();
  const [annonce, setAnnonce] = useState("");
  const aFocaliser = useRef<number | null>(null);
  const assez = saisie.trim().length >= MIN_CARACTERES;

  useEffect(() => {
    if (aFocaliser.current === null) return;
    const statut = document.getElementById(`demande-equipe-${aFocaliser.current}`);
    if (statut) {
      statut.focus();
      aFocaliser.current = null;
    }
  }, [demandes.data]);

  async function envoyer(equipe: TeamResult) {
    if (demander.isPending) return;
    try {
      aFocaliser.current = equipe.participation_id;
      await demander.mutateAsync(equipe.participation_id);
      setAnnonce(`Demande envoyée pour ${equipe.team_name}, le club va vérifier.`);
    } catch {
      aFocaliser.current = null; // l'erreur s'affiche via demander.error
    }
  }

  function ligne(equipe: TeamResult) {
    const demande = demandes.data?.find((d) => d.participation_id === equipe.participation_id);
    const details = [
      equipe.course_name,
      equipe.event_date && formatDate(equipe.event_date),
      equipe.rank_overall !== null && `${ordinalFr(equipe.rank_overall)} au scratch`,
      equipe.total_time,
    ].filter(Boolean);
    return (
      <li key={equipe.participation_id} style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
        <p className="break-words" style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "var(--tcn-ink)" }}>{equipe.team_name}</p>
        <p style={texteDiscret}>{details.join(" · ")}</p>
        {equipe.teammates.length > 0 && <p style={texteDiscret}>{`Avec : ${equipe.teammates.join(", ")}`}</p>}
        {demande?.status === "pending" ? (
          <p id={`demande-equipe-${equipe.participation_id}`} tabIndex={-1} style={texteDiscret}>
            Demande envoyée, le club va vérifier.
          </p>
        ) : (
          <>
            {demande?.status === "rejected" && <p style={texteDiscret}>Demande refusée par le club.</p>}
            <Button
              variant="secondary"
              size="sm"
              aria-label={`C'était mon équipe : ${equipe.team_name}, ${equipe.course_name}`}
              aria-disabled={demander.isPending || undefined}
              onClick={() => void envoyer(equipe)}
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
      <Eyebrow>
        <h2 style={{ margin: 0, font: "inherit", letterSpacing: "inherit", textTransform: "inherit" }}>Un résultat d&apos;équipe manque ?</h2>
      </Eyebrow>
      <p style={{ ...texteDiscret, margin: "12px 0 0", fontSize: 14 }}>Swimrun, raid, relais : cherchez le nom de votre équipe.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (assez) {
            demander.reset();
            setRecherche(saisie.trim());
            setAnnonce("");
          }
        }}
        style={{ margin: "12px 0 0", display: "flex", flexDirection: "column", gap: 8 }}
      >
        <label htmlFor="resultat-equipe-nom" style={{ fontSize: 13, fontWeight: 600, color: "var(--tcn-ink)" }}>
          Nom de l&apos;équipe
        </label>
        <Input
          id="resultat-equipe-nom"
          value={saisie}
          onChange={(e) => setSaisie(e.target.value)}
          autoComplete="off"
          maxLength={MAX_CARACTERES}
          aria-describedby="resultat-equipe-aide"
        />
        <p id="resultat-equipe-aide" style={{ ...texteDiscret, margin: 0 }}>
          Au moins {MIN_CARACTERES} caractères.
        </p>
        <Button type="submit" variant="secondary" aria-disabled={!assez || undefined} aria-describedby="resultat-equipe-aide">
          Chercher
        </Button>
      </form>
      <AnnonceStatut texte={annonce || (active && resultats.data ? `${motCompte(resultats.data.length, "résultat")} d'équipe` : "")} busy={active && resultats.isPending} />
      {active && resultats.isPending && <Skeleton data-testid="squelette-equipes" className="mt-3 h-16 w-full rounded-lg" />}
      {active && resultats.data && resultats.data.length === 0 && (
        <p style={{ ...texteDiscret, margin: "12px 0 0", fontSize: 14 }}>{`Aucun résultat d'équipe ne correspond à « ${recherche} ». Vérifiez l'orthographe, ou `}
          <Link href="/ajouter" className="font-semibold text-accent-ink underline underline-offset-2">
            ajoutez l&apos;épreuve
          </Link>{" "}
          si elle manque.
        </p>
      )}
      {active && resultats.data && resultats.data.length > 0 && (
        <ul style={{ margin: "12px 0 0", padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 16 }}>
          {resultats.data.map(ligne)}
        </ul>
      )}
      {active && resultats.data?.length === PLAFOND_RESULTATS && (
        <p style={{ ...texteDiscret, margin: "12px 0 0" }}>
          Les {PLAFOND_RESULTATS} résultats les plus récents : précisez le nom pour trouver un plus ancien.
        </p>
      )}
      {active && resultats.error && (
        <div role="alert" style={{ marginTop: 12 }}>
          <Alert status="error" title="Recherche impossible">
            {resultats.error.message || "La recherche n'a pas abouti. Réessayez dans un instant."}
          </Alert>
        </div>
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
