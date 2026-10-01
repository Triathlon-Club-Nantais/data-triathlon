"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Lien vers la saisie du code d'accès, qui y revient ensuite (#877).
 *
 * Un écran d'administration refusé faute de cookie de site ne peut pas rendre
 * le formulaire sur place (`/admin` est hors de la garde du site, pour que
 * `/admin/acces` reste joignable au premier démarrage). Sans `retour`, `/acces`
 * renverrait l'admin à l'accueil, loin de l'écran qu'il voulait voir.
 */
export function SiteAccessLink() {
  const chemin = usePathname();
  return (
    <Link
      href={`/acces?retour=${encodeURIComponent(chemin || "/")}`}
      className="text-sm font-medium text-primary underline-offset-4 hover:underline"
    >
      Saisir le code d&apos;accès
    </Link>
  );
}
