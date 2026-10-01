import Link from "next/link";
import { LEGAL_ROUTES } from "./legal-routes";

/** Les trois textes légaux, en pied de toutes les pages (#333). */
export function LegalLinks() {
  return (
    <nav aria-label="Informations légales">
      <ul className="flex flex-wrap justify-center gap-x-4 gap-y-2">
        {LEGAL_ROUTES.map((route) => (
          <li key={route.href}>
            <Link
              href={route.href}
              prefetch={false}
              // Même teinte que le texte du pied : le soulignement au repos le désigne comme lien (WCAG 1.4.1).
              // `py`/`-my` : cible tactile agrandie sans déplacer le texte (WCAG 2.5.8), motif de `BackLink`.
              // `-deeper` au survol : 5,19:1 sur `--tcn-paper` en 12 px, `-deep` n'y tient que 4,12:1.
              className="-my-1.5 inline-block py-1.5 text-[var(--tcn-text-faint)] underline underline-offset-2 hover:text-[var(--tcn-orange-deeper)]"
            >
              {route.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
