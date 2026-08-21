import type { ReactNode } from "react";

/**
 * Libellé + champ d'une barre de filtres du back-office, partagé par
 * `CoursesAdminTable` et `QualityQueueTable` (revue UI/UX #119, constat 11).
 *
 * `htmlFor` est facultatif : les deux écrans n'y recourent pas encore tous —
 * `CoursesAdminTable` associe ses champs par proximité visuelle seule — mais
 * l'ajouter ici ne change rien pour un appelant qui ne le passe pas.
 */
export function Champ({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex w-full flex-col gap-1.5 sm:w-auto">
      <label htmlFor={htmlFor} className="text-xs font-medium text-[var(--tcn-text-faint)]">
        {label}
      </label>
      {children}
    </div>
  );
}
