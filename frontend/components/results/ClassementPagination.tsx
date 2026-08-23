"use client";
import Link from "next/link";
import { PAGE_SIZE_OPTIONS, pageSizeLabel, type PageSize } from "@/lib/pageSize";

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
  onTaille,
}: {
  page: number;
  nbPages: number;
  lienVers: (modifications: Record<string, string | null>) => string;
  tailleCourante: PageSize;
  onTaille: (taille: PageSize) => void;
}) {
  const style = {
    padding: "6px 14px",
    fontSize: 13,
    fontWeight: 700,
    borderRadius: 8,
    border: "1px solid var(--tcn-border)",
    color: "var(--tcn-ink)",
  } as const;
  const inactif = { ...style, color: "var(--tcn-text-faint)", opacity: 0.5 };
  // Hors bornes, « Précédent » ramène à la dernière page réelle : reculer d'un
  // cran depuis la page 99 999 ferait traverser 99 908 pages vides.
  const precedente = Math.min(page - 1, nbPages);

  return (
    <div style={{ borderTop: "1px solid var(--tcn-border)" }}>
      {nbPages > 1 && (
        <nav
          aria-label="Pagination du classement"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, padding: "14px 24px", flexWrap: "wrap" }}
        >
          {page > 1 ? (
            <Link
              href={lienVers({ page: precedente === 1 ? null : String(precedente) })}
              style={style}
              rel="prev"
            >
              ‹ Précédent
            </Link>
          ) : (
            <span style={inactif} aria-disabled="true">‹ Précédent</span>
          )}
          <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }} aria-current="page">
            Page {page} sur {nbPages}
          </span>
          {page < nbPages ? (
            <Link href={lienVers({ page: String(page + 1) })} style={style} rel="next">
              Suivant ›
            </Link>
          ) : (
            <span style={inactif} aria-disabled="true">Suivant ›</span>
          )}
        </nav>
      )}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "10px 24px", fontSize: 13, color: "var(--tcn-text-muted)" }}>
        <label htmlFor="classement-taille">Lignes par page</label>
        <select
          id="classement-taille"
          value={String(tailleCourante)}
          onChange={(e) => onTaille(e.target.value === "all" ? "all" : (Number(e.target.value) as PageSize))}
          // Plancher tactile WCAG 2.2 2.5.8 (#479).
          style={{ minHeight: 28, padding: "2px 8px", fontSize: 13, borderRadius: 8, border: "1px solid var(--tcn-border)", background: "var(--tcn-surface)", color: "var(--tcn-ink)" }}
        >
          {PAGE_SIZE_OPTIONS.map((o) => (
            <option key={String(o)} value={String(o)}>
              {pageSizeLabel(o)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
