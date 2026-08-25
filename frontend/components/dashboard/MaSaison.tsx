"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AnnonceStatut, Card, Eyebrow } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
import { apiClient } from "@/lib/api/client";
import { rankTypeLabel } from "@/lib/labels";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import type { Participation } from "@/lib/types";
import { motCompte } from "@/lib/utils/format";
import { compteMaSaison } from "@/lib/utils/ma-saison";

type Etat = "chargement" | "ok" | "echec";

/** Hauteur intérieure fixe de la bande, dans ses trois états visibles.
 *
 *  La bande n'est **pas** dans le HTML initial — l'athlète retenu vit en
 *  `localStorage` et n'atteint aucun rendu serveur (`frontend/AGENTS.md:218`).
 *  Elle apparaît donc à l'hydratation, ce qui décale les compteurs club vers le
 *  bas : coût déjà assumé par #467. Ce qu'on refuse, c'est un **second**
 *  décalage au retour du fetch — d'où le squelette à la hauteur définitive. */
const HAUTEUR_INTERIEURE = 68;

/**
 * Bande « Ma saison » en tête du tableau de bord (#502, NAV-9).
 *
 * L'écran d'atterrissage ne parlait que du club en agrégat : le membre qui
 * avait désigné son nom n'y trouvait rien de lui, et le geste de choix restait
 * sans récompense. La bande met ses deux chiffres en regard de ceux du club
 * **sur la même sélection** — mêmes saisons, mêmes disciplines, même type de
 * rang, sans quoi la comparaison serait bancale.
 *
 * `?rank=` ne déclenche aucun fetch : il ne change que le champ lu dans des
 * participations déjà en main. Même arbitrage que `RankTypeToggle` (#328) et
 * qu'`EventsTable` (#489).
 *
 * Accessibilité (#477) : `AnnonceStatut` signale un changement de données
 * **sans navigation**, jamais la première apparition — sans quoi chaque
 * chargement de page serait annoncé comme un bruit. Elle ne s'annonce donc
 * qu'à partir du **second** chargement réussi (athlète ou saisons changés),
 * jamais sur `?rank=` seul : `StatCardsRank` porte déjà cette annonce pour la
 * même bascule, ailleurs sur la page — la redoubler ici serait une double
 * annonce du même événement à un lecteur d'écran.
 */
export function MaSaison({
  clubEvents,
  seasons,
  federalOnly,
}: {
  /** Épreuves distinctes courues par le club sur la même sélection (`stats.events`). */
  clubEvents: number;
  /** Sélection de saisons en CSV — une primitive, donc une dépendance d'effet stable. */
  seasons: string;
  federalOnly: boolean | undefined;
}) {
  const athlete = useSelectedAthlete();
  const sp = useSearchParams();
  const mode = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);

  const [etat, setEtat] = useState<Etat>("chargement");
  const [participations, setParticipations] = useState<Participation[]>([]);
  // Compte les chargements réussis, pour distinguer la première apparition
  // (silencieuse) d'un rechargement déclenché par un changement d'athlète ou
  // de saisons (annoncé). État et non ref : sa lecture pendant le rendu doit
  // rester réactive.
  const [chargementsReussis, setChargementsReussis] = useState(0);

  const id = athlete?.id;
  useEffect(() => {
    if (id === undefined) return;
    let annule = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEtat("chargement");
    apiClient
      .getAthlete(id, { seasons, federal_only: federalOnly })
      .then((detail) => {
        if (annule) return;
        setChargementsReussis((n) => n + 1);
        setParticipations(detail.participations);
        setEtat("ok");
      })
      .catch(() => {
        if (!annule) setEtat("echec");
      });
    return () => {
      annule = true;
    };
  }, [id, seasons, federalOnly]);
  const annoncer = chargementsReussis > 1;

  if (!athlete) return null;

  const nom = nomComplet(athlete);
  const lienProfil = (
    <Link
      href={`/athletes/${athlete.id}`}
      className="text-sm font-semibold text-accent-ink hover:underline"
    >
      Voir mon athlète →
    </Link>
  );

  if (etat === "chargement") {
    return (
      <Bande>
        <div
          data-testid="ma-saison-squelette"
          style={{ display: "flex", flexDirection: "column", gap: 10 }}
        >
          <Skeleton className="h-6 w-72" />
          <Skeleton className="h-4 w-56" />
        </div>
      </Bande>
    );
  }

  if (etat === "echec") {
    return (
      <Bande>
        <Ligne
          principale={nom}
          secondaire="Chiffres indisponibles pour l'instant."
          action={lienProfil}
        />
      </Bande>
    );
  }

  const { epreuves, podiums } = compteMaSaison(participations, mode);
  const rang = rankTypeLabel(mode, { form: "long" });

  if (epreuves === 0) {
    const texte = `${nom} — aucune épreuve sur cette sélection.`;
    return (
      <Bande>
        {annoncer && (
          <AnnonceStatut texte={`Ma saison : ${texte} Le club en a couru ${clubEvents}.`} />
        )}
        <Ligne
          principale={texte}
          secondaire={`Le club en a couru ${clubEvents}.`}
          action={
            <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
              Ajouter un résultat →
            </Link>
          }
        />
      </Bande>
    );
  }

  const principale = `${nom} — ${motCompte(epreuves, "épreuve")} · ${motCompte(podiums, "podium")} (classement ${rang})`;
  const secondaire = `Le club a couru ${motCompte(clubEvents, "épreuve")} sur la même sélection.`;

  return (
    <Bande>
      {annoncer && <AnnonceStatut texte={`Ma saison : ${principale}. ${secondaire}`} />}
      <Ligne principale={principale} secondaire={secondaire} action={lienProfil} />
    </Bande>
  );
}

function Bande({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <Card>
        <Eyebrow>Ma saison</Eyebrow>
        <div style={{ minHeight: HAUTEUR_INTERIEURE, display: "flex", alignItems: "center" }}>
          {children}
        </div>
      </Card>
    </div>
  );
}

function Ligne({
  principale,
  secondaire,
  action,
}: {
  principale: string;
  secondaire: string;
  action: React.ReactNode;
}) {
  return (
    <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 20, color: "var(--tcn-ink)" }}>
          {principale}
        </div>
        <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", marginTop: 4 }}>{secondaire}</div>
      </div>
      {action}
    </div>
  );
}
