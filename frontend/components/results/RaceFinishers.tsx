"use client";
import Link, { useLinkStatus } from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { Card, SegmentedControl, PlaceBadge, AnnonceStatut } from "@/components/tcn";
import { StatusBadge } from "@/components/results/StatusBadge";
import { isNonFinisher } from "@/lib/utils/raceOrder";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { secondsFromHms } from "@/lib/utils/time";
import { genderShort } from "@/lib/utils/format";
import { EmptyState } from "@/components/ui/empty-state";
import { ClassementPagination } from "@/components/results/ClassementPagination";
import { PAGE_SIZE_DEFAUT, PAGE_SIZE_PARAM, parsePageSize } from "@/lib/pageSize";
import { CATEGORY_PARAM, CLUB_PARAM, SCOPE_CLUB, SCOPE_PARAM } from "@/lib/scope";
import { CLUB_NAME } from "@/lib/club";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
import { categoryTitle } from "@/lib/categories";
import type { CourseSummary, Participation } from "@/lib/types";

// Colonnes fixes (rang, athlète, catég., sexe, temps total) + club en fin.
const BASE_COLS = "54px 1fr 70px 56px 100px";
const CLUB_COL = "1.1fr";

// Clé de tri du temps total : distincte de toute clé de split réelle
// (swim/t1/bike/t2/run/course1/course2), qui vivent dans `Participation.splits`
// alors que le temps total vit dans `Participation.total_time`.
const CLE_TEMPS_TOTAL = "__temps_total__";

// Style partagé des boutons d'action des états d'absence (« Effacer la
// recherche », « Voir tous les participants ») : `padding` + `minHeight: 24`
// pour le plancher tactile WCAG 2.2 2.5.8, sous 24 px quand le bouton ne tient
// sa hauteur que du texte.
const STYLE_BOUTON_ABSENCE = {
  background: "none",
  border: "none",
  padding: "4px 0",
  minHeight: 24,
  font: "inherit",
  fontWeight: 700,
  color: "var(--tcn-ink)",
  cursor: "pointer",
} as const;

/**
 * Une ligne de finisher ouvre le détail de **ce résultat**, pas le profil de
 * l'athlète : depuis un classement, la question est « comment s'est passée
 * cette course », pas « qui est ce coureur ».
 */
function detailHref(p: Participation): string {
  return `/courses/${p.course.id}/participations/${p.id}`;
}

/**
 * Marque d'attente de la ligne cliquée (#481, FR-005).
 *
 * Vit **dans** le lien parce que `useLinkStatus` ne se lit que depuis un
 * descendant de `<Link>` (doc de Next 16.3.1), et se cale sur la **ligne**, le
 * `<tr>` étant l'ancêtre positionné (`.tcn-rowlink`).
 *
 * **C'est un filet en pied de ligne, pas un voile par-dessus.** La première
 * version couvrait la ligne entière d'une nappe `--tcn-surface-sunk` à 0,6 :
 * un descendant positionné passe au-dessus du contenu en flux de *toutes* les
 * cellules, et le texte tombait à 2,50:1 (`--tcn-ink`) voire 1,74:1
 * (`--tcn-text-muted`, colonne Club) — sous le plancher WCAG 1.4.3 de 4,5:1
 * (revue UI/UX). Elle était en outre **invisible** sur la ligne survolée,
 * c'est-à-dire celle qu'on vient de cliquer à la souris : le `:hover` de
 * `.tcn-rowlink` pose déjà exactement ce fond. Inefficace comme changement de
 * fond, trop violent comme atténuation de texte.
 *
 * Le filet ne recouvre aucun texte, donc aucun contraste de texte ne bouge, et
 * `--tcn-orange` tient 1.4.11 (3,32:1) sur les deux fonds de ligne.
 *
 * Toujours monté, seule son opacité change : la doc de Next met en garde contre
 * un indicateur monté au clic, qui déplace la mise en page. C'est aussi ce qui
 * le rend perceptible sous `prefers-reduced-motion` — il n'y a aucun mouvement
 * à figer.
 *
 * `pending` reste faux sur un ⌘/Ctrl+clic ou un clic milieu : ils n'ouvrent pas
 * de navigation cliente. Le scénario « ouvrir dans un onglet n'allume rien »
 * est donc satisfait sans code.
 */
function VoileAttente() {
  const { pending } = useLinkStatus();
  return (
    <span
      aria-hidden="true"
      data-attente={String(pending)}
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: 3,
        background: "var(--tcn-orange)",
        opacity: pending ? 1 : 0,
        transition: "opacity var(--tcn-dur-fast)",
        pointerEvents: "none",
      }}
    />
  );
}

/**
 * Cellule d'un inter — **ne rend que ce qui se lit comme une durée** (#472).
 *
 * Le repli `—` ne couvrait que l'absence de valeur, jamais l'impossible : un
 * `0-2:-15:00` (observé sur la course 340) partait à l'écran tel quel, que rien
 * ne distinguait d'un chronomètre exact. Il devient un manque **signalé** — ni
 * la chaîne brute, ni un silence qui ferait croire que le chronométreur n'a rien
 * publié. Même lecture que le tri, qui écarte déjà ces valeurs faute de pouvoir
 * les comparer.
 */
function CelluleInter({ valeur, small }: { valeur?: string; small?: boolean }) {
  const style = {
    fontSize: 13,
    fontWeight: small ? 400 : 600,
    color: small ? "var(--tcn-grey-400)" : "var(--tcn-text-body)",
  };
  if (valeur && secondsFromHms(valeur) == null) {
    const motif = `Temps illisible chez le chronométreur (« ${valeur} ») — la donnée existe, mais ce n'est pas un temps.`;
    return (
      <td role="cell" style={style}>
        —{" "}
        <span
          // `role="img"` : le marqueur informe, il ne commande rien.
          role="img"
          title={motif}
          aria-label={motif}
          // `position: relative` : le `::after` de `.tcn-rowlink__cible` couvre
          // la ligne entière et gagne le survol sur tout contenu en flux. Sans
          // cette remontée, le ⚠ affiche le pointeur de la ligne et **aucune**
          // infobulle — le marqueur redevient muet, ce que #472 avait
          // justement corrigé.
          style={{ position: "relative", color: "var(--tcn-text-faint)", cursor: "help", userSelect: "none" }}
        >
          ⚠
        </span>
      </td>
    );
  }
  return <td role="cell" style={style}>{valeur ?? "—"}</td>;
}

/**
 * Seuils du marqueur d'écart, calés par sondage (#486, RES-10).
 *
 * Point de vérité : `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`,
 * qui **prime** — le seuil de 2 % proposé par l'audit signalait 8,02 % du classement,
 * dont 285 lignes d'une épreuve que le produit tient pour fiable. Les régler se fait
 * là-bas, en re-mesurant, pas ici.
 *
 * Une ligne n'est douteuse que face à **ses pairs** : 81,7 % des écarts mesurés sont
 * « total > somme », signature d'un segment que le chronométreur ne publie pas — une
 * propriété de l'épreuve, dite une seule fois en tête de page.
 */
const ECART_SEUIL = 0.05;
/** Sous cet effectif, la médiane n'est pas une référence (course 65 : neuf enfants). */
const ECART_MIN_LIGNES = 10;
/** Sans ce plancher, un petit dénominateur suffit à franchir 5 %. */
const ECART_MIN_SECONDES = 60;

/**
 * Marqueur d'une ligne dont les inters ne rendent pas compte de son temps total.
 *
 * L'écart lui-même vient du serveur (`split_gap_ratio`) : le recalculer ici rejouerait
 * #76, où trois listes divergentes du critère club ont fait compter tout Nantes comme
 * TCN. L'écran ne fait que comparer aux seuils d'affichage.
 */
function MarqueurEcart({
  ratio,
  mediane,
  lignesEvaluees,
  totalTime,
}: {
  ratio?: number | null;
  mediane: number | null;
  lignesEvaluees: number;
  totalTime: string | null;
}) {
  if (ratio == null || mediane == null || lignesEvaluees < ECART_MIN_LIGNES) return null;

  const ecart = Math.abs(ratio - mediane);
  if (ecart <= ECART_SEUIL) return null;

  const secondes = secondsFromHms(totalTime);
  if (secondes == null || ecart * secondes <= ECART_MIN_SECONDES) return null;

  const motif =
    "Les temps intermédiaires de cette ligne ne rendent pas compte de son temps total — " +
    "les autres lignes de l'épreuve ne présentent pas cet écart. Les temps affichés sont " +
    "ceux publiés par le chronométreur.";

  return (
    <span
      // `role="img"` : le marqueur informe, il ne commande rien — même patron que
      // `CelluleInter`, posé par #472.
      role="img"
      title={motif}
      aria-label={motif}
      style={{ marginLeft: 6, color: "var(--tcn-text-faint)", cursor: "help", userSelect: "none" }}
    >
      ⚠
    </span>
  );
}

export function RaceFinishers({
  participations,
  summary,
  total,
  page,
  pageSize,
  eventType,
}: {
  /** La tranche courante, **déjà ordonnée par le backend** — ne pas la retrier. */
  participations: Participation[];
  /** Synthèse de l'épreuve entière : indépendante de la recherche et du filtre. */
  summary: CourseSummary;
  /** Total de la sélection (recherche + filtre club), qui donne le nombre de pages. */
  total: number;
  page: number;
  /** `null` quand tout le classement a été demandé. */
  pageSize: number | null;
  eventType?: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const rechercheUrl = searchParams.get("q") ?? "";
  const [recherche, setRecherche] = useState(rechercheUrl);
  const [derniereUrl, setDerniereUrl] = useState(rechercheUrl);
  // Tri optionnel côté client, déclenché par un clic sur l'en-tête d'un split
  // ou du temps total (#309) — sur la seule tranche affichée. `null` tant
  // qu'aucun en-tête n'a été cliqué : l'ordre reste alors celui du backend.
  // Recliquer sur le même en-tête inverse la direction ; cliquer sur un autre
  // en-tête repart en croissant.
  const [tri, setTri] = useState<{ cle: string; direction: "asc" | "desc" } | null>(null);

  // Athlète retenu (#467) : lu côté client, sur les seules lignes de la
  // tranche affichée — c'est tout ce que le client tient. Un seul appel, en
  // tête : un hook ne s'appelle pas dans la boucle des lignes.
  const athleteRetenu = useSelectedAthlete();
  // Même patron que `ResultsFilters` (`nomRetenu`) : les deux surfaces se
  // lisent pareil, et évite de recalculer `nomComplet` à chaque usage du rendu.
  const nomRetenu = athleteRetenu ? nomComplet(athleteRetenu) : null;

  function trierSur(cle: string) {
    setTri((precedent) =>
      precedent?.cle === cle
        ? { cle, direction: precedent.direction === "asc" ? "desc" : "asc" }
        : { cle, direction: "asc" }
    );
  }

  // L'URL est la vérité : après un « Précédent » du navigateur, le champ doit
  // suivre. Ajustement pendant le rendu plutôt qu'en effet — React le
  // recommande pour un état dérivé d'une valeur qui change.
  if (rechercheUrl !== derniereUrl) {
    setDerniereUrl(rechercheUrl);
    setRecherche(rechercheUrl);
  }

  const filtreClub = searchParams.get(SCOPE_PARAM) === SCOPE_CLUB;
  // Filtres venus des cartes de synthèse (#486, RES-11). Distincts de
  // `filtreClub`, qui porte la sémantique TCN arbitrée par le backend : ici,
  // c'est un club quelconque, en égalité exacte.
  const clubChoisi = searchParams.get(CLUB_PARAM) ?? "";
  const categorieChoisie = searchParams.get(CATEGORY_PARAM) ?? "";
  // La taille vient de l'URL, pas de la prop `pageSize` : sous `all`, le
  // backend renvoie `null` et le sélecteur n'aurait plus quoi afficher.
  const tailleCourante = parsePageSize(searchParams.get(PAGE_SIZE_PARAM));

  /** Construit une URL en repartant des paramètres courants. */
  function lienVers(modifications: Record<string, string | null>): string {
    const params = new URLSearchParams(searchParams.toString());
    for (const [cle, valeur] of Object.entries(modifications)) {
      if (valeur === null || valeur === "") params.delete(cle);
      else params.set(cle, valeur);
    }
    const query = params.toString();
    return `${pathname}${query ? `?${query}` : ""}`;
  }

  /**
   * Toute modification de la recherche ou du filtre remet à la première page :
   * une recherche à trois résultats atterrirait sinon sur une page vide.
   */
  function naviguer(modifications: Record<string, string | null>) {
    startTransition(() => router.push(lienVers({ ...modifications, page: null })));
  }

  /** Saut direct à une page, la recherche et le filtre en cours conservés. */
  function naviguerPage(n: number) {
    startTransition(() => router.push(lienVers({ page: n === 1 ? null : String(n) })));
  }

  // Les colonnes viennent de la synthèse et non des lignes affichées : sur vingt
  // lignes, elles changeraient d'une page à l'autre.
  const segments = splitColumnsFromKeys(eventType ?? "", summary.split_keys);
  const fcols = [BASE_COLS, ...segments.map((s) => (s.small ? "64px" : "80px")), CLUB_COL].join(" ");

  const nbPages = pageSize ? Math.max(1, Math.ceil(total / pageSize)) : 1;

  /**
   * État du tri **de la colonne**, pour l'aide technique (#481, WCAG 1.3.1).
   *
   * Complémentaire de l'`aria-label` du bouton d'`EnteteTriable`, qui annonce
   * l'action **à venir** : `aria-sort` dit l'état courant. `"none"` sur une
   * colonne triable mais non triée — l'omettre la rendrait indiscernable d'une
   * colonne qui ne se trie pas.
   */
  function ariaSort(cle: string): "ascending" | "descending" | "none" {
    if (tri?.cle !== cle) return "none";
    return tri.direction === "asc" ? "ascending" : "descending";
  }

  /** Temps (en secondes) du participant pour la colonne de tri active. */
  function temps(p: Participation, cle: string): number | null {
    return secondsFromHms(cle === CLE_TEMPS_TOTAL ? p.total_time : p.splits?.[cle]);
  }

  // Valeurs non temporelles (DNF/DNS/DSQ, segment non publié) envoyées en fin
  // de classement, croissant comme décroissant : ce n'est pas un temps nul, il
  // n'y a simplement rien à comparer. `sort` est stable (ES2019+) : les
  // égalités et les lignes non triées gardent l'ordre du backend.
  const lignes = tri
    ? [...participations].sort((a, b) => {
        const sa = temps(a, tri.cle);
        const sb = temps(b, tri.cle);
        if (sa == null) return sb == null ? 0 : 1;
        if (sb == null) return -1;
        return tri.direction === "asc" ? sa - sb : sb - sa;
      })
    : participations;

  // WCAG 4.1.3 (#477) : le tri par en-tête réordonne les 1080 px du tableau
  // sans déplacer le focus — sans cette annonce, un lecteur d'écran ne le voit
  // pas passer, pas plus que le nouveau décompte après une recherche.
  const libelleTri = tri
    ? tri.cle === CLE_TEMPS_TOTAL
      ? "temps total"
      : `temps ${segments.find((s) => s.key === tri.cle)?.label ?? tri.cle}`
    : null;
  // Le tri par en-tête ne porte que sur la tranche affichée. Sur 43 pages, le
  // taire rendrait le classement trompeur ; sous `page_size=all`, il n'y a rien
  // à dire, le tri est global.
  const perimetreTri =
    pageSize == null || lignes.length === 0
      ? ""
      : `, sur ${lignes.length === 1 ? "la ligne affichée" : `les ${lignes.length} lignes affichées`}`;
  const texteAnnonce =
    `${lignes.length} résultat${lignes.length > 1 ? "s" : ""} affiché${lignes.length > 1 ? "s" : ""}` +
    (libelleTri
      ? `, trié par ${libelleTri}, ${tri!.direction === "asc" ? "croissant" : "décroissant"}${perimetreTri}`
      : "");

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <AnnonceStatut texte={texteAnnonce} />
      <div style={{ padding: "20px 26px", borderBottom: "1px solid var(--tcn-border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        {/* `id` : il nomme le tableau plus bas. `/courses/[id]` en porte deux,
            et sans nom un lecteur d'écran les annonce tous deux « tableau »
            sans dire lequel — « Top clubs » l'était déjà (#481). */}
        <div id="titre-classement" style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>Classement</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <form
            role="search"
            onSubmit={(e) => {
              e.preventDefault();
              naviguer({ q: recherche.trim() || null });
            }}
            style={{ display: "flex", gap: 6 }}
          >
            <label htmlFor="recherche-athlete" className="sr-only">
              Rechercher un athlète
            </label>
            <input
              id="recherche-athlete"
              type="search"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Rechercher un athlète"
              style={{ height: 34, minWidth: 190, padding: "0 10px", fontSize: 13, borderRadius: 8, border: "1px solid var(--tcn-border)", background: "var(--tcn-surface)", color: "var(--tcn-ink)" }}
            />
            <button
              type="submit"
              style={{ height: 34, padding: "0 12px", fontSize: 13, fontWeight: 700, borderRadius: 8, border: "1px solid var(--tcn-border)", background: "var(--tcn-fill)", color: "var(--tcn-ink)", cursor: "pointer" }}
            >
              Chercher
            </button>
          </form>
          {athleteRetenu && (
            <button
              type="button"
              // La portée club ne survit pas au saut : `scope=club` filtre déjà
              // sur `is_tcn`, or la recherche par nom peut viser un athlète
              // hors club — le garder pouvait faire échouer un saut qui devrait
              // réussir.
              onClick={() => naviguer({ q: nomRetenu, [SCOPE_PARAM]: null })}
              aria-label={`Aller à ma ligne — ${nomRetenu}`}
              // Bordé, pas un lien de texte : `.tcn-lien-action` ne convient
              // pas. Stylé en ligne, il ne peut pas déclarer son propre
              // `:focus-visible` — d'où `.tcn-cta-classement`, qui ne porte
              // que l'anneau (globals.css).
              className="tcn-cta-classement"
              style={{ height: 34, padding: "0 12px", fontSize: 13, fontWeight: 700, borderRadius: 8, border: "1.5px solid var(--tcn-orange-deep)", background: "var(--tcn-surface)", color: "var(--tcn-orange-deep)", cursor: "pointer" }}
            >
              Aller à ma ligne
            </button>
          )}
          <SegmentedControl
            tone="ink"
            value={filtreClub ? "tcn" : "all"}
            onChange={(v) => naviguer({ [SCOPE_PARAM]: v === "tcn" ? SCOPE_CLUB : null })}
            options={[
              { value: "all", label: `Tous les participants (${summary.total})` },
              { value: "tcn", label: `${CLUB_NAME} (${summary.tcn_count})`, dot: true, disabled: summary.tcn_count === 0 },
            ]}
          />
        </div>
      </div>
      {(rechercheUrl || filtreClub || clubChoisi || categorieChoisie) && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: "10px 26px", borderBottom: "1px solid var(--tcn-border)", fontSize: 13, color: "var(--tcn-text-body)" }}>
          <span>
            {libelleSelection(total, summary.total, {
              recherche: rechercheUrl,
              filtreClub,
              club: clubChoisi,
              categorie: categorieChoisie,
            })}
          </span>
          {/* Un repère par filtre, **retirable indépendamment** : deux
              sélections actives ne se retirent pas d'un bloc, sinon activer une
              catégorie depuis la carte effacerait le club qu'on venait de
              choisir (#486, FR-021). */}
          {clubChoisi && (
            <ChipRetirable
              libelle={clubChoisi}
              sujet="le filtre club"
              onRetirer={() => naviguer({ [CLUB_PARAM]: null })}
            />
          )}
          {categorieChoisie && (
            <ChipRetirable
              libelle={categoryTitle(categorieChoisie)}
              sujet="le filtre catégorie"
              onRetirer={() => naviguer({ [CATEGORY_PARAM]: null })}
            />
          )}
          <button
            type="button"
            onClick={() =>
              naviguer({
                q: null,
                [SCOPE_PARAM]: null,
                [CLUB_PARAM]: null,
                [CATEGORY_PARAM]: null,
              })
            }
            style={{ background: "none", border: "none", padding: "4px 0", minHeight: 24, font: "inherit", fontWeight: 700, color: "var(--tcn-ink)", textDecoration: "underline", cursor: "pointer" }}
          >
            Tout effacer
          </button>
        </div>
      )}
      <div
        style={{ overflowX: "auto" }}
        data-pending={pending || undefined}
        className="transition-opacity data-pending:opacity-60"
      >
        <div style={{ minWidth: 1080 }}>
          <table className="tcn-table" role="table" aria-labelledby="titre-classement">
          <thead role="rowgroup">
          <tr role="row" style={{ display: "grid", gridTemplateColumns: fcols, gap: "0 12px", alignItems: "center", padding: "12px 22px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
            <th role="columnheader" scope="col">Rang</th><th role="columnheader" scope="col">Athlète</th><th role="columnheader" scope="col">Catég.</th><th role="columnheader" scope="col">Sexe</th>
            <th role="columnheader" scope="col" aria-sort={ariaSort(CLE_TEMPS_TOTAL)}>
              <EnteteTriable cle={CLE_TEMPS_TOTAL} libelle="Temps total" ariaSujet="temps total" tri={tri} onTrier={trierSur} perimetre={perimetreTri} />
            </th>
            {segments.map((s) => (
              <th role="columnheader" scope="col" key={s.key} aria-sort={ariaSort(s.key)}>
                <EnteteTriable cle={s.key} libelle={s.label} ariaSujet={`temps ${s.label}`} tri={tri} onTrier={trierSur} perimetre={perimetreTri} />
              </th>
            ))}
            <th role="columnheader" scope="col">Club</th>
          </tr>
          </thead>
          <tbody role="rowgroup">
          {lignes.map((p) => {
            const own = p.is_tcn;
            const nf = isNonFinisher(p.status);
            const moi = athleteRetenu?.id === p.athlete.id;
            const name = [p.athlete.nom, p.athlete.prenom].filter(Boolean).join(" ");
            const splits = p.splits ?? {};
            return (
              <tr
                key={p.id}
                role="row"
                className={moi ? "tcn-rowlink tcn-rowlink--moi" : "tcn-rowlink"}
                style={{
                  display: "grid",
                  gridTemplateColumns: fcols,
                  gap: "0 12px",
                  alignItems: "center",
                  padding: "12px 22px",
                  borderBottom: "1px solid var(--tcn-border-faint)",
                  borderLeft: `3px solid ${own ? "var(--tcn-orange)" : "transparent"}`,
                  // Le fond de « ma ligne » vit en classe (`.tcn-rowlink--moi`,
                  // globals.css), pas ici : un style en ligne battrait toute
                  // couche CSS et couperait le survol de `.tcn-rowlink:hover`
                  // (#439). Le chip « Vous » porte seul la distinction — le
                  // fond n'est qu'un appui de teinte (1,11:1 mesuré contre une
                  // ligne blanche, nul en luminance contre le gris ci-dessous :
                  // WCAG 1.4.1 tient sur le chip, pas sur ce fond). Il reste
                  // posé même sur un non-finisher : un athlète qui a abandonné
                  // reste l'athlète retenu. Le gris des non-finishers, lui,
                  // reste en ligne — il ne concerne que les lignes qui ne sont
                  // pas la mienne, `.tcn-rowlink--moi` primant les siennes par
                  // la classe.
                  background: !moi && nf
                    ? "color-mix(in srgb, var(--tcn-grey-400) 15%, transparent)"
                    : undefined,
                }}
              >
                <td role="cell">
                  {nf ? (
                    <StatusBadge status={p.status} />
                  ) : p.rank_overall != null ? (
                    <PlaceBadge place={p.rank_overall} style={{ minWidth: 28, fontSize: 16 }} />
                  ) : (
                    <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                  )}
                </td>
                {/* `minWidth: 0` remplace l'`overflow: hidden` que portait la
                    cellule, et l'ellipsis descend sur le `<span>` intérieur.
                    Les deux faisaient le même travail sur la piste `1fr` — mais
                    un `overflow` ici **rognerait** le voile de couverture du
                    lien et celui de l'attente, tous deux absolus et calés sur la
                    ligne : la ligne cesserait d'être cliquable hors du nom. */}
                <td role="cell" style={{ fontSize: 14, fontWeight: 700, color: "var(--tcn-ink)", minWidth: 0 }}>
                  <Link
                    href={detailHref(p)}
                    prefetch={false}
                    aria-label={`Voir le détail du résultat de ${name}`}
                    className="tcn-rowlink__cible"
                    style={{ display: "flex", alignItems: "center", gap: 8, maxWidth: "100%" }}
                  >
                    <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {name}
                    </span>
                    {/* Le chip, pas le fond, est le signifiant : la couleur seule
                        échouerait WCAG 1.4.1. `flex: none` pour qu'il survive à
                        un nom long, dont c'est l'ellipse qui cède. */}
                    {moi && (
                      <span
                        style={{
                          flex: "none",
                          padding: "1px 7px",
                          borderRadius: "var(--tcn-radius-sm)",
                          background: "var(--tcn-orange-deep)",
                          color: "#fff",
                          fontFamily: "var(--tcn-font-cond)",
                          fontWeight: 700,
                          fontSize: 11,
                          letterSpacing: ".04em",
                        }}
                      >
                        Vous
                      </span>
                    )}
                    <VoileAttente />
                  </Link>
                </td>
                <td role="cell" style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>{p.category ?? "—"}</td>
                <td role="cell" style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>{genderShort(p.athlete.gender)}</td>
                <td role="cell" style={{ fontFamily: "var(--tcn-font-cond)", fontWeight: 700, fontSize: 15, color: "var(--tcn-ink)" }}>
                  {p.total_time ?? "—"}
                  <MarqueurEcart
                    ratio={p.split_gap_ratio}
                    mediane={summary.split_gap_median}
                    lignesEvaluees={summary.split_gap_rows}
                    totalTime={p.total_time}
                  />
                </td>
                {segments.map((s) => (
                  <CelluleInter key={s.key} valeur={splits[s.key]} small={s.small} />
                ))}
                <td role="cell" style={{ fontSize: 13, fontWeight: own ? 700 : 400, color: own ? "var(--tcn-orange-deeper)" : "var(--tcn-text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.club ?? "—"}</td>
              </tr>
            );
          })}
          </tbody>
          </table>
          {participations.length === 0 && (
            // `total > 0` : sans ce garde, une recherche sans résultat sur une
            // page sautée (`?q=zzz&page=5`) tombe dans cette branche — `nbPages`
            // vaut 1 faute de résultats, donc `page > nbPages` est vrai pour une
            // tout autre raison que « cette page n'existe pas ».
            page > nbPages && total > 0 ? (
              <EmptyState
                bare
                title="Cette page n'existe pas"
                description={`le classement s'arrête à la page ${nbPages}`}
                action={
                  <Link href={lienVers({ page: null })} style={{ fontWeight: 700, color: "var(--tcn-ink)" }}>
                    Revenir au début
                  </Link>
                }
              />
            ) : rechercheUrl && athleteRetenu && rechercheUrl === nomRetenu ? (
              // « Aller à ma ligne » ne peut pas savoir d'avance si l'athlète
              // retenu a couru : ici, il n'a pas couru. Le dire, plutôt que
              // d'annoncer un échec de recherche que personne n'a lancée. La
              // portée club tombe avec la recherche : la sélection club n'est
              // pas une intention que « aller à ma ligne » doit préserver, et
              // « Voir tous les participants » doit montrer tous les
              // participants, pas seulement ceux du club.
              <EmptyState
                bare
                title={`${nomRetenu} ne figure pas sur cette épreuve`}
                action={
                  <button
                    type="button"
                    onClick={() => naviguer({ q: null, [SCOPE_PARAM]: null })}
                    style={STYLE_BOUTON_ABSENCE}
                  >
                    Voir tous les participants
                  </button>
                }
              />
            ) : rechercheUrl && !clubChoisi && !categorieChoisie ? (
              // `&& !clubChoisi && !categorieChoisie` : sans cette exclusion, une
              // recherche **et** un filtre de carte tombaient ici, et « Effacer la
              // recherche » laissait le visiteur sur un écran toujours vide, sans
              // jamais nommer le filtre qui le vidait (relevé en revue de code).
              <EmptyState
                bare
                title="Aucun athlète ne correspond à cette recherche"
                action={
                  <button
                    type="button"
                    onClick={() => naviguer({ q: null })}
                    style={STYLE_BOUTON_ABSENCE}
                  >
                    Effacer la recherche
                  </button>
                }
              />
            ) : clubChoisi || categorieChoisie ? (
              // L'état d'absence **nomme le filtre en cause** (#486, FR-025) et
              // ne parle jamais de « recherche » quand aucune n'est active —
              // c'est le défaut constaté sur `/courses/340?scope=club`.
              <EmptyState
                bare
                title={titreAbsenceFiltre(clubChoisi, categorieChoisie, filtreClub)}
                action={
                  <button
                    type="button"
                    // La recherche part avec, quand elle est là : la laisser
                    // renverrait sur un second écran vide, pour une autre raison.
                    onClick={() =>
                      naviguer({ [CLUB_PARAM]: null, [CATEGORY_PARAM]: null, q: null })
                    }
                    style={STYLE_BOUTON_ABSENCE}
                  >
                    Voir tous les participants
                  </button>
                }
              />
            ) : filtreClub ? (
              <EmptyState
                bare
                title={`Aucun athlète du ${CLUB_NAME} sur cette épreuve`}
                action={
                  <button
                    type="button"
                    onClick={() => naviguer({ [SCOPE_PARAM]: null })}
                    style={STYLE_BOUTON_ABSENCE}
                  >
                    Voir tous les participants
                  </button>
                }
              />
            ) : (
              <EmptyState bare title="Aucun participant à afficher" />
            )
          )}
        </div>
      </div>

      <ClassementPagination
        page={page}
        nbPages={nbPages}
        lienVers={lienVers}
        tailleCourante={tailleCourante}
        onTaille={(taille) =>
          naviguer({ [PAGE_SIZE_PARAM]: taille === PAGE_SIZE_DEFAUT ? null : String(taille) })
        }
        onAllerPage={naviguerPage}
      />

      <div style={{ padding: "16px 24px", borderTop: "1px solid var(--tcn-border)", textAlign: "center", fontSize: 13, color: "var(--tcn-text-faint)" }}>
        <span>Sur l&apos;ensemble de l&apos;épreuve : </span>
        <span>{resumeEpreuve(summary)}</span>
      </div>
    </Card>
  );
}

/**
 * Cadre de la vue filtrée : ce qu'on regarde, et sur quoi.
 *
 * `total` est le total de la **sélection**, `totalEpreuve` celui de l'épreuve
 * entière — c'est leur opposition qui manquait, l'écran affirmant « 498
 * participants » sous deux lignes de résultats.
 */
function libelleSelection(
  total: number,
  totalEpreuve: number,
  selection: { recherche: string; filtreClub: boolean; club: string; categorie: string },
): string {
  const tete = `${total} résultat${total > 1 ? "s" : ""} sur ${totalEpreuve}`;
  const morceaux = [];
  if (selection.recherche) morceaux.push(`pour « ${selection.recherche} »`);
  if (selection.filtreClub) morceaux.push(`du ${CLUB_NAME}`);
  // Le club et la catégorie ne sont pas repris ici : leurs repères les portent
  // juste à côté, et les redire allongerait la ligne sans rien apprendre.
  // `join(" ")`, pas `join(", ")` : les deux clauses n'ont pas la même nature
  // (l'une qualifie la recherche, l'autre le périmètre), la virgule les met à
  // tort sur le même plan (revue UI/UX #485).
  return `${tete} ${morceaux.join(" ")}`.trimEnd();
}

/**
 * Ce que l'écran dit quand un filtre de carte ne rend personne.
 *
 * Le cas le plus fréquent n'est pas l'erreur de saisie mais le **croisement vide par
 * construction** : choisir un club autre que le TCN alors que la portée TCN est active
 * ne peut rien rendre. Le taire laisserait chercher une cause ailleurs.
 */
function titreAbsenceFiltre(club: string, categorie: string, filtreClub: boolean): string {
  if (club && filtreClub && !isTcnLabel(club)) {
    return `Aucun athlète : le filtre « ${club} » et la portée ${CLUB_NAME} s'excluent`;
  }
  const morceaux = [];
  if (club) morceaux.push(`du club « ${club} »`);
  if (categorie) morceaux.push(`en catégorie « ${categorie} »`);
  return `Aucun athlète ${morceaux.join(" ")} sur cette épreuve`;
}

/**
 * Le club choisi est-il le TCN ? Comparaison de **libellé affiché**, pas le prédicat
 * d'appartenance — celui-ci vit dans `app/core/club.py` côté serveur, dépositaire unique
 * (#76), et n'a pas à être réimplémenté ici. On compare ce que la carte a proposé.
 */
function isTcnLabel(club: string): boolean {
  return club.trim().toLowerCase() === CLUB_NAME.toLowerCase();
}

/**
 * Repère d'un filtre actif, retirable **seul** (#486, FR-021).
 *
 * Le nom accessible dit ce qu'on retire, pas seulement « × » : sur un écran où
 * quatre repères peuvent coexister, « Retirer » sans complément ne distingue rien.
 */
function ChipRetirable({
  libelle,
  sujet,
  onRetirer,
}: {
  libelle: string;
  sujet: string;
  onRetirer: () => void;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 6px 3px 10px",
        borderRadius: 999,
        border: "1px solid var(--tcn-border)",
        background: "var(--tcn-fill)",
        fontSize: 12,
        fontWeight: 700,
      }}
    >
      {libelle}
      <button
        type="button"
        onClick={onRetirer}
        aria-label={`Retirer ${sujet} « ${libelle} »`}
        // 24 px pleins : plancher tactile WCAG 2.2 2.5.8 — la croix des chips
        // était sous le seuil avant #479, et ce lot n'en réintroduit pas.
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 24,
          height: 24,
          padding: 0,
          border: "none",
          borderRadius: 999,
          background: "none",
          font: "inherit",
          fontSize: 14,
          lineHeight: 1,
          color: "var(--tcn-text-muted)",
          cursor: "pointer",
        }}
      >
        ×
      </button>
    </span>
  );
}

/**
 * Décompte de l'épreuve **entière**, distinct du nombre de lignes affichées.
 *
 * « participants », pas « partants » (#322) : `summary.total` additionne
 * finishers, abandons (dnf), non-partants (dns), disqualifiés (dsq) et
 * indéterminés — il compte donc tous ceux qui figurent sur l'épreuve, y
 * compris ceux qui n'ont jamais pris le départ. La distinction que posait #23
 * reste entière, un participant n'est pas un finisher ; seul le mot était
 * faux. Les trois premiers étaient agrégés sous un seul « abandons » avant
 * #331 — un DNS n'a jamais couru, un DSQ a fini disqualifié.
 */
function resumeEpreuve(summary: CourseSummary): string {
  const { total, finishers, dnf, dns, dsq, unknown } = summary;
  const parts = [
    `${total} participant${total > 1 ? "s" : ""}`,
    `${finishers} finisher${finishers > 1 ? "s" : ""}`,
  ];
  if (dnf > 0) parts.push(`${dnf} abandon${dnf > 1 ? "s" : ""}`);
  if (dns > 0) parts.push(`${dns} non-partant${dns > 1 ? "s" : ""}`);
  if (dsq > 0) parts.push(`${dsq} disqualifié${dsq > 1 ? "s" : ""}`);
  if (unknown > 0) parts.push(`${unknown} indéterminé${unknown > 1 ? "s" : ""}`);
  return parts.join(" · ");
}

/**
 * En-tête de colonne triable (temps total ou un split) : un clic trie en
 * croissant, recliquer sur la même colonne inverse en décroissant, cliquer sur
 * une autre colonne repart en croissant.
 */
function EnteteTriable({
  cle,
  libelle,
  ariaSujet,
  tri,
  onTrier,
  perimetre,
}: {
  cle: string;
  libelle: string;
  ariaSujet: string;
  tri: { cle: string; direction: "asc" | "desc" } | null;
  onTrier: (cle: string) => void;
  perimetre: string;
}) {
  const actif = tri?.cle === cle;
  const direction = actif ? tri.direction : null;
  const prochaineDirection = direction === "asc" ? "desc" : "asc";

  return (
    <button
      type="button"
      onClick={() => onTrier(cle)}
      aria-label={`Trier par ${ariaSujet}, ${prochaineDirection === "asc" ? "croissant" : "décroissant"}${perimetre}`}
      // `padding` + `minHeight: 24` : plancher tactile WCAG 2.2 2.5.8, contre
      // 11 px sans padding avant #479.
      style={{
        font: "inherit",
        fontSize: 11,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: ".04em",
        color: actif ? "var(--tcn-ink)" : "inherit",
        background: "none",
        border: "none",
        padding: "4px 0",
        minHeight: 24,
        display: "inline-flex",
        alignItems: "center",
        cursor: "pointer",
      }}
    >
      {libelle}
      {direction === "asc" ? " ▲" : direction === "desc" ? " ▼" : ""}
    </button>
  );
}

