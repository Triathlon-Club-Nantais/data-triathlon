import Link from "next/link";
import { BookOpen } from "lucide-react";
import type { ReactNode } from "react";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { NoAdminAccess } from "@/components/admin/NoAdminAccess";
import { spaceRefusal } from "@/components/layout/space-guard";

/**
 * Garde d'accès aux écrans d'administration (FR-040), portée par
 * `spaceRefusal` (voir `components/layout/space-guard.tsx` pour la conduite
 * générale : redirection, FR-036, panne du backend).
 *
 * Propre au back-office : le pouvoir attendu est `can_administer`, et
 * `pages:preview` n'en est pas un (pouvoir de consultation, #1109). Le lien
 * « Guide » disparaît avec les enfants.
 *
 * **Elle ne vérifie pas le code d'accès au site.** La plupart des routes
 * `/admin/*` l'exigent en plus de la session (#509), mais `/admin/acces` doit
 * rester joignable sans lui pour poser le premier code. Un écran refusé pour
 * cette raison le dit lui-même : son 401 porte `code: "site_access_required"`,
 * que `messageDeRefus` distingue d'une session expirée (#877).
 */
export default async function AdminLayout({ children }: { children: ReactNode }) {
  const refus = await spaceRefusal("Back-office", (session) => session.can_administer, <NoAdminAccess />);
  if (refus) return refus;

  // Le dialog des gestes destructifs, monté une fois pour toutes les
  // sous-routes (#499). Composant client sous un layout serveur : les enfants
  // rendus par le serveur traversent le provider sans devenir clients.
  return (
    <DangerConfirmProvider>
      {/* Lien fixe vers le guide (#865), hors de `nav.config.ts` par choix
          délibéré : voir le commentaire sur `a-flags` dans nav.config.ts et
          research.md. La garde ci-dessus (`can_administer`) suffit, aucun
          `permission` par écran n'est donc nécessaire ici. */}
      <div
        className="mx-auto flex justify-end px-4 pt-4 sm:px-8 md:px-10"
        style={{ maxWidth: "var(--tcn-content-max)" }}
      >
        <Link
          href="/admin/guide"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--tcn-text-faint)] transition-colors hover:text-foreground"
        >
          <BookOpen className="size-4" aria-hidden />
          Guide
        </Link>
      </div>
      {children}
    </DangerConfirmProvider>
  );
}
