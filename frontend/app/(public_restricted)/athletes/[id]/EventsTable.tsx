"use client";
import { useMemo } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Eye } from "lucide-react";
import { Button, Card, FormatChip, PlaceBadge, PendingBadge, LigneCarte } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { ParticipationAdminActions } from "@/components/athletes/ParticipationAdminActions";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { eventTypeLabel } from "@/lib/constants";
import { describeQualityIssues } from "@/lib/quality";
import type { Participation } from "@/lib/types";
import { recentParticipations } from "@/lib/utils/club-aggregate";
import { formatDate } from "@/lib/utils/date";
import { disciplineOf, formatToken } from "@/lib/utils/format";
import { isNonFinisher } from "@/lib/utils/raceOrder";
import { rankRatio } from "@/lib/utils/ranking";
import { seasonLabel, seasonOf } from "@/lib/utils/season";
import { gridColumns, gridMinWidth, type Track } from "@/lib/utils/table";
import { isHttpUrl } from "@/lib/utils/url";

// Date | Épreuve | Type | Format | Temps final | Place | →
// La colonne Place loge la pastille *et* le « /N » de classés (issue #80).
const TRACKS: Track[] = [120, { flexMin: 200 }, 150, 90, 120, 120, 28];

const GAP = 18;
const PADDING_X = 26;
const COLS = gridColumns(TRACKS);
const MIN_WIDTH = gridMinWidth(TRACKS, { gap: GAP, paddingX: PADDING_X });

/** Paramètres d'URL des deux filtres. Absents = tout afficher. */
const SEASON_PARAM = "season";
const DISCIPLINE_PARAM = "discipline";
/** Valeur du choix « tout », qui s'écrit par l'absence du paramètre. */
const ALL = "all";

// Tooltip d'une course non fiable : détail des anomalies quand connues, repli
// générique sinon (ancien import backfillé sans quality_issues).
function unreliableTooltip(issues: Record<string, number> | null | undefined): string {
  const details = describeQualityIssues(issues);
  if (details.length === 0) return "Fiabilité des données incertaine chez le chronométreur — le classement complet ne peut pas être affiché.";
  return `Fiabilité incertaine : ${details.join(" ; ")}.`;
}

/** « 3 épreuves », ou « 1 épreuve sur 3 » dès qu'un filtre retire des lignes. */
function countLabel(shown: number, total: number): string {
  const noun = shown > 1 ? "épreuves" : "épreuve";
  return shown === total ? `${total} ${noun}` : `${shown} ${noun} sur ${total}`;
}

/**
 * Ce que la grille et les cartes lisent identiquement par ligne — un seul
 * calcul, pour que les deux arbres ne puissent pas diverger en silence
 * (#461).
 */
function rowDerived(p: Participation) {
  const { ratio } = rankRatio(p);
  // AC5 : le marqueur ⚠ dépend de la fiabilité de la course, pas du rang ni
  // du statut. Il doit apparaître à côté d'un DNF non fiable comme à côté
  // d'un finisher classé.
  const unreliableTitle =
    p.course?.is_reliable === false ? unreliableTooltip(p.course?.quality_issues) : null;
  return {
    ratio,
    unreliableTitle,
    nonFinisher: isNonFinisher(p.status),
    sigle: (p.status ?? "").toUpperCase(),
    preuve: p.evidence_url && isHttpUrl(p.evidence_url) ? p.evidence_url : null,
  };
}

/**
 * Cellule Place, partagée par la grille et les cartes (#461) : DNF/DNS/DSQ
 * (sigle + rang/total entre parenthèses), sinon `PlaceBadge` (+ `/N`), sinon
 * un tiret d'absence. `carte` ne change que les écarts légitimes de
 * disposition — la police du sigle non-finisher (14px en grille, héritée de
 * la carte sinon) et le regroupement du badge et du `/N` sous un même
 * `inline-flex`, nécessaire uniquement en carte : sans lui, les deux
 * flotteraient comme deux éléments distincts dans la `meta` de `LigneCarte`
 * (`flexWrap` + `gap: 8`).
 */
function marqueurPlace(
  p: Participation,
  { ratio, nonFinisher, sigle }: Pick<ReturnType<typeof rowDerived>, "ratio" | "nonFinisher" | "sigle">,
  carte = false,
) {
  if (nonFinisher) {
    return (
      <span style={{ fontSize: carte ? undefined : 14, fontWeight: 700, color: "var(--tcn-text-muted)" }}>
        {sigle}
        {p.rank_overall != null ? (
          <>({p.rank_overall}{ratio ? `/${ratio.total}` : ""})</>
        ) : null}
      </span>
    );
  }
  if (p.rank_overall != null) {
    const badge = (
      <>
        <PlaceBadge place={p.rank_overall} />
        {ratio ? (
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--tcn-text-faint)" }}>
            /{ratio.total}
          </span>
        ) : null}
      </>
    );
    return carte ? (
      <span style={{ display: "inline-flex", alignItems: "baseline", gap: 4 }}>{badge}</span>
    ) : (
      badge
    );
  }
  return <span style={{ color: "var(--tcn-text-faint)" }}>—</span>;
}

/** Marqueur ⚠ de fiabilité, partagé par la grille et les cartes (#461). */
function marqueurFiabilite(titre: string | null) {
  if (!titre) return null;
  return (
    <span
      data-testid="unreliable-marker"
      title={titre}
      aria-label={titre}
      // `role="img"` : le texte est purement informatif, pas un contrôle.
      role="img"
      // `position: relative` : le `::after` de `.tcn-rowlink__cible` couvre la
      // ligne et gagne le survol sur tout contenu en flux. Sans cette remontée,
      // l'infobulle du marqueur — qui fonctionnait avant #481 — ne s'ouvre plus.
      style={{ position: "relative", fontSize: 13, color: "var(--tcn-text-faint)", cursor: "help", userSelect: "none" }}
    >
      ⚠
    </span>
  );
}

/**
 * Le tableau des épreuves d'un profil, avec ses filtres saison et discipline
 * (#489). Sans eux, un membre de dix ans lit quarante lignes à plat, la
 * chronologie pour seul schéma d'organisation.
 *
 * **Filtrage en mémoire, URL écrite par l'historique natif** — même arbitrage
 * que `RankTypeToggle` (#328), et pour la même raison : aucun rendu serveur ne
 * lit `?season=` ni `?discipline=`. La page tient déjà *toutes* les
 * participations de l'athlète (`GET /athletes/{id}` les rend en un appel), donc
 * un `router.push` rejouerait ce fetch pour un résultat que le client a sous la
 * main. `pushState` s'intègre au routeur Next : `useSearchParams` le reflète,
 * la vue filtrée se partage par son URL, et retour/avant restent cohérents.
 *
 * Les deux contrôles de `/club/athletes` (`SeasonSelector`, `DisciplineToggle`)
 * n'ont pas pu être réemployés tels quels : leur défaut est de *filtrer* — la
 * saison en cours pour l'un, la seule fédération triathlon pour l'autre. Sur un
 * profil, ce défaut escamoterait neuf saisons sur dix et toutes les courses
 * hors triathlon sans que personne l'ait demandé, alors que la carte s'annonce
 * « Toutes les épreuves ». Ici le défaut est donc « tout », et un filtre ne
 * s'applique que choisi.
 *
 * Les cinq StatCard du haut de page restent, elles, calculées sur l'ensemble
 * des participations validées : ce sont les records d'une carrière, pas la
 * lecture d'une vue.
 */
export function EventsTable({
  participations,
  athleteId,
  athleteName,
}: {
  participations: Participation[];
  athleteId: number;
  athleteName: string;
}) {
  const pathname = usePathname();
  const sp = useSearchParams();

  // Saisons représentées, la plus récente d'abord. Une épreuve sans date n'en
  // désigne aucune : elle reste visible tant qu'aucune saison n'est demandée.
  const seasonOptions = useMemo(() => {
    const years = new Set<number>();
    for (const p of participations) {
      if (p.course.event_date) years.add(seasonOf(p.course.event_date));
    }
    return [...years].sort((a, b) => b - a);
  }, [participations]);

  // Disciplines représentées, la plus pratiquée d'abord : sur un profil, c'est
  // celle qu'on cherche. Les formats d'une même discipline sont regroupés — la
  // colonne Format dit déjà XS, M ou L.
  const disciplineOptions = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of participations) {
      const discipline = disciplineOf(p.course.event_type);
      if (!discipline) continue;
      counts.set(discipline, (counts.get(discipline) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort(([a, na], [b, nb]) => nb - na || eventTypeLabel(a).localeCompare(eventTypeLabel(b)))
      .map(([discipline]) => discipline);
  }, [participations]);

  // Une valeur qui ne correspond à aucune épreuve retombe sur « tout », sans
  // rien dire : même défaut silencieux que `?rank=foo` (#328). Un lien vieilli
  // ou bricolé rend le profil complet, jamais un tableau vide inexplicable.
  const season = seasonOptions.find((year) => String(year) === sp.get(SEASON_PARAM)) ?? null;
  const discipline = disciplineOptions.find((d) => d === sp.get(DISCIPLINE_PARAM)) ?? null;

  const filtered = participations.filter((p) => {
    if (season != null && (!p.course.event_date || seasonOf(p.course.event_date) !== season)) {
      return false;
    }
    return discipline == null || disciplineOf(p.course.event_type) === discipline;
  });
  const ordered = recentParticipations(filtered, filtered.length);

  function write(params: URLSearchParams) {
    const qs = params.toString();
    window.history.pushState(null, "", `${pathname}${qs ? `?${qs}` : ""}`);
  }

  function apply(param: string, value: string) {
    const params = new URLSearchParams(sp.toString());
    if (value === ALL) params.delete(param);
    else params.set(param, value);
    write(params);
  }

  function clearFilters() {
    const params = new URLSearchParams(sp.toString());
    params.delete(SEASON_PARAM);
    params.delete(DISCIPLINE_PARAM);
    write(params);
  }

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 26px 16px", flexWrap: "wrap", gap: 8 }}>
        <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>Toutes les épreuves</h2>
        <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", fontWeight: 600 }}>Clique sur une épreuve pour voir le détail →</div>
      </div>

      {participations.length > 0 && (
        // Barre de filtres : un sélecteur n'apparaît que s'il y a un choix à
        // faire. 47 % des membres n'ont qu'une épreuve — leur profil n'a rien à
        // filtrer, et deux contrôles inertes n'y seraient que du bruit.
        <div
          style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: `0 ${PADDING_X}px 16px` }}
        >
          {seasonOptions.length > 1 && (
            <Select
              value={season == null ? ALL : String(season)}
              onValueChange={(value) => apply(SEASON_PARAM, value as string)}
            >
              <SelectTrigger aria-label="Filtrer par saison" className="h-9">
                <SelectValue>
                  {(value) => (value === ALL ? "Toutes les saisons" : seasonLabel(Number(value)))}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Toutes les saisons</SelectItem>
                {seasonOptions.map((year) => (
                  <SelectItem key={year} value={String(year)}>
                    {seasonLabel(year)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {disciplineOptions.length > 1 && (
            <Select
              value={discipline ?? ALL}
              onValueChange={(value) => apply(DISCIPLINE_PARAM, value as string)}
            >
              <SelectTrigger aria-label="Filtrer par discipline" className="h-9">
                <SelectValue>
                  {(value) =>
                    value === ALL ? "Toutes les disciplines" : eventTypeLabel(value as string)
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Toutes les disciplines</SelectItem>
                {disciplineOptions.map((value) => (
                  <SelectItem key={value} value={value}>
                    {eventTypeLabel(value)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {/* `role="status"` : le compte est la seule preuve qu'un filtre a
              pris. Sans région live, un lecteur d'écran ne l'apprend qu'en
              reparcourant le tableau. */}
          <div
            role="status"
            style={{ marginLeft: "auto", fontSize: 13, fontWeight: 700, color: "var(--tcn-text-muted)" }}
          >
            {countLabel(filtered.length, participations.length)}
          </div>
        </div>
      )}

      {participations.length === 0 ? (
        <EmptyState
          bare
          title="Aucun résultat pour cet athlète"
          action={
            <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
              Ajouter un résultat →
            </Link>
          }
        />
      ) : ordered.length === 0 ? (
        // Un état vide de filtre n'est pas un cul-de-sac : il porte sa sortie.
        <div style={{ padding: 40, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>
          <div>Aucune épreuve ne correspond à ces filtres.</div>
          <Button variant="secondary" size="sm" onClick={clearFilters} style={{ marginTop: 14 }}>
            Afficher toutes les épreuves
          </Button>
        </div>
      ) : (
        <>
        <div
          data-testid="epreuves-grille"
          data-affichage="grille"
          // `min-[1145px]` = MIN_WIDTH (988) + CHROME_RAIL_REPLIE (`lib/utils/table.ts`),
          // pas le cran Tailwind `md:` (768) : ce dernier rouvrait une bande de
          // défilement horizontal entre 768 et 1145px (revue UI/UX #461).
          className="hidden min-[1145px]:block overflow-x-auto"
          role="region"
          aria-label="Épreuves, défilement horizontal"
          tabIndex={0}
        >
          <div style={{ minWidth: MIN_WIDTH }}>
            <table className="tcn-table" role="table">
            <thead role="rowgroup">
            <tr role="row" style={{ display: "grid", gridTemplateColumns: COLS, columnGap: GAP, padding: `0 ${PADDING_X}px 12px`, fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
              <th role="columnheader" scope="col">Date</th><th role="columnheader" scope="col">Épreuve</th><th role="columnheader" scope="col">Type</th><th role="columnheader" scope="col">Format</th><th role="columnheader" scope="col">Temps final</th><th role="columnheader" scope="col">Place</th><th role="columnheader" scope="col"><span className="sr-only">Ouvrir</span></th>
            </tr>
            </thead>
            {ordered.map((p) => {
              const { ratio, unreliableTitle, nonFinisher, sigle, preuve } = rowDerived(p);
              return (
                // Le trait de séparation est porté par le groupe, et non par la
                // ligne ni par chacune de ses sous-lignes : la sous-ligne
                // d'actions n'existe que dans le navigateur (#439), donc aucun
                // rendu serveur ne peut savoir laquelle est la dernière. Le
                // dessin reste celui d'avant — sans trait pour une ligne en
                // attente qui n'a pas de sous-ligne de preuve (#270). Le groupe
                // est un `<tbody>` depuis #481 : un tableau n'autorise aucun
                // élément intermédiaire entre le corps et ses lignes.
                <tbody
                  role="rowgroup"
                  key={p.id}
                  style={{ borderBottom: p.is_pending_validation && !preuve ? "none" : "1px solid var(--tcn-border-faint)" }}
                >
                <tr role="row" className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: COLS, columnGap: GAP, alignItems: "center", padding: `15px ${PADDING_X}px` }}>
                  <td role="cell" style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>{formatDate(p.course.event_date)}</td>
                  <td role="cell" style={{ fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <Link href={`/courses/${p.course.id}/participations/${p.id}`} className="tcn-rowlink__cible">
                      {p.course.name}
                    </Link>
                    {p.is_pending_validation && <PendingBadge rejected={p.is_rejected} />}
                  </td>
                  <td role="cell" style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>{eventTypeLabel(p.course.event_type)}</td>
                  <td role="cell"><FormatChip>{formatToken(p.course.event_type, p.course.distance_km)}</FormatChip></td>
                  <td role="cell" style={{ fontSize: 15, color: "var(--tcn-ink)", fontFamily: "var(--tcn-font-cond)", fontWeight: 700 }}>{p.total_time ?? "—"}</td>
                  <td role="cell" style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                    {marqueurPlace(p, { ratio, nonFinisher, sigle })}
                    {marqueurFiabilite(unreliableTitle)}
                  </td>
                  <td role="cell" style={{ textAlign: "right", color: "var(--tcn-text-disabled)", fontSize: 16 }}><span aria-hidden>→</span></td>
                </tr>
                {preuve ? (
                  // Ligne séparée, hors du `<Link>` de la ligne : un `<a>`
                  // imbriqué dans un autre serait invalide en HTML. Le texte
                  // qui n'est pas une URL http(s) exploitable reste stocké
                  // (cas limite de la spec) mais n'est jamais rendu cliquable.
                  <tr role="row" style={{ display: "block", padding: `0 ${PADDING_X}px 12px` }}>
                  {/* `aria-colspan` double `colSpan` pour la même raison que
                      les rôles doublent les balises : la surcharge de `display`
                      peut faire tomber la portée dérivée de la disposition, et
                      la sous-ligne serait exposée en cellule de la seule
                      première colonne. */}
                  <td role="cell" colSpan={TRACKS.length} aria-colspan={TRACKS.length} style={{ display: "block" }}>
                    <a
                      href={preuve}
                      target="_blank"
                      rel="noreferrer"
                      // Affordance de bouton discret : classes partagées avec
                      // `tcn/Button` (voir globals.css) plutôt qu'un composant
                      // dédié — un `<button>` serait sémantiquement faux ici,
                      // c'est une navigation, pas une action (rôle "link" à
                      // conserver, cf. page.test.tsx). `--secondary` et non
                      // `--ghost` : cette carte a un fond blanc
                      // (`--tcn-surface`), sur lequel le remplissage et la
                      // bordure de `--ghost` tombent sous 1,3:1 (WCAG
                      // 1.4.11) — quasi invisibles, à l'inverse de
                      // l'affordance recherchée. La bordure encre de
                      // `--secondary` reste à ~16:1 sur ce même fond.
                      className="tcn-btn tcn-btn--sm tcn-btn--secondary"
                    >
                      <Eye size={14} aria-hidden="true" />
                      Voir la preuve
                    </a>
                  </td>
                  </tr>
                ) : null}
                {/* Sous-ligne d'actions : le composant se rend lui-même nul
                    pour qui ne porte aucun des pouvoirs, donc rien ici ne
                    réserve d'espace au visiteur public (#439). `colonnes` lui
                    fait porter sa propre `<tr>` — la poser ici la rendrait
                    vide pour le public, et l'aide technique annoncerait une
                    ligne de plus par épreuve (#481). */}
                <ParticipationAdminActions
                  colonnes={TRACKS.length}
                  resultat={{
                    id: p.id,
                    epreuve: p.course.name,
                    date: p.course.event_date,
                    coureur: athleteName,
                    coureurId: athleteId,
                  }}
                  style={{ padding: `0 ${PADDING_X}px 14px` }}
                />
                </tbody>
              );
            })}
            </table>
          </div>
        </div>

        {/* Sous 1145 px (988 px de grille + CHROME_RAIL_REPLIE), FORMAT, TEMPS,
            PLACE et le ⚠ sortaient de l'écran : la donnée pour laquelle on
            ouvre un profil était invisible sans geste (#461, WCAG 1.4.10). */}
        <div data-testid="epreuves-cartes" data-affichage="cartes" className="min-[1145px]:hidden">
          {ordered.map((p) => {
            const { ratio, unreliableTitle, nonFinisher, sigle, preuve } = rowDerived(p);
            return (
              <LigneCarte
                key={p.id}
                href={`/courses/${p.course?.id}/participations/${p.id}`}
                surtitre={formatDate(p.course?.event_date)}
                titre={
                  <>
                    {p.course?.name}
                    {p.is_pending_validation && <PendingBadge rejected={p.is_rejected} />}
                  </>
                }
                valeur={p.total_time ?? "—"}
                meta={
                  <>
                    <span>{eventTypeLabel(p.course?.event_type)}</span>
                    <FormatChip>{formatToken(p.course?.event_type, p.course?.distance_km)}</FormatChip>
                    {marqueurPlace(p, { ratio, nonFinisher, sigle }, true)}
                    {marqueurFiabilite(unreliableTitle)}
                  </>
                }
                actions={
                  <>
                    {preuve ? (
                      <div style={{ padding: "0 16px 12px" }}>
                        <a
                          href={preuve}
                          target="_blank"
                          rel="noreferrer"
                          className="tcn-btn tcn-btn--sm tcn-btn--secondary"
                        >
                          <Eye size={14} aria-hidden="true" />
                          Voir la preuve
                        </a>
                      </div>
                    ) : null}
                    <ParticipationAdminActions
                      resultat={{
                        id: p.id,
                        epreuve: p.course?.name ?? "cette épreuve",
                        date: p.course?.event_date ?? null,
                        coureur: athleteName,
                        coureurId: athleteId,
                      }}
                      style={{ padding: "0 16px 14px" }}
                    />
                  </>
                }
              />
            );
          })}
        </div>
        </>
      )}
    </Card>
  );
}
