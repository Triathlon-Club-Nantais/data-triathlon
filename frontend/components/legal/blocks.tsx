import Link from "next/link";
import type { ReactNode } from "react";
import { RIGHTS_CONTACT_EMAIL } from "./legal-routes";

// Le preflight Tailwind efface puces et soulignés : les textes légaux les rétablissent ici.
const LINK_CLASS = "font-medium text-[var(--tcn-orange-deep)] underline underline-offset-4";

export function List({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-1.5 pl-5">{children}</ul>;
}

export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} className={LINK_CLASS} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

export function InternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className={LINK_CLASS}>
      {children}
    </Link>
  );
}

export function ContactEmail() {
  return (
    <a href={`mailto:${RIGHTS_CONTACT_EMAIL}`} className={LINK_CLASS}>
      {RIGHTS_CONTACT_EMAIL}
    </a>
  );
}

export function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    // Défilement horizontal confiné au tableau : la page ne déborde pas à 320 px.
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr>
            {head.map((cell) => (
              <th key={cell} scope="col" className="border-b border-[var(--tcn-border)] py-2 pr-4 font-semibold">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            // Lignes éditoriales statiques, sans identifiant plus stable que leur position.
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) =>
                cellIndex === 0 ? (
                  <th key={cellIndex} scope="row" className="border-b border-[var(--tcn-border)] py-2 pr-4 align-top font-medium">
                    {cell}
                  </th>
                ) : (
                  <td key={cellIndex} className="border-b border-[var(--tcn-border)] py-2 pr-4 align-top">
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
