# Tableaux repliés en cartes sur mobile — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sous le seuil où chacun cesse de tenir, les quatre tableaux à largeur plancher de l'app se rendent en cartes empilées, et les deux matrices du détail de participation réduisent leurs colonnes — pour qu'un téléphone n'ait plus jamais à défiler à l'horizontale.

**Architecture:** Chaque écran rend **deux arbres** — la grille existante et une liste de cartes — que deux classes Tailwind (`hidden lg:block` / `lg:hidden`) font alterner en CSS pure : aucun `matchMedia`, aucun état client, aucun saut d'hydratation. Un composant partagé sans état, `LigneCarte`, porte le dessin de la carte ; chaque écran y verse son contenu. Les deux matrices, elles, sont de vrais `<table>` exemptés de WCAG 1.4.10 et reçoivent une simple réduction de colonnes.

**Tech Stack:** Next.js 16 (App Router), TypeScript strict, Tailwind v4 (seuils par défaut : `sm` 640 px, `md` 768 px, `lg` 1024 px), Vitest + Testing Library (`@testing-library/dom` 10.4.1), shadcn/ui (`components/ui/select`).

**Spec:** `docs/superpowers/specs/2026-08-25-tableaux-mobiles-design.md`

## Global Constraints

- **Langue** (Principe I de la constitution) : **français** pour tout ce que l'utilisateur lit et pour les commentaires de règle métier ; **English** pour les identifiants, les tests, les docstrings techniques et les préfixes Conventional Commits. Les nouveaux identifiants de ce plan sont en français (`LigneCarte`, `depliant`, `marqueur`) parce qu'ils prolongent un voisinage déjà français (`AnnonceStatut`, `EnteteTriable`, `CelluleInter`) — ne pas les angliciser.
- **Vocabulaire public** (#478) : l'objet importé se dit **« épreuve »**, jamais « course ». Registre : **vouvoiement** sur tout écran public.
- **TDD non négociable** (Principe III) : chaque tâche écrit son test avant son code, et le voit échouer.
- **Ne pas préserver la compatibilité ascendante** : pas de prop de repli, pas d'ancien chemin conservé « au cas où ».
- **Identité visuelle figée** : tokens `--tcn-*` uniquement, aucune couleur en dur, aucune famille typographique nouvelle.
- **Plancher tactile 44 px** (WCAG 2.2 2.5.8) sur toute zone cliquable créée par ce plan.
- **Commandes** : depuis `frontend/` — `npm test` (vitest run), `npm run lint`, `npm run build`. Un test seul : `npx vitest run <chemin> -t "<nom>"`.
- **Commits** : Conventional Commits, titre en anglais, `Refs #461` en pied.

---

### Task 1: La configuration de test qui neutralise l'arbre carte

**Pourquoi en premier :** jsdom ne charge aucune feuille de style, donc dès la première tâche qui ajoute un arbre carte, les deux arbres coexistent et tout `getByText` singulier lève « found multiple elements » — 159 requêtes singulières existent dans les quatre fichiers concernés. Cette tâche pose la parade avant qu'elle soit nécessaire ; appliquée seule, son sélecteur ne matche rien et ne change rien.

**Files:**
- Modify: `frontend/test/setup.ts`
- Create: `frontend/test/cartes.ts`
- Create: `frontend/test/affichage-cartes.test.tsx`

**Interfaces:**
- Consumes: rien.
- Produces:
  - la convention d'attribut `data-affichage="cartes"` (arbre carte) et `data-affichage="grille"` (arbre grille), sur laquelle reposent toutes les tâches suivantes ;
  - `dansLesCartes(testId: string)` (`test/cartes.ts`) — rend le résultat de `within(screen.getByTestId(testId))` augmenté d'une méthode `texte(matcher)`, seule façon de lire du texte dans l'arbre carte.

**Deux faits vérifiés à l'exécution, sur lesquels toute la tâche repose :**

1. `defaultIgnore` est appliqué par `node.matches(ignore)` (`@testing-library/dom@10.4.1`, `dist/queries/text.js:31`), donc il n'écarte que les nœuds qui matchent **eux-mêmes**. `'script, style'` marche parce que le texte y est porté *par* la balise ; le texte d'une carte est porté par un **descendant** du conteneur marqué. Le sélecteur doit donc porter `[data-affichage="cartes"] *` — sans lui, la parade ne filtre rien.
2. `within` **ne lève pas** l'exclusion : la configuration étant globale, `within(cartes()).getByText(…)` ne trouve rien. Un test qui vise les cartes doit passer `{ ignore: false }`, ce que `dansLesCartes().texte()` fait une fois pour toutes. L'oubli ne se lit pas dans le message d'erreur — la requête dit « unable to find an element », comme si la carte n'existait pas.

- [ ] **Step 1: Write the failing test**

Créer `frontend/test/affichage-cartes.test.tsx` :

```tsx
// frontend/test/affichage-cartes.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";

/**
 * Verrou de la configuration posée dans `test/setup.ts`.
 *
 * Les écrans à tableau rendent deux arbres — la grille et les cartes — dont un
 * seul est affiché, par CSS. jsdom ne charge aucune feuille de style : sans
 * cette configuration, chaque valeur existerait en double pour Testing Library
 * et toute requête texte singulière lèverait « found multiple elements ». La
 * règle est globale, donc invisible à la lecture d'un fichier de test : ce test
 * est ce qui la rend visible le jour où elle disparaît.
 */
describe("data-affichage=cartes", () => {
  // Le texte d'une carte est porté par un DESCENDANT du conteneur marqué, et
  // `defaultIgnore` filtre par `node.matches()` : c'est le `*` du sélecteur,
  // et lui seul, qui fait tenir cette assertion.
  it("sort les descendants de l'arbre carte des requêtes texte", () => {
    render(
      <>
        <div data-affichage="grille">
          <span>Jean DUPONT</span>
        </div>
        <div data-affichage="cartes">
          <article>
            <span>Jean DUPONT</span>
          </article>
        </div>
      </>,
    );

    expect(screen.getByText("Jean DUPONT")).toBeInTheDocument();
  });

  it("laisse `dansLesCartes` lire l'arbre carte", () => {
    render(
      <div data-testid="cartes" data-affichage="cartes">
        <span>Jean DUPONT</span>
      </div>,
    );

    expect(dansLesCartes("cartes").texte("Jean DUPONT")).toBeInTheDocument();
  });

  // Le piège que `dansLesCartes` existe pour désamorcer : `within` n'annule pas
  // une exclusion globale, et l'échec ne dit pas pourquoi.
  it("ne laisse pas `within` seul y entrer", () => {
    render(
      <div data-testid="cartes" data-affichage="cartes">
        <span>Jean DUPONT</span>
      </div>,
    );

    expect(within(screen.getByTestId("cartes")).queryByText("Jean DUPONT")).toBeNull();
  });
});
```

Importer `dansLesCartes` depuis `./cartes` en tête du fichier.

- [ ] **Step 2: Run test to verify it fails**

Run : `npx vitest run test/affichage-cartes.test.tsx`
Expected : FAIL — « Failed to resolve import "./cartes" ». Une fois le module créé mais `setup.ts` non modifié, le premier test échoue avec « Found multiple elements with the text: Jean DUPONT » et le troisième trouve l'élément au lieu de `null`.

- [ ] **Step 3: Write minimal implementation**

**3a.** Ajouter à la fin de `frontend/test/setup.ts` :

```ts
import { configure } from "@testing-library/react";

// Les écrans à tableau rendent deux arbres — la grille et les cartes — dont la
// CSS n'en affiche qu'un (#461). jsdom ne charge aucune feuille de style, donc
// les deux sont là pour Testing Library, et chaque nom, chaque temps, chaque
// badge existerait en double : tout `getByText` singulier lèverait « found
// multiple elements ». `defaultIgnore` s'applique aux requêtes **texte** et
// retire l'arbre carte de leur portée — les 159 requêtes singulières des quatre
// fichiers de test concernés passent donc sans être touchées.
//
// `[data-affichage="cartes"] *` n'est pas décoratif : `defaultIgnore` est
// appliqué par `node.matches(ignore)` (@testing-library/dom, queries/text.js),
// donc il n'écarte que les nœuds qui matchent EUX-MÊMES. `script, style`
// fonctionne parce que le texte y est porté par la balise ; le texte d'une
// carte, lui, est porté par un descendant du conteneur marqué. Sans le `*`,
// cette configuration ne filtre rien.
//
// Deux conséquences à connaître :
// - `getByRole` n'utilise pas `ignore` : une requête de rôle visant l'intérieur
//   d'une ligne doit être scopée à la main, avec `within`.
// - `within` ne lève PAS l'exclusion, qui est globale : l'arbre carte est
//   invisible aux requêtes texte, y compris à celles qui le visent. Un test qui
//   porte sur les cartes passe par `dansLesCartes` (`test/cartes.ts`), qui porte
//   le `{ ignore: false }`.
//
// `test/affichage-cartes.test.tsx` verrouille cette configuration.
configure({
  defaultIgnore: 'script, style, [data-affichage="cartes"], [data-affichage="cartes"] *',
});
```

**3b.** Créer `frontend/test/cartes.ts` :

```ts
import { screen, within } from "@testing-library/react";
import type { Matcher } from "@testing-library/react";

/**
 * Requêtes portant sur l'**arbre carte** d'un écran (#461).
 *
 * `test/setup.ts` retire cet arbre des requêtes texte — sans quoi chaque valeur
 * y existerait en double, jsdom ne chargeant aucune feuille de style pour n'en
 * afficher qu'un. L'exclusion étant globale, `within` ne la lève pas : un test
 * qui veut justement lire les cartes doit passer `{ ignore: false }`, et
 * l'oubli ne se lit pas — la requête rend « unable to find an element », comme
 * si la carte n'existait pas. D'où cette porte d'entrée unique.
 *
 * Les requêtes de rôle et de testid ne sont pas concernées (`ignore` ne
 * s'applique qu'au texte) : elles sont rendues telles quelles.
 */
export function dansLesCartes(testId: string) {
  const scope = within(screen.getByTestId(testId));
  return {
    ...scope,
    /** `getByText` qui voit l'arbre carte. */
    texte: (matcher: Matcher) => scope.getByText(matcher, { ignore: false }),
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run test/affichage-cartes.test.tsx`
Expected : 3 PASS.

Puis la suite entière, pour prouver que la configuration ne casse rien :
Run : `npm test`
Expected : PASS, même nombre de tests qu'avant plus 3.

> `test/cartes.ts` n'est pas un fichier de test : `test/environments.test.ts` exige que chaque fichier **collecté** appartienne à exactement un projet vitest, et un module sans `.test.` n'est pas collecté. Si ce test rougit malgré tout, c'est le signe que le fichier a été nommé `cartes.test.ts` par erreur.

- [ ] **Step 5: Commit**

```bash
git add test/setup.ts test/cartes.ts test/affichage-cartes.test.tsx
git commit -m "test(461): ignore the card tree in text queries

Refs #461"
```

---

### Task 2: `LigneCarte`, la coquille partagée

**Files:**
- Create: `frontend/components/tcn/LigneCarte.tsx`
- Create: `frontend/components/tcn/LigneCarte.test.tsx`
- Modify: `frontend/components/tcn/index.ts`

**Interfaces:**
- Consumes: rien (aucun autre composant TCN).
- Produces:

```ts
export function LigneCarte(props: {
  href?: string;            // zone cliquable = <Link>. Exclusif avec onSelect.
  onSelect?: () => void;    // zone cliquable = <button>. Exige ariaLabel.
  ariaLabel?: string;       // nom accessible du <button>
  ouvert?: boolean;         // aria-expanded du <button> (cartes qui replient, #463)
  surtitre?: ReactNode;     // ligne au-dessus du titre (une date, en général)
  marqueur?: ReactNode;     // pastille à gauche du titre (PlaceBadge, StatusBadge)
  titre: ReactNode;         // nom d'athlète ou d'épreuve
  valeur?: ReactNode;       // valeur forte, alignée à droite (temps, compteur)
  meta?: ReactNode;         // bande secondaire sous le titre
  depliant?: { libelle: string; contenu: ReactNode };
  actions?: ReactNode;      // sous-ligne d'actions, hors de la zone cliquable
  accent?: boolean;         // liseré orange TCN à gauche
  attenue?: boolean;        // fond grisé (non-finisher)
}): JSX.Element
```

- [ ] **Step 1: Write the failing test**

Créer `frontend/components/tcn/LigneCarte.test.tsx` :

```tsx
// frontend/components/tcn/LigneCarte.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LigneCarte } from "./LigneCarte";

describe("LigneCarte", () => {
  it("rend une ancre quand la carte mène quelque part", () => {
    render(<LigneCarte href="/courses/1" titre="Triathlon de Nantes" />);
    expect(screen.getByRole("link", { name: /Triathlon de Nantes/ })).toHaveAttribute(
      "href",
      "/courses/1",
    );
  });

  it("rend un bouton nommé quand la carte agit au lieu de naviguer", async () => {
    const onSelect = vi.fn();
    render(
      <LigneCarte onSelect={onSelect} ariaLabel="Déplier Coupe de Bretagne" ouvert={false} titre="Coupe de Bretagne" />,
    );
    const bouton = screen.getByRole("button", { name: "Déplier Coupe de Bretagne" });
    expect(bouton).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(bouton);
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("rend surtitre, marqueur, valeur et méta", () => {
    render(
      <LigneCarte
        href="/x"
        surtitre="12 mai 2025"
        marqueur={<span>①</span>}
        titre="Jean DUPONT"
        valeur="1:04:12"
        meta="TCN · SEM · H"
      />,
    );
    expect(screen.getByText("12 mai 2025")).toBeInTheDocument();
    expect(screen.getByText("①")).toBeInTheDocument();
    expect(screen.getByText("1:04:12")).toBeInTheDocument();
    expect(screen.getByText("TCN · SEM · H")).toBeInTheDocument();
  });

  // Un <button> ou un <a> imbriqué dans un <a> est du HTML invalide : le
  // dépliant et les actions doivent rester FRÈRES de la zone cliquable.
  it("garde le dépliant hors de la zone cliquable", () => {
    render(
      <LigneCarte
        href="/x"
        titre="Jean DUPONT"
        depliant={{ libelle: "Inters", contenu: <span>12:03</span> }}
      />,
    );
    const lien = screen.getByRole("link", { name: /Jean DUPONT/ });
    const resume = screen.getByText("Inters");
    expect(lien).not.toContainElement(resume);
  });

  it("garde les actions hors de la zone cliquable", () => {
    render(
      <LigneCarte href="/x" titre="Jean DUPONT" actions={<a href="/preuve">Voir la preuve</a>} />,
    );
    const lien = screen.getByRole("link", { name: /Jean DUPONT/ });
    expect(lien).not.toContainElement(screen.getByRole("link", { name: "Voir la preuve" }));
  });

  // WCAG 2.2 2.5.8 : 24 px est le minimum normatif, 44 px le seuil au doigt
  // que la coquille de l'app se donne déjà (AppNav).
  it("donne 44 px de haut à la zone cliquable et au résumé du dépliant", () => {
    render(
      <LigneCarte
        href="/x"
        titre="Jean DUPONT"
        depliant={{ libelle: "Inters", contenu: <span>12:03</span> }}
      />,
    );
    expect(screen.getByRole("link", { name: /Jean DUPONT/ })).toHaveStyle({ minHeight: "44px" });
    expect(screen.getByText("Inters").closest("summary")).toHaveStyle({ minHeight: "44px" });
  });

  // `toHaveStyle` ne voit PAS un `var()` posé dans un raccourci sous jsdom :
  // cssstyle abandonne la déclaration au calcul, et l'assertion échoue sur du
  // code correct (vérifié à l'exécution). L'attribut `style`, lui, la porte
  // telle quelle — c'est donc lui qu'on lit. `toHaveStyle` reste bon pour les
  // valeurs sans variable, comme le `minHeight` du test précédent.
  it("pose le liseré orange sur une ligne du club et le retire sinon", () => {
    const { rerender } = render(<LigneCarte href="/x" titre="Jean DUPONT" accent />);
    expect(screen.getByRole("article").getAttribute("style")).toContain(
      "border-left: 3px solid var(--tcn-orange)",
    );

    rerender(<LigneCarte href="/x" titre="Jean DUPONT" />);
    expect(screen.getByRole("article").getAttribute("style")).toContain(
      "border-left: 3px solid transparent",
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run : `npx vitest run components/tcn/LigneCarte.test.tsx`
Expected : FAIL — « Failed to resolve import "./LigneCarte" ».

- [ ] **Step 3: Write minimal implementation**

Créer `frontend/components/tcn/LigneCarte.tsx` :

```tsx
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

/**
 * Une ligne de tableau repliée en carte, pour les largeurs où la grille ne
 * tient plus (#461, `RESP-1`).
 *
 * **Sans état, donc sans `"use client"`** : `/ajouter` est un Server Component
 * et doit le rester. Le dépliant est un `<details>` natif, pas un état React.
 *
 * **Le dépliant et les actions sont FRÈRES de la zone cliquable, jamais
 * enfants** : un `<a>` ou un `<button>` imbriqué dans un `<a>` est du HTML
 * invalide. C'est déjà la raison pour laquelle `EventsTable` sort « Voir la
 * preuve » de sa ligne ; la coquille ne fait que généraliser la contrainte.
 *
 * Le composant ne sait rien des colonnes : ce que les quatre tableaux partagent
 * est un dessin, pas une structure. Chaque écran verse son contenu.
 */
export function LigneCarte({
  href,
  onSelect,
  ariaLabel,
  ouvert,
  surtitre,
  marqueur,
  titre,
  valeur,
  meta,
  depliant,
  actions,
  accent = false,
  attenue = false,
}: {
  /** Cible de la zone cliquable, quand la carte navigue. Exclusif avec `onSelect`. */
  href?: string;
  /** Action de la zone cliquable, quand la carte ne navigue pas. */
  onSelect?: () => void;
  /** Nom accessible du bouton — un `<button>` n'a pas d'URL à annoncer. */
  ariaLabel?: string;
  /** `aria-expanded` du bouton, pour une carte qui en replie d'autres (#463). */
  ouvert?: boolean;
  /** Ligne au-dessus du titre : une date, en général. */
  surtitre?: ReactNode;
  /** Pastille à gauche du titre : `PlaceBadge`, `StatusBadge`. */
  marqueur?: ReactNode;
  titre: ReactNode;
  /** Valeur forte alignée à droite : temps total, compteur. */
  valeur?: ReactNode;
  /** Bande secondaire sous le titre. */
  meta?: ReactNode;
  depliant?: { libelle: string; contenu: ReactNode };
  /** Sous-ligne d'actions, rendue hors de la zone cliquable. */
  actions?: ReactNode;
  /** Liseré orange TCN, comme le `borderLeft` des lignes du classement. */
  accent?: boolean;
  /** Fond grisé des non-finishers. */
  attenue?: boolean;
}) {
  const contenu = (
    <>
      {surtitre ? <div style={STYLE_SURTITRE}>{surtitre}</div> : null}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        {marqueur ? <div style={{ flex: "none" }}>{marqueur}</div> : null}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={STYLE_TITRE}>{titre}</div>
          {meta ? <div style={STYLE_META}>{meta}</div> : null}
        </div>
        {valeur ? <div style={STYLE_VALEUR}>{valeur}</div> : null}
      </div>
    </>
  );

  return (
    <article
      style={{
        borderBottom: "1px solid var(--tcn-border-faint)",
        // Toujours 3 px, transparents à défaut : un liseré qui n'existe que
        // sur les lignes du club décalerait toutes les autres de 3 px.
        borderLeft: `3px solid ${accent ? "var(--tcn-orange)" : "transparent"}`,
        background: attenue
          ? "color-mix(in srgb, var(--tcn-grey-400) 15%, transparent)"
          : undefined,
      }}
    >
      {href ? (
        <Link href={href} className="tcn-rowlink" style={STYLE_CLIC}>
          {contenu}
        </Link>
      ) : (
        <button
          type="button"
          onClick={onSelect}
          aria-label={ariaLabel}
          aria-expanded={ouvert}
          className="tcn-rowlink"
          style={{ ...STYLE_CLIC, width: "100%", textAlign: "left", border: "none" }}
        >
          {contenu}
        </button>
      )}
      {depliant ? (
        <details style={{ padding: "0 16px 8px" }}>
          <summary style={STYLE_RESUME}>{depliant.libelle}</summary>
          <div style={{ paddingBottom: 8 }}>{depliant.contenu}</div>
        </details>
      ) : null}
      {actions}
    </article>
  );
}

// `minHeight: 44` : plancher tactile WCAG 2.2 2.5.8, le même seuil que la
// coquille de navigation se donne déjà (AppNav).
const STYLE_CLIC = {
  display: "block",
  minHeight: 44,
  padding: "12px 16px",
} as const;

const STYLE_RESUME = {
  display: "flex",
  alignItems: "center",
  minHeight: 44,
  fontSize: 13,
  fontWeight: 700,
  color: "var(--tcn-text-muted)",
  cursor: "pointer",
} as const;

const STYLE_SURTITRE = {
  marginBottom: 4,
  fontSize: 13,
  fontWeight: 600,
  color: "var(--tcn-text-muted)",
} as const;

const STYLE_TITRE = {
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: 8,
  fontSize: 15,
  fontWeight: 700,
  color: "var(--tcn-ink)",
} as const satisfies CSSProperties;

const STYLE_META = {
  marginTop: 4,
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: 8,
  fontSize: 13,
  color: "var(--tcn-text-body)",
} as const satisfies CSSProperties;

const STYLE_VALEUR = {
  flex: "none",
  fontFamily: "var(--tcn-font-cond)",
  fontWeight: 700,
  fontSize: 16,
  color: "var(--tcn-ink)",
  textAlign: "right",
} as const satisfies CSSProperties;
```

Ajouter dans `frontend/components/tcn/index.ts`, à la suite des autres exports :

```ts
export { LigneCarte } from "./LigneCarte";
```

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run components/tcn/LigneCarte.test.tsx`
Expected : 7 PASS.

Run : `npm run lint`
Expected : aucune erreur.

- [ ] **Step 5: Commit**

```bash
git add components/tcn/LigneCarte.tsx components/tcn/LigneCarte.test.tsx components/tcn/index.ts
git commit -m "feat(461): add LigneCarte, the shared collapsed-row shell

Refs #461"
```

---

### Task 3: Le classement en cartes (`RaceFinishers`)

**Files:**
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Modify: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consumes: `LigneCarte` (Task 2) ; la convention `data-affichage` et `dansLesCartes` (Task 1).
- Produces: rien pour les tâches suivantes.

**Contexte à lire avant d'écrire :** `RaceFinishers.tsx` porte déjà `CelluleInter` (le ⚠ des temps illisibles, #472), `EnteteTriable`, l'état `tri` et sa fonction `trierSur`. La tâche **réutilise** `CelluleInter` telle quelle et **ajoute** deux fonctions d'écriture de `tri` — elle n'en réécrit aucune.

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/results/RaceFinishers.test.tsx`. Importer `within` depuis `@testing-library/react` et `dansLesCartes` depuis `@/test/cartes` — **`carte.texte(…)` est obligatoire pour toute lecture de texte dans l'arbre carte**, `getByText` n'y voit rien (cf. Task 1).

```tsx
describe("rendu carte sous lg", () => {
  const cartes = () => dansLesCartes("classement-cartes");
  const grille = () => screen.getByTestId("classement-grille");

  it("bascule la grille et les cartes aux seuils annoncés", () => {
    render(
      <RaceFinishers
        participations={[p({ id: 1, nom: "DUPONT", rank_overall: 1, total_time: "01:04:12" })]}
        summary={synthese()}
        total={1}
        page={1}
        pageSize={20}
      />,
    );
    expect(grille().className).toContain("hidden lg:block");
    expect(screen.getByTestId("classement-cartes").className).toContain("lg:hidden");
  });

  it("porte place, nom, temps et méta dans la carte", () => {
    render(
      <RaceFinishers
        participations={[
          p({ id: 1, nom: "DUPONT", rank_overall: 1, total_time: "01:04:12", club: "TCN", is_tcn: true }),
        ]}
        summary={synthese()}
        total={1}
        page={1}
        pageSize={20}
      />,
    );
    const carte = cartes();
    expect(carte.texte("DUPONT T")).toBeInTheDocument();
    expect(carte.texte("01:04:12")).toBeInTheDocument();
    expect(carte.texte("1")).toBeInTheDocument();
    // La méta est une seule chaîne « club · catégorie · sexe ».
    expect(carte.texte(/TCN · S4/)).toBeInTheDocument();
  });

  it("range les inters dans un dépliant, ⚠ compris", () => {
    render(
      <RaceFinishers
        participations={[
          p({ id: 1, nom: "DUPONT", rank_overall: 1, total_time: "01:04:12", splits: { swim: "0-2:-15:00" } }),
        ]}
        summary={synthese({ split_keys: ["swim"] })}
        total={1}
        page={1}
        pageSize={20}
        eventType="triathlon"
      />,
    );
    const carte = cartes();
    expect(carte.texte("Inters")).toBeInTheDocument();
    // `getByRole` n'est pas concerné par `defaultIgnore`, mais reste scopé aux
    // cartes : le même ⚠ existe dans l'arbre grille.
    expect(carte.getByRole("img", { name: /illisible/i })).toBeInTheDocument();
  });

  // Trois lignes, dans un ordre backend qui n'est ni croissant ni décroissant :
  // avec deux lignes, « décroissant » redonnerait l'ordre de départ et le test
  // ne prouverait rien.
  it("trie depuis le contrôle mobile, et la grille suit", async () => {
    render(
      <RaceFinishers
        participations={[
          p({ id: 1, nom: "MOYEN", rank_overall: 1, total_time: "01:30:00" }),
          p({ id: 2, nom: "LENT", rank_overall: 2, total_time: "02:00:00" }),
          p({ id: 3, nom: "RAPIDE", rank_overall: 3, total_time: "01:00:00" }),
        ]}
        summary={synthese()}
        total={3}
        page={1}
        pageSize={20}
      />,
    );
    const noms = () =>
      within(grille())
        .getAllByText(/^(MOYEN|LENT|RAPIDE) T$/)
        .map((n) => n.textContent);

    // L'ordre du backend d'abord : la vue n'est pas triée.
    expect(noms()).toEqual(["MOYEN T", "LENT T", "RAPIDE T"]);

    await userEvent.click(cartes().getByRole("button", { name: /Inverser l'ordre/ }));

    // Le contrôle mobile écrit dans le même état `tri` que les en-têtes :
    // l'arbre grille est réordonné lui aussi. Premier appui = décroissant, ce
    // que le nom accessible du bouton annonçait (« actuellement croissant »).
    expect(noms()).toEqual(["LENT T", "MOYEN T", "RAPIDE T"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run : `npx vitest run components/results/RaceFinishers.test.tsx -t "rendu carte"`
Expected : FAIL — « Unable to find an element by: [data-testid="classement-cartes"] ».

- [ ] **Step 3: Write minimal implementation**

Dans `frontend/components/results/RaceFinishers.tsx` :

**3a.** Ajouter les imports manquants en tête de fichier :

```tsx
import { LigneCarte } from "@/components/tcn";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
```

**3b.** À côté de `trierSur`, ajouter les deux fonctions qu'utilise le sélecteur mobile. Elles écrivent dans **le même état** que les en-têtes — c'est ce qui fait que tourner le téléphone ne perd pas le tri :

```tsx
  /**
   * Choix d'une colonne depuis le sélecteur mobile. Distinct de `trierSur`,
   * qui bascule la direction quand on reclique la même colonne : rechoisir la
   * colonne déjà active dans une liste déroulante n'est pas un geste
   * d'inversion, et inverserait à chaque réouverture du menu.
   */
  function choisirTri(cle: string) {
    setTri((precedent) => ({
      cle,
      direction: precedent?.cle === cle ? precedent.direction : "asc",
    }));
  }

  /** Inversion explicite, seul geste d'inversion du rendu carte. */
  function inverserTri() {
    setTri((precedent) => ({
      cle: precedent?.cle ?? CLE_TEMPS_TOTAL,
      // Non trié → « décroissant », et non « croissant » : le nom accessible du
      // bouton annonce alors « actuellement croissant », donc l'appuyer doit
      // donner l'autre sens. Le test compare le sens **et** le libellé — les
      // désaccorder est une régression silencieuse pour un lecteur d'écran.
      direction: precedent?.direction === "desc" ? "asc" : "desc",
    }));
  }
```

**3c.** Remplacer l'ouverture du bloc scrollable (aujourd'hui `<div style={{ overflowX: "auto" }} data-pending=… >`) par les deux arbres. La grille garde **exactement** son contenu actuel ; seul son conteneur change :

```tsx
      <div
        data-testid="classement-grille"
        data-affichage="grille"
        className="hidden overflow-x-auto transition-opacity data-pending:opacity-60 lg:block"
        data-pending={pending || undefined}
      >
        <div style={{ minWidth: 1080 }}>
          {/* … l'en-tête et les lignes, inchangés … */}
        </div>
      </div>
```

Puis, **immédiatement après** ce bloc, l'arbre carte :

```tsx
      {/* Sous 1 024 px la grille de 1 080 px ne tient plus : elle demandait 3,1
          écrans de défilement horizontal sur un iPhone SE, et la colonne
          « Athlète » sortait de l'écran avant les inters (#461, WCAG 1.4.10). */}
      <div
        data-testid="classement-cartes"
        data-affichage="cartes"
        className="transition-opacity data-pending:opacity-60 lg:hidden"
        data-pending={pending || undefined}
      >
        {lignes.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderBottom: "1px solid var(--tcn-border)" }}>
            <span id="libelle-tri-classement" style={{ fontSize: 13, fontWeight: 700, color: "var(--tcn-text-muted)" }}>
              Trier par
            </span>
            <Select value={tri?.cle ?? CLE_TEMPS_TOTAL} onValueChange={(v) => choisirTri(v as string)}>
              <SelectTrigger aria-labelledby="libelle-tri-classement" className="h-11 flex-1">
                <SelectValue>
                  {(value) =>
                    value === CLE_TEMPS_TOTAL
                      ? "Temps total"
                      : (segments.find((s) => s.key === value)?.label ?? String(value))
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={CLE_TEMPS_TOTAL}>Temps total</SelectItem>
                {segments.map((s) => (
                  <SelectItem key={s.key} value={s.key}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <button
              type="button"
              onClick={inverserTri}
              aria-label={`Inverser l'ordre, actuellement ${tri?.direction === "desc" ? "décroissant" : "croissant"}${perimetreTri}`}
              // 44 px : plancher tactile WCAG 2.2 2.5.8.
              style={{ minWidth: 44, minHeight: 44, borderRadius: 8, border: "1px solid var(--tcn-border)", background: "var(--tcn-fill)", color: "var(--tcn-ink)", fontSize: 15, cursor: "pointer" }}
            >
              {tri?.direction === "desc" ? "▼" : "▲"}
            </button>
          </div>
        )}
        {lignes.map((p) => {
          const nf = isNonFinisher(p.status);
          const name = [p.athlete?.nom, p.athlete?.prenom].filter(Boolean).join(" ");
          const splits = p.splits ?? {};
          const meta = [p.club ?? "—", p.category ?? "—", genderShort(p.athlete?.gender)]
            .filter(Boolean)
            .join(" · ");
          return (
            <LigneCarte
              key={p.id}
              href={detailHref(p)}
              accent={p.is_tcn}
              attenue={nf}
              marqueur={
                nf ? (
                  <StatusBadge status={p.status} />
                ) : p.rank_overall != null ? (
                  <PlaceBadge place={p.rank_overall} />
                ) : (
                  <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                )
              }
              titre={name}
              valeur={p.total_time ?? "—"}
              meta={meta}
              depliant={
                segments.length > 0
                  ? {
                      libelle: "Inters",
                      // `CelluleInter` telle quelle : le ⚠ des temps illisibles
                      // (#472), son `title` et son `aria-label` voyagent avec.
                      contenu: (
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(72px, 1fr))", gap: 8 }}>
                          {segments.map((s) => (
                            <div key={s.key}>
                              <div className="micro-label" style={{ color: "var(--tcn-text-faint)" }}>
                                {s.label}
                              </div>
                              <CelluleInter valeur={splits[s.key]} small={s.small} />
                            </div>
                          ))}
                        </div>
                      ),
                    }
                  : undefined
              }
            />
          );
        })}
      </div>
```

**3d.** Le bloc des **états vides** (`participations.length === 0 && …`) vit aujourd'hui *dans* le `minWidth: 1080`. Le sortir des deux arbres, juste après le bloc carte, pour qu'il ne soit ni rendu deux fois ni enfermé dans une largeur plancher :

```tsx
      {participations.length === 0 && (
        /* … le bloc conditionnel existant, déplacé sans modification … */
      )}
```

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run components/results/RaceFinishers.test.tsx`
Expected : PASS — les 75 tests existants **et** les 4 nouveaux. Si un test existant échoue sur « found multiple elements », c'est un `getByRole` (que `defaultIgnore` ne couvre pas) : le scoper avec `within(screen.getByTestId("classement-grille"))`.

Run : `npm run lint`
Expected : aucune erreur.

- [ ] **Step 5: Commit**

```bash
git add components/results/RaceFinishers.tsx components/results/RaceFinishers.test.tsx
git commit -m "feat(461): render the race ranking as stacked cards below lg

Refs #461"
```

---

### Task 4: La fiche athlète en cartes (`EventsTable`)

**Files:**
- Modify: `frontend/app/(public_restricted)/athletes/[id]/EventsTable.tsx`
- Modify: `frontend/app/(public_restricted)/athletes/[id]/EventsTable.test.tsx`

**Interfaces:**
- Consumes: `LigneCarte` (Task 2) ; la convention `data-affichage` et `dansLesCartes` (Task 1).
- Produces: rien.

- [ ] **Step 1: Write the failing test**

Importer `dansLesCartes` depuis `@/test/cartes` en tête de
`EventsTable.test.tsx`, puis ajouter ce bloc. Le fabricant de fixture existant est
`participation(id, over)` avec `over: { date?, type?, name? }` — le réutiliser,
et étendre une participation par déstructuration pour les champs qu'il ne prend
pas en paramètre. Il rend `total_time: "01:59:00"`, `rank_overall: null` et
`event_date: "2026-05-16"` par défaut, que `formatDate` affiche `16/05/2026`.

```tsx
describe("rendu carte sous md", () => {
  const cartes = () => dansLesCartes("epreuves-cartes");

  it("bascule la grille et les cartes aux seuils annoncés", () => {
    render(
      <EventsTable
        participations={[participation(1, { name: "Triathlon de Nantes" })]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    expect(screen.getByTestId("epreuves-grille").className).toContain("hidden md:block");
    expect(screen.getByTestId("epreuves-cartes").className).toContain("md:hidden");
  });

  it("porte date, épreuve, temps et place dans la carte", () => {
    render(
      <EventsTable
        participations={[{ ...participation(1, { name: "Triathlon de Nantes" }), rank_overall: 2 }]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    const carte = cartes();
    expect(carte.texte("16/05/2026")).toBeTruthy();
    expect(carte.texte("Triathlon de Nantes")).toBeTruthy();
    expect(carte.texte("01:59:00")).toBeTruthy();
    expect(carte.texte("2")).toBeTruthy();
  });

  it("garde la preuve dans la carte, hors du lien de la ligne", () => {
    render(
      <EventsTable
        participations={[
          {
            ...participation(1, { name: "Triathlon de Nantes" }),
            evidence_url: "https://example.org/p.jpg",
          },
        ]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    const carte = cartes();
    const preuve = carte.getByRole("link", { name: /Voir la preuve/ });
    expect(preuve).toHaveAttribute("href", "https://example.org/p.jpg");
    expect(carte.getByRole("link", { name: /Triathlon de Nantes/ })).not.toContainElement(preuve);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run : `npx vitest run "app/(public_restricted)/athletes/[id]/EventsTable.test.tsx" -t "rendu carte"`
Expected : FAIL — testid introuvable.

- [ ] **Step 3: Write minimal implementation**

Dans `EventsTable.tsx`, importer `LigneCarte` (`import { …, LigneCarte } from "@/components/tcn";`).

La branche `ordered.length > 0` rend aujourd'hui un seul `<div style={{ overflowX: "auto" }}>`. La remplacer par les deux arbres. La grille garde son contenu ; son conteneur devient :

```tsx
        <div
          data-testid="epreuves-grille"
          data-affichage="grille"
          className="hidden overflow-x-auto md:block"
        >
          <div style={{ minWidth: MIN_WIDTH }}>
            {/* … en-tête et lignes, inchangés … */}
          </div>
        </div>
```

Puis l'arbre carte, juste après :

```tsx
        {/* Sous 768 px, les 988 px de la grille laissaient FORMAT, TEMPS,
            PLACE et le ⚠ hors écran : la donnée pour laquelle on ouvre un
            profil était invisible sans geste (#461, WCAG 1.4.10). */}
        <div data-testid="epreuves-cartes" data-affichage="cartes" className="md:hidden">
          {ordered.map((p) => {
            const { ratio } = rankRatio(p);
            const unreliableTitle =
              p.course?.is_reliable === false ? unreliableTooltip(p.course?.quality_issues) : null;
            const nonFinisher = isNonFinisher(p.status);
            const sigle = (p.status ?? "").toUpperCase();
            const preuve = p.evidence_url && isHttpUrl(p.evidence_url) ? p.evidence_url : null;
            return (
              <LigneCarte
                key={p.id}
                href={`/courses/${p.course?.id}/participations/${p.id}`}
                surtitre={formatDate(p.course?.event_date)}
                titre={
                  <>
                    {p.course?.name}
                    {p.is_pending_validation && <PendingBadge rejected={p.is_rejected} />}
                  </>
                }
                valeur={p.total_time ?? "—"}
                meta={
                  <>
                    <span>{eventTypeLabel(p.course?.event_type)}</span>
                    <FormatChip>{formatToken(p.course?.event_type, p.course?.distance_km)}</FormatChip>
                    {nonFinisher ? (
                      <span style={{ fontWeight: 700, color: "var(--tcn-text-muted)" }}>
                        {sigle}
                        {p.rank_overall != null ? <>({p.rank_overall}{ratio ? `/${ratio.total}` : ""})</> : null}
                      </span>
                    ) : p.rank_overall != null ? (
                      <span style={{ display: "inline-flex", alignItems: "baseline", gap: 4 }}>
                        <PlaceBadge place={p.rank_overall} />
                        {ratio ? (
                          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--tcn-text-faint)" }}>
                            /{ratio.total}
                          </span>
                        ) : null}
                      </span>
                    ) : (
                      <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                    )}
                    {unreliableTitle ? (
                      <span
                        data-testid="unreliable-marker"
                        title={unreliableTitle}
                        aria-label={unreliableTitle}
                        role="img"
                        style={{ fontSize: 13, color: "var(--tcn-text-faint)", cursor: "help", userSelect: "none" }}
                      >
                        ⚠
                      </span>
                    ) : null}
                  </>
                }
                actions={
                  <>
                    {preuve ? (
                      <div style={{ padding: "0 16px 12px" }}>
                        <a
                          href={preuve}
                          target="_blank"
                          rel="noreferrer"
                          className="tcn-btn tcn-btn--sm tcn-btn--secondary"
                        >
                          <Eye size={14} aria-hidden="true" />
                          Voir la preuve
                        </a>
                      </div>
                    ) : null}
                    <ParticipationAdminActions
                      resultat={{
                        id: p.id,
                        epreuve: p.course?.name ?? "cette épreuve",
                        date: p.course?.event_date ?? null,
                        coureur: athleteName,
                        coureurId: athleteId,
                      }}
                      style={{ padding: "0 16px 14px" }}
                    />
                  </>
                }
              />
            );
          })}
        </div>
```

> **Attendu, pas un défaut :** `ParticipationAdminActions` est ainsi monté deux fois par ligne, une fois par arbre. Le surcoût réseau est nul — les vingt lignes d'une page partagent déjà un seul appel de session, `useSession` ayant une clé de cache unique — et l'arbre masqué par CSS n'est ni cliquable ni atteignable au clavier.

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run "app/(public_restricted)/athletes/[id]/EventsTable.test.tsx"`
Expected : PASS — les 17 existants et les 3 nouveaux. Attention à `data-testid="unreliable-marker"` : il existe désormais dans les deux arbres, donc un `getByTestId` existant doit devenir `within(screen.getByTestId("epreuves-grille")).getByTestId("unreliable-marker")`.

Run : `npx vitest run "app/(public_restricted)/athletes/[id]/page.test.tsx"`
Expected : PASS. Même remède si un `getByRole` y devient ambigu.

- [ ] **Step 5: Commit**

```bash
git add "app/(public_restricted)/athletes/[id]/EventsTable.tsx" "app/(public_restricted)/athletes/[id]/EventsTable.test.tsx"
git commit -m "feat(461): render the athlete event table as cards below md

Refs #461"
```

---

### Task 5: `/resultats` en cartes (`EventList`)

**Files:**
- Modify: `frontend/components/results/EventList.tsx`
- Modify: `frontend/components/results/EventList.test.tsx`

**Interfaces:**
- Consumes: `LigneCarte` (Task 2) ; la convention `data-affichage` et `dansLesCartes` (Task 1) ; `EventGroup` de `lib/utils/eventGroups` (existant : `{ prefix, events, total, tcnCount }`).
- Produces: rien.

- [ ] **Step 1: Write the failing test**

Ajouter `within` à l'import de `@testing-library/react` et importer
`dansLesCartes` depuis `@/test/cartes` en tête de `EventList.test.tsx`, puis
ajouter ce bloc. Ce fichier n'a pas de fabricant de fixture :
il pose les données avec `setEvents({ data: { pages: [{ items: […] }] } })` et
rend avec `renderList()` — suivre ce style, et ne pas introduire de fabricant.

```tsx
describe("rendu carte sous md", () => {
  const cartes = () => dansLesCartes("epreuves-cartes");

  /** Une épreuve minimale, au format que `useInfiniteEvents` sert. */
  function epreuve(over: Record<string, unknown>) {
    return {
      id: 14,
      event_name: "Tri de Nantes",
      event_type: "triathlon-m",
      event_date: "2026-05-16",
      distance_km: null,
      is_relay: false,
      total: 148,
      tcn_count: 3,
      ...over,
    };
  }

  it("bascule la grille et les cartes aux seuils annoncés", () => {
    setEvents({
      data: { pages: [{ items: [epreuve({})], total_events: 1, total_participations: 148 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
    renderList();

    expect(screen.getByTestId("epreuves-grille").className).toContain("hidden md:block");
    expect(screen.getByTestId("epreuves-cartes").className).toContain("md:hidden");
  });

  it("porte l'épreuve, ses compteurs et son lien dans la carte", () => {
    setEvents({
      data: { pages: [{ items: [epreuve({})], total_events: 1, total_participations: 148 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
    renderList();

    const carte = cartes();
    expect(carte.getByRole("link", { name: /Tri de Nantes/ })).toHaveAttribute(
      "href",
      "/courses/14",
    );
    expect(carte.texte(/148 résultats/)).toBeTruthy();
  });

  // L'état `ouverts` est au-dessus des deux arbres : replier au téléphone puis
  // élargir garde le repli, et l'inverse aussi.
  it("partage le repli d'une compétition entre les deux arbres", async () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              epreuve({ id: 1, event_name: "Coupe de Bretagne - Sprint H" }),
              epreuve({ id: 2, event_name: "Coupe de Bretagne - Sprint F" }),
            ],
            total_events: 2,
            total_participations: 296,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
    renderList();

    const grille = () => within(screen.getByTestId("epreuves-grille"));
    expect(grille().queryByRole("link", { name: /Sprint H/ })).toBeNull();

    await userEvent.click(cartes().getByRole("button", { name: /Coupe de Bretagne/ }));

    expect(grille().getByRole("link", { name: /Sprint H/ })).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run : `npx vitest run components/results/EventList.test.tsx -t "rendu carte"`
Expected : FAIL — testid introuvable.

- [ ] **Step 3: Write minimal implementation**

Dans `EventList.tsx`, importer `LigneCarte` (`import { Card, Badge, FormatChip, AnnonceStatut, LigneCarte } from "@/components/tcn";`).

Le conteneur de la grille devient :

```tsx
      <div
        data-testid="epreuves-grille"
        data-affichage="grille"
        className="hidden md:block overflow-x-auto"
      >
        <div style={{ minWidth: MIN_WIDTH }}>
          {/* … en-tête et groupes, inchangés … */}
        </div>
      </div>
```

Puis l'arbre carte, juste après :

```tsx
      {/* Sous 768 px, les 948 px de la grille sortaient de l'écran (#461,
          WCAG 1.4.10). Le repli par compétition (#463) y est plus utile
          encore : c'est en carte que quinze lignes coûtent quinze écrans. */}
      <div data-testid="epreuves-cartes" data-affichage="cartes" className="md:hidden">
        {groups.map((groupe) =>
          groupe.events.length === 1 ? (
            <CarteEpreuve key={groupe.events[0].id} event={groupe.events[0]} />
          ) : (
            <CartesCompetition
              key={groupe.events[0].id}
              groupe={groupe}
              ouvert={ouverts.has(groupe.events[0].id)}
              onBascule={() => basculer(groupe.events[0].id)}
            />
          ),
        )}
      </div>
```

Ajouter enfin les deux composants, à côté de `EventRow` et `CompetitionRows` :

```tsx
/** Une épreuve, repliée en carte. `label` remplace son nom sous un groupe. */
function CarteEpreuve({ event: ev, label }: { event: EventOut; label?: string }) {
  return (
    <LigneCarte
      href={`/courses/${ev.id}`}
      surtitre={formatDate(ev.event_date)}
      titre={
        <>
          {formatEventName(label ?? ev.event_name, ev.is_relay)}
          {ev.is_relay && <Badge variant="orange">Relais</Badge>}
        </>
      }
      valeur={ev.tcn_count > 0 ? <Badge count>{ev.tcn_count}</Badge> : <span style={{ color: "var(--tcn-text-faint)" }}>—</span>}
      meta={
        <>
          <span>{eventTypeLabel(ev.event_type)}</span>
          <FormatChip>{formatToken(ev.event_type, ev.distance_km)}</FormatChip>
          <span>
            {ev.total} résultat{ev.total > 1 ? "s" : ""}
          </span>
        </>
      }
    />
  );
}

/** Carte de compétition dépliable, suivie de ses épreuves quand elle l'est. */
function CartesCompetition({
  groupe,
  ouvert,
  onBascule,
}: {
  groupe: EventGroup;
  ouvert: boolean;
  onBascule: () => void;
}) {
  return (
    <>
      <LigneCarte
        onSelect={onBascule}
        ariaLabel={`${ouvert ? "Replier" : "Déplier"} ${groupe.prefix}`}
        ouvert={ouvert}
        surtitre={formatDate(groupe.events[0].event_date)}
        titre={groupe.prefix}
        valeur={<span aria-hidden style={{ color: "var(--tcn-text-muted)" }}>{ouvert ? "▾" : "▸"}</span>}
        meta={
          <>
            <span>{groupe.events.length} épreuves</span>
            <span>
              {groupe.total} résultat{groupe.total > 1 ? "s" : ""}
            </span>
            {groupe.tcnCount > 0 ? <Badge count>{groupe.tcnCount}</Badge> : null}
          </>
        }
      />
      {ouvert && (
        // Retrait : la même hiérarchie que le `indent` de la grille, portée
        // ici par la marge du bloc plutôt que par le padding d'une cellule.
        <div style={{ marginLeft: 16 }}>
          {groupe.events.map((ev) => (
            <CarteEpreuve key={ev.id} event={ev} label={eventSuffix(ev.event_name, groupe.prefix)} />
          ))}
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run components/results/EventList.test.tsx`
Expected : PASS — les 14 existants et les 3 nouveaux. Scoper avec `within(screen.getByTestId("epreuves-grille"))` tout `getByRole` existant devenu ambigu.

Run : `npm run lint`
Expected : aucune erreur.

- [ ] **Step 5: Commit**

```bash
git add components/results/EventList.tsx components/results/EventList.test.tsx
git commit -m "feat(461): render the event list as cards below md

Refs #461"
```

---

### Task 6: `/ajouter` en cartes

**Files:**
- Modify: `frontend/app/(public_restricted)/ajouter/page.tsx`
- Modify: `frontend/app/(public_restricted)/ajouter/page.test.tsx`

**Interfaces:**
- Consumes: `LigneCarte` (Task 2) ; la convention `data-affichage` et `dansLesCartes` (Task 1).
- Produces: rien.

**Point d'attention :** cette page est un **Server Component**. Ne pas y ajouter `"use client"` — `LigneCarte` est sans état précisément pour ça.

- [ ] **Step 1: Write the failing test**

Importer `dansLesCartes` depuis `@/test/cartes` en tête de
`page.test.tsx`, puis ajouter ces deux tests dans le `describe("AjouterPage")`. Le
`beforeEach` du fichier fait déjà rendre `listEvents` vide ; un test qui veut
des lignes le re-mocke pour lui seul.

```tsx
  it("bascule la grille et les cartes aux seuils annoncés", async () => {
    const ui = await AjouterPage();
    render(ui);

    expect(screen.getByTestId("recents-grille").className).toContain("hidden sm:block");
    expect(screen.getByTestId("recents-cartes").className).toContain("sm:hidden");
  });

  it("porte date, épreuve et format dans la carte", async () => {
    listEvents.mockResolvedValue({
      items: [
        {
          id: 14,
          event_name: "Tri de Nantes",
          event_type: "triathlon-m",
          event_date: "2026-05-16",
          distance_km: null,
          is_relay: false,
          total: 148,
          tcn_count: 3,
        },
      ],
      total_events: 1,
      total_participations: 148,
    });
    const ui = await AjouterPage();
    render(ui);

    const carte = dansLesCartes("recents-cartes");
    expect(carte.getByRole("link", { name: /Tri de Nantes/ })).toHaveAttribute(
      "href",
      "/courses/14",
    );
    expect(carte.texte("16/05/2026")).toBeTruthy();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run : `npx vitest run "app/(public_restricted)/ajouter/page.test.tsx"`
Expected : FAIL — testid introuvable.

- [ ] **Step 3: Write minimal implementation**

Dans `page.tsx`, importer `LigneCarte` (`import { Card, Eyebrow, FormatChip, Badge, LigneCarte } from "@/components/tcn";`).

Le conteneur de la grille devient :

```tsx
        <div
          data-testid="recents-grille"
          data-affichage="grille"
          className="hidden sm:block overflow-x-auto"
        >
          <div style={{ minWidth: 480 }}>
            {/* … en-tête et lignes, inchangés … */}
          </div>
        </div>
```

Puis l'arbre carte, juste après :

```tsx
        {/* Sous 640 px, les 480 px de la grille dépassent la largeur utile
            d'un iPhone SE, gouttière `PageShell` déduite (#461). */}
        <div data-testid="recents-cartes" data-affichage="cartes" className="sm:hidden">
          {recent.length === 0 ? (
            // Pas d'action : le formulaire d'import est juste au-dessus.
            <EmptyState bare title="Aucun résultat enregistré pour l'instant" />
          ) : (
            recent.map((e) => (
              <LigneCarte
                key={e.id}
                href={`/courses/${e.id}`}
                surtitre={formatDate(e.event_date)}
                titre={formatEventName(e.event_name, e.is_relay)}
                valeur={
                  e.tcn_count > 0 ? (
                    <Badge count>{e.tcn_count}</Badge>
                  ) : (
                    <span style={{ color: "var(--tcn-text-faint)", fontSize: 13 }}>—</span>
                  )
                }
                meta={<FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip>}
              />
            ))
          )}
        </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run "app/(public_restricted)/ajouter/page.test.tsx"`
Expected : PASS — les 3 existants et les 2 nouveaux.

Run : `npm run build`
Expected : succès. Un échec ici dirait que la page a perdu son statut de Server Component.

- [ ] **Step 5: Commit**

```bash
git add "app/(public_restricted)/ajouter/page.tsx" "app/(public_restricted)/ajouter/page.test.tsx"
git commit -m "feat(461): render the recent imports list as cards below sm

Refs #461"
```

---

### Task 7: Les deux matrices du détail réduisent leurs colonnes

**Files:**
- Modify: `frontend/components/tcn/participation-detail/ComparisonTable.tsx`
- Modify: `frontend/components/tcn/participation-detail/ImprovementMatrix.tsx`
- Modify: `frontend/components/tcn/participation-detail/ComparisonTable.test.tsx`
- Modify: `frontend/components/tcn/participation-detail/ImprovementMatrix.test.tsx`

**Interfaces:**
- Consumes: rien des tâches précédentes.
- Produces: rien.

**Ce que cette tâche n'est pas :** une mise en conformité. Ces deux composants sont de vrais `<table>` portant des matrices croisées, que WCAG 1.4.10 exempte explicitement (« parties du contenu qui nécessitent une disposition bidimensionnelle pour leur usage ou leur sens »). C'est un gain de **lisibilité**, et le commentaire de code doit le dire pour qu'on ne le relise pas plus tard comme un point d'audit fermé.

- [ ] **Step 1: Write the failing test**

Ajouter à `ComparisonTable.test.tsx`, qui porte déjà les fixtures `ROWS`,
`SEGMENTS` et l'aide `renderTable()` — les réutiliser, ne pas en créer d'autres :

```tsx
  // Sept colonnes tombent à ~500 px de large : sur un téléphone, le tableau
  // défile dans sa carte. Les segments courts sortent les premiers — ils sont
  // déjà atténués, et déjà signalés comme bruités par la note du bas.
  it("masque les colonnes des segments courts sous sm", () => {
    renderTable();

    expect(screen.getByRole("columnheader", { name: "T1" }).className).toContain(
      "hidden sm:table-cell",
    );
    expect(screen.getByRole("columnheader", { name: "T2" }).className).toContain(
      "hidden sm:table-cell",
    );
    expect(screen.getByRole("columnheader", { name: "Natation" }).className ?? "").not.toContain(
      "hidden",
    );
  });

  it("masque aussi les cellules de ces colonnes, pas seulement leur en-tête", () => {
    renderTable();

    const premiere = screen.getByRole("row", { name: /1er/ });
    // 137,8 % est la valeur T1 de la première ligne de `ROWS`.
    expect(within(premiere).getByText("137,8 %").className).toContain("hidden sm:table-cell");
  });

  it("dit que les colonnes masquées se lisent sur écran large", () => {
    renderTable();

    expect(screen.getByText(/écran plus large/)).toBeTruthy();
  });
```

Ajouter à `ImprovementMatrix.test.tsx`, qui porte déjà `ROWS` et `renderMatrix()` :

```tsx
  // Trois paliers suffisent à lire la courbe ; les autres s'interpolent à
  // l'œil entre eux, et le tableau tient alors dans ~300 px.
  it("ne garde que trois paliers sous sm", () => {
    renderMatrix();

    for (const masque of ["0,5 %", "2 %", "10 %"]) {
      expect(screen.getByRole("columnheader", { name: masque }).className).toContain(
        "hidden sm:table-cell",
      );
    }
    for (const garde of ["1 %", "5 %", "25 %"]) {
      expect(screen.getByRole("columnheader", { name: garde }).className ?? "").not.toContain(
        "hidden",
      );
    }
  });

  it("masque aussi les cellules de ces paliers", () => {
    renderMatrix();

    const natation = screen.getByRole("row", { name: /Natation/ });
    // +18 est le gain à 10 % de la ligne `swim` de `ROWS`.
    expect(within(natation).getByText("+18").className).toContain("hidden sm:table-cell");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run : `npx vitest run components/tcn/participation-detail/`
Expected : FAIL — les `className` ne contiennent pas encore les utilitaires.

- [ ] **Step 3: Write minimal implementation**

Dans `ComparisonTable.tsx` — les colonnes `small` (T1, T2) sont déjà rendues en gris atténué et déjà signalées comme bruitées par la note du bas :

```tsx
// Sous 640 px, sept colonnes tombent à ~500 px de large et le tableau défile
// dans sa carte. Les segments courts sont les premiers à sortir : ils sont
// déjà rendus en gris atténué, et la note du bas dit déjà que leurs
// pourcentages sont bruités. Ce n'est pas une mise en conformité — un tableau
// de données est exempté de WCAG 1.4.10 —, c'est de la lisibilité.
const classeColonne = (small?: boolean) => (small ? "hidden sm:table-cell" : undefined);
```

à appliquer sur le `<th>` d'en-tête **et** sur le `<td>` correspondant de chaque ligne :

```tsx
<th key={column.key} className={classeColonne(column.small)} style={{ … }}>
…
<td key={column.key} className={classeColonne(column.small)} style={cellStyle}>
```

Et compléter la note existante :

```tsx
        <p style={{ marginTop: 10, fontSize: 13, color: "var(--tcn-text-faint)" }}>
          Les segments courts ({shortSegmentLabels.join(", ")}) sont sensibles au bruit de
          chronométrage : leurs pourcentages peuvent ne pas décroître régulièrement d&apos;un
          rang à l&apos;autre. Leurs colonnes s&apos;affichent sur un écran plus large.
        </p>
```

Dans `ImprovementMatrix.tsx` :

```tsx
// Les six paliers tombent à ~440 px de large sur un téléphone. Trois suffisent
// à lire la courbe — les autres s'interpolent à l'œil entre eux — et le
// tableau tient alors dans ~300 px. Comme pour `ComparisonTable` : lisibilité,
// pas conformité.
const PALIERS_ETROITS = new Set(["1", "5", "25"]);
const classePalier = (percentage: string) =>
  PALIERS_ETROITS.has(percentage) ? undefined : "hidden sm:table-cell";
```

appliqué au `<th>` d'en-tête et au `<td>` de chaque ligne :

```tsx
<th key={percentage} className={classePalier(percentage)} style={headStyle}>
…
<td key={percentage} className={classePalier(percentage)} style={cellStyle}>
```

- [ ] **Step 4: Run tests to verify they pass**

Run : `npx vitest run components/tcn/participation-detail/`
Expected : PASS.

Run : `npm run lint`
Expected : aucune erreur.

- [ ] **Step 5: Commit**

```bash
git add components/tcn/participation-detail/
git commit -m "feat(461): drop the noisiest matrix columns below sm

Refs #461"
```

---

### Task 8: Vérification d'ensemble et note d'architecture

**Files:**
- Modify: `frontend/AGENTS.md`

**Interfaces:**
- Consumes: toutes les tâches précédentes.
- Produces: rien.

- [ ] **Step 1: Run the whole suite**

Run : `npm test`
Expected : PASS, sans un seul « found multiple elements ».

- [ ] **Step 2: Lint and build**

Run : `npm run lint && npm run build`
Expected : les deux réussissent.

- [ ] **Step 3: Write the architecture note**

Ajouter à `frontend/AGENTS.md`, dans la liste à puces de la section « Architecture frontend » :

```markdown
- **Tableaux repliés en cartes sous leur seuil** (#461, `RESP-1`) — quatre
  écrans rendent **deux arbres**, la grille et une liste de cartes, que deux
  classes Tailwind font alterner en CSS pure : `hidden lg:block`/`lg:hidden`
  pour le classement (plancher 1 080 px), `md` pour la fiche athlète (988 px)
  et `/resultats` (948 px), `sm` pour `/ajouter` (480 px). Le dessin de la carte
  vit une seule fois, dans `components/tcn/LigneCarte.tsx` — **sans état, donc
  sans `"use client"`**, ce qui laisse `/ajouter` en Server Component. Trois
  points qui se re-cassent :
  - **Le dépliant et les actions sont frères de la zone cliquable**, jamais
    enfants : un `<a>` ou un `<button>` dans un `<a>` est du HTML invalide.
  - **jsdom ne charge aucune CSS**, donc les deux arbres coexistent en test.
    `test/setup.ts` retire l'arbre carte des requêtes **texte** via
    `configure({ defaultIgnore })`, et le sélecteur porte
    `[data-affichage="cartes"] *` en plus du conteneur : `defaultIgnore` filtre
    par `node.matches()`, donc sans le `*` il n'écarterait que le conteneur, et
    la parade ne filtrerait rien. `test/affichage-cartes.test.tsx` verrouille la
    règle. Deux angles morts : `getByRole` n'utilise pas `ignore` (une requête
    de rôle visant l'intérieur d'une ligne se scope à la main), et **`within` ne
    lève pas l'exclusion** — un test qui vise les cartes passe par
    `dansLesCartes(testId)` de `test/cartes.ts`, dont `texte()` porte le
    `{ ignore: false }`. L'oublier ne se lit pas : la requête dit « unable to
    find an element », comme si la carte n'existait pas.
  - **`ParticipationAdminActions` est monté deux fois par ligne**, une fois par
    arbre. Accepté : `useSession` a une clé de cache unique, donc aucun appel
    supplémentaire, et l'arbre masqué n'est ni cliquable ni atteignable au
    clavier.

  Les deux matrices du détail de participation (`ComparisonTable`,
  `ImprovementMatrix`) ne suivent **pas** ce patron : ce sont de vrais
  `<table>`, que WCAG 1.4.10 exempte, et qu'une carte par ligne priverait de
  leur comparaison colonne à colonne. Elles réduisent leurs colonnes sous `sm:`,
  et c'est de la lisibilité, pas de la conformité.
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(461): record the two-tree table pattern in frontend AGENTS.md

Refs #461"
```

- [ ] **Step 5: Fin de branche**

Enchaîner, dans cet ordre, la fin de branche commune aux trois voies :
`requesting-code-review` → le sous-agent `ui-ux-review` (la branche touche
`frontend/`) → `verification-before-completion` → `finishing-a-development-branch`.
La PR porte `Closes #461` — mot-clé anglais, sans quoi GitHub ne ferme rien.
