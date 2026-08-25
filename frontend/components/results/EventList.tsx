"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, Badge, FormatChip, AnnonceStatut } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useInfiniteEvents } from "@/lib/queries/events";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";
import { groupEventsByCompetition, eventSuffix, type EventGroup } from "@/lib/utils/eventGroups";
import { ReliabilityMark } from "@/components/results/ReliabilityMark";
import { gridColumns, gridMinWidth, type Track } from "@/lib/utils/table";
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";
import type { EventOut, EventPage, ParticipationFilters } from "@/lib/types";

const SORT_OPTIONS = [
  { value: "date_desc", label: "Date (récent)" },
  { value: "date_asc", label: "Date (ancien)" },
  { value: "name", label: "Nom" },
];

// #577 : pendant une recherche d'épreuve, le backend classe toujours par
// similarité en tête (`event_name` déclenche `similarity(Course.name, …)`,
// `_events_order`) — le tri choisi ne fait que départager. « Pertinence »
// n'a de sens que dans ce contexte, donc n'apparaît qu'alors, sélectionnée
// d'office tant qu'aucun tri n'a été explicitement posé.
const PERTINENCE_OPTION = { value: "pertinence", label: "Pertinence" };

// Date | Épreuve | Type | Format | Résultats | TCN | →
const TRACKS: Track[] = [120, { flexMin: 200 }, 150, 90, 110, 90, 28];
const GAP = 18;
const PADDING_X = 26;
const COLS = gridColumns(TRACKS);
const MIN_WIDTH = gridMinWidth(TRACKS, { gap: GAP, paddingX: PADDING_X });

export function EventList({
  filters,
  initial,
}: {
  filters: ParticipationFilters;
  initial?: EventPage;
}) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteEvents(
    filters,
    initial,
  );
  const router = useRouter();
  const sp = useSearchParams();
  const sentinel = useRef<HTMLDivElement | null>(null);

  const [ouverts, setOuverts] = useState<ReadonlySet<number>>(new Set());

  const events = data?.pages.flatMap((p) => p.items) ?? [];
  // #463 : replier les épreuves d'une même compétition sous une ligne parente.
  // ponytail: totaux sommés sur les seules épreuves chargées — un groupe à
  // cheval sur deux pages du défilement infini affiche donc un total partiel
  // jusqu'à la page suivante. Un compteur exact dès la 1re page demanderait un
  // agrégat côté backend (events_page), à ouvrir si la gêne se constate.
  const groups = groupEventsByCompetition(events);

  function basculer(id: number) {
    setOuverts((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  const totalEvents = data?.pages[0]?.total_events ?? 0;
  const totalParticipations = data?.pages[0]?.total_participations ?? 0;

  // Scroll infini : charge la page suivante quand la sentinelle entre dans le viewport.
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasNextPage) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && !isFetchingNextPage) fetchNextPage();
    });
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  function setSort(value: string) {
    const params = new URLSearchParams(sp.toString());
    // « Pertinence » n'est pas une clé de tri backend : elle représente
    // l'absence de tri explicitement choisi (`sort` par défaut, similarité en
    // tête). La reposer, c'est retirer le paramètre.
    if (value === "pertinence") {
      params.delete("sort");
    } else {
      params.set("sort", value);
    }
    router.push(`/resultats?${params.toString()}`);
  }

  const rechercheEpreuveActive = !!sp.get("event_name");
  const sortOptions = rechercheEpreuveActive ? [PERTINENCE_OPTION, ...SORT_OPTIONS] : SORT_OPTIONS;
  const currentSort =
    rechercheEpreuveActive && !sp.get("sort") ? "pertinence" : (sp.get("sort") ?? "date_desc");

  // WCAG 4.1.3 (#477) : filtrer ou trier remplace la liste sans déplacer le
  // focus, et le défilement infini y ajoute des pages sans un mot — sans
  // cette annonce, un lecteur d'écran ne signale ni l'un ni l'autre. Le
  // décompte d'épreuves chargées (`events.length`) est inclus précisément
  // pour que le défilement infini change le texte annoncé : les totaux seuls
  // (`totalEvents`/`totalParticipations`) sont ceux de la sélection entière et
  // ne bougent pas d'une page à l'autre. Rendue avant le retour anticipé sur
  // liste vide, à dessein : sinon la région disparaît du DOM précisément
  // quand un filtre venant de tout effacer aurait le plus besoin de le dire.
  //
  // #463 y ajoute les compétitions repliées : `events.length` compte les
  // épreuves **chargées**, pas les lignes **visibles**, donc replier quinze
  // lignes en une ne changeait pas un mot de l'annonce. Mention omise quand
  // rien n'est replié, pour ne pas allonger le cas courant.
  const repliees = groups.filter(
    (g) => g.events.length > 1 && !ouverts.has(g.events[0].id),
  ).length;
  const annonce = (
    <AnnonceStatut
      texte={
        `${totalEvents} épreuve${totalEvents > 1 ? "s" : ""}, ${totalParticipations} résultat${totalParticipations > 1 ? "s" : ""}` +
        (events.length > 0 ? `, ${events.length} affichée${events.length > 1 ? "s" : ""}` : "") +
        (repliees > 0
          ? ` dans ${repliees} compétition${repliees > 1 ? "s" : ""} repliée${repliees > 1 ? "s" : ""}`
          : "")
      }
    />
  );

  if (!isLoading && events.length === 0) {
    return (
      <>
        {annonce}
        <EmptyState
          title="Aucun résultat"
          description="Importez une épreuve depuis une URL de chronométrage pour voir apparaître les résultats ici."
        />
      </>
    );
  }

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      {annonce}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 26px 16px",
        }}
      >
        <div>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>
            Toutes les épreuves
          </div>
        </div>
        <Select value={currentSort} onValueChange={(v) => setSort(v as string)}>
          <SelectTrigger className="h-9 w-44">
            <SelectValue>
              {(v) => sortOptions.find((o) => o.value === v)?.label ?? "Trier"}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {sortOptions.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div style={{ overflowX: "auto" }}>
        <div style={{ minWidth: MIN_WIDTH }}>
          <table className="tcn-table" role="table">
          <thead role="rowgroup">
          <tr
            role="row"
            style={{
              display: "grid",
              gridTemplateColumns: COLS,
              columnGap: GAP,
              padding: `0 ${PADDING_X}px 12px`,
              fontSize: 12,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: ".04em",
              color: "var(--tcn-text-faint)",
              borderBottom: "1px solid var(--tcn-border)",
            }}
          >
            <th role="columnheader" scope="col">Date</th>
            <th role="columnheader" scope="col">Épreuve</th>
            <th role="columnheader" scope="col">Type</th>
            <th role="columnheader" scope="col">Format</th>
            <th role="columnheader" scope="col">Résultats</th>
            <th role="columnheader" scope="col" title={CLUB_NAME}>{CLUB_NAME_SHORT}</th>
            {/* Nommée en `sr-only` plutôt que laissée vide : un `<th>` sans
                nom accessible est une colonne anonyme, et son contenu — la
                flèche — était annoncé à chaque ligne (revue UI/UX #481). */}
            <th role="columnheader" scope="col"><span className="sr-only">Ouvrir</span></th>
          </tr>
          </thead>

          {groups.map((groupe) =>
            groupe.events.length === 1 ? (
              <tbody role="rowgroup" key={groupe.events[0].id}>
                <EventRow event={groupe.events[0]} />
              </tbody>
            ) : (
              <CompetitionRows
                key={groupe.events[0].id}
                groupe={groupe}
                ouvert={ouverts.has(groupe.events[0].id)}
                onBascule={() => basculer(groupe.events[0].id)}
              />
            ),
          )}
          </table>
        </div>
      </div>

      {isLoading && events.length === 0 && (
        <p style={{ padding: 24, textAlign: "center", fontSize: 14, color: "var(--tcn-text-faint)" }}>
          Chargement…
        </p>
      )}

      <div ref={sentinel} aria-hidden />
      {isFetchingNextPage && (
        <p style={{ padding: 16, textAlign: "center", fontSize: 14, color: "var(--tcn-text-faint)" }}>
          Chargement…
        </p>
      )}
    </Card>
  );
}

const ROW_STYLE = {
  display: "grid",
  gridTemplateColumns: COLS,
  columnGap: GAP,
  alignItems: "center",
  padding: `15px ${PADDING_X}px`,
  borderBottom: "1px solid var(--tcn-border-faint)",
} as const;

/** Une épreuve. `label` remplace son nom quand un groupe porte déjà le préfixe. */
function EventRow({ event: ev, label, indent }: { event: EventOut; label?: string; indent?: boolean }) {
  return (
    <tr role="row" className="tcn-rowlink" style={ROW_STYLE}>
      <td
        role="cell"
        style={{
          fontSize: 14,
          color: "var(--tcn-text-muted)",
          fontWeight: 600,
          paddingLeft: indent ? 22 : 0,
        }}
      >
        {formatDate(ev.event_date)}
      </td>
      <td role="cell" style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
        <Link href={`/courses/${ev.id}`} className="tcn-rowlink__cible" style={{ fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}>
          {formatEventName(label ?? ev.event_name, ev.is_relay)}
        </Link>
        {ev.is_relay && <Badge variant="orange">Relais</Badge>}
        {/* Même marque et même vocabulaire que la page épreuve (#486) : la
            colonne n'a pas la place d'un libellé, d'où la forme compacte. */}
        <ReliabilityMark isReliable={ev.is_reliable} issues={ev.quality_issues} compact />
      </td>
      <td role="cell" style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>{eventTypeLabel(ev.event_type)}</td>
      <td role="cell">
        <FormatChip>{formatToken(ev.event_type, ev.distance_km)}</FormatChip>
      </td>
      <td role="cell" style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>
        {ev.total} résultat{ev.total > 1 ? "s" : ""}
      </td>
      <td role="cell">
        {ev.tcn_count > 0 ? (
          <Badge count>{ev.tcn_count}</Badge>
        ) : (
          <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
        )}
      </td>
      <td role="cell" style={{ textAlign: "right", color: "var(--tcn-text-disabled)", fontSize: 16 }}><span aria-hidden>→</span></td>
    </tr>
  );
}

/** Ligne de compétition parente dépliable, suivie de ses épreuves quand elle l'est. */
function CompetitionRows({
  groupe,
  ouvert,
  onBascule,
}: {
  groupe: EventGroup;
  ouvert: boolean;
  onBascule: () => void;
}) {
  return (
    <tbody role="rowgroup">
      <tr
        role="row"
        className="tcn-rowlink"
        style={{
          ...ROW_STYLE,
          borderBottom: "1px solid var(--tcn-border-faint)",
          cursor: "pointer",
        }}
        // Pas de `background` ici : `.tcn-rowlink` le pose en couche CSS pour
        // que son `:hover` gagne, et un style en ligne le battrait — la ligne
        // de groupe serait la seule de la liste sans retour au survol.
      >
        <td role="cell" style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>
          {formatDate(groupe.events[0].event_date)}
        </td>
        <td role="cell" style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          {/* Un **bouton**, et il le reste : cette ligne déplie, elle ne
              navigue pas. En faire un lien serait la régression 4.1.2 que #481
              corrige sur le classement d'épreuve. */}
          <button
            type="button"
            onClick={onBascule}
            aria-expanded={ouvert}
            className="tcn-rowlink__cible"
            style={{ font: "inherit", fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700, background: "none", border: "none", padding: 0, textAlign: "left", cursor: "pointer" }}
          >
            {groupe.prefix}
          </button>
        </td>
        {/* Le décompte tient la colonne « Type » : les épreuves d'une même
            compétition n'en partagent ni le type ni le format. */}
        <td role="cell" style={{ fontSize: 14, color: "var(--tcn-text-muted)" }}>
          {groupe.events.length} épreuves
        </td>
        <td role="cell" />
        <td role="cell" style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>
          {groupe.total} résultat{groupe.total > 1 ? "s" : ""}
        </td>
        <td role="cell">
          {groupe.tcnCount > 0 ? (
            <Badge count>{groupe.tcnCount}</Badge>
          ) : (
            <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
          )}
        </td>
        {/* `aria-hidden` sur le glyphe, **jamais** sur la cellule : posé sur le
            `<td>`, il retirait la cellule de l'arbre et la ligne de groupe
            annonçait 6 cellules pour 7 colonnes — l'incohérence même que la
            promesse 1.3.1 de #481 interdit. L'état déplié est déjà porté par
            l'`aria-expanded` du bouton. */}
        <td
          role="cell"
          style={{ textAlign: "right", color: "var(--tcn-text-muted)", fontSize: 16 }}
        >
          <span aria-hidden>{ouvert ? "▾" : "▸"}</span>
        </td>
      </tr>
      {ouvert &&
        groupe.events.map((ev) => (
          <EventRow key={ev.id} event={ev} label={eventSuffix(ev.event_name, groupe.prefix)} indent />
        ))}
    </tbody>
  );
}
