"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { PAGE_SIZE_ALL_MAX, PAGE_SIZE_OPTIONS, pageSizeLabel, parsePageSize, type PageSize } from "@/lib/pageSize";

/**
 * Commandes de pagination du classement, en liens et non en boutons :
 * ouvrables en nouvel onglet, utilisables au clavier et fonctionnels avant
 * hydratation. Le sélecteur de taille de tranche est **toujours** rendu ;
 * la navigation de pages, elle, ne l'est que si `nbPages > 1`.
 */
export function ClassementPagination({
  page,
  nbPages,
  lienVers,
  tailleCourante,
  options = PAGE_SIZE_OPTIONS,
  onTaille,
  onAllerPage,
}: {
  page: number;
  nbPages: number;
  lienVers: (modifications: Record<string, string | null>) => string;
  tailleCourante: PageSize;
  /** Tailles proposées : sans « Tout » au-delà de 500 résultats (#1355). */
  options?: readonly PageSize[];
  onTaille: (taille: PageSize) => void;
  onAllerPage: (n: number) => void;
}) {
  const style = {
    padding: "6px 14px",
    fontSize: 13,
    fontWeight: 700,
    borderRadius: "var(--tcn-radius-md)",
    border: "1px solid var(--tcn-border-input)",
    color: "var(--tcn-ink)",
    // Centre le libellé dans les 44 px que `.tcn-cible-tactile` impose sous md (#1539).
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  } as const;
  // 44 px sous md, plancher de 28 px au delà, sous la hauteur naturelle (31 px) : le bureau ne bouge pas.
  const touchTarget = "tcn-cible-tactile";
  // `--tcn-text-faint` seul tient 5,21:1 sur blanc (revue UI/UX #485) : une
  // opacité en plus n'ajoutait qu'une redondance illisible (2,03:1).
  const inactif = { ...style, color: "var(--tcn-text-faint)" };
  // Hors bornes, « Précédent » ramène à la dernière page réelle : reculer d'un
  // cran depuis la page 99 999 ferait traverser 99 908 pages vides.
  const precedente = Math.min(page - 1, nbPages);

  const searchParams = useSearchParams();
  const [saisie, setSaisie] = useState(String(page));
  const [dernierePage, setDernierePage] = useState(page);

  // L'URL est la vérité : après un « Précédent » du navigateur, le champ suit.
  // Même patron d'état dérivé que la recherche de `RaceFinishers`.
  if (page !== dernierePage) {
    setDernierePage(page);
    setSaisie(String(page));
  }

  // Les autres paramètres voyagent en champs cachés : le saut fonctionne alors
  // aussi en soumission native, avant hydratation, sans perdre la recherche.
  const autresParametres = Array.from(searchParams.entries()).filter(([cle]) => cle !== "page");

  function surSoumission(e: React.FormEvent) {
    e.preventDefault();
    // Hors bornes, on ramène dans le classement : « 99 » sur 43 pages veut dire
    // « la fin », le refuser ne rendrait service à personne.
    const n = Math.min(Math.max(1, Math.trunc(Number(saisie)) || 1), nbPages);
    onAllerPage(n);
  }

  return (
    <div style={{ borderTop: "1px solid var(--tcn-border)" }}>
      {nbPages > 1 && (
        <nav
          aria-label="Pagination du classement"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, padding: "14px 24px", flexWrap: "wrap" }}
        >
          {page > 1 ? (
            <Link href={lienVers({ page: null })} className={touchTarget} style={style}>‹‹ Première</Link>
          ) : (
            <span className={touchTarget} style={inactif} aria-disabled="true">‹‹ Première</span>
          )}
          {page > 1 ? (
            <Link
              href={lienVers({ page: precedente === 1 ? null : String(precedente) })}
              className={touchTarget}
              style={style}
              rel="prev"
            >
              ‹ Précédent
            </Link>
          ) : (
            <span className={touchTarget} style={inactif} aria-disabled="true">‹ Précédent</span>
          )}
          <form method="get" onSubmit={surSoumission} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--tcn-text-muted)" }}>
            {autresParametres.map(([cle, valeur]) => (
              <input key={cle} type="hidden" name={cle} value={valeur} />
            ))}
            <label htmlFor="classement-page">Aller à la page</label>
            <input
              id="classement-page"
              name="page"
              type="number"
              inputMode="numeric"
              min={1}
              // Pas de `max` : une saisie hors bornes doit atteindre `surSoumission`
              // pour être ramenée dans le classement, pas être bloquée par la
              // validation native du navigateur avant même la soumission.
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              aria-describedby="classement-page-total"
              className={touchTarget}
              style={{ width: 68, padding: "2px 8px", fontSize: 13, borderRadius: "var(--tcn-radius-md)", border: "1px solid var(--tcn-border-input)", background: "var(--tcn-surface)", color: "var(--tcn-ink)" }}
            />
            <span id="classement-page-total">sur {nbPages}</span>
            {/* Bouton de soumission explicite : sans lui, la soumission
                implicite par Entrée dépend du nombre de champs du formulaire et
                n'existe pas du tout au doigt. Il porte aussi le saut sans
                JavaScript. */}
            <button type="submit" className={touchTarget} style={{ ...style, background: "var(--tcn-fill)", cursor: "pointer" }}>
              Aller
            </button>
          </form>
          {page < nbPages ? (
            <Link href={lienVers({ page: String(page + 1) })} className={touchTarget} style={style} rel="next">Suivant ›</Link>
          ) : (
            <span className={touchTarget} style={inactif} aria-disabled="true">Suivant ›</span>
          )}
          {page < nbPages ? (
            <Link href={lienVers({ page: String(nbPages) })} className={touchTarget} style={style}>Dernière ››</Link>
          ) : (
            <span className={touchTarget} style={inactif} aria-disabled="true">Dernière ››</span>
          )}
        </nav>
      )}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "10px 24px", fontSize: 13, color: "var(--tcn-text-muted)" }}>
        <label htmlFor="classement-taille">Lignes par page</label>
        <select
          id="classement-taille"
          value={String(tailleCourante)}
          onChange={(e) => onTaille(parsePageSize(e.target.value))}
          className={touchTarget}
          style={{ padding: "2px 8px", fontSize: 13, borderRadius: "var(--tcn-radius-md)", border: "1px solid var(--tcn-border-input)", background: "var(--tcn-surface)", color: "var(--tcn-ink)" }}
        >
          {options.map((o) => (
            <option key={String(o)} value={String(o)}>
              {pageSizeLabel(o)}
            </option>
          ))}
        </select>
      </div>
      {/* Dit pourquoi « Tout » manque, surtout à qui arrive par un lien
          `?page_size=all` servi en 200 lignes (revue UI/UX de #1376). */}
      {!options.includes("all") && (
        <p style={{ margin: 0, padding: "0 24px 10px", textAlign: "center", fontSize: 13, color: "var(--tcn-text-muted)" }}>
          Au-delà de {PAGE_SIZE_ALL_MAX} résultats dans l&apos;épreuve, le classement s&apos;affiche par pages de 200 au plus.
        </p>
      )}
    </div>
  );
}
