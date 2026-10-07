"use client";
import Link from "next/link";
import { Card, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { A_TRAITER, NAV, ROLE, estVisible, type NavItem } from "@/components/layout/nav.config";
import { useSession } from "@/lib/queries/auth";
import { libelleCompteur, useNavBadges } from "@/lib/queries/nav-badges";
import { NoAdminAccess } from "./NoAdminAccess";

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
 *
 * Les files « À traiter » viennent en tête avec leur compteur (#1246), celui
 * des pastilles du rail : on sait d'un coup d'œil ce qui attend. Elles ne sont
 * pas répétées en tuiles plus bas, où les autres écrans se rangent sous leur
 * sous-section.
 */

/** Les écrans du back-office : ceux dont la destination vit sous `/admin`. */
const SECTIONS = NAV.filter((s) =>
  s.items.some((i) => i.href?.startsWith("/admin/")),
);

/** Les entrées se suivent par groupe dans la table : l'ordre des intertitres en découle. */
function parGroupe<T extends NavItem>(items: T[]): { groupe: string | undefined; items: T[] }[] {
  const groupes: { groupe: string | undefined; items: T[] }[] = [];
  for (const item of items) {
    const dernier = groupes.at(-1);
    if (dernier && dernier.groupe === item.groupe) dernier.items.push(item);
    else groupes.push({ groupe: item.groupe, items: [item] });
  }
  return groupes;
}

const ANNEAU =
  "block h-full rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]";

export function AdminIndex() {
  const session = useSession();
  const pouvoirs = new Set(session.data?.permissions ?? []);
  const compteurs = useNavBadges(pouvoirs, session.data?.can_administer ?? false);

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

  // Même règle que la garde du layout (#1109), qui rend déjà cet état : ce
  // repli couvre le rendu client quand la session change sous l'écran.
  if (session.data && !session.data.can_administer) return <NoAdminAccess />;

  const visibles = SECTIONS.map((s) => ({
    ...s,
    items: s.items.filter((i) => estVisible(i, pouvoirs, ROLE.CONNECTED)),
  }));
  const files = visibles.flatMap((s) => s.items).filter((i) => i.groupe === A_TRAITER);
  const sections = visibles
    .map((s) => ({ ...s, items: s.items.filter((i) => i.groupe !== A_TRAITER) }))
    .filter((s) => s.items.length > 0);

  // Un pouvoir sans écran à lui dit la même chose que l'absence de pouvoir :
  // un seul texte, une seule sortie.
  if (files.length === 0 && sections.length === 0) return <NoAdminAccess />;

  return (
    <div className="space-y-8">
      {files.length > 0 && (
        <section aria-labelledby="admin-a-traiter" className="space-y-4">
          <h2 id="admin-a-traiter" className="font-heading text-lg font-semibold">
            {A_TRAITER}
          </h2>
          <ul className="grid list-none gap-3 sm:grid-cols-2">
            {files.map((item) => {
              const n = item.badge ? compteurs[item.badge] : undefined;
              return (
                <li key={item.id}>
                  <Link href={item.href} className={ANNEAU}>
                    <Card className="h-full flex-row items-center gap-4 p-5 transition-all hover:ring-foreground/25">
                      <div className="flex-1 space-y-1">
                        <CardTitle>{item.label}</CardTitle>
                        <p className="text-sm text-[var(--tcn-text-faint)]">{item.description}</p>
                      </div>
                      {!!n && (
                        <span className="flex-none">
                          {/* Même pastille que le rail : `--tcn-orange-deep`, où le
                              blanc tient 4,57:1 (#299). */}
                          <span
                            aria-hidden="true"
                            className="inline-block min-w-7 rounded-full bg-[var(--tcn-orange-deep)] px-2 py-0.5 text-center text-sm font-bold text-white"
                          >
                            {n}
                          </span>
                          <span className="sr-only">{libelleCompteur(item.badge, n)}</span>
                        </span>
                      )}
                      {n === 0 && (
                        <span className="flex-none text-sm text-[var(--tcn-text-muted)]">Rien en attente</span>
                      )}
                    </Card>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {sections.map((section) => (
        <section key={section.id} className="space-y-4">
          <h2 className="font-heading text-lg font-semibold">{section.label}</h2>
          {parGroupe(section.items).map(({ groupe, items }) => (
            <div key={groupe ?? section.id} className="space-y-3">
              {groupe && <h3 className="text-sm font-semibold text-[var(--tcn-text-muted)]">{groupe}</h3>}
              {/* Une liste, et pas des liens frères : le lecteur d'écran annonce le
                  nombre d'écrans ouverts et la position dans la section. */}
              <ul className="grid list-none gap-4 sm:grid-cols-2">
                {items.map((item) => (
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
                    <Link href={item.href} className={ANNEAU}>
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
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
