"use client";
import Link from "next/link";
import { Card, CardTitle } from "@/components/ui/card";
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

  if (session.isPending)
    return <Skeleton className="h-40 w-full" aria-label="Chargement des écrans" />;
  // Une session illisible n'est pas une session sans pouvoirs : `useSession` ne
  // réessaie pas, et afficher « aucun écran » ferait croire à un retrait de
  // droits là où il n'y a qu'une panne. Le message du serveur n'est **pas**
  // réaffiché : son repli est `statusText`, donc anglais, et la panne la plus
  // fréquente ici — le réveil à froid du backend — n'est même pas une
  // `ApiError` (même doctrine que `tcn/ErrorScreen`).
  if (session.error)
    return (
      <EmptyState
        title="Vos pouvoirs n'ont pas pu être lus"
        description="Rechargez la page. Si le problème persiste, signalez-le depuis le bouton de retour du site."
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
        description="Ces écrans s'ouvrent avec les pouvoirs correspondants. Demandez-les à un administrateur du club."
      />
    );

  return (
    <div className="space-y-8">
      {sections.map((section) => (
        <section key={section.id} className="space-y-4">
          <h2 className="font-heading text-lg font-semibold">{section.label}</h2>
          {/* Une liste, et pas des liens frères : le lecteur d'écran annonce le
              nombre d'écrans ouverts et la position dans la section. */}
          <ul className="grid list-none gap-4 sm:grid-cols-2">
            {section.items.map((item) => (
              <li key={item.id}>
                {/* L'anneau de focus est celui du reste du front — trait opaque
                    `--tcn-orange` à 3,32:1 sur `--tcn-paper` (cf. `.tcn-btn` et
                    consorts dans `globals.css`). Le halo `ring-ring/50` seul
                    tombait à 1,86:1, sous le seuil WCAG 1.4.11.
                    **Pas d'`outline-none` ici** : en Tailwind v4 il ne se
                    contente pas d'annuler l'anneau au repos, il pose
                    `--tw-outline-style: none`, dont `focus-visible:outline-2`
                    dépend — l'anneau ne se dessinait pas du tout (constaté au
                    navigateur, invisible en revue de code). Sans lui, le repos
                    n'a pas d'anneau de toute façon. */}
                <Link
                  href={item.href}
                  className="block h-full rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
                >
                  <Card className="h-full gap-2 p-6 transition-all hover:ring-foreground/25">
                    <CardTitle>{item.label}</CardTitle>
                    <p className="text-sm text-[var(--tcn-text-faint)]">
                      {item.description}
                    </p>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
