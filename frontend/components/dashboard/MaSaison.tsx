"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AnnonceStatut, Button, Card, Eyebrow } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ATHLETE_LOST_EVENT,
  clearAthlete,
  nomComplet,
  OPEN_PICKER_EVENT,
  useSelectedAthlete,
} from "@/components/layout/AthletePicker";
import { ApiError, apiClient } from "@/lib/api/client";
import { RANK_PARAM, rankTypeFromParam, type RankType } from "@/lib/rank";
import type { Participation } from "@/lib/types";
import { motCompte } from "@/lib/utils/format";
import { compteMaSaison } from "@/lib/utils/ma-saison";
import { parseSeasonsParam } from "@/lib/utils/season";

// « chargement »/« ok »/« echec » sont l'issue du fetch ; « perdu » est le
// cas particulier d'un 404 (#502, item 11) : l'athlète retenu a disparu
// (suppression, fusion admin) — le stock est purgé mais la bande reste
// affichée pour porter l'invitation à en choisir un autre.
type Etat = "chargement" | "ok" | "echec" | "perdu";

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

/** Première lettre en capitale — le libellé de rang ouvre la ligne
 *  secondaire (#502, revue UI/UX) et y tient donc le rôle du premier mot de
 *  la phrase, quand `LIBELLE_RANG_BANDE` le garde en minuscules pour son
 *  usage entre parenthèses de `resumeCourant`. */
function capitaliser(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

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
 *  `flex-col` sous `sm`, où l'action se retrouve **sous** le texte plutôt
 *  qu'à côté.
 *
 *  Mesures réelles (revue UI/UX #502, `hmtx`/`hhea` du woff2 servi) : une
 *  ligne Anton 20px pèse 30,1px de boîte, une ligne Barlow 14px 16,8px.
 *  Depuis que le parenthétique de rang a quitté la ligne principale pour
 *  ouvrir la secondaire, celle-ci pèse 295px et la secondaire 309px — contre
 *  471px pour l'ancienne ligne unique, dont 176px pour le seul parenthétique.
 *
 *  **À partir de `sm`** (largeur de texte disponible ≥391px, mesurée jusqu'à
 *  425px au rail replié de 768px), les deux tiennent chacune sur une ligne :
 *  30,1 + 4px de marge + 16,8 = 50,9px, sous les 68px réservés. La promesse
 *  tient donc désormais sur **toute** la plage `sm`, alors qu'avant ce lot le
 *  parenthétique ne laissait passer une ligne principale seule qu'au-delà
 *  d'environ 814px de viewport — le repli sur deux lignes était l'état
 *  ordinaire entre `sm` et ce seuil, pas l'exception, d'où le décalage de
 *  +13px mesuré en revue sur cette plage.
 *
 *  **Sous `sm`** (270px de texte disponible à 360px de viewport), les deux
 *  lignes dépassent encore cette largeur (295px et 309px) et peuvent se
 *  replier à deux lignes chacune — ce lot ne change rien à ce cas : c'était
 *  déjà vrai de l'ancien texte (+39px de décalage mesuré à 360px, plancher de
 *  84px contre ~123px réels, action comprise sur sa propre ligne). La
 *  promesse ne couvre donc que `sm` et au-delà, comme le disait déjà cette
 *  note avant ce lot — un viewport plus étroit que 360px ou un nom très long
 *  peut la rouvrir plus encore ; ce cas-là n'est pas couvert ici. */

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
 *
 * Un 404 sur `getAthlete` (#502, revue UI/UX, item 11) distingue son cause de
 * celle d'une panne réseau : `ApiError.status === 404` signe une fiche
 * disparue (suppression, fusion admin), une `TypeError` de `fetch` signe une
 * panne. Seul le premier purge le stock — le second le laisserait perdre le
 * choix de quelqu'un dont l'athlète existe très bien.
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
  // Rejoue l'effet sans changer ni `id` ni `seasons` ni `federalOnly` — le
  // bouton « Réessayer » de l'état d'échec incrémente ce compteur, seule
  // façon honnête de refaire le même fetch (#502, item 5).
  const [tentative, setTentative] = useState(0);
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
      .catch((err) => {
        if (annule) return;
        if (err instanceof ApiError && err.status === 404) {
          // La fiche a disparu (suppression, fusion admin, #502 item 11) :
          // le stock pointerait sur un athlète mort — on le purge pour que
          // la tuile du rail cesse elle aussi de pointer dessus. Jamais sur
          // une simple panne réseau (`TypeError`, pas `ApiError`) : ce
          // serait perdre le choix de quelqu'un dont l'athlète existe bien.
          clearAthlete();
          // Après `clearAthlete()`, pour que la mise en veille de
          // `InvitationAthlete` (#588) tienne compte de l'ordre des deux
          // événements (`ATHLETE_CHANGED_EVENT` d'abord, celui-ci ensuite).
          window.dispatchEvent(new Event(ATHLETE_LOST_EVENT));
          setEtat("perdu");
        } else {
          setEtat("echec");
        }
      });
    return () => {
      annule = true;
    };
  }, [id, seasons, federalOnly, tentative]);

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

  // « Ma saison » suppose une saison unique — faux dès que `SeasonSelector`
  // en retient plusieurs, où le h1 juste au-dessus dit « N saisons
  // sélectionnées » (#502, item 10). C'est le seul mot du bloc qui pouvait
  // devenir faux ; le corps s'en tirait déjà (« sur cette sélection »).
  const titre = parseSeasonsParam(seasons).length > 1 ? "Mes saisons" : "Ma saison";

  if (!athlete && etat !== "perdu") return null;

  const lienProfil = (
    <Link
      href={`/athletes/${athlete?.id}`}
      className="-my-1 inline-block py-1 text-sm font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
    >
      Voir mon athlète →
    </Link>
  );

  if (etat === "chargement") {
    return (
      <Bande titre={titre}>
        <AnnonceStatut texte={texteAnnonce ?? ""} busy />
        <div
          data-testid="ma-saison-squelette"
          style={{ display: "flex", flexDirection: "column", gap: 10 }}
        >
          <Skeleton className="h-6 w-full max-w-72" />
          <Skeleton className="h-4 w-3/4 max-w-56" />
        </div>
      </Bande>
    );
  }

  if (etat === "perdu") {
    return (
      <Bande titre={titre}>
        <AnnonceStatut texte={texteAnnonce ?? ""} />
        <Ligne
          principale="Votre fiche a changé"
          secondaire="Choisissez votre nom à nouveau."
          action={
            <button
              type="button"
              onClick={() => window.dispatchEvent(new Event(OPEN_PICKER_EVENT))}
              className="-my-1 inline-block py-1 text-sm font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
            >
              Choisir mon athlète →
            </button>
          }
        />
      </Bande>
    );
  }

  if (etat === "echec") {
    return (
      <Bande titre={titre}>
        <AnnonceStatut texte={texteAnnonce ?? ""} />
        <Ligne
          principale={nom}
          secondaire="Chiffres indisponibles pour l'instant."
          action={
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" onClick={() => setTentative((t) => t + 1)}>
                Réessayer
              </Button>
              {lienProfil}
            </div>
          }
        />
      </Bande>
    );
  }

  if (epreuves === 0) {
    const texte = `${nom} — aucune épreuve sur cette sélection.`;
    return (
      <Bande titre={titre}>
        <AnnonceStatut texte={texteAnnonce ?? ""} />
        <Ligne
          principale={texte}
          secondaire={`Le club en a couru ${motCompte(clubEvents, "épreuve")} sur la même sélection.`}
          action={
            <Link
              href="/ajouter"
              className="-my-1 inline-block py-1 text-sm font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
            >
              Ajouter une épreuve →
            </Link>
          }
        />
      </Bande>
    );
  }

  const principale = `${nom} — ${motCompte(epreuves, "épreuve")} · ${motCompte(podiums, "podium")}`;
  const secondaire = `${capitaliser(rang)} · le club a couru ${motCompte(clubEvents, "épreuve")} sur la même sélection.`;

  return (
    <Bande titre={titre}>
      <AnnonceStatut texte={texteAnnonce ?? ""} />
      <Ligne principale={principale} secondaire={secondaire} action={lienProfil} />
    </Bande>
  );
}

function Bande({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <Card>
        {/* `Eyebrow` rend un `<div>` (pas de sémantique de titre) : sans
            relais, un parcours par titres (WCAG 1.3.1) saute le seul bloc de
            l'écran qui parle du membre, quand ses deux voisins immédiats sont
            des `h2` (#502, item 6). Un `h2` masqué visuellement porte donc le
            même texte que l'`Eyebrow` visible plutôt qu'un `aria-labelledby`
            de section : le libellé est dynamique (« Ma saison »/« Mes
            saisons », item 10) et un simple relais de titre évite d'ouvrir un
            second point d'entrée (la sémantique de landmark) pour un bloc qui
            n'en a nul besoin ailleurs sur la page. */}
        <h2 className="sr-only">{titre}</h2>
        <Eyebrow>{titre}</Eyebrow>
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
