"use client";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { NAV, ROLE, estVisible } from "@/components/layout/nav.config";
import { useSession } from "@/lib/queries/auth";

/**
 * Sommaire du back-office (ADM-6).
 *
 * Le public est un bénévole occasionnel qui revient après plusieurs mois, face
 * à quatre libellés quasi synonymes pour un non-initié — « Accès au
 * back-office », « Rôles des utilisateurs », « Droits des rôles », « Groupes
 * d'appartenance ». La phrase qui les désambiguïse existait déjà, mais dans le
 * `PageHeader` de chaque écran : lisible **après** le choix, donc après
 * l'hésitation qu'elle devait éviter. Elle est ici, avant.
 *
 * Rien n'est écrit deux fois : titres et phrases viennent de `nav.config.ts`,
 * la même table que le rail, filtrée par la **même** règle (`estVisible`).
 * Comme le rail, ce n'est pas une garde : chaque route de l'API porte la
 * sienne.
 */

/** Les écrans du back-office : ceux dont la destination vit sous `/admin`. */
const SECTIONS = NAV.filter((s) =>
  s.items.some((i) => i.href?.startsWith("/admin/")),
);

export function AdminIndex() {
  const session = useSession();
  const pouvoirs = new Set(session.data?.permissions ?? []);

  if (session.isPending) return <Skeleton className="h-40 w-full" />;
  // Une session illisible n'est pas une session sans pouvoirs : `useSession` ne
  // réessaie pas, et afficher « aucun écran » ferait croire à un retrait de
  // droits là où il n'y a qu'une panne.
  if (session.error)
    return (
      <EmptyState
        title="Vos pouvoirs n'ont pas pu être lus"
        description={session.error.message}
      />
    );

  const sections = SECTIONS.map((s) => ({
    ...s,
    items: s.items.filter((i) => estVisible(i, pouvoirs, ROLE.CONNECTED)),
  })).filter((s) => s.items.length > 0);

  if (sections.length === 0)
    return (
      <EmptyState
        title="Aucun écran d'administration ne vous est ouvert"
        description="Ces écrans s'ouvrent avec un rôle. Demandez-en un à un administrateur du club."
      />
    );

  return (
    <div className="space-y-8">
      {sections.map((section) => (
        <section key={section.id} className="space-y-4">
          <h2 className="text-lg font-bold">{section.label}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {section.items.map((item) => (
              <Link
                key={item.id}
                href={item.href}
                className="block rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <Card className="h-full p-6 space-y-2 transition-all hover:ring-foreground/25">
                  <div className="font-bold">{item.label}</div>
                  <p className="text-sm text-[var(--tcn-text-faint)]">
                    {item.description}
                  </p>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
