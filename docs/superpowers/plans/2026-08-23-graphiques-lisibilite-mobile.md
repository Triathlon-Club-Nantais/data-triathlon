# Graphiques lisibles au téléphone, couleurs distinguables — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre lisibles au téléphone les six graphiques existants du front, et
faire de la couleur des disciplines un encodage qui distingue réellement.

**Architecture :** Trois mouvements indépendants. (1) `lib/sport-colors.ts`
devient la **source unique** de l'échelle des disciplines, avec des tokens
réaffectés pour que deux familles voisines de la barre empilée se distinguent.
(2) Les deux SVG à `viewBox` fixe cessent de porter leurs textes : ils gardent la
géométrie, les libellés passent en HTML dimensionné en px réels autour d'eux.
(3) Chaque graphique reçoit une alternative textuelle et cesse de réserver une
information au survol. Aucun JavaScript ajouté : le rendu serveur sans JS est
préservé partout.

**Tech Stack :** Next.js 16 (App Router, RSC), TypeScript strict, Tailwind CSS
v4, `d3-scale` / `d3-shape` (déjà installés), Vitest + Testing Library.

**Spec :** `docs/superpowers/specs/2026-08-23-graphiques-lisibilite-mobile-design.md`

**Issue :** [#480](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/480)

## Global Constraints

- **Aucune nouvelle dépendance.** `d3-scale` et `d3-shape` sont déjà là ; rien
  d'autre ne s'ajoute.
- **Aucun JavaScript ajouté.** Tous les correctifs doivent tenir au rendu
  serveur, sans hydratation. Ne jamais introduire `useState`/`useEffect`/
  `"use client"` dans un composant qui n'en a pas déjà.
  (`RankingEvolutionChart` est le seul `"use client"` du lot, il l'était déjà.)
- **La palette TCN ne s'élargit pas.** Toute couleur doit être un token
  `--tcn-*` déjà déclaré dans `app/globals.css`. Interdiction d'ajouter une
  teinte (#325, non rejugé).
- **Copie en français, au vouvoiement.** Tout texte visible ou lu par un lecteur
  d'écran (`aria-label` compris). L'objet importé se dit « épreuve », jamais
  « course » (`frontend/AGENTS.md`).
- **Identifiants et tests en anglais**, commentaires de règle métier en
  français (Principe I de la constitution).
- **Commits Conventional Commits**, un par tâche, message en anglais avec
  `Refs #480`.
- **TDD non négociable** : le test échoue d'abord, pour la bonne raison.
- **Seuil d'adjacence : 1,6:1** entre deux familles voisines de la barre
  empilée. **Seuil de texte : 4,5:1** pour tout libellé (WCAG 1.4.3).
- Commandes, depuis `frontend/` : `npx vitest run <fichier>` pour un fichier,
  `npm test` pour tout, `npm run lint`, `npm run build`.

---

## Structure des fichiers

| Fichier | Responsabilité après le lot |
| --- | --- |
| `lib/sport-colors.ts` | **Source unique** : familles de disciplines (nom + token), ordre, couleur d'un `event_type`, teintes de libellé |
| `lib/utils/format.ts` | Formatage et agrégation ; n'a plus de couleurs à lui, importe la famille |
| `app/globals.css` | Tokens ; `--tri` et `--violet` disparaissent |
| `components/charts/Histogram.tsx` | Géométrie SVG + libellés HTML + alternative textuelle |
| `components/charts/MonthlyTrend.tsx` | Barres HTML, valeurs toujours visibles, alternative textuelle |
| `components/charts/BarList.tsx` | Barres HTML avec plancher de largeur, alternative textuelle |
| `components/charts/CategoryBars.tsx` | Alternative textuelle |
| `components/tcn/participation-detail/RankingEvolutionChart.tsx` | Géométrie SVG + libellés HTML + positions en clair |
| `components/club/PodiumsList.tsx` | Retrait du dernier `text-[9px]` |
| `app/(public_restricted)/dashboard/page.tsx` | Barre empilée : filet, libellés, alternative textuelle |

**Ordre d'exécution :** la tâche 1 d'abord (les autres lisent ses couleurs) ;
les tâches 2 à 6 sont indépendantes entre elles.

---

## Task 1: Échelle unique des disciplines

**Files:**
- Modify: `frontend/lib/sport-colors.ts`
- Modify: `frontend/lib/utils/format.ts:66-100`
- Modify: `frontend/app/globals.css:59-63` (bloc `@theme`) et `:root` (`--tri`, `--violet`)
- Test: `frontend/lib/sport-colors.test.ts`, `frontend/app/globals.test.ts`

**Interfaces:**
- Consomme : `token`, `resolve`, `contrast`, `SURFACES`, `evalue`, `surSurface`,
  `versOklch`, `ecartDeTeinte` de `@/test/couleur` (helpers de test existants).
- Produit :
  - `export interface Discipline { name: string; color: string }`
  - `export const FAMILY_ORDER: readonly string[]` — l'ordre d'empilement et de légende
  - `export function disciplineFamily(eventType: string | null | undefined): Discipline`
  - `export function eventTypeColor(type: string | null | undefined): string`
  - `inkColor(color: string): string` et `tintedStyle(color: string): React.CSSProperties` — inchangés

**Contexte pour l'implémenteur.** Deux échelles de disciplines coexistent
aujourd'hui : `DISCIPLINE_COLORS` + `eventTypeColor` dans
`lib/sport-colors.ts`, et `disciplineFamily` + `FAMILY_ORDER` +
`aggregateDisciplines` dans `lib/utils/format.ts`. Elles ne s'accordent ni sur
les familles ni sur les couleurs. On garde **le jeu de familles de
`format.ts`** — celui que la légende du tableau de bord affiche déjà — et on le
déplace dans `sport-colors.ts`, qui est le module nommé pour cette échelle.
`aggregateDisciplines` reste dans `format.ts` et importe la famille.

Les prédicats de famille sont **recopiés à l'identique** : `cross-triathlon`
tombe dans « Autres » aujourd'hui (il ne commence pas par `triathlon`), et ce
n'est pas ce lot qui le change.

- [ ] **Step 1: Écrire les tests d'échelle qui échouent**

Remplacer entièrement `frontend/lib/sport-colors.test.ts` par :

```tsx
import { describe, expect, it } from "vitest";
import {
  FAMILY_ORDER,
  disciplineFamily,
  eventTypeColor,
  tintedStyle,
} from "./sport-colors";
import {
  SURFACES,
  contrast,
  ecartDeTeinte,
  evalue,
  resolve,
  surSurface,
  versOklch,
} from "@/test/couleur";

/** Seuil d'adjacence de deux familles voisines dans la barre empilée. */
const SEUIL_ADJACENCE = 1.6;

/**
 * Un `event_type` représentatif par famille, **dans l'ordre de FAMILY_ORDER**.
 * On ne peut pas retrouver une famille depuis son nom : `disciplineFamily` prend
 * un type d'épreuve, pas un libellé.
 */
const TYPE_REPRESENTATIF: Record<string, string> = {
  Triathlon: "triathlon-m",
  "Swim & Run": "swimrun-l",
  Duathlon: "duathlon-s",
  Aquathlon: "aquathlon",
  "Run & Bike": "bike-run",
  Autres: "trail-court",
};

/** Les couleurs qui entrent dans `tintedStyle` : les six familles, plus les
 *  trois alias de splits et le neutre des transitions. */
const TEINTES = [
  ...FAMILY_ORDER.map((nom) => ({
    name: nom,
    color: disciplineFamily(TYPE_REPRESENTATIF[nom]).color,
  })),
  { name: "swim", color: "var(--swim)" },
  { name: "bike", color: "var(--bike)" },
  { name: "run", color: "var(--run)" },
  { name: "transition", color: "var(--muted-foreground)" },
];

describe("échelle unique des disciplines", () => {
  it("nomme les six familles dans l'ordre d'empilement", () => {
    expect([...FAMILY_ORDER]).toEqual([
      "Triathlon",
      "Swim & Run",
      "Duathlon",
      "Aquathlon",
      "Run & Bike",
      "Autres",
    ]);
  });

  it.each([
    ["triathlon-m", "Triathlon"],
    ["swimrun-l", "Swim & Run"],
    ["duathlon-s", "Duathlon"],
    ["aquathlon", "Aquathlon"],
    ["aquarun", "Aquathlon"],
    ["bike-run", "Run & Bike"],
    ["trail-court", "Autres"],
    ["cyclisme-clm", "Autres"],
    ["", "Autres"],
    [null, "Autres"],
  ])("range %s dans « %s »", (type, attendue) => {
    expect(disciplineFamily(type).name).toBe(attendue);
  });

  it("donne à chaque famille une couleur de la palette TCN", () => {
    for (const nom of FAMILY_ORDER) {
      expect(disciplineFamily(TYPE_REPRESENTATIF[nom]).color).toMatch(
        /^var\(--tcn-[a-z0-9-]+\)$/,
      );
    }
  });

  it("sépare deux familles voisines d'au moins 1,6:1", () => {
    // C'est la seule garde de l'arbitrage de la spec : la palette ne permet pas
    // de séparer les 15 paires, seulement les 5 qui se **touchent** dans la
    // barre empilée. Réordonner FAMILY_ORDER ou retoucher un token casse cette
    // séparation sans qu'aucun autre test ne bronche.
    const couleurs = FAMILY_ORDER.map(
      (nom) => evalue(disciplineFamily(TYPE_REPRESENTATIF[nom]).color).hex,
    );
    for (let i = 0; i < couleurs.length - 1; i++) {
      expect(contrast(couleurs[i], couleurs[i + 1])).toBeGreaterThanOrEqual(SEUIL_ADJACENCE);
    }
  });

  it("ne rend plus la même couleur à un trail et à un triathlon (#480)", () => {
    // `--run` et `--tri` valaient tous deux `--tcn-orange` : le grief de VIZ-1.
    expect(eventTypeColor("trail-court")).not.toBe(eventTypeColor("triathlon-m"));
  });
});

describe("tintedStyle", () => {
  it.each(TEINTES)("$name : son libellé atteint 4,5:1 sur son propre aplat", ({ color }) => {
    // WCAG 1.4.3. L'aplat est semi-transparent : il se compose sur la surface,
    // et c'est le résultat composité qui porte le texte. C'est CETTE contrainte
    // qui exclut les trois tons pâles de la palette du jeu des familles.
    const { color: libelleExpr, background } = tintedStyle(color);
    const libelle = evalue(String(libelleExpr)).hex;
    for (const surface of SURFACES) {
      const aplat = surSurface(evalue(String(background)), resolve(surface));
      expect(contrast(libelle, aplat)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each(TEINTES.filter(({ color }) => versOklch(evalue(color).hex)[1] >= 0.05))(
    "$name : son libellé garde la teinte de la discipline",
    ({ color }) => {
      // Le piège d'OKLCH, mesuré sur #469 : vers une encre quasi neutre mais
      // bleutée, l'arc de teinte le plus court fait passer l'orange de marque
      // par le prune (#E9530E → #863c6c).
      const { color: libelleExpr } = tintedStyle(color);
      expect(
        ecartDeTeinte(evalue(String(libelleExpr)).hex, evalue(color).hex),
      ).toBeLessThanOrEqual(15);
    },
  );

  it.each(TEINTES.filter(({ color }) => versOklch(evalue(color).hex)[1] >= 0.05))(
    "$name : son libellé reste coloré, pas repeint en encre",
    ({ color }) => {
      // Le seuil de contraste seul serait satisfait par une part d'encre de
      // 100 %, qui rendrait tous les libellés identiques.
      const { color: libelleExpr } = tintedStyle(color);
      expect(versOklch(evalue(String(libelleExpr)).hex)[1]).toBeGreaterThanOrEqual(
        versOklch(evalue(color).hex)[1] * 0.5,
      );
    },
  );
});
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
cd frontend && npx vitest run lib/sport-colors.test.ts
```

Attendu : ÉCHEC — `FAMILY_ORDER` et `disciplineFamily` ne sont pas exportés par
`lib/sport-colors.ts` (`SyntaxError` / `undefined is not iterable`).

- [ ] **Step 3: Réécrire `lib/sport-colors.ts`**

Remplacer le haut du fichier (de l'en-tête jusqu'à la fin d'`eventTypeColor`)
par le bloc ci-dessous. **Ne pas toucher** à `inkColor` ni à `tintedStyle`, qui
restent tels quels en bas du fichier.

```ts
// Échelle catégorielle **unique** des disciplines (TCN Design System). Elle a
// vécu en double jusqu'à #480 — ici pour les badges, dans `lib/utils/format.ts`
// pour la barre empilée du tableau de bord — avec des familles et des couleurs
// qui ne s'accordaient pas. Tout part désormais d'ici.
//
// Le choix des tokens obéit à DEUX contraintes, dans cet ordre :
//
//   1. **Chaque couleur porte du texte.** `SportBadge` la passe à `tintedStyle`,
//      qui en tire un libellé posé sur son propre aplat : il lui faut 4,5:1
//      (WCAG 1.4.3). Mesuré, cela **exclut** `--tcn-grey-300` (3,44:1),
//      `--tcn-grey-400` (4,37:1) et `--tcn-orange-200` (3,71:1) — les trois tons
//      les plus pâles de la palette.
//   2. **Deux familles voisines se distinguent** dans la barre empilée, au
//      seuil de 1,6:1. Six familles toutes distinguables deux à deux est
//      *impossible* sans quitter la palette (au mieux 4 couleurs) ; on tient
//      donc les 5 paires **adjacentes** — minimum obtenu : 2,27:1 — et la
//      couleur cesse d'être le seul encodage (libellés, filet, légende).
//
// Réordonner FAMILY_ORDER ou retoucher un token casse la seconde contrainte en
// silence : `lib/sport-colors.test.ts` est ce qui l'attrape.
export const FAMILY_ORDER = [
  "Triathlon",
  "Swim & Run",
  "Duathlon",
  "Aquathlon",
  "Run & Bike",
  "Autres",
] as const;

export type FamilyName = (typeof FAMILY_ORDER)[number];

/** Famille de discipline : ce que la légende nomme, et la couleur qui la code. */
export interface Discipline {
  name: FamilyName;
  color: string;
}

const FAMILY_COLORS: Record<FamilyName, string> = {
  Triathlon: "var(--tcn-orange)",
  "Swim & Run": "var(--tcn-ink-2)",
  Duathlon: "var(--tcn-orange-300)",
  Aquathlon: "var(--tcn-orange-deeper)",
  "Run & Bike": "var(--tcn-ink)",
  Autres: "var(--tcn-text-muted)",
};

/**
 * Famille d'un `event_type`. Les prédicats sont ceux qui vivaient dans
 * `lib/utils/format.ts` — `cross-triathlon` tombe donc dans « Autres », faute de
 * commencer par « triathlon ». C'est l'état antérieur, pas un arbitrage de #480.
 */
export function disciplineFamily(eventType: string | null | undefined): Discipline {
  const type = (eventType ?? "").toLowerCase();
  const name = familyName(type);
  return { name, color: FAMILY_COLORS[name] };
}

function familyName(type: string): FamilyName {
  if (type.startsWith("triathlon")) return "Triathlon";
  if (type.startsWith("swimrun")) return "Swim & Run";
  if (type.startsWith("duathlon")) return "Duathlon";
  if (type === "aquathlon" || type === "aquarun") return "Aquathlon";
  if (type === "bike-run") return "Run & Bike";
  return "Autres";
}

/** Couleur d'un type d'épreuve — la couleur de sa famille, rien d'autre. */
export function eventTypeColor(type: string | null | undefined): string {
  return disciplineFamily(type).color;
}
```

- [ ] **Step 4: Faire pointer `lib/utils/format.ts` sur la nouvelle source**

Dans `frontend/lib/utils/format.ts`, **supprimer** l'interface `Discipline`, la
fonction `disciplineFamily` et la constante `FAMILY_ORDER` (le bloc qui va du
commentaire « Famille de discipline… » jusqu'à la ligne `const FAMILY_ORDER = …`),
puis ajouter en haut du fichier :

```ts
import { FAMILY_ORDER, disciplineFamily } from "@/lib/sport-colors";
```

`aggregateDisciplines` reste identique — elle appelle déjà `disciplineFamily(type)`
et `FAMILY_ORDER.indexOf(...)`. Vérifier seulement que son `.sort()` compile :
`FAMILY_ORDER` étant désormais `readonly`, écrire

```ts
    .sort((a, b) => FAMILY_ORDER.indexOf(a.name as FamilyName) - FAMILY_ORDER.indexOf(b.name as FamilyName));
```

et importer `FamilyName` avec le reste. Si un appelant importait `Discipline`
depuis `format.ts`, le rediriger vers `@/lib/sport-colors`.

- [ ] **Step 5: Supprimer les deux tokens morts de `app/globals.css`**

Dans le bloc `@theme`, supprimer ces deux lignes :

```css
  --color-violet: var(--tcn-ink-3);
  --color-tri: var(--tcn-orange);
```

Dans `:root`, supprimer ces deux lignes du bloc « Échelle disciplines » :

```css
  --tri:    var(--tcn-orange);
  --violet: var(--tcn-ink-3);
```

et remplacer le commentaire de ce bloc par :

```css
  /* Couleurs des **segments** d'une course (splits), consommées par
     lib/utils/splits.ts. Ce ne sont plus des couleurs de discipline : depuis
     #480, l'échelle des disciplines vit entièrement dans lib/sport-colors.ts et
     n'utilise que des tokens `--tcn-*`. `--tri` et `--violet` ont disparu avec
     leur dernier consommateur. */
```

Aucun utilitaire Tailwind (`bg-tri`, `text-violet`…) n'existe : vérifié par
`grep -rn "bg-tri\|text-tri\|bg-violet\|text-violet" app components lib`, qui ne
rend rien.

- [ ] **Step 6: Ajouter la garde de suppression dans `app/globals.test.ts`**

Ajouter ce `describe` à la fin de `frontend/app/globals.test.ts` :

```ts
describe("échelle des disciplines", () => {
  it("n'a plus de token `--tri` ni `--violet` (#480)", () => {
    // Les deux étaient des alias sémantiques de l'ancienne échelle de
    // `lib/sport-colors.ts`. `--violet` n'a jamais eu de consommateur et `--tri`
    // a perdu le sien avec la fusion : la table des familles écrit directement
    // ses tokens `--tcn-*`. Un alias qui survit à son usage se remet en service
    // par mégarde.
    expect(() => token("--tri")).toThrow();
    expect(() => token("--violet")).toThrow();
    expect(css).not.toContain("--color-tri:");
    expect(css).not.toContain("--color-violet:");
  });

  it("garde les trois couleurs de segments dont les splits ont besoin", () => {
    for (const nom of ["--swim", "--bike", "--run"]) {
      expect(resolve(nom)).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });
});
```

Ajouter `resolve` à l'import depuis `@/test/couleur` en tête de fichier.

- [ ] **Step 7: Lancer les tests concernés**

```bash
cd frontend && npx vitest run lib/sport-colors.test.ts app/globals.test.ts lib/utils/format.test.ts components/results/ResultCard.test.tsx
```

Attendu : PASS. Si `ResultCard.test.tsx` échoue sur `inkColor("var(--swim)")`,
c'est normal **seulement** si le token a bougé — il n'a pas bougé, donc toute
erreur ici est une régression à corriger, pas un test à ajuster.

- [ ] **Step 8: Vérifier que rien d'autre ne casse**

```bash
cd frontend && npm test && npm run lint && npm run build
```

Attendu : PASS partout. `npm run build` est ici la garde de typage strict sur
`FamilyName`.

- [ ] **Step 9: Commit**

```bash
git add frontend/lib/sport-colors.ts frontend/lib/sport-colors.test.ts \
        frontend/lib/utils/format.ts frontend/app/globals.css frontend/app/globals.test.ts
git commit -m "fix(frontend): one discipline scale, and colours that actually differ

Refs #480"
```

---

## Task 2: La barre empilée du tableau de bord cesse de coder par la seule couleur

**Files:**
- Modify: `frontend/app/(public_restricted)/dashboard/page.tsx:87-105`
- Create: `frontend/app/(public_restricted)/dashboard/DisciplineBar.tsx`
- Test: `frontend/app/(public_restricted)/dashboard/DisciplineBar.test.tsx`

**Interfaces:**
- Consomme : `aggregateDisciplines(byType)` de `@/lib/utils/format`, qui rend
  `{ name: string; color: string; count: number; pct: number }[]` (tâche 1).
- Produit : `export function DisciplineBar({ disciplines }: { disciplines: Discipline[] })`
  où `Discipline = { name: string; color: string; count: number; pct: number }`.

**Contexte.** La barre vit aujourd'hui en JSX nu dans `dashboard/page.tsx` : une
`div` en `flex` de 20 px de haut, un enfant par famille dont la seule propriété
est `width` + `background`. Ni libellé, ni frontière, ni alternative textuelle —
la couleur est le seul encodage (WCAG 1.4.1). On l'extrait dans son propre
composant pour qu'elle soit testable, et on lui donne trois encodages de plus.

Le filet de séparation est un `outline` blanc **intérieur**, pas une `gap` :
une `gap` déformerait les pourcentages en retranchant de la largeur totale.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `frontend/app/(public_restricted)/dashboard/DisciplineBar.test.tsx` :

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DisciplineBar } from "./DisciplineBar";

const TROIS = [
  { name: "Triathlon", color: "var(--tcn-orange)", count: 300, pct: 75 },
  { name: "Duathlon", color: "var(--tcn-orange-300)", count: 96, pct: 24 },
  { name: "Aquathlon", color: "var(--tcn-orange-deeper)", count: 4, pct: 1 },
];

describe("DisciplineBar", () => {
  it("récapitule la répartition pour un lecteur d'écran", () => {
    render(<DisciplineBar disciplines={TROIS} />);
    const barre = screen.getByRole("img");
    expect(barre).toHaveAccessibleName(
      "Répartition des dossards par type d'épreuve : Triathlon 75,0 %, Duathlon 24,0 %, Aquathlon 1,0 %.",
    );
  });

  it("écrit le nom de la famille dans les segments assez larges", () => {
    render(<DisciplineBar disciplines={TROIS} />);
    // 75 % et 24 % portent leur nom ; 1 % ne peut rien porter et reste à la légende.
    expect(screen.getByText("Triathlon")).toBeInTheDocument();
    expect(screen.getByText("Duathlon")).toBeInTheDocument();
    expect(screen.queryByText("Aquathlon")).not.toBeInTheDocument();
  });

  it("sépare les segments d'un filet, sans rogner leur largeur", () => {
    const { container } = render(<DisciplineBar disciplines={TROIS} />);
    const segments = [...container.querySelectorAll("[data-segment]")] as HTMLElement[];
    expect(segments.map((s) => s.style.width)).toEqual(["75%", "24%", "1%"]);
    expect(segments[0].style.outline).toContain("var(--tcn-surface)");
  });

  it("ne rend rien quand il n'y a aucune discipline", () => {
    const { container } = render(<DisciplineBar disciplines={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
cd frontend && npx vitest run "app/(public_restricted)/dashboard/DisciplineBar.test.tsx"
```

Attendu : ÉCHEC — `Failed to resolve import "./DisciplineBar"`.

- [ ] **Step 3: Créer le composant**

`frontend/app/(public_restricted)/dashboard/DisciplineBar.tsx` :

```tsx
import { pctFr } from "@/lib/utils/format";

interface Part {
  name: string;
  color: string;
  count: number;
  pct: number;
}

/**
 * Part minimale, en pourcentage, pour qu'un segment puisse porter son nom.
 * En dessous, le libellé serait tronqué à une lettre : c'est la légende qui le
 * nomme, et l'alternative textuelle qui le chiffre.
 */
const SEUIL_LIBELLE = 12;

/**
 * Barre empilée de la répartition par type d'épreuve.
 *
 * La couleur n'y est **pas** le seul encodage (WCAG 1.4.1) : chaque segment
 * assez large écrit son nom, un filet blanc marque les frontières, et la barre
 * entière porte un récapitulatif chiffré. Le filet est un `outline` intérieur
 * et non une `gap` : une gouttière retrancherait de la largeur totale et
 * fausserait les pourcentages qu'on vient d'afficher.
 */
export function DisciplineBar({ disciplines }: { disciplines: Part[] }) {
  if (disciplines.length === 0) return null;

  const resume = disciplines.map((d) => `${d.name} ${pctFr(d.pct)} %`).join(", ");

  return (
    <div
      role="img"
      aria-label={`Répartition des dossards par type d'épreuve : ${resume}.`}
      style={{ display: "flex", height: 24, borderRadius: 999, overflow: "hidden", marginBottom: 24 }}
    >
      {disciplines.map((d) => (
        <div
          key={d.name}
          data-segment={d.name}
          style={{
            width: `${d.pct}%`,
            background: d.color,
            outline: "1px solid var(--tcn-surface)",
            outlineOffset: -1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
            whiteSpace: "nowrap",
          }}
        >
          {d.pct >= SEUIL_LIBELLE && (
            <span
              aria-hidden
              className="micro-label"
              style={{ color: "var(--tcn-surface)", padding: "0 6px" }}
            >
              {d.name}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

```bash
cd frontend && npx vitest run "app/(public_restricted)/dashboard/DisciplineBar.test.tsx"
```

Attendu : PASS.

- [ ] **Step 5: Brancher le composant dans la page**

Dans `frontend/app/(public_restricted)/dashboard/page.tsx`, remplacer le bloc

```tsx
              <div style={{ display: "flex", height: 20, borderRadius: 999, overflow: "hidden", marginBottom: 24 }}>
                {disciplines.map((d) => <div key={d.name} style={{ width: d.pct + "%", background: d.color }} />)}
              </div>
```

par

```tsx
              <DisciplineBar disciplines={disciplines} />
```

et ajouter l'import :

```tsx
import { DisciplineBar } from "./DisciplineBar";
```

Le bloc de légende qui suit (`disciplines.map` avec les pastilles de 12 px) ne
change pas : il reste la clé des segments trop étroits pour porter leur nom.

- [ ] **Step 6: Vérifier la page entière**

```bash
cd frontend && npm test && npm run lint && npm run build
```

Attendu : PASS.

- [ ] **Step 7: Commit**

```bash
git add "frontend/app/(public_restricted)/dashboard/DisciplineBar.tsx" \
        "frontend/app/(public_restricted)/dashboard/DisciplineBar.test.tsx" \
        "frontend/app/(public_restricted)/dashboard/page.tsx"
git commit -m "fix(a11y): the stacked discipline bar no longer encodes by colour alone

Refs #480"
```

---

## Task 3: `MonthlyTrend` affiche ses chiffres, au doigt comme à la souris

**Files:**
- Modify: `frontend/components/charts/MonthlyTrend.tsx`
- Modify: `frontend/components/club/PodiumsList.tsx:78`
- Test: `frontend/components/charts/MonthlyTrend.test.tsx`

**Interfaces:**
- Consomme : `formatMonthShort(key)` et `formatMonth(key)` de `@/lib/utils/date` — inchangés.
- Produit : `MonthlyTrend({ byMonth }: { byMonth: Record<string, number> })` — signature inchangée.

**Contexte.** Deux défauts tactiles cumulés : la valeur de chaque barre est en
`opacity-0` révélée au `group-hover`, et le repli est un attribut `title`.
Aucun des deux n'existe au doigt — sur téléphone, les 12 barres n'affichent donc
**jamais** de chiffre. C'est WCAG 1.4.13. Les mois sont en outre en `text-[8px]`,
compensation d'un temps où `.micro-label` n'était pas déclarée (#470, corrigé).

Douze valeurs à 11 px ne tiennent pas côte à côte sur 287 px : on n'affiche
**qu'un mois sur deux**, en gardant toujours le plus récent (donc on part de la
fin). Les valeurs, elles, sont plus courtes et restent toutes affichées.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter ces trois `it` dans le `describe("MonthlyTrend")` de
`frontend/components/charts/MonthlyTrend.test.tsx` :

```tsx
  it("affiche la valeur de chaque barre en permanence, sans survol", () => {
    // WCAG 1.4.13 : `opacity-0` + `group-hover` et l'attribut `title` n'existent
    // ni l'un ni l'autre au doigt — sur téléphone, aucune barre ne portait de
    // chiffre.
    const { container } = render(<MonthlyTrend byMonth={{ "2026-01": 7, "2026-02": 20 }} />);
    expect(screen.getByText("7")).toBeVisible();
    expect(screen.getByText("20")).toBeVisible();
    expect(container.querySelector(".opacity-0")).toBeNull();
    expect(container.querySelector("[title]")).toBeNull();
  });

  it("n'écrit qu'un mois sur deux, en gardant le plus récent", () => {
    const byMonth = {
      "2025-09": 1, "2025-10": 2, "2025-11": 3, "2025-12": 4,
      "2026-01": 5, "2026-02": 6,
    };
    const { container } = render(<MonthlyTrend byMonth={byMonth} />);
    const mois = [...container.querySelectorAll("[data-month-label]")].map(
      (n) => n.textContent,
    );
    // 6 mois → 3 libellés, dont le dernier.
    expect(mois.length).toBe(3);
    expect(mois.at(-1)).not.toBe("");
  });

  it("récapitule la tendance pour un lecteur d'écran", () => {
    render(<MonthlyTrend byMonth={{ "2026-01": 7, "2026-02": 20 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Activité mensuelle sur 2 mois, de 7 à 20 dossards.",
    );
  });
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
cd frontend && npx vitest run components/charts/MonthlyTrend.test.tsx
```

Attendu : ÉCHEC sur les trois — `getByText("7")` ne trouve rien de visible,
`[data-month-label]` est vide, `getByRole("img")` ne trouve rien.

- [ ] **Step 3: Réécrire le corps de `MonthlyTrend`**

Remplacer le `return` final de `frontend/components/charts/MonthlyTrend.tsx`
(à partir de `return (` jusqu'à la fin de la fonction) par :

```tsx
  const valeurs = entries.map(([, v]) => v);
  const resume =
    `Activité mensuelle sur ${entries.length} mois, ` +
    `de ${Math.min(...valeurs)} à ${Math.max(...valeurs)} dossards.`;

  return (
    <div
      role="img"
      aria-label={resume}
      className="flex h-44 items-end gap-1.5"
    >
      {entries.map(([key, value], index) => (
        <div key={key} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
          {/* Valeur toujours écrite : `opacity-0` + `group-hover` n'existent pas
              au doigt, et l'attribut `title` non plus (WCAG 1.4.13, #480). */}
          <span aria-hidden className="num text-[11px] font-bold text-[var(--tcn-text-faint)]">
            {value}
          </span>
          <div
            className="w-full rounded-t-sm bg-[color-mix(in_oklch,var(--primary)_70%,transparent)]"
            style={{ height: `${Math.max(4, heightScale(value))}%` }}
          />
          {/* Un mois sur deux, compté depuis la fin pour que le plus récent soit
              toujours écrit : douze libellés de 11px ne tiennent pas sur 287px. */}
          <span aria-hidden data-month-label className="micro-label text-[var(--tcn-text-faint)]">
            {(entries.length - 1 - index) % 2 === 0 ? formatMonthShort(key) : ""}
          </span>
        </div>
      ))}
    </div>
  );
```

Puis alléger l'import en tête de fichier — `formatMonth` ne servait qu'à
l'attribut `title`, qui disparaît :

```ts
import { formatMonthShort } from "@/lib/utils/date";
```

**Note :** `transition-opacity`, `group`, `group-hover:bg-primary` et
`transition-[height]` disparaissent avec ce bloc. La transition de hauteur ne
sert à rien au rendu serveur — elle s'exécutait une fois, au montage.

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

```bash
cd frontend && npx vitest run components/charts/MonthlyTrend.test.tsx
```

Attendu : PASS, y compris les cinq tests préexistants (hauteurs 4 % / 50 % /
100 %, 12 mois max) — le calcul de hauteur n'a pas bougé.

- [ ] **Step 5: Retirer le dernier `text-[9px]` de `PodiumsList`**

Dans `frontend/components/club/PodiumsList.tsx:78`, remplacer

```tsx
                  <span className="micro-label text-[9px]">{podiumScopeLabel(best.scope)}</span>
```

par

```tsx
                  <span className="micro-label">{podiumScopeLabel(best.scope)}</span>
```

C'est le dernier reliquat du temps où `.micro-label` n'était déclarée nulle part
(#470) : la classe porte désormais sa propre taille.

- [ ] **Step 6: Vérifier l'ensemble**

```bash
cd frontend && npm test && npm run lint && npm run build
```

Attendu : PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/charts/MonthlyTrend.tsx \
        frontend/components/charts/MonthlyTrend.test.tsx \
        frontend/components/club/PodiumsList.tsx
git commit -m "fix(a11y): monthly bars show their value without a hover

Refs #480"
```

---

## Task 4: `BarList` et `CategoryBars` — barre visible et alternative textuelle

**Files:**
- Modify: `frontend/components/charts/BarList.tsx`
- Modify: `frontend/components/charts/CategoryBars.tsx`
- Create: `frontend/components/charts/BarList.test.tsx`
- Test: `frontend/components/charts/CategoryBars.test.tsx`

**Interfaces:**
- `BarList({ entries, labeller, colorer, emptyTitle })` — signature inchangée.
- `CategoryBars({ categories, total })` — signature inchangée.

**Contexte.** Le `BarList` de `/club` s'étend de 1 à 279 sur une échelle
linéaire : 8 lignes sur 14 rendent une barre invisible. L'échelle **reste
linéaire** — une racine ferait lire 279 contre 1 comme un rapport de 17, que le
chiffre affiché à droite dément aussitôt. On pose seulement un plancher de
largeur, comme `MonthlyTrend` le fait déjà à 4 %.

Ni l'un ni l'autre composant ne porte de `role`, `aria-*`, `<title>` ou `<desc>`.

- [ ] **Step 1: Écrire le test de `BarList` qui échoue**

Créer `frontend/components/charts/BarList.test.tsx` :

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BarList } from "./BarList";

const ETALE: [string, number][] = [
  ["a", 279],
  ["b", 40],
  ["c", 1],
];

describe("BarList", () => {
  it("garde une barre visible sur deux ordres de grandeur", () => {
    // 1 sur un maximum de 279 vaut 0,36 % : la barre disparaissait. Le plancher
    // la rend visible sans toucher à l'échelle — la valeur exacte reste écrite
    // à droite, c'est elle qui porte la comparaison fine.
    const { container } = render(<BarList entries={ETALE} labeller={(k) => k} />);
    const barres = [...container.querySelectorAll("[data-bar]")] as HTMLElement[];
    expect(barres[0].style.width).toBe("100%");
    expect(parseFloat(barres[2].style.width)).toBeGreaterThanOrEqual(2);
  });

  it("reste strictement linéaire entre deux valeurs au-dessus du plancher", () => {
    const { container } = render(
      <BarList entries={[["a", 100], ["b", 50]]} labeller={(k) => k} />,
    );
    const barres = [...container.querySelectorAll("[data-bar]")] as HTMLElement[];
    expect(barres[1].style.width).toBe("50%");
  });

  it("récapitule la répartition pour un lecteur d'écran", () => {
    render(<BarList entries={ETALE} labeller={(k) => k.toUpperCase()} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Répartition sur 3 entrées : A 279, B 40, C 1.",
    );
  });

  it("rend l'état vide sans récapitulatif", () => {
    render(<BarList entries={[]} labeller={(k) => k} emptyTitle="Aucune donnée" />);
    expect(screen.getByText("Aucune donnée")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
  });
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
cd frontend && npx vitest run components/charts/BarList.test.tsx
```

Attendu : ÉCHEC — `[data-bar]` ne rend aucun élément, `getByRole("img")` ne
trouve rien.

- [ ] **Step 3: Modifier `BarList`**

Dans `frontend/components/charts/BarList.tsx`, après la ligne
`const max = Math.max(1, ...entries.map(([, v]) => v));`, ajouter :

```tsx
  // Plancher de largeur : sur /club l'étendue va de 1 à 279, soit 0,36 % pour la
  // plus petite barre. L'échelle reste **linéaire** — une racine ferait lire ce
  // rapport de 279 comme un rapport de 17, que le chiffre à droite dément — et
  // c'est seulement la visibilité de la barre qu'on garantit.
  const LARGEUR_MINIMALE = 2;
  const resume = entries
    .map(([key, value]) => `${labeller(key)} ${value}`)
    .join(", ");
```

Puis remplacer le conteneur et la barre :

```tsx
    <div
      role="img"
      aria-label={`Répartition sur ${entries.length} entrées : ${resume}.`}
      className="space-y-2.5"
    >
```

```tsx
            <div
              data-bar
              className="h-full rounded-full"
              style={{
                width: `${Math.max(LARGEUR_MINIMALE, (value / max) * 100)}%`,
                background: colorer ? colorer(key) : "var(--accent-ink)",
              }}
            />
```

(`transition-[width] duration-500` disparaît : elle ne jouait qu'une fois, au
montage, et n'a aucun effet au rendu serveur.)

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

```bash
cd frontend && npx vitest run components/charts/BarList.test.tsx
```

Attendu : PASS.

- [ ] **Step 5: Écrire le test d'alternative textuelle de `CategoryBars`**

Ajouter dans `frontend/components/charts/CategoryBars.test.tsx` :

```tsx
  it("récapitule la répartition pour un lecteur d'écran", () => {
    render(
      <CategoryBars
        categories={[
          { name: "V1", count: 30 },
          { name: "S", count: 20 },
        ]}
        total={100}
      />,
    );
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Répartition par catégorie : V1 30,0 %, S 20,0 %.",
    );
  });
```

`screen` est déjà importé dans ce fichier.

- [ ] **Step 6: Lancer le test pour vérifier qu'il échoue**

```bash
cd frontend && npx vitest run components/charts/CategoryBars.test.tsx
```

Attendu : ÉCHEC — `getByRole("img")` ne trouve rien.

- [ ] **Step 7: Modifier `CategoryBars`**

Dans `frontend/components/charts/CategoryBars.tsx`, après la ligne
`const scale = total > 0 ? … : () => 0;`, ajouter :

```tsx
  const resume = categories.map((c) => `${c.name} ${pctFr(scale(c.count))} %`).join(", ");
```

et donner son rôle au conteneur :

```tsx
    <div
      role="img"
      aria-label={`Répartition par catégorie : ${resume}.`}
      style={{ display: "flex", flexDirection: "column", gap: 10 }}
    >
```

- [ ] **Step 8: Lancer les deux suites**

```bash
cd frontend && npx vitest run components/charts/BarList.test.tsx components/charts/CategoryBars.test.tsx
```

Attendu : PASS.

- [ ] **Step 9: Vérifier l'ensemble et commit**

```bash
cd frontend && npm test && npm run lint && npm run build
```

```bash
git add frontend/components/charts/BarList.tsx frontend/components/charts/BarList.test.tsx \
        frontend/components/charts/CategoryBars.tsx frontend/components/charts/CategoryBars.test.tsx
git commit -m "fix(a11y): visible bars across two orders of magnitude, and a text alternative

Refs #480"
```

---

## Task 5: `Histogram` — la géométrie reste en SVG, les textes passent en HTML

**Files:**
- Modify: `frontend/components/charts/Histogram.tsx`
- Test: `frontend/components/charts/Histogram.test.tsx`

**Interfaces:**
- `Histogram({ bars, max, startSec, bucketSec })` — signature inchangée.
- Consomme : `buildTicks(startSec, endSec)` et `formatTickLabel(sec)` de
  `@/lib/utils/histogram-ticks` — inchangés.

**Contexte, à lire avant de coder.** Avec `viewBox` fixe et `width: 100%`,
**aucune unité CSS ne fige la taille d'un `<text>` SVG en px** : tout est mis à
l'échelle avec le `viewBox`. Desktop ~900 px contre iPhone SE ~287 px, soit un
rapport de 3:1 — aucune valeur de `fontSize` ne sert les deux, et les
graduations tombent à 3,5 px sur téléphone.

La sortie : **le SVG cesse de porter du texte**, et les libellés deviennent du
HTML dimensionné en px réels. Pour que ces libellés HTML restent **alignés** sur
la géométrie, le SVG doit avoir une hauteur en px fixe et non `height: auto` —
d'où `preserveAspectRatio="none"` avec `height: {H}` : l'axe X s'étire, l'axe Y
reste à 1 unité de `viewBox` pour 1 px, donc une ordonnée du `viewBox` est
directement une position en px pour le HTML. Les traits reçoivent
`vectorEffect="non-scaling-stroke"` pour ne pas s'amincir avec l'étirement ; les
barres sont des aplats sans contour, l'étirement ne les gêne pas.

Les positions X du HTML s'expriment en **pourcentage** (`x / W * 100`), qui suit
l'étirement sans le connaître.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter ces quatre `it` dans le `describe("Histogram")` de
`frontend/components/charts/Histogram.test.tsx` :

```tsx
  it("ne met plus aucun texte dans le SVG", () => {
    // Un <text> dans un viewBox étiré à width:100% se réduit à 3,5px sur un
    // iPhone SE (facteur 0,32). Aucune unité CSS ne l'en empêche : le texte doit
    // sortir du SVG (#480, RESP-2).
    const { container } = render(
      <Histogram bars={[1, 2, 3]} max={3} startSec={0} bucketSec={300} />,
    );
    expect(container.querySelectorAll("svg text").length).toBe(0);
  });

  it("garde une hauteur en pixels, pour que les libellés HTML s'alignent", () => {
    const { container } = render(
      <Histogram bars={[1, 2, 3]} max={3} startSec={0} bucketSec={300} />,
    );
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("preserveAspectRatio")).toBe("none");
    expect((svg as unknown as HTMLElement).style.height).toBe("200px");
  });

  it("gradue l'axe Y de 0 au maximum, en HTML", () => {
    const { container } = render(
      <Histogram bars={[10]} max={10} startSec={0} bucketSec={60} />,
    );
    const graduations = [...container.querySelectorAll("[data-y-tick]")].map(
      (n) => n.textContent,
    );
    expect(graduations).toContain("0");
    expect(graduations).toContain("10");
  });

  it("récapitule la distribution pour un lecteur d'écran", () => {
    render(<Histogram bars={[2, 5, 3]} max={5} startSec={1800} bucketSec={300} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Distribution des temps d'arrivée, de 0:30 à 0:45, maximum 5 finishers sur une tranche.",
    );
  });
```

Ajouter `screen` à l'import de `@testing-library/react`.

Adapter enfin les **deux tests préexistants** qui lisent les `<text>` du SVG —
« gradue l'axe Y de 0 au maximum » (remplacé par le nouveau, à supprimer) et
« aligne les graduations X sur des multiples ronds du pas (#129) », qui devient :

```tsx
  it("aligne les graduations X sur des multiples ronds du pas (#129)", () => {
    // 6 tranches de 15 min = 90 min de fenêtre → pas de 15 min (histogram-ticks.ts).
    const { container } = render(
      <Histogram bars={[1, 1, 1, 1, 1, 1]} max={1} startSec={0} bucketSec={900} />,
    );
    const labels = [...container.querySelectorAll("[data-x-tick]")].map((t) => t.textContent);
    expect(labels).toContain("0:15");
    expect(labels).toContain("1:30");
  });
```

Le test « reste un bandeau large plutôt qu'un pavé » garde son sens : il lit le
`viewBox`, qui reste `0 0 900 200`.

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
cd frontend && npx vitest run components/charts/Histogram.test.tsx
```

Attendu : ÉCHEC — le SVG contient encore des `<text>`, `[data-y-tick]` et
`[data-x-tick]` ne rendent rien.

- [ ] **Step 3: Réécrire `Histogram.tsx`**

Remplacer **tout** le contenu de `frontend/components/charts/Histogram.tsx` par :

```tsx
import { scaleLinear } from "d3-scale";
import { buildTicks, formatTickLabel } from "@/lib/utils/histogram-ticks";

// Espace de tracé. `W` n'est plus qu'un système de coordonnées horizontal : le
// SVG s'étire à la largeur disponible (`preserveAspectRatio="none"`), donc une
// abscisse ne vaut qu'en **pourcentage** de W. `H`, lui, est en pixels réels —
// la hauteur du SVG est fixée, ce qui permet aux libellés HTML de s'aligner sur
// les ordonnées de la géométrie sans connaître la largeur rendue.
const W = 900;
const H = 200;
const TOP = 12;
const BOTTOM = 188;
const Y_TICKS = 5;

/**
 * Distribution des temps d'arrivée d'une épreuve.
 *
 * **Le SVG ne porte aucun texte** (#480, RESP-2). Un `<text>` dans un `viewBox`
 * étiré à `width: 100%` est mis à l'échelle avec lui : sur iPhone SE le facteur
 * vaut 0,32 et les graduations tombent à 3,5 px, sans qu'aucune unité CSS ne
 * puisse les en empêcher. Les libellés sont donc du HTML, en px réels, posés
 * autour de la géométrie.
 *
 * Rendu serveur pur : aucun état, aucun survol, aucune hydratation.
 */
export function Histogram({
  bars,
  max,
  startSec,
  bucketSec,
}: {
  bars: number[];
  max: number;
  startSec: number;
  bucketSec: number;
}) {
  const barGap = W / Math.max(1, bars.length);
  const barW = Math.max(4, barGap * 0.72);

  // Domaine [0, max] → pixel [BOTTOM, TOP] (plus de finishers = plus haut).
  // Repli constant si max=0 : scaleLinear diviserait par un domaine nul.
  const yScale = max > 0 ? scaleLinear().domain([0, max]).range([BOTTOM, TOP]) : () => BOTTOM;

  const endSec = startSec + bars.length * bucketSec;
  const xTicks = bars.length > 0 ? buildTicks(startSec, endSec) : [];
  const secToPct = (sec: number) => (((sec - startSec) / bucketSec) * barGap * 100) / W;

  // Graduations Y : position i-basée, PAS yScale(v). `v` est arrondi, et router
  // par l'échelle décale les graduations quand max n'est pas divisible par
  // Y_TICKS — et les collapse toutes à BOTTOM quand max=0. Régression déjà
  // rencontrée, gardée par les tests max=3 / max=0.
  const yTicks = Array.from({ length: Y_TICKS + 1 }, (_, i) => ({
    valeur: Math.round((max / Y_TICKS) * i),
    y: BOTTOM - (i / Y_TICKS) * (BOTTOM - TOP),
  }));

  const resume =
    bars.length === 0
      ? "Distribution des temps d'arrivée : aucune donnée."
      : `Distribution des temps d'arrivée, de ${formatTickLabel(startSec)} à ` +
        `${formatTickLabel(endSec)}, maximum ${max} finishers sur une tranche.`;

  return (
    <div role="img" aria-label={resume} style={{ position: "relative", paddingLeft: 34, paddingBottom: 20 }}>
      {/* Graduations Y, en px réels : `top` vaut directement l'ordonnée du
          viewBox, la hauteur du SVG étant fixée à H pixels. */}
      {yTicks.map(({ valeur, y }) => (
        <span
          key={valeur + "-" + y}
          data-y-tick
          aria-hidden
          style={{
            position: "absolute",
            left: 0,
            top: y - 7,
            width: 28,
            textAlign: "right",
            fontSize: 11,
            lineHeight: "14px",
            color: "var(--tcn-text-faint)",
            fontFamily: "var(--tcn-font-body)",
          }}
        >
          {valeur}
        </span>
      ))}

      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ width: "100%", height: H, display: "block" }}
      >
        {yTicks.map(({ y }) => (
          <line
            key={y}
            x1={0}
            y1={y}
            x2={W}
            y2={y}
            stroke="var(--tcn-border-faint)"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {bars.map((count, i) => {
          const y = yScale(count);
          return (
            <rect
              key={i}
              x={i * barGap}
              y={y}
              width={barW}
              height={BOTTOM - y}
              rx="2"
              fill="var(--tcn-orange)"
            />
          );
        })}
        {xTicks.map((tickSec) => (
          <line
            key={tickSec}
            x1={(secToPct(tickSec) * W) / 100}
            y1={TOP}
            x2={(secToPct(tickSec) * W) / 100}
            y2={BOTTOM}
            stroke="var(--tcn-border-faint)"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>

      {/* Libellés de l'axe X, en px réels. `left` est un pourcentage : il suit
          l'étirement horizontal sans avoir à le connaître. */}
      {xTicks.map((tickSec) => (
        <span
          key={tickSec}
          data-x-tick
          aria-hidden
          style={{
            position: "absolute",
            left: `calc(34px + ${secToPct(tickSec)}% - 20px)`,
            bottom: 0,
            width: 40,
            textAlign: "center",
            fontSize: 11,
            lineHeight: "14px",
            color: "var(--tcn-text-faint)",
            fontFamily: "var(--tcn-font-body)",
          }}
        >
          {formatTickLabel(tickSec)}
        </span>
      ))}
    </div>
  );
}
```

**Attention au test préexistant « bandeau large »** : il lit `viewBox` et exige
`h / w <= 0.3`. Avec `0 0 900 200`, le rapport vaut 0,22 — il passe.

**Attention aux tests de graduations Y** : ils comptent 6 lignes horizontales et
un pas constant. Avec `TOP = 12` et `BOTTOM = 188`, le pas vaut
`(188 - 12) / 5 = 35,2`. Les deux tests attendent `expectedStep = 34` : mettre
cette constante à jour dans les deux, en remplaçant le commentaire par
`// (BOTTOM - TOP) / Y_TICKS = (188 - 12) / 5 = 35.2`.

Enfin, ces deux tests filtrent les lignes horizontales par
`line.getAttribute("x1") !== line.getAttribute("x2")` : c'est toujours vrai
(`x1=0`, `x2=900`), le filtre continue de fonctionner.

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

```bash
cd frontend && npx vitest run components/charts/Histogram.test.tsx
```

Attendu : PASS sur les 9 tests.

- [ ] **Step 5: Vérifier l'ensemble et commit**

```bash
cd frontend && npm test && npm run lint && npm run build
```

```bash
git add frontend/components/charts/Histogram.tsx frontend/components/charts/Histogram.test.tsx
git commit -m "fix(frontend): histogram labels leave the viewBox scale

Refs #480"
```

---

## Task 6: `RankingEvolutionChart` — libellés HTML et positions en clair

**Files:**
- Modify: `frontend/components/tcn/participation-detail/RankingEvolutionChart.tsx`
- Test: `frontend/components/tcn/participation-detail/RankingEvolutionChart.test.tsx`

**Interfaces:**
- `RankingEvolutionChart({ steps, eventType })` — signature inchangée.
- Consomme : `splitColumnsFromKeys(eventType, segments)` de `@/lib/utils/splits`.

**Contexte.** Même défaut que `Histogram` (`WIDTH = 1000`, `fontSize={12}` →
3,8 px sur iPhone SE), plus un défaut propre : **la position de chaque étape
n'existe que dans l'infobulle au survol**. Au doigt, la courbe montre un sens de
variation sans jamais dire de quelle place à quelle place (WCAG 1.4.13).

Traitement identique : `preserveAspectRatio="none"` + hauteur en px,
`vectorEffect="non-scaling-stroke"` sur la courbe et les axes. **Les points de
la courbe deviennent des marqueurs HTML** absolument positionnés : un `<circle>`
dans un SVG étiré non uniformément rend une ellipse. Les barres de segment sont
des aplats, l'étirement ne les gêne pas. L'infobulle reste ce qu'elle est — elle
n'est plus le seul accès au chiffre, ce qui était le grief.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter dans `frontend/components/tcn/participation-detail/RankingEvolutionChart.test.tsx` :

```tsx
  it("ne met plus aucun texte dans le SVG", () => {
    const { container } = renderChart();
    expect(container.querySelectorAll("svg text").length).toBe(0);
  });

  it("écrit la position de chaque étape sans survol", () => {
    // WCAG 1.4.13 : l'infobulle au survol était le seul accès au chiffre, donc
    // au doigt la courbe ne disait de quelle place à quelle place on allait.
    // `getAllByText` et non `getByText` : STEPS porte deux fois la position 91.
    renderChart();
    for (const etape of STEPS) {
      expect(screen.getAllByText(String(etape.scratch_position)).length).toBeGreaterThan(0);
    }
  });

  it("garde une hauteur en pixels, pour que les libellés HTML s'alignent", () => {
    const { container } = renderChart();
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("preserveAspectRatio")).toBe("none");
    expect((svg as unknown as HTMLElement).style.height).toBe("210px");
  });
```

`STEPS` et `renderChart()` sont la fixture et le helper déjà en tête de ce
fichier — les réutiliser tels quels. `screen` y est déjà importé.

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
cd frontend && npx vitest run components/tcn/participation-detail/RankingEvolutionChart.test.tsx
```

Attendu : ÉCHEC — le SVG contient encore des `<text>` et sa hauteur est `auto`.

- [ ] **Step 3: Modifier les constantes de géométrie**

Dans `frontend/components/tcn/participation-detail/RankingEvolutionChart.tsx`,
remplacer le bloc de constantes en tête de fichier par :

```tsx
// `WIDTH` n'est plus qu'un système de coordonnées horizontal : le SVG s'étire à
// la largeur disponible (`preserveAspectRatio="none"`), donc une abscisse ne
// vaut qu'en **pourcentage** de WIDTH. `HEIGHT` est en pixels réels — hauteur
// fixée, pour que les libellés HTML s'alignent sur les ordonnées de la
// géométrie sans connaître la largeur rendue (#480, RESP-2).
const WIDTH = 1000;
const HEIGHT = 210;
const PAD = { top: 14, right: 0, bottom: 10, left: 0 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;
const BAR_W = 44;

// Gouttières **en pixels**, hors du SVG : la colonne des graduations à gauche,
// la rangée des libellés d'étape en bas.
const GOUTTIERE_GAUCHE = 40;
const GOUTTIERE_BAS = 34;

// Nombre de graduations de l'axe des positions, bornes comprises.
const TICKS = 4;

const TOOLTIP_W = 210;
const TOOLTIP_H = 52;
```

- [ ] **Step 4: Sortir les textes du SVG**

Toujours dans le même fichier, remplacer le `<svg>` et son contenu par le bloc
ci-dessous. La `<Card>`, l'`<Eyebrow>` et la légende `data-legend` **ne changent
pas** ; le `Tooltip` en bas de fichier non plus.

```tsx
      <div style={{ position: "relative", paddingLeft: GOUTTIERE_GAUCHE, paddingBottom: GOUTTIERE_BAS, marginTop: 12 }}>
        {/* Graduations de position, en px réels. La 1re place est en haut :
            l'axe est inversé, et ses bornes viennent des positions réellement
            atteintes sur cette course. */}
        {ticks.map((position) => (
          <span
            key={position}
            data-tick=""
            aria-hidden
            style={{
              position: "absolute",
              left: 0,
              top: yOf(position) - 7,
              width: GOUTTIERE_GAUCHE - 10,
              textAlign: "right",
              fontSize: 12,
              lineHeight: "14px",
              color: "var(--tcn-text-faint)",
            }}
          >
            {position}
          </span>
        ))}

        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          style={{ width: "100%", height: HEIGHT, display: "block" }}
          role="presentation"
          onMouseLeave={() => setHovered(null)}
        >
          {ticks.map((position) => (
            <line
              key={position}
              x1={0}
              y1={yOf(position)}
              x2={PLOT_W}
              y2={yOf(position)}
              stroke="var(--tcn-border-faint)"
              vectorEffect="non-scaling-stroke"
            />
          ))}

          {steps.map((step, index) => {
            const label = labels.get(step.segment) ?? step.segment;
            const x = xOf(index);
            const barY = yOf(step.segment_position);
            return (
              <rect
                key={step.segment}
                data-step={step.segment}
                data-role="segment"
                data-y={barY}
                x={x - BAR_W / 2}
                y={barY}
                width={BAR_W}
                height={Math.max(1, PAD.top + PLOT_H - barY)}
                fill="var(--tcn-orange-12)"
                onMouseEnter={() => setHovered({ step, label, role: "segment", x, y: barY })}
              />
            );
          })}

          <path
            d={line}
            fill="none"
            stroke="var(--tcn-orange)"
            strokeWidth={2.5}
            vectorEffect="non-scaling-stroke"
          />

          {hovered && <Tooltip hovered={hovered} />}
        </svg>

        {/* Les points de la courbe sont du HTML : un <circle> dans un viewBox
            étiré non uniformément rendrait une ellipse. */}
        {steps.map((step, index) => {
          const label = labels.get(step.segment) ?? step.segment;
          const pointY = yOf(step.scratch_position);
          return (
            <span
              key={step.segment}
              data-step={step.segment}
              data-role="scratch"
              data-y={pointY}
              aria-hidden
              onMouseEnter={() =>
                setHovered({ step, label, role: "scratch", x: xOf(index), y: pointY })
              }
              style={{
                position: "absolute",
                left: `calc(${GOUTTIERE_GAUCHE}px + ${(xOf(index) / WIDTH) * 100}% - 6px)`,
                top: pointY - 6,
                width: 12,
                height: 12,
                borderRadius: 999,
                background: "var(--tcn-orange)",
              }}
            />
          );
        })}

        {/* Nom de l'étape **et sa position**, écrits en permanence : l'infobulle
            au survol n'existe pas au doigt (WCAG 1.4.13, #480). */}
        {steps.map((step, index) => (
          <span
            key={step.segment}
            data-step-label={step.segment}
            style={{
              position: "absolute",
              left: `calc(${GOUTTIERE_GAUCHE}px + ${(xOf(index) / WIDTH) * 100}% - 40px)`,
              bottom: 0,
              width: 80,
              textAlign: "center",
              fontSize: 12,
              lineHeight: "15px",
              color: "var(--tcn-text-faint)",
            }}
          >
            {labels.get(step.segment) ?? step.segment}
            <br />
            <b style={{ color: "var(--tcn-ink)" }}>{step.scratch_position}</b>
          </span>
        ))}
      </div>
```

Le récapitulatif accessible monte d'un cran : `role="img"` +
`aria-label="Évolution de la position au fil des étapes"` quittent le `<svg>`
(devenu `role="presentation"`) pour le `<div>` conteneur — c'est lui qui porte
désormais le graphique entier, points et libellés compris. Ajouter donc
`role="img" aria-label="Évolution de la position au fil des étapes"` sur ce
`<div>`.

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

```bash
cd frontend && npx vitest run components/tcn/participation-detail/RankingEvolutionChart.test.tsx
```

Attendu : PASS. Les tests préexistants lisent `[data-step]`, `[data-role]` et
`[data-y]`, tous conservés — si l'un échoue, c'est un attribut oublié dans la
réécriture, pas un test à ajuster.

- [ ] **Step 6: Vérifier l'ensemble et commit**

```bash
cd frontend && npm test && npm run lint && npm run build
```

```bash
git add frontend/components/tcn/participation-detail/RankingEvolutionChart.tsx \
        frontend/components/tcn/participation-detail/RankingEvolutionChart.test.tsx
git commit -m "fix(a11y): ranking positions are written, not hidden behind a hover

Refs #480"
```

---

## Fin de branche

Une fois les six tâches passées, le cycle de `docs/WORKFLOW-IA.md` s'applique :

1. `superpowers:requesting-code-review`
2. Le sous-agent `ui-ux-review` — **la branche touche `frontend/`**, il juge du
   rendu, en lecture seule, sur déclenchement de l'utilisateur.
3. `superpowers:verification-before-completion`
4. `superpowers:finishing-a-development-branch`

La PR se lie à l'issue avec un mot-clé anglais : `Closes #480`.

## Ce que ce plan ne fait pas

- **L'échelle des splits reste à 1,45:1** entre `--bike` et `--run` : la palette
  ne permet pas de la séparer sans casser le seuil de texte, et rien n'y repose
  sur la couleur seule (§ 2.5 de la spec).
- **WCAG 1.4.11 sur les aplats** : `--tcn-orange-300` ne tient que 2,53:1 sur
  `--tcn-surface`. État antérieur, non relevé par l'audit, corrigeable seulement
  en re-arbitrant la rampe orange (#325).
- **Aucune nouvelle visualisation.** Ce lot est l'hygiène des six graphiques
  existants ; #466 se pose dessus.
