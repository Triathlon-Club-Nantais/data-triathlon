"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AnnonceStatut, Card, Eyebrow } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
import { apiClient } from "@/lib/api/client";
import { RANK_PARAM, rankTypeFromParam, type RankType } from "@/lib/rank";
import type { Participation } from "@/lib/types";
import { motCompte } from "@/lib/utils/format";
import { compteMaSaison } from "@/lib/utils/ma-saison";

type Etat = "chargement" | "ok" | "echec";

/**
 * Parenthétique de rang de la bande (#502) — pas `RANK_LABEL_LONG`
 * (`lib/labels.ts`), qui documente sa forme comme le delta minuscule affiché
 * *sous* les compteurs, pas comme de la prose enchâssée dans une phrase à
 * 20px : son « général, genre ou catégorie » y pèse trop lourd. Le mode `all`
 * prend ici un libellé propre — « meilleur classement » — puisque c'est
 * exactement ce qu'il désigne, le meilleur des trois.
 */
const LIBELLE_RANG_BANDE: Record<RankType, string> = {
  scratch: "classement général",
  category: "classement catégorie",
  gender: "classement genre",
  all: "meilleur classement",
};

/** Hauteur intérieure minimale de la bande, dans ses trois états visibles.
 *
 *  La bande n'est **pas** dans le HTML initial — l'athlète retenu vit en
 *  `localStorage` et n'atteint aucun rendu serveur (`frontend/AGENTS.md:218`).
 *  Elle apparaît donc à l'hydratation, ce qui décale les compteurs club vers le
 *  bas : coût déjà assumé par #467. Ce qu'on refuse, c'est un **second**
 *  décalage au retour du fetch — d'où un plancher de hauteur posé dès le
 *  squelette.
 *
 *  Deux plateaux, posés en classes Tailwind sur `Bande` (`min-h-[84px]
 *  sm:min-h-[68px]`) plutôt qu'un seul `minHeight` inline : `Ligne` passe en
 *  `flex-col` sous `sm`, où son empilement mesuré (texte principal ~55px +
 *  8px de `gap` + secondaire ~20px) dépasse les 68px qui suffisent à la
 *  disposition sur une ligne. La promesse ne tient donc **qu'à partir de
 *  `sm`**, et seulement tant que le texte principal ne fait pas deux lignes —
 *  un écran plus étroit que 360px ou un nom très long peut encore la
 *  rouvrir ; ce cas-là n'est pas couvert ici. */

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
 * Accessibilité (#477) : `AnnonceStatut` sur changement de saison, de
 * discipline **ou** de rang — les trois se répercutent sur le résumé calculé
 * (`resumeCourant`), donc un seul mécanisme de comparaison au résumé
 * précédent couvre les trois. Muette à la **première** apparition, qui serait
 * du bruit à chaque chargement de page.
 *
 * La région `role="status"` est montée **inconditionnellement**, dans les
 * quatre branches (y compris `chargement` et `echec`) — comme tous les autres
 * usages du dépôt (`StatCardsRank`, `PodiumsList`, `EventList`,
 * `RaceFinishers`). Une région ARIA live injectée déjà pleine (montage
 * conditionnel sur son propre contenu) est le cas que les lecteurs d'écran
 * laissent tomber : seul son **texte** doit changer après l'enregistrement de
 * la région pour être annoncé. Le silence de la première apparition vient
 * donc de `texteAnnonce` vide (`""`), jamais de l'absence du nœud.
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
  // Dernier texte effectivement annoncé — `null` avant la première annonce.
  // État et non ref : sa lecture pendant le rendu doit rester réactive (c'est
  // lui qui décide si `<AnnonceStatut>` est monté).
  const [texteAnnonce, setTexteAnnonce] = useState<string | null>(null);
  // Résumé silencieusement enregistré à la dernière comparaison. Ref et non
  // état : sa seule mise à jour ne doit pas provoquer de rendu — c'est
  // `texteAnnonce` qui en décide, via l'effet ci-dessous. Jamais lu pendant
  // le rendu (`react-hooks/refs`), seulement dans l'effet.
  const dernierResume = useRef<string | null>(null);

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

  // Calculés inconditionnellement (participations vide hors de l'état "ok",
  // coût négligeable) : un Hook ne peut pas suivre un retour anticipé, et
  // l'effet d'annonce ci-dessous a besoin du résumé à chaque rendu.
  const nom = athlete ? nomComplet(athlete) : "";
  const { epreuves, podiums } = compteMaSaison(participations, mode);
  const rang = LIBELLE_RANG_BANDE[mode];
  const resumeCourant =
    etat === "ok"
      ? epreuves === 0
        ? `Ma saison : ${nom} — aucune épreuve sur cette sélection. Le club en a couru ${clubEvents}.`
        : `Ma saison : ${nom} — ${motCompte(epreuves, "épreuve")} · ${motCompte(podiums, "podium")} (${rang}). Le club a couru ${motCompte(clubEvents, "épreuve")} sur la même sélection.`
      : null;

  useEffect(() => {
    if (resumeCourant === null) return;
    if (dernierResume.current === null) {
      // Première apparition : on retient le résumé pour comparaison future,
      // sans l'annoncer (#477).
      dernierResume.current = resumeCourant;
      return;
    }
    if (dernierResume.current !== resumeCourant) {
      dernierResume.current = resumeCourant;
      setTexteAnnonce(resumeCourant);
    }
  }, [resumeCourant]);

  if (!athlete) return null;

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
        <AnnonceStatut texte={texteAnnonce ?? ""} />
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
        <AnnonceStatut texte={texteAnnonce ?? ""} />
        <Ligne
          principale={nom}
          secondaire="Chiffres indisponibles pour l'instant."
          action={lienProfil}
        />
      </Bande>
    );
  }

  if (epreuves === 0) {
    const texte = `${nom} — aucune épreuve sur cette sélection.`;
    return (
      <Bande>
        <AnnonceStatut texte={texteAnnonce ?? ""} />
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

  const principale = `${nom} — ${motCompte(epreuves, "épreuve")} · ${motCompte(podiums, "podium")} (${rang})`;
  const secondaire = `Le club a couru ${motCompte(clubEvents, "épreuve")} sur la même sélection.`;

  return (
    <Bande>
      <AnnonceStatut texte={texteAnnonce ?? ""} />
      <Ligne principale={principale} secondaire={secondaire} action={lienProfil} />
    </Bande>
  );
}

function Bande({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <Card>
        <Eyebrow>Ma saison</Eyebrow>
        <div className="flex min-h-[84px] items-center sm:min-h-[68px]">
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
    <div
      data-testid="ma-saison-ligne"
      className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
    >
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
