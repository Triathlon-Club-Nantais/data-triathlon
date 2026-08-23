# Rail replié lisible, cookie de largeur, nav mobile hors hamburger — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer NAV-2, NAV-3 et NAV-4 du rapport UI/UX (#325, §5) sur `AppNav.tsx` : un rail replié qui porte une marque et des libellés accessibles, une largeur de rail décidée avant la peinture serveur, et une navigation mobile qui sort de derrière le hamburger.

**Architecture:** Huit tâches indépendantes sur un seul gros fichier (`AppNav.tsx`) plus quatre compagnons ponctuels (`app/layout.tsx`, `app/globals.css`, `UserMenu.tsx`, un nouveau `components/ui/tooltip.tsx`). Aucune ne touche `nav.config.ts` : tout le travail est de la logique de rendu ou de la plomberie serveur/cookie, jamais de la donnée de navigation.

**Tech Stack:** Next.js 16 (App Router) / TypeScript strict / React / `@base-ui/react` (déjà en dépendance) / Tailwind / Vitest + Testing Library (projet `jsdom`).

**Spec:** `docs/superpowers/specs/2026-08-22-nav-rail-lisible-design.md`

## Global Constraints

- **Issue** : #482 (epic #460, backlog #325). Le message de PR devra porter `Closes #482`.
- **Langue** (Principe I) : français pour tout texte visible utilisateur (libellés, `aria-label`) et les commentaires de règle métier ; anglais pour les identifiants de code et noms de tests techniques — ce fichier suit déjà ce mélange, ne pas le rectifier au passage.
- **Identité arbitrée, non rejugée** : aucune modification de palette, du couple Anton/Barlow, ni des dégradés `--tcn-*`. Le monogramme (Task 4) est du texte dans un token de police déjà arbitré (`--tcn-font-display`), jamais un nouvel asset graphique.
- **Frontière `components/tcn/` vs `components/ui/`, non rejugée** : le nouveau `Tooltip` (Task 1) est une primitive accessible sans équivalent TCN → `components/ui/`, au même titre que `sheet.tsx`, `popover.tsx`, `dialog.tsx`.
- **Invariant de montage unique d'`Entree` (#428)** : aucune tâche ne doit démonter/remonter un `Link` déjà monté pour la même route entre les états repliés/dépliés du rail. Concrètement : ne jamais faire dépendre la présence de `Tooltip`/`TooltipTrigger` autour d'un `Link` de la valeur d'`expanded` — seul le contenu de l'infobulle et son état `disabled` en dépendent, jamais la structure de l'arbre.
- **TDD non négociable** (Principe III) : chaque tâche comportant une modification de comportement observable écrit et fait échouer son test avant d'implémenter. Task 1 (scaffolding pur, sans branche logique propre) fait exception documentée — précédent : `components/ui/sheet.tsx`, `popover.tsx`, `dialog.tsx` n'ont pas de fichier de test dédié dans ce dépôt ; son comportement réel est verrouillé par les tests **rouges** de Task 5, qui le consomment.
- **Hors périmètre, à ne pas traiter dans ce plan** : le second saut de NAV-3 (session client sans `initialData`) et NAV-5 (déjà en worktree `issue-483-dashboard-toolbar`).
- **Commandes** (depuis `frontend/`) : `npx vitest run <fichier>` pour un fichier ciblé (projet `jsdom` implicite pour un `.test.tsx`) ; `npm test` pour la suite complète ; `npm run lint` avant de clore la branche.

---

## Structure des fichiers

| Fichier | Responsabilité | Action |
| --- | --- | --- |
| `frontend/components/ui/tooltip.tsx` | Infobulle accessible (survol + focus), enveloppe `@base-ui/react/tooltip` | Créer |
| `frontend/AGENTS.md` | Une ligne : `tooltip` rejoint l'énumération des primitives `ui/` ; paragraphe de synthèse #482 en fin de tâche | Modifier |
| `frontend/components/layout/AppNav.tsx` | Cookie de largeur, monogramme, infobulles, lien direct « Club », barre basse mobile, portée du tiroir | Modifier |
| `frontend/components/layout/AppNav.test.tsx` | Tous les tests de comportement de ce plan sauf `UserMenu` | Modifier |
| `frontend/app/layout.tsx` | Lecture du cookie `tcn-nav-expanded`, réservation d'espace sous le contenu mobile | Modifier |
| `frontend/app/layout.test.tsx` | Test de la réservation d'espace mobile | Modifier |
| `frontend/app/globals.css` | Token `--tcn-nav-bottom` | Modifier |
| `frontend/components/auth/UserMenu.tsx` | Prop `onNavigate`, appelé au bon moment | Modifier |
| `frontend/components/auth/UserMenu.test.tsx` | Comportement de `onNavigate` | Modifier |

---

### Task 1: `components/ui/tooltip.tsx` — l'infobulle accessible

**Files:**
- Create: `frontend/components/ui/tooltip.tsx`
- Modify: `frontend/AGENTS.md` (une ligne)

**Interfaces:**
- Consumes: `@base-ui/react/tooltip` (dépendance déjà installée, jamais encore enveloppée dans ce dépôt), `cn` de `@/lib/utils` (déjà utilisé par tous les wrappers `ui/`).
- Produces: `Tooltip`, `TooltipTrigger`, `TooltipContent` — exportés de `@/components/ui/tooltip`, consommés par Task 5.

- [ ] **Step 1: Créer le composant (sans test dédié — voir Global Constraints)**

`@base-ui/react/tooltip` expose `Root`, `Trigger` (rend un `<button>` par défaut, mais accepte `render` pour se composer avec un `<Link>` ou tout autre élément — même patron que `DialogPrimitive.Close render={<Button .../>}` dans `dialog.tsx`), `Portal`, `Positioner`, `Popup`. `Trigger.delay` vaut 600 ms par défaut : on le ramène à 0 dans le wrapper, l'audit UI/UX reprochant justement le délai natif du navigateur (~1 s), pas seulement son absence au clavier/tactile.

```tsx
"use client"

import * as React from "react"
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip"

import { cn } from "@/lib/utils"

/**
 * Infobulle accessible — ouvre au survol **et** au focus clavier (natif au
 * primitif Base UI), ferme sur Échap ou perte de focus. Remplace les `title`
 * natifs du rail replié (#482, NAV-2) : une infobulle native n'ouvre qu'au
 * survol, après ~1 s, jamais au tactile ni au clavier.
 *
 * Délai ramené à 0 ms (`delay` de `TooltipTrigger` vaut 600 ms par défaut) :
 * c'est ce délai-là, pas seulement son absence au clavier, que l'audit
 * reprochait au `title` natif du navigateur.
 */
function Tooltip({ ...props }: TooltipPrimitive.Root.Props) {
  return <TooltipPrimitive.Root data-slot="tooltip" {...props} />
}

function TooltipTrigger({ delay = 0, ...props }: TooltipPrimitive.Trigger.Props) {
  return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" delay={delay} {...props} />
}

function TooltipContent({
  className,
  side = "right",
  sideOffset = 8,
  ...props
}: TooltipPrimitive.Popup.Props &
  Pick<TooltipPrimitive.Positioner.Props, "side" | "sideOffset">) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Positioner side={side} sideOffset={sideOffset} className="z-50">
        <TooltipPrimitive.Popup
          data-slot="tooltip-content"
          style={{
            background: "var(--tcn-ink)",
            color: "var(--tcn-paper)",
            borderRadius: "var(--tcn-radius-sm)",
          }}
          className={cn(
            "px-2.5 py-1.5 text-xs font-semibold whitespace-nowrap data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
            className
          )}
          {...props}
        />
      </TooltipPrimitive.Positioner>
    </TooltipPrimitive.Portal>
  )
}

export { Tooltip, TooltipContent, TooltipTrigger }
```

`side="right"` par défaut : le rail est ancré à gauche de l'écran, l'infobulle s'ouvre donc naturellement vers le contenu plutôt que vers le bord de la fenêtre.

- [ ] **Step 2: Vérifier que ça compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur sur `tooltip.tsx` (le comportement réel est vérifié par les tests **rouges** de Task 5, pas ici).

- [ ] **Step 3: Ajouter `tooltip` à l'énumération des primitives `ui/` dans `frontend/AGENTS.md`**

Chercher la phrase « porte les primitives complexes bâties sur `@base-ui/react` — `dialog`, `select`, `dropdown-menu`, `popover`, `sheet`, `table` » dans la section **Deux bibliothèques, une frontière** et y insérer `tooltip` :

```
porte les primitives complexes bâties sur `@base-ui/react` — `dialog`,
`select`, `dropdown-menu`, `popover`, `sheet`, `table`, `tooltip` —
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ui/tooltip.tsx frontend/AGENTS.md
git commit -m "feat(482): add an accessible Tooltip primitive wrapping @base-ui/react/tooltip"
```

---

### Task 2: la largeur du rail décidée avant la peinture (NAV-3)

**Files:**
- Modify: `frontend/components/layout/AppNav.tsx:37-98`
- Modify: `frontend/app/layout.tsx:1-52`
- Modify: `frontend/components/layout/AppNav.test.tsx:72-82,110-129,177-184,214-224`

**Interfaces:**
- Consumes: `cookies()` de `next/headers` (déjà utilisé par le même patron dans `lib/api/server.ts`).
- Produces: `AppNav({ initialExpanded?: boolean })` — nouvelle prop, `false` par défaut, consommée par `app/layout.tsx`. Le test harness `afficher(session, { initialExpanded? })` dans `AppNav.test.tsx`, consommé par les tâches suivantes qui ont besoin d'un rail déjà déplié sans passer par un clic.

- [ ] **Step 1: Étendre le harnais de test et écrire les tests qui échouent**

Dans `AppNav.test.tsx`, remplacer `afficher` (lignes 72-82) :

```tsx
function afficher(session: SessionUser | null, { initialExpanded = false }: { initialExpanded?: boolean } = {}) {
  if (session) getSession.mockResolvedValue(session);
  else getSession.mockRejectedValue(new ApiError(401, "anonyme"));

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AppNav initialExpanded={initialExpanded} />
    </QueryClientProvider>,
  );
}
```

Ajouter, dans le `beforeEach` existant (après le bloc qui redéfinit `window.localStorage`, ligne ~128), une remise à zéro du cookie pour éviter toute fuite d'un test à l'autre :

```tsx
  // Le cookie de largeur (#482, NAV-3) n'est réinitialisé par aucun mock —
  // contrairement à `localStorage` ci-dessus, `document.cookie` est un vrai
  // objet du document jsdom qui persiste d'un test à l'autre dans le même fichier.
  document.cookie = "tcn-nav-expanded=; path=/; max-age=0";
```

Remplacer les deux tests qui seedaient `localStorage` pour tester la persistance de la largeur (lignes 177-184 et 214-224) :

```tsx
  it("ne prefetche « Résultats » qu'une fois quand le rail persisté est déjà déplié", async () => {
    afficher(null, { initialExpanded: true });

    // Le rail est déjà déplié dès le premier rendu — synchrone, sans attendre
    // un effet de montage (#482, NAV-3) : c'est exactement ce que ce correctif
    // change par rapport à l'ancien comportement, qui exigeait un `findByRole`.
    // Scopé au rail : Task 6 y ajoute une barre basse mobile qui porte, elle
    // aussi, une entrée « Résultats ».
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getByRole("link", { name: "Résultats" })).toBeInTheDocument();
    expect(montages.get("/resultats")).toBe(1);
  });
```

```tsx
  it("ne prefetche pas le logo du rail déplié, qui double la route de « Tableau de bord »", async () => {
    afficher(null, { initialExpanded: true });

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const logo = within(rail).getByRole("link", { name: "TCN — Accueil" });
    expect(logo).toHaveAttribute("href", "/dashboard");
    expect(logo).toHaveAttribute("data-prefetch", "false");
  });
```

Ajouter un nouveau describe, à la suite du describe `#428` existant :

```tsx
describe("AppNav — largeur du rail décidée avant la peinture (#482, NAV-3)", () => {
  it("réplique replié par défaut quand aucune prop n'est fournie", () => {
    afficher(null);

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(rail.style.width).toBe("var(--tcn-nav-rail)");
  });

  it("peint le rail à sa largeur persistée dès le premier rendu, sans jamais lire localStorage", () => {
    // Le stock localStorage reste vide : si le rail lisait encore
    // `tcn-nav-expanded` depuis là, la prop n'aurait aucun effet.
    afficher(null, { initialExpanded: true });

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(rail.style.width).toBe("var(--tcn-nav-panel)");
    expect(window.localStorage.getItem("tcn-nav-expanded")).toBeNull();
  });

  it("écrit un cookie — jamais localStorage — quand on (re)plie le rail à la main", async () => {
    afficher(null);
    await userEvent.click(screen.getByRole("button", { name: "Déplier la navigation" }));

    expect(document.cookie).toContain("tcn-nav-expanded=1");
    expect(window.localStorage.getItem("tcn-nav-expanded")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Replier la navigation" }));
    expect(document.cookie).toContain("tcn-nav-expanded=0");
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx`
Expected: FAIL — `AppNav` ne connaît pas encore de prop `initialExpanded` (TypeScript refuse `<AppNav initialExpanded={...} />`, et à défaut d'erreur de type les nouvelles assertions sur `rail.style.width`/le cookie échouent).

- [ ] **Step 3: Implémenter dans `AppNav.tsx`**

Signature et état initial (remplace lignes 37-49) :

```tsx
export function AppNav({ initialExpanded = false }: { initialExpanded?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  // `expanded` vient désormais du cookie lu par `app/layout.tsx` (#482,
  // NAV-3), synchrone dès le premier rendu — plus rien à y lire au montage.
  // `athlete` et raccourci clavier restent client-only : `localStorage` et
  // `navigator` n'existent pas au rendu serveur.
  const [{ expanded, athlete, kbd }, setClient] = useState({
    expanded: initialExpanded,
    athlete: null as PickedAthlete | null,
    kbd: "Ctrl K",
  });
```

Effet de montage (remplace lignes 51-66) :

```tsx
  useEffect(() => {
    // `localStorage` et `navigator` n'existent pas au rendu serveur : leur
    // lecture ne peut avoir lieu qu'au montage, en un seul `setState`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setClient((c) => ({
      ...c,
      athlete: readAthlete(),
      kbd: /Mac|iPhone|iPad/i.test(navigator.userAgent) ? "⌘K" : "Ctrl K",
    }));
  }, []);
```

`setExpanded` (remplace lignes 91-98) :

```tsx
  function setExpanded(next: boolean) {
    setClient((c) => ({ ...c, expanded: next }));
    // Cookie plutôt que `localStorage` (#482, NAV-3) : lu par `app/layout.tsx`
    // au prochain chargement, pour peindre la bonne largeur avant la
    // peinture — jamais relayé à l'API, donc sans effet sur le Data Cache
    // (#352). Un an de `max-age` : c'est une préférence d'affichage, pas une
    // session à faire expirer.
    document.cookie = `${STORE_NAV}=${next ? "1" : "0"}; path=/; max-age=31536000; SameSite=Lax`;
  }
```

- [ ] **Step 4: Implémenter dans `app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { connection } from "next/server";
import { Anton, Barlow, Barlow_Semi_Condensed } from "next/font/google";
```

Et dans `RootLayout`, juste après `await connection();` (ligne 50) :

```tsx
  await connection();

  // Largeur du rail décidée avant la peinture (#482, NAV-3) : le cookie que
  // `AppNav` écrit au pliage/dépliage (`document.cookie`, jamais relayé à
  // l'API) est relu ici pour que le rendu serveur et la première passe
  // client partagent déjà la bonne largeur — plus de bascule 76 px → 288 px
  // après coup.
  const jar = await cookies();
  const initialExpanded = jar.get("tcn-nav-expanded")?.value === "1";
```

Et passer la prop à l'appel existant :

```tsx
            <AppNav initialExpanded={initialExpanded} />
```

- [ ] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx`
Expected: PASS — l'intégralité du fichier, y compris les tests non touchés par cette tâche (aucune régression sur #428, #323, #442…).

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/layout/AppNav.tsx frontend/app/layout.tsx frontend/components/layout/AppNav.test.tsx
git commit -m "fix(482): decide the nav rail width server-side via a cookie, before paint (NAV-3)"
```

---

### Task 3: une section à une seule destination devient un lien direct (NAV-2)

**Files:**
- Modify: `frontend/components/layout/AppNav.tsx:548-552`
- Modify: `frontend/components/layout/AppNav.test.tsx:449-464`

**Interfaces:**
- Consumes: `SectionRendue.items` (déjà typé, aucun changement de forme).
- Produces: rien de nouveau — comportement de rendu uniquement.

- [ ] **Step 1: Réécrire le test #274 et en ajouter un de non-régression**

Remplacer le test existant (lignes 449-464) :

```tsx
  it("rend « Club » comme un lien direct sur le rail replié, une seule destination livrée (#482, NAV-2)", async () => {
    afficher(null);
    // Scopé au rail : Task 6 y ajoute une barre basse mobile qui porte, elle
    // aussi, une entrée « Athlètes par saison ».
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });

    // Plus de bouton dépliant pour une section à une seule destination : le
    // rail replié porte directement le lien.
    expect(within(rail).queryByRole("button", { name: "Club" })).not.toBeInTheDocument();
    const lien = within(rail).getByRole("link", { name: "Athlètes par saison" });
    expect(lien).toHaveAttribute("href", "/club/athletes");
    expect(screen.queryByLabelText("Carte")).not.toBeInTheDocument();

    await deplier();
    expect(within(rail).getByText("Club")).toBeInTheDocument();
    expect(within(rail).getByRole("link", { name: "Athlètes par saison" })).toHaveAttribute(
      "href",
      "/club/athletes",
    );
    expect(within(rail).queryByText("Espace club")).not.toBeInTheDocument();
  });

  it("garde le bouton dépliant pour une section à plusieurs destinations livrées (#482, NAV-2)", async () => {
    afficher(habilite("pending_providers:read", "batch:run"));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Administration" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("link", { name: "Fournisseurs en attente" })).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx -t "Club"`
Expected: FAIL — le rail replié rend encore un `button` nommé « Club ».

- [ ] **Step 3: Implémenter**

Dans `NavContent`, remplacer la condition (ligne 548) :

```tsx
              {!expanded && !sec.root && sec.items.length > 1 ? (
                <button type="button" onClick={onExpand} title={sec.label} aria-label={sec.label} style={tuile(actifIci)}>
                  <sec.icon size={20} />
                  {actifIci && <span style={barreActive(9)} />}
                </button>
              ) : (
                // `gap: 0` replié, l'espacement des tuiles venant de leur propre
                // `margin: 0 auto 4px` (cf. `tuile()`) — un `gap` s'y ajouterait.
                // Une section réduite à une seule destination livrée (« Club »
                // aujourd'hui) rend directement son `Entree` ici plutôt que le
                // bouton dépliant ci-dessus : deux gestes pour une seule
                // destination n'ont plus de sens (#482, NAV-2).
                <div style={{ display: "flex", flexDirection: "column", gap: expanded ? 2 : 0 }}>
                  {sec.items.map((it) => (
                    <Entree
                      key={it.id}
                      item={it}
                      actif={isActive(it.href)}
                      expanded={expanded}
                      onNavigate={onNavigate}
                    />
                  ))}
                </div>
              )}
```

(Seul le premier caractère de la condition change — `!expanded && !sec.root` devient `!expanded && !sec.root && sec.items.length > 1` ; le reste du bloc est inchangé.)

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx`
Expected: PASS, fichier entier.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/AppNav.tsx frontend/components/layout/AppNav.test.tsx
git commit -m "fix(482): render a single-destination nav section as a direct link on the collapsed rail (NAV-2)"
```

---

### Task 4: le monogramme du rail replié (NAV-2)

**Files:**
- Modify: `frontend/components/layout/AppNav.tsx:168-202`
- Modify: `frontend/components/layout/AppNav.test.tsx` (nouveau describe)

**Interfaces:**
- Consumes: `CLUB_NAME_SHORT` de `@/lib/club` (déjà importé), token `--tcn-font-display`, prop `initialExpanded` de Task 2.
- Produces: rien de nouveau consommé ailleurs.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter, après le describe de Task 2 :

```tsx
describe("AppNav — monogramme du rail replié (#482, NAV-2)", () => {
  it("porte un lien vers /dashboard même rail replié, alors qu'aucune marque n'existait avant", () => {
    afficher(null);

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const monogramme = within(rail).getByRole("link", { name: "TCN — Accueil" });
    expect(monogramme).toHaveAttribute("href", "/dashboard");
    expect(monogramme).toHaveTextContent("TCN");
  });

  it("ne double pas le monogramme une fois le rail déplié — seul le logo image reste", () => {
    afficher(null, { initialExpanded: true });

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getAllByRole("link", { name: "TCN — Accueil" })).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx -t "monogramme"`
Expected: FAIL — aucun lien nommé « TCN — Accueil » n'existe rail replié.

- [ ] **Step 3: Implémenter**

Remplacer le bloc d'en-tête du rail (lignes 168-202) :

```tsx
        <div
          style={{
            flex: "none",
            display: "flex",
            flexDirection: expanded ? "row" : "column",
            alignItems: "center",
            justifyContent: "center",
            gap: expanded ? 10 : 4,
            height: 68,
            padding: expanded ? "0 14px" : "8px 0",
            borderBottom: "1px solid var(--tcn-border-faint)",
          }}
        >
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-label={expanded ? "Replier la navigation" : "Déplier la navigation"}
            style={boutonFantome}
          >
            {expanded ? <PanelLeft size={20} /> : <Menu size={20} />}
          </button>
          {expanded ? (
            /* prefetch={false} (#428) : rendu au seul état déplié, ce lien
               monte un second observateur vers `/dashboard` alors que l'entrée
               « Tableau de bord » du rail prefetche déjà la route. */
            <Link
              href="/dashboard"
              prefetch={false}
              aria-label={`${CLUB_NAME_SHORT} — Accueil`}
              style={{ display: "inline-flex" }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-tcn.png" alt={CLUB_NAME} style={{ height: 26, display: "block" }} />
            </Link>
          ) : (
            // Monogramme du rail replié (#482, NAV-2) : jusqu'ici seule la
            // barre mobile portait une marque dans le HTML servi. Texte plutôt
            // qu'un second asset graphique — `logo-tcn.png` est un wordmark
            // 2000×638, illisible à 76 px de large, et calquer un mark carré
            // dessus aurait rouvert l'identité visuelle (#325), hors mandat de
            // ce lot. Même `aria-label` et même destination que le logo
            // déplié : un seul lien « accueil », deux habillages.
            <Link
              href="/dashboard"
              prefetch={false}
              aria-label={`${CLUB_NAME_SHORT} — Accueil`}
              style={{
                display: "inline-flex",
                fontFamily: "var(--tcn-font-display)",
                fontSize: 15,
                letterSpacing: "0.02em",
                color: "var(--tcn-ink)",
                textDecoration: "none",
              }}
            >
              {CLUB_NAME_SHORT}
            </Link>
          )}
        </div>
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx`
Expected: PASS, fichier entier (vérifier en particulier que le test de Task 2 sur le logo déplié — qui cherche aussi « TCN — Accueil » — passe toujours : un seul lien de ce nom doit exister à la fois).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/AppNav.tsx frontend/components/layout/AppNav.test.tsx
git commit -m "feat(482): show a text monogram in the collapsed rail header, linked to /dashboard (NAV-2)"
```

---

### Task 5: remplacer les six `title` du rail replié par des infobulles (NAV-2)

**Files:**
- Modify: `frontend/components/layout/AppNav.tsx:1-13,217-244,363-391,397-442,461-469,548-552,607-689`
- Modify: `frontend/components/layout/AppNav.test.tsx` (nouveau describe)

**Interfaces:**
- Consumes: `Tooltip`, `TooltipTrigger`, `TooltipContent` de Task 1.
- Produces: rien de nouveau consommé ailleurs.

- [ ] **Step 1: Écrire les tests qui échouent**

```tsx
describe("AppNav — infobulles du rail replié remplacent les title (#482, NAV-2)", () => {
  it("affiche une infobulle « Se connecter » au survol du bouton replié", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const bouton = within(rail).getByRole("button", { name: "Se connecter" });

    await userEvent.hover(bouton);
    expect(await screen.findByRole("tooltip", { name: "Se connecter" })).toBeInTheDocument();
  });

  it("affiche la même infobulle au focus clavier, pas seulement au survol", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const bouton = within(rail).getByRole("button", { name: "Se connecter" });

    act(() => bouton.focus());
    expect(await screen.findByRole("tooltip", { name: "Se connecter" })).toBeInTheDocument();
  });

  it("n'affiche plus aucune infobulle sur ce bouton une fois le rail déplié", async () => {
    afficher(null, { initialExpanded: true });
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const bouton = within(rail).getByRole("button", { name: "Se connecter" });

    await userEvent.hover(bouton);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("porte une infobulle sur le lien « Ajouter une épreuve » replié", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const lien = within(rail).getByRole("link", { name: "Ajouter une épreuve" });

    await userEvent.hover(lien);
    expect(await screen.findByRole("tooltip", { name: "Ajouter une épreuve" })).toBeInTheDocument();
  });

  it("porte une infobulle sur le bouton « Rechercher un athlète » replié", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const bouton = within(rail).getByRole("button", { name: "Rechercher un athlète" });

    await userEvent.hover(bouton);
    expect(await screen.findByRole("tooltip", { name: "Rechercher un athlète" })).toBeInTheDocument();
  });

  it("porte une infobulle « Mon profil » sur la tuile de l'athlète retenu, repliée", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 12, prenom: "Jean", nom: "Dupont" }));
    afficher(null);
    const avatar = await screen.findByRole("link", { name: "Mon profil — Jean Dupont" });

    await userEvent.hover(avatar);
    expect(await screen.findByRole("tooltip", { name: "Mon profil" })).toBeInTheDocument();
  });

  it("porte une infobulle sur la tuile de catégorie repliée (« Administration »)", async () => {
    afficher(habilite("pending_providers:read", "batch:run"));
    const bouton = await screen.findByRole("button", { name: "Administration" });

    await userEvent.hover(bouton);
    expect(await screen.findByRole("tooltip", { name: "Administration" })).toBeInTheDocument();
  });

  it("porte une infobulle sur une entrée repliée du rail (« Tableau de bord »)", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const lien = within(rail).getByRole("link", { name: "Tableau de bord" });

    await userEvent.hover(lien);
    expect(await screen.findByRole("tooltip", { name: "Tableau de bord" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx -t "infobulles"`
Expected: FAIL — aucun élément de rôle `tooltip` n'existe encore.

- [ ] **Step 3: Implémenter — imports**

```tsx
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
```

- [ ] **Step 4: Implémenter — bouton « Se connecter » (remplace lignes 217-244)**

```tsx
            <Tooltip>
              <TooltipTrigger
                disabled={expanded}
                render={
                  <button
                    type="button"
                    onClick={() => router.push("/login")}
                    aria-label="Se connecter"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      width: "100%",
                      height: 44,
                      padding: expanded ? "0 14px" : 0,
                      justifyContent: expanded ? "flex-start" : "center",
                      borderRadius: "var(--tcn-radius-lg)",
                      background: "var(--tcn-surface)",
                      color: "var(--tcn-ink)",
                      border: "1.5px solid var(--tcn-border-strong)",
                      fontFamily: "var(--tcn-font-body)",
                      fontWeight: 700,
                      fontSize: 13.5,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      cursor: "pointer",
                    }}
                  />
                }
              >
                <LogIn size={18} style={{ flex: "none" }} />
                {expanded && <span>Se connecter</span>}
              </TooltipTrigger>
              {!expanded && <TooltipContent>Se connecter</TooltipContent>}
            </Tooltip>
```

- [ ] **Step 5: Implémenter — lien « Ajouter une épreuve » (remplace lignes 363-391)**

```tsx
        <Tooltip>
          <TooltipTrigger
            disabled={expanded}
            render={
              <Link
                href="/ajouter"
                onClick={onNavigate}
                aria-label="Ajouter une épreuve"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  height: 44,
                  padding: padAction,
                  justifyContent: justify,
                  borderRadius: "var(--tcn-radius-lg)",
                  background: "var(--tcn-orange-deep)",
                  color: "#fff",
                  textDecoration: "none",
                  boxShadow: "var(--tcn-shadow-orange)",
                  fontWeight: 800,
                  fontSize: 14,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                }}
              />
            }
          >
            <Plus size={20} style={{ flex: "none" }} />
            {expanded && <span>Ajouter une épreuve</span>}
          </TooltipTrigger>
          {!expanded && <TooltipContent>Ajouter une épreuve</TooltipContent>}
        </Tooltip>
```

- [ ] **Step 6: Implémenter — bouton « Rechercher un athlète » (remplace lignes 397-442)**

```tsx
        <Tooltip>
          <TooltipTrigger
            disabled={expanded}
            render={
              <button
                type="button"
                onClick={onOpenPicker}
                aria-label="Rechercher un athlète"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  height: 44,
                  padding: padAction,
                  justifyContent: justify,
                  borderRadius: "var(--tcn-radius-lg)",
                  background: "var(--tcn-surface)",
                  color: "var(--tcn-ink)",
                  border: "1.5px solid var(--tcn-ink)",
                  fontFamily: "var(--tcn-font-body)",
                  fontWeight: 700,
                  fontSize: 14,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  cursor: "pointer",
                }}
              />
            }
          >
            <Search size={18} style={{ flex: "none" }} />
            {expanded && (
              <>
                <span style={{ flex: 1, textAlign: "left" }}>Rechercher un athlète</span>
                <span
                  style={{
                    flex: "none",
                    padding: "2px 7px",
                    borderRadius: "var(--tcn-radius-sm)",
                    background: "var(--tcn-fill)",
                    border: "1px solid var(--tcn-border)",
                    fontFamily: "var(--tcn-font-cond)",
                    fontWeight: 700,
                    fontSize: 11,
                    color: "var(--tcn-text-muted)",
                  }}
                >
                  {kbd}
                </span>
              </>
            )}
          </TooltipTrigger>
          {!expanded && <TooltipContent>{`Rechercher un athlète (${kbd})`}</TooltipContent>}
        </Tooltip>
```

- [ ] **Step 7: Implémenter — avatar « Mon profil » (remplace lignes 461-469, seul le `<Link>` de l'avatar — celui du prénom, plus bas, n'a jamais porté de `title`)**

```tsx
            <Tooltip>
              <TooltipTrigger
                disabled={expanded}
                render={
                  <Link
                    href={`/athletes/${athlete.id}`}
                    prefetch={false}
                    onClick={onNavigate}
                    aria-label={`Mon profil — ${nomComplet(athlete)}`}
                  />
                }
              >
                <Avatar name={nomComplet(athlete)} size={30} style={{ boxShadow: "var(--tcn-shadow-orange)" }} />
              </TooltipTrigger>
              {!expanded && <TooltipContent>Mon profil</TooltipContent>}
            </Tooltip>
```

- [ ] **Step 8: Implémenter — tuile de catégorie repliée (remplace la branche bouton de Task 3, ligne 549)**

```tsx
                <Tooltip>
                  <TooltipTrigger
                    render={<button type="button" onClick={onExpand} aria-label={sec.label} style={tuile(actifIci)} />}
                  >
                    <sec.icon size={20} />
                    {actifIci && <span style={barreActive(9)} />}
                  </TooltipTrigger>
                  <TooltipContent>{sec.label}</TooltipContent>
                </Tooltip>
```

(Ce bouton n'existe que dans la branche `!expanded` — pas de `disabled`/rendu conditionnel du contenu à faire ici, contrairement aux cinq autres emplacements.)

- [ ] **Step 9: Implémenter — `Entree` (remplace lignes 607-689)**

Même patron que les cinq emplacements précédents : `render` ne porte que les attributs du `Link` (bare, sans enfants), les enfants visibles restent les propres `children` JSX de `TooltipTrigger` — jamais l'inverse, pour rester dans la forme déjà éprouvée aux étapes 4 à 8 plutôt que d'introduire une variante non vérifiée du contrat `render`.

```tsx
function Entree({
  item,
  actif,
  expanded,
  onNavigate,
}: {
  item: Destination;
  actif: boolean;
  expanded: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  // Replié, le seul porteur visible du libellé était le `title` natif du
  // navigateur — jamais lu au tactile, jamais au clavier (#482, NAV-2). Une
  // infobulle maison le remplace ; `aria-label` reste le nom accessible, donc
  // rien ne change pour les technologies d'assistance. `disabled` plutôt
  // qu'un rendu conditionnel du `Tooltip` lui-même : la structure de l'arbre
  // ne dépend jamais d'`expanded`, seul ce qui protège le montage unique du
  // `Link` (#428).
  return (
    <Tooltip>
      <TooltipTrigger
        disabled={expanded}
        render={
          <Link
            href={item.href}
            onClick={onNavigate}
            aria-label={expanded ? undefined : item.label}
            aria-current={actif ? "page" : undefined}
            style={expanded ? entree(actif) : tuile(actif)}
          />
        }
      >
        {actif && <span style={barreActive(expanded ? 10 : 9)} />}
        {expanded ? (
          <>
            <span
              style={{
                flex: "none",
                width: 5,
                height: 5,
                borderRadius: "var(--tcn-radius-pill)",
                background: actif ? "var(--tcn-orange)" : "var(--tcn-text-disabled)",
              }}
            />
            <span style={{ flex: 1 }}>{item.label}</span>
            {!!item.count && (
              <span style={{ flex: "none", display: "inline-flex", alignItems: "center" }}>
                <span
                  aria-hidden="true"
                  style={{
                    minWidth: 20,
                    padding: "1px 6px",
                    borderRadius: "var(--tcn-radius-pill)",
                    background: "var(--tcn-orange-deep)",
                    color: "#fff",
                    fontSize: 11,
                    fontWeight: 700,
                    textAlign: "center",
                  }}
                >
                  {item.count}
                </span>
                <span className="sr-only">{libelleCompteur(item)}</span>
              </span>
            )}
          </>
        ) : (
          Icon && <Icon size={20} />
        )}
      </TooltipTrigger>
      {!expanded && <TooltipContent>{item.label}</TooltipContent>}
    </Tooltip>
  );
}
```

- [ ] **Step 10: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx`
Expected: PASS, **fichier entier** — en particulier le describe `#428` (montages de `next/link`) : la preuve que l'enveloppe `Tooltip` ne remonte jamais le `Link` sous-jacent.

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 11: Commit**

```bash
git add frontend/components/layout/AppNav.tsx frontend/components/layout/AppNav.test.tsx
git commit -m "fix(482): replace the collapsed rail's native title attributes with accessible tooltips (NAV-2)"
```

---

### Task 6: la barre basse mobile (NAV-4)

**Files:**
- Modify: `frontend/app/globals.css:218-219`
- Modify: `frontend/components/layout/AppNav.tsx:100-125,249-276`
- Modify: `frontend/app/layout.tsx:71-79` (état post-Task 2)
- Modify: `frontend/components/layout/AppNav.test.tsx` (nouveau describe)
- Modify: `frontend/app/layout.test.tsx` (nouveau describe)

**Interfaces:**
- Consumes: `sections` (calculé dans `AppNav`), `ROLE.ANON`, `isActive`.
- Produces: `publicItems` — variable locale à `AppNav`, non exportée.

- [ ] **Step 1: Écrire les tests qui échouent — `AppNav.test.tsx`**

```tsx
describe("AppNav — barre basse mobile (#482, NAV-4)", () => {
  it("porte les trois destinations publiques, avec libellé visible", () => {
    afficher(null);

    const barre = screen.getByRole("navigation", { name: "Navigation" });
    expect(within(barre).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("href", "/dashboard");
    expect(within(barre).getByRole("link", { name: "Résultats" })).toHaveAttribute("href", "/resultats");
    expect(within(barre).getByRole("link", { name: "Athlètes par saison" })).toHaveAttribute(
      "href",
      "/club/athletes",
    );
  });

  it("marque la destination courante avec aria-current=\"page\"", () => {
    afficher(null);

    const barre = screen.getByRole("navigation", { name: "Navigation" });
    expect(within(barre).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("aria-current", "page");
    expect(within(barre).getByRole("link", { name: "Résultats" })).not.toHaveAttribute("aria-current");
  });

  it("ne porte aucune destination privée, connecté ou non", async () => {
    afficher(habilite("pending_providers:read"));
    await waitFor(() => expect(screen.getByText("Administration")).toBeInTheDocument());

    const barre = screen.getByRole("navigation", { name: "Navigation" });
    expect(within(barre).queryByRole("link", { name: "Fournisseurs en attente" })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Écrire le test qui échoue — `app/layout.test.tsx`**

```tsx
describe("RootLayout — espace réservé sous le contenu mobile (#482, NAV-4)", () => {
  it("réserve la hauteur de la barre basse mobile sous <main>, seulement sous md", async () => {
    render(await RootLayout({ children: <p>contenu de la page</p> }));

    const conteneur = document.querySelector("main")?.parentElement;
    expect(conteneur?.className).toContain("pb-[var(--tcn-nav-bottom)]");
    expect(conteneur?.className).toContain("md:pb-0");
  });
});
```

- [ ] **Step 3: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx app/layout.test.tsx -t "barre basse|espace réservé"`
Expected: FAIL — aucune navigation nommée « Navigation » n'existe, `<main>` n'a pas de padding réservé.

- [ ] **Step 4: Ajouter le token dans `globals.css`**

Après la ligne 219 (`--tcn-nav-panel: 288px;`) :

```css
  --tcn-nav-bottom: 64px;  /* barre basse mobile — 3 destinations publiques */
```

- [ ] **Step 5: Calculer `publicItems` dans `AppNav`**

Juste après le calcul de `sections` (après la ligne qui filtre les sections vides, ~125) :

```tsx
  // Barre basse mobile (#482, NAV-4) : jamais codé en dur — dérivé des
  // sections dont `minRole` vaut `ROLE.ANON`, pour rester aligné avec
  // `nav.config.ts` au fil des livraisons futures (ex. « Carte », #10/#28).
  const publicItems = sections.filter((s) => s.minRole === ROLE.ANON).flatMap((s) => s.items);
```

- [ ] **Step 6: Rendre la barre, après le `<header>` mobile (après la ligne qui ferme `</header>`, ~276)**

```tsx
      {/* ── Barre basse mobile — 3 destinations publiques (#482, NAV-4) ── */}
      <nav
        aria-label="Navigation"
        className="fixed inset-x-0 bottom-0 z-30 flex md:hidden"
        style={{
          height: "var(--tcn-nav-bottom)",
          background: "var(--tcn-surface)",
          borderTop: "1px solid var(--tcn-border-strong)",
        }}
      >
        {publicItems.map((it) => {
          const Icon = it.icon;
          const actif = isActive(it.href);
          return (
            <Link
              key={it.id}
              href={it.href}
              aria-current={actif ? "page" : undefined}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
                textDecoration: "none",
                fontFamily: "var(--tcn-font-cond)",
                fontWeight: 700,
                fontSize: 11,
                color: actif ? "var(--tcn-orange)" : "var(--tcn-text-muted)",
              }}
            >
              {Icon && <Icon size={20} />}
              <span>{it.label}</span>
            </Link>
          );
        })}
      </nav>
```

- [ ] **Step 7: Corriger trois assertions préexistantes désormais ambiguës**

La barre basse porte les **mêmes libellés accessibles** que les entrées du rail (« Tableau de bord », « Résultats », « Athlètes par saison ») — trois tests écrits avant ce plan interrogeaient ces libellés sans les scoper au rail, faute d'un second élément du même nom à distinguer jusqu'ici. Sans ce correctif, `screen.getByRole(...)`/`screen.getByText(...)` échoueraient désormais avec « multiple elements found ». (Task 2 et Task 3 ont déjà scopé leurs propres tests dès leur écriture — seuls ceux-ci, plus anciens, restent à corriger.)

Test « ne rend que les écrans livrés (#242) » :

```tsx
  it("ne rend que les écrans livrés (#242)", async () => {
    afficher(null);
    await deplier();

    // Scopé au rail : la barre basse mobile (#482, NAV-4) porte les mêmes
    // libellés pour les mêmes destinations.
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("href", "/dashboard");
    expect(within(rail).getByRole("link", { name: "Résultats" })).toHaveAttribute("href", "/resultats");

    // Une entrée `soon` reste déclarée dans `nav.config.ts` — feuille de route
    // de la navigation — mais n'est plus rendue nulle part.
    expect(screen.queryByText("Carte")).not.toBeInTheDocument();
    expect(screen.queryByText("À VENIR")).not.toBeInTheDocument();
  });
```

Test « marque l'entrée courante avec aria-current="page" » :

```tsx
  it("marque l'entrée courante avec aria-current=\"page\"", async () => {
    afficher(null);
    await deplier();

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("aria-current", "page");
    expect(within(rail).getByRole("link", { name: "Résultats" })).not.toHaveAttribute("aria-current");
  });
```

Test « n'annonce pas les fournisseurs à un connecté sans le pouvoir (#239) » :

```tsx
  it("n'annonce pas les fournisseurs à un connecté sans le pouvoir (#239)", async () => {
    afficher(SESSION);
    await deplier();

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    await waitFor(() => expect(within(rail).getByText("Résultats")).toBeInTheDocument());
    expect(
      screen.queryByRole("link", { name: "Fournisseurs en attente" }),
    ).not.toBeInTheDocument();
  });
```

- [ ] **Step 8: Réserver l'espace dans `app/layout.tsx`**

Ligne 73 (état après Task 2), ajouter les classes Tailwind au conteneur du contenu :

```tsx
            <div className="flex min-w-0 flex-1 flex-col pb-[var(--tcn-nav-bottom)] md:pb-0">
```

- [ ] **Step 9: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx app/layout.test.tsx`
Expected: PASS, les deux fichiers entiers — en particulier les trois tests corrigés à l'étape 7, qui échoueraient sinon sur « multiple elements found ».

- [ ] **Step 10: Commit**

```bash
git add frontend/app/globals.css frontend/components/layout/AppNav.tsx frontend/app/layout.tsx frontend/components/layout/AppNav.test.tsx frontend/app/layout.test.tsx
git commit -m "feat(482): add a fixed mobile bottom bar for the three public destinations (NAV-4)"
```

---

### Task 7: le tiroir mobile réduit à l'administration et au compte (NAV-4)

**Files:**
- Modify: `frontend/components/layout/AppNav.tsx:106-153,297`
- Modify: `frontend/components/layout/AppNav.test.tsx` (nouveau describe)

**Interfaces:**
- Consumes: `sections`, `ROLE.ANON`.
- Produces: `sectionsPrivees` — variable locale, `contenu(deplie, fermer, listeSections?)` — signature étendue avec un troisième paramètre optionnel.

- [ ] **Step 1: Écrire les tests qui échouent**

```tsx
describe("AppNav — tiroir mobile réduit à l'administration et au compte (#482, NAV-4)", () => {
  it("ne porte plus les sections publiques dans le tiroir, désormais dans la barre basse", async () => {
    afficher(null);
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));

    const tiroir = await screen.findByRole("dialog");
    expect(within(tiroir).queryByRole("link", { name: "Tableau de bord" })).not.toBeInTheDocument();
    expect(within(tiroir).queryByText("Club")).not.toBeInTheDocument();
  });

  it("garde les sections privées dans le tiroir pour un connecté habilité", async () => {
    afficher(habilite("pending_providers:read"));
    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir le menu" }));

    const tiroir = await screen.findByRole("dialog");
    expect(within(tiroir).getByText("Administration")).toBeInTheDocument();
    expect(within(tiroir).getByRole("link", { name: "Fournisseurs en attente" })).toHaveAttribute(
      "href",
      "/admin/fournisseurs",
    );
  });

  it("garde les deux actions primaires en tête du tiroir même réduit", async () => {
    afficher(null);
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));

    const tiroir = await screen.findByRole("dialog");
    expect(within(tiroir).getByRole("link", { name: "Ajouter une épreuve" })).toBeInTheDocument();
    expect(within(tiroir).getByRole("button", { name: "Rechercher un athlète" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx -t "tiroir mobile réduit"`
Expected: FAIL — le tiroir porte encore « Tableau de bord » et « Club ».

- [ ] **Step 3: Implémenter**

Calculer `sectionsPrivees`, juste après `publicItems` (Task 6) :

```tsx
  // Le tiroir mobile ne garde plus que ce qui exige une session — les
  // sections publiques vivent désormais dans la barre basse (#482, NAV-4).
  const sectionsPrivees = sections.filter((s) => s.minRole > ROLE.ANON);
```

Étendre `contenu` (remplace le bloc actuel) :

```tsx
  const contenu = (deplie: boolean, fermer?: () => void, listeSections: SectionRendue[] = sections) => (
    <NavContent
      expanded={deplie}
      sections={listeSections}
      isActive={isActive}
      athlete={athlete}
      kbd={kbd}
      onNavigate={fermer}
      onOpenPicker={() => {
        fermer?.();
        setPickerOpen(true);
      }}
      onExpand={() => setExpanded(true)}
    />
  );
```

Et l'appel dans le tiroir (ligne 297, `{contenu(true, () => setDrawerOpen(false))}`) :

```tsx
          {contenu(true, () => setDrawerOpen(false), sectionsPrivees)}
```

(L'appel du rail, `{contenu(expanded)}`, garde son comportement — le troisième paramètre par défaut vaut `sections`, la liste complète.)

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx`
Expected: PASS, fichier entier — en particulier les tests existants qui déplient le **rail** (`deplier()`) doivent rester inchangés, seul le tiroir est concerné.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/AppNav.tsx frontend/components/layout/AppNav.test.tsx
git commit -m "fix(482): scope the mobile drawer to admin sections and the account, drop the public tree (NAV-4)"
```

---

### Task 8: fermeture du tiroir restreinte à la navigation réelle (NAV-4)

**Files:**
- Modify: `frontend/components/auth/UserMenu.tsx:1-59`
- Modify: `frontend/components/auth/UserMenu.test.tsx:36,58-176`
- Modify: `frontend/components/layout/AppNav.tsx:301-306`
- Modify: `frontend/components/layout/AppNav.test.tsx` (nouveau describe)
- Modify: `frontend/AGENTS.md` (paragraphe de synthèse #482)

**Interfaces:**
- Consumes: `useLogout`, `useRouter` (déjà importés dans `UserMenu.tsx`).
- Produces: `UserMenu({ pleineLargeur?, onNavigate? })` — nouvelle prop optionnelle, consommée par `AppNav.tsx`.

- [ ] **Step 1: Écrire les tests qui échouent — `UserMenu.test.tsx`**

Élargir le harnais (ligne 36) :

```tsx
function afficher(session: SessionUser | null, props: { pleineLargeur?: boolean; onNavigate?: () => void } = {}) {
```

Ajouter un nouveau describe, en fin de fichier :

```tsx
describe("UserMenu — onNavigate ferme le tiroir au bon moment (#482, NAV-4)", () => {
  it("appelle onNavigate juste avant de router vers /login", async () => {
    const onNavigate = vi.fn();
    afficher(null, { onNavigate });

    await userEvent.click(await screen.findByRole("button", { name: "Se connecter" }));

    expect(onNavigate).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/login");
  });

  it("n'appelle pas onNavigate au clic de « Se déconnecter », seulement après le succès de la mutation", async () => {
    const onNavigate = vi.fn();
    afficher(SESSION, { pleineLargeur: true, onNavigate });
    let resoudre!: () => void;
    logout.mockReturnValue(new Promise<void>((resolve) => { resoudre = resolve; }));

    await userEvent.click(await screen.findByRole("button", { name: "Se déconnecter" }));

    // La mutation est en vol : `onNavigate` ne doit pas encore avoir été
    // appelé, sans quoi le tiroir se fermerait avant que l'état d'attente du
    // bouton n'ait eu le temps de s'afficher (#482, NAV-4).
    expect(onNavigate).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Se déconnecter" })).toBeDisabled();

    resoudre();
    await waitFor(() => expect(onNavigate).toHaveBeenCalled());
    expect(push).toHaveBeenCalledWith("/");
  });

  it("ne casse rien quand onNavigate est omis (usage historique du rail desktop)", async () => {
    afficher(SESSION);
    await ouvrirLeMenu();

    await userEvent.click(screen.getByRole("menuitem", { name: "Se déconnecter" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });
});
```

- [ ] **Step 2: Écrire le test qui échoue — `AppNav.test.tsx`**

```tsx
describe("AppNav — le tiroir ne se ferme plus au clic du pied (#482, NAV-4)", () => {
  it("reste ouvert juste après un clic sur « Se déconnecter », le temps de la mutation", async () => {
    afficher(SESSION);
    await waitFor(() => expect(screen.getByRole("button", { name: `Compte — ${SESSION.email}` })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
    const tiroir = await screen.findByRole("dialog");
    let resoudre!: () => void;
    logout.mockReturnValue(new Promise<void>((resolve) => { resoudre = resolve; }));

    await userEvent.click(within(tiroir).getByRole("button", { name: "Se déconnecter" }));

    // Toujours dans le DOM juste après le clic : la fermeture n'est plus
    // câblée sur l'événement de clic du pied (#482, NAV-4).
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    resoudre();
  });

  it("ne ferme pas le tiroir au clic sur un élément neutre du pied (l'adresse, hors bouton)", async () => {
    afficher(SESSION);
    await waitFor(() => expect(screen.getByRole("button", { name: `Compte — ${SESSION.email}` })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
    const tiroir = await screen.findByRole("dialog");

    await userEvent.click(within(tiroir).getByText(SESSION.email));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/auth/UserMenu.test.tsx components/layout/AppNav.test.tsx -t "onNavigate|tiroir ne se ferme plus"`
Expected: FAIL — `UserMenu` ne connaît pas de prop `onNavigate`, et le tiroir se ferme encore au premier clic sur son pied.

- [ ] **Step 4: Implémenter — `UserMenu.tsx`**

```tsx
/**
 * Bouton « Se connecter » si anonyme, menu utilisateur sinon.
 *
 * Posé **deux fois** par `AppNav` — pied du rail et pied du tiroir mobile.
 * Les deux formes ne coexistent jamais à l'écran : le rail est `hidden md:flex`,
 * le tiroir `md:hidden`.
 *
 * `onNavigate` s'appelle au moment où une navigation **a réellement lieu**
 * (#482, NAV-4) : juste avant `router.push("/login")`, ou dans le `onSuccess`
 * de la déconnexion — jamais au clic de « Se déconnecter » lui-même, qui
 * couperait l'affichage de son état d'attente (`logout.isPending`) avant que
 * la requête n'ait eu le temps de partir. Un prop fonction ne pose ici aucun
 * problème de sérialisation Next : `UserMenu` n'est aujourd'hui rendu que par
 * `AppNav`, lui-même `"use client"` — aucune frontière serveur/client n'est
 * traversée à l'un ou l'autre de ses deux points d'appel. Un futur appelant
 * serveur rouvrirait la question.
 */
export function UserMenu({
  pleineLargeur = false,
  onNavigate,
}: {
  pleineLargeur?: boolean;
  onNavigate?: () => void;
}) {
  const { data: session, isPending } = useSession();
  const logout = useLogout();
  const router = useRouter();

  if (isPending) return null;

  if (!session) {
    return (
      <Button
        variant="secondary"
        onClick={() => {
          onNavigate?.();
          router.push("/login");
        }}
        style={{ width: pleineLargeur ? "100%" : undefined }}
      >
        Se connecter
      </Button>
    );
  }

  const nom = session.display_name || session.email;
  const seDeconnecter = () => {
    captureEvent("user_logged_out");
    // posthog.reset() n'est pas appelé ici : PostHogSessionSync (providers.tsx)
    // le déclenche dès que session repasse à null, quelle qu'en soit la cause.
    logout.mutate(undefined, {
      onSuccess: () => {
        router.push("/");
        onNavigate?.();
      },
    });
  };
```

(Le reste du fichier, à partir du bloc `pleineLargeur` de rendu, ne change pas.)

- [ ] **Step 5: Implémenter — `AppNav.tsx`**

Remplacer le pied du tiroir (lignes 301-306) :

```tsx
          <div style={{ flex: "none", padding: 14, borderTop: "1px solid var(--tcn-border-faint)" }}>
            <UserMenu pleineLargeur onNavigate={() => setDrawerOpen(false)} />
          </div>
```

- [ ] **Step 6: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/auth/UserMenu.test.tsx components/layout/AppNav.test.tsx`
Expected: PASS, les deux fichiers entiers.

Run: `cd frontend && npm test`
Expected: PASS, suite complète — dernière vérification avant de clore la branche.

Run: `cd frontend && npm run lint`
Expected: aucune erreur.

- [ ] **Step 7: Documenter la synthèse #482 dans `frontend/AGENTS.md`**

Ajouter, à la fin de la puce **Navigation** existante (après le paragraphe sur `pushState`/`router.push`, avant la puce `components/`) :

```
  **Rail replié, cookie de largeur, nav mobile** (#482) — le rail replié
  porte désormais un monogramme texte lié à `/dashboard` en plus du bouton de
  pliage (l'en-tête passe en colonne à cet état, faute de place pour les
  deux côte à côte), et ses six `title` sont remplacés par
  `components/ui/tooltip.tsx` (`@base-ui/react/tooltip`, délai ramené à
  0 ms — l'audit reprochait le délai natif d'~1 s, pas seulement son absence
  au clavier/tactile). Une section réduite à une seule destination livrée
  (« Club » aujourd'hui) rend directement son `Entree` au lieu du bouton
  dépliant. La largeur du rail (`tcn-nav-expanded`) est désormais un
  **cookie**, lu par `app/layout.tsx` avant la peinture plutôt qu'un
  `localStorage` relu au montage — la seule exception documentée au refus de
  miroir cookie de #467, parce que le besoin serveur y est authentique et
  qu'aucun `fetch()` vers `/api/v1` n'est concerné. Sous `md`, une barre
  basse fixe porte les destinations dont `minRole === ROLE.ANON` (calculée
  dynamiquement, jamais en dur) ; le hamburger ne garde que les sections
  `minRole > ROLE.ANON` et les deux actions primaires. Le pied du tiroir ne
  ferme plus au clic : `UserMenu` ferme lui-même via `onNavigate`, au moment
  où la navigation a réellement lieu (immédiat pour la connexion, après le
  succès de la mutation pour la déconnexion) — jamais au clic de « Se
  déconnecter » seul, qui couperait l'affichage de son état d'attente.
```

- [ ] **Step 8: Commit**

```bash
git add frontend/components/auth/UserMenu.tsx frontend/components/auth/UserMenu.test.tsx frontend/components/layout/AppNav.tsx frontend/components/layout/AppNav.test.tsx frontend/AGENTS.md
git commit -m "fix(482): only close the mobile drawer footer when navigation actually happens (NAV-4)"
```

---

## Fin de branche

Une fois les huit tâches vertes, suivre la fin de branche commune aux trois voies (`AGENTS.md` racine) : `requesting-code-review` → `verification-before-completion` → `ui-ux-review` (la branche touche `frontend/`) → `finishing-a-development-branch`. La PR ferme #482 (`Closes #482`).
