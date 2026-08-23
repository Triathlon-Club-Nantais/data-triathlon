"use client";
import Link from "next/link";

/**
 * Commandes de pagination du classement, en liens et non en boutons :
 * ouvrables en nouvel onglet, utilisables au clavier et fonctionnels avant
 * hydratation.
 */
export function ClassementPagination({
  page,
  nbPages,
  lienVers,
}: {
  page: number;
  nbPages: number;
  lienVers: (modifications: Record<string, string | null>) => string;
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
    <nav
      aria-label="Pagination du classement"
      style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, padding: "14px 24px", borderTop: "1px solid var(--tcn-border)" }}
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
  );
}
