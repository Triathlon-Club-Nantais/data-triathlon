import Link from "next/link";
import { EmptyState } from "@/components/ui/empty-state";
import type { ClubCount } from "@/lib/types";

/**
 * La carte « Top clubs » d'une épreuve (#486, RES-7).
 *
 * Extraite du JSX inline de `courses/[id]/page.tsx` : elle gagne un pied qui compte ce
 * qu'elle n'affiche pas, ce qui la rend testable pour elle-même.
 *
 * Reste un `<table>` à lignes inertes (#481, A11Y-3) : l'en-tête de colonnes
 * survit à la liste vide — `page.test.tsx` le verrouille — l'état vide se
 * rendant après le tableau, jamais à sa place.
 */
export function ClubBreakdown({
  clubs,
  total,
  hrefFor,
}: {
  /** Les clubs affichés — un extrait, plafonné à neuf par le backend. */
  clubs: ClubCount[];
  /** Nombre de clubs **distincts** de l'épreuve entière (`clubs_total`). */
  total: number;
  /**
   * Rend chaque ligne activable vers le classement filtré sur ce club (#486,
   * RES-11) : on lit « BLAIN TRIATHLON 33 », on veut voir ces 33 athlètes.
   *
   * Reçoit `isTcn` parce que **la ligne du club ne se filtre pas comme les
   * autres** : la synthèse fusionne les variantes de libellé sous le nom
   * canonique (#200), qui n'est le verbatim d'**aucune** ligne en base — sur la
   * base de dev, les quatre orthographes stockées sont « TRI CLUB NANTAIS »,
   * « TRIATHLON CLUB NANTAIS », « Triathlon club nantais » et « Tcn ». Un
   * `?club=Triathlon Club Nantais` en égalité exacte ne ramènerait donc
   * personne, sous une carte qui vient d'annoncer 216. C'est `scope=club` qui
   * porte cette sélection, et son prédicat vit côté serveur (#76).
   */
  hrefFor?: (name: string, isTcn: boolean) => string;
}) {
  const restants = Math.max(0, total - clubs.length);

  return (
    <>
      <table className="tcn-table" role="table" aria-labelledby="titre-top-clubs">
        <thead role="rowgroup">
          <tr role="row" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10, paddingBottom: 8, fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)", marginBottom: 4 }}>
            <th role="columnheader" scope="col">Club</th><th role="columnheader" scope="col" style={{ textAlign: "right" }}>Athlètes</th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {clubs.map(({ name, count, is_tcn: own }) => (
            <tr
              key={name}
              role="row"
              className={hrefFor ? "tcn-rowlink" : undefined}
              style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10, padding: "7px 0", minHeight: 24, borderBottom: "1px solid var(--tcn-border-faint2)" }}
            >
              <td role="cell" style={{ fontSize: 13, fontWeight: own ? 700 : 600, color: own ? "var(--tcn-orange-deeper)" : "var(--tcn-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {hrefFor ? (
                  <Link
                    href={hrefFor(name, own)}
                    aria-label={`${name}, ${count} athlète${count > 1 ? "s" : ""}. Voir ces participants dans le classement.`}
                    className="tcn-rowlink__cible"
                  >
                    {name}
                  </Link>
                ) : (
                  name
                )}
              </td>
              {/* Le chevron vit dans la même cellule que l'effectif, plutôt qu'une
                  troisième colonne : le tableau garde deux `<th>` quel que soit
                  `hrefFor`, sans quoi l'en-tête et les lignes divergeraient en
                  nombre de cellules (WCAG 1.3.1). Seul signal, avec le curseur,
                  qu'une ligne de statistique mène quelque part (patron d'`EventList`). */}
              <td role="cell" style={{ fontFamily: "var(--tcn-font-display)", fontSize: 16, color: own ? "var(--tcn-orange-deeper)" : "var(--tcn-ink)", textAlign: "right", display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6 }}>
                {count}
                {hrefFor && (
                  <span aria-hidden style={{ color: "var(--tcn-text-disabled)", fontSize: 13 }}>→</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {clubs.length === 0 && (
        <EmptyState bare className="px-0 py-4" title="Clubs non renseignés" />
      )}
      {/* Ce que la carte omet, dit en toutes lettres. Du texte visible, donc déjà
          dans l'arbre d'accessibilité : aucun `aria-*` à ajouter par-dessus. */}
      {restants > 0 && (
        <div style={{ paddingTop: 10, fontSize: 12, color: "var(--tcn-text-muted)" }}>
          et {restants} autre{restants > 1 ? "s" : ""} club{restants > 1 ? "s" : ""}
        </div>
      )}
    </>
  );
}
