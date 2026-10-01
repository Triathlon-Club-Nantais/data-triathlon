import Link from "next/link";
import { LEGAL_ROUTES } from "./legal-routes";

/** Les trois textes légaux, en pied de toutes les pages (#333). */
export function LegalLinks() {
  return (
    <nav aria-label="Informations légales">
      <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1">
        {LEGAL_ROUTES.map((route) => (
          <li key={route.href}>
            <Link
              href={route.href}
              prefetch={false}
              // Même teinte que le texte du pied : le soulignement au repos le désigne comme lien (WCAG 1.4.1).
              className="text-[var(--tcn-text-faint)] underline underline-offset-2 hover:text-[var(--tcn-orange-deep)]"
            >
              {route.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
