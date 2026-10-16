# Navigation : correctifs de la revue UI/UX de l'epic (#1295) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger les constats de la revue `ui-ux-review` qui a porté sur toute la pile #1306 à #1316 : débordements du sélecteur d'espace, navigation vidée sur un refus, libellés ambigus, compteurs et copie.

**Architecture:** Une PR empilée sur #1316 plutôt qu'une réécriture des quatre branches. Chaque correctif est petit et localisé dans `AppNav.tsx`, `SpaceSwitcher.tsx`, `nav.config.ts`, `MaSaison.tsx` et la page `/dashboard`.

**Tech Stack:** Next.js 16, TypeScript strict, Tailwind 4, Base UI, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-10-navigation-espaces-design.md`. La revue UI/UX (rapport du 2026-10-11, consigné dans le ledger) prime sur la spec pour le rendu.

## Global Constraints

- Pas de commande hors écran à 360 px ni à 375 px. Pas de débordement du rail déplié (288 px).
- Langue : UI et commentaires métier en français, identifiants et noms de tests neufs en anglais. Les fichiers existants gardent leur style.
- Jamais de tiret (—, –, -) pour ponctuer une phrase. Commentaires seulement si nécessaires.
- Avant chaque commit : `git checkout frontend/.vitest/json/output.json`.
- Commits : Conventional Commits, `(Refs #1295)`, aucun `Co-Authored-By`.

## Rulings du plan

- **Constat 4.** L'espace public s'appelle « Consulter », le libellé de sa section racine. « Résultats » nommait aussi une entrée de l'espace, qui menait ailleurs. Si c'est faux, c'est une chaîne à changer.
- **Constat 2.** Dans le rail déplié, le sélecteur passe sur sa propre ligne sous le logo, et non en `compact`. Le rail déplié a la place de nommer l'espace.
- **Constat 9.** La copie ajoutée par la branche réserve « espace » aux trois espaces, et « Voir l'espace club » devient « Voir la page Club ». Le titre existant « Espace club » de `/club` n'est pas renommé : il est antérieur à l'epic, et le renommer sort du périmètre.
- **Constat 10** (saut de l'en-tête du rail replié) : à vérifier au rendu en préprod, rien dans ce plan.
- **Constat 11** (anciennes URL `/admin/jeunes`, `/admin/benevolat`) : pas de redirection, conformément à la spec et au principe « pas de compatibilité ascendante ».

---

### Task 1: Navigation, débordements, refus, libellés et compteur

**Files:**
- Modify: `frontend/components/layout/AppNav.tsx`
- Modify: `frontend/components/layout/SpaceSwitcher.tsx` (+ test)
- Modify: `frontend/components/layout/nav.config.ts` (`SPACES.public.label`)
- Test: `frontend/components/layout/AppNav.test.tsx`, `frontend/components/layout/SpaceSwitcher.test.tsx`, `frontend/components/layout/nav.config.test.ts`
- Modify: `frontend/AGENTS.md`, s'il cite le libellé « Résultats » de l'espace

**Interfaces:**
- Consumes: `SpaceSwitcher({ spaces, current, compact })` ; `SPACES`, `spaceOf` ; `sections`, `sectionsRepli`, `espacesOuverts`, `countAdmin` dans `AppNav`.
- Produces: `SPACES.public.label === "Consulter"`.

- [ ] **Step 1: Write the failing tests**

Dans `AppNav.test.tsx`, avec les helpers du fichier (`afficher`, `habilite`, `chemin.courant`, `rail()`, `barre()`) :

```tsx
describe("AppNav: UI/UX review of the spaces (#1295)", () => {
  it("the mobile header uses the compact switcher", async () => {
    // compte à deux espaces (courses:write + jeunes:read), chemin "/dashboard"
    // le déclencheur de l'en-tête mobile n'affiche pas le libellé de l'espace en texte visible
    // (le nom accessible reste « Espace : Consulter, changer d'espace »)
  });

  it("the expanded rail puts the switcher on its own row under the logo", async () => {
    // rail déplié : le déclencheur n'est pas dans le même conteneur flex que le logo
    // (asserter sur la structure réelle choisie, par exemple un data-attribute de ligne)
  });

  it("a refused private space falls back to the public navigation", async () => {
    // session sans pouvoir d'encadrement, chemin "/encadrement/jeunes" :
    // le rail porte les entrées publiques (/dashboard, /resultats) et le tiroir n'est pas vide
  });

  it("the Encadrement switcher entry carries its pending count", async () => {
    // jeunes:read + athletes:volunteer_validate + pages:preview, compteur bénévolat mocké à 4
    // ouvrir le sélecteur : l'entrée Encadrement annonce « 4 »
    // (libellé lu via libelleCompteur, avec le badge du compteur sommé)
  });
});
```

Écrire ces tests complètement. Les commentaires fixent les entrées et les attentes. Mettre à jour les attentes « Résultats » du sélecteur (nom accessible, entrée de menu) en « Consulter ».

Dans `SpaceSwitcher.test.tsx` : le déclencheur compact n'utilise plus `LayoutGrid`. Asserter sur l'icône choisie (attribut `data-icon` ou classe lucide) ou, à défaut, l'absence de la classe `lucide-layout-grid`.

- [ ] **Step 2: Run tests to verify they fail**

Run (depuis `frontend/`) : `npx vitest run components/layout`
Expected: FAIL.

- [ ] **Step 3: Implement**

1. **Constat 1, en-tête mobile** (`AppNav.tsx` ~l.456) : passer `compact` au `SpaceSwitcher`.
2. **Constat 2, rail déplié** (~l.322) : sortir le sélecteur de la ligne du logo et le poser sur sa propre ligne, juste dessous, pleine largeur avec le padding de l'en-tête. Vérifier qu'il ne déborde plus de 288 px. Le libellé le plus long est « Encadrement ».
3. **Constat 3, refus** (~l.157) : quand `sections` est vide pour l'espace courant, le rail et le tiroir retombent sur les sections publiques. Exemple :

   ```tsx
   const sectionsEspace = toutesSections.filter((s) => s.space === espace);
   // Un espace refusé n'a aucune section visible : la navigation retombe sur
   // l'espace public plutôt que de laisser l'écran de refus sans issue.
   const sections = sectionsEspace.length > 0 ? sectionsEspace : toutesSections.filter((s) => s.space === "public");
   ```

   Vérifier ensuite la barre basse : en repli, elle doit porter les onglets publics. `barreItems` dérive de `sections`, mais l'onglet « Sommaire » dépend de `espace === "admin"`. Ne l'ajouter que si l'espace admin n'est pas en repli. Utiliser une variable `espaceAffiche` (l'espace effectivement rendu) partout où `espace` décide du rendu : `barreItems`, `versAdmin`.
4. **Constat 4** : `SPACES.public.label = "Consulter"`.
5. **Constat 6** (`SpaceSwitcher.tsx:38`) : remplacer `LayoutGrid` par `ArrowLeftRight` (vérifier l'export de lucide-react).
6. **Constat 8** (`AppNav.tsx` ~l.190) : l'entrée Encadrement du sélecteur porte la somme des compteurs de ses entrées visibles. Calcul : somme des `count` des items de `toutesSections` de l'espace `encadrement`. Badge `"backoffice"` pour le libellé « N éléments à traiter », ou un nouveau cas `libelleCompteur` s'il faut un libellé distinct. Garder « éléments à traiter », qui convient aux deux.

Mettre à jour `frontend/AGENTS.md` si un paragraphe cite l'espace « Résultats ».

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run components/layout`, puis `npx tsc --noEmit` et `npm run lint`.
Expected: vert.

- [ ] **Step 5: Commit**

```bash
git checkout frontend/.vitest/json/output.json
git add frontend
git commit -m "fix(nav): fit the space switcher on mobile and in the rail, keep a way out on refusal (Refs #1295)"
```

---

### Task 2: Accueil, copie du renvoi vers Club et sélecteur de rang

**Files:**
- Modify: `frontend/app/(public_restricted)/dashboard/page.tsx` (+ `page.test.tsx`)
- Modify: `frontend/components/dashboard/MaSaison.tsx` (+ `MaSaison.test.tsx`)

**Interfaces:**
- Consumes: `currentSeason()`, `selected` (sélection de saisons de la page), `isCurrentSeasonSelected` (déjà calculé dans `page.tsx`).
- Produces: rien.

- [ ] **Step 1: Write the failing tests**

`page.test.tsx` :

```tsx
it("names the Club link as a page, not a space", async () => {
  // rendu nominal
  expect(screen.getByRole("link", { name: /Voir la page Club/ })).toHaveAttribute("href", "/club");
});

it("says the Club figures are for the current season when another season is selected", async () => {
  // searchParams { seasons: <une saison passée, au format de parseSeasonsParam> }
  expect(screen.getByText(/saison en cours/)).toBeInTheDocument();
});

it("does not mention the season scope when the current season is selected", async () => {
  // rendu nominal (saison en cours)
  expect(screen.queryByText(/saison en cours/)).toBeNull();
});
```

Adapter les tests existants qui cherchaient `/espace club/i`.

`MaSaison.test.tsx` : le sélecteur « Type de rang » est rendu dans l'état nominal (au moins une épreuve). Il est absent dans les états perdu, échec et aucune épreuve. Réutiliser les mocks d'état du fichier.

- [ ] **Step 2: Run tests to verify they fail**

Run : `npx vitest run "app/(public_restricted)/dashboard" components/dashboard/MaSaison.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

`page.tsx`, carte « Le club » :
- le lien devient « Voir la page Club <span aria-hidden>→</span> » ;
- la phrase devient « Podiums, compteurs, disciplines et athlètes du club. ». Quand `!isCurrentSeasonSelected`, ajouter « Sur la saison en cours. » pour nommer la portée de `/club`.

`MaSaison.tsx` : ne rendre « Type de rang » et `RankTypeToggle` que dans l'état nominal (`ok` et au moins une épreuve).

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run` (suite complète), `npx tsc --noEmit`, `npm run lint`, `npm run build`.
Expected: tout vert. `CourseAdminActions.test.tsx` échoue parfois sous charge et passe seul. C'est un défaut antérieur, hors périmètre.

- [ ] **Step 5: Commit**

```bash
git checkout frontend/.vitest/json/output.json
git add frontend
git commit -m "fix(dashboard): name the Club page and its season, show the rank toggle only when it acts (Refs #1295)"
```
