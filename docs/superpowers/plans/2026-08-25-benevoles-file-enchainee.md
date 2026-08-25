# File bénévole enchaînée et enregistrement unique — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire de `/benevoles` une file qui s'enchaîne d'elle-même après chaque validation ou rejet, et réduire son panneau de détail à un seul état de formulaire avec un seul enregistrement.

**Architecture:** Toute la logique métier passe dans deux modules purs (`lib/benevoles/brouillon.ts`, `lib/benevoles/file.ts`) testés sans DOM, puis dans deux hooks (`useBrouillon`, `useFileValidation`) qui portent l'état et les appels réseau. Les composants redeviennent présentationnels. Aucun changement backend : `PATCH /benevoles/participations/{id}` est déjà partiel (`exclude_unset`), et « un seul enregistrement » se fait en n'appelant que les routes dont les champs ont bougé.

**Tech Stack:** Next.js 16 (App Router, composants client), TypeScript, React 19, vitest + @testing-library/react + userEvent, sonner (toasts, `Toaster` déjà monté), `components/ui/sheet` (Base UI), `components/tcn` (Button, Card, Input, AnnonceStatut).

**Spec:** `docs/superpowers/specs/2026-08-25-benevoles-file-enchainee-design.md`

## Global Constraints

- **Langue** (Principe I de la constitution) : **français** pour tout ce qui est visible utilisateur — libellés, messages d'erreur, textes de toast, titres de tests. **English** pour les identifiants purement techniques et les préfixes Conventional Commits. Les identifiants métier existants de ce périmètre sont déjà en français (`participations`, `rejetees`, `enCours…`) — on suit l'existant du dossier.
- **Pas de compatibilité ascendante** : « Enregistrer le nom » et « Enregistrer les modifications » disparaissent. Les tests qui les cherchent sont réécrits, pas conservés.
- **Aucun changement dans `backend/`.** Si une tâche semble en exiger un, s'arrêter et le signaler.
- **Identité visuelle non rejugée** (#460, #325) : jetons `--tcn-*`, polices Anton/Barlow, frontière `components/tcn/` ↔ `components/ui/` telles quelles.
- **Environnements vitest** : `vitest.config.ts` envoie tout `*.test.tsx` sous **jsdom** et tout `*.test.ts` sous **node**, sauf trois fichiers listés nommément. Donc : un test qui a besoin d'un DOM ou de `renderHook` **doit** s'appeler `.test.tsx`. Un test pur s'appelle `.test.ts`. Ne pas modifier `GLOBS_JSDOM` — `test/environments.test.ts` garde la partition.
- **Commandes** (depuis `frontend/`) : `npm test -- <chemin>` pour un fichier, `npm test` pour la suite, `npm run lint`, `npm run build`.
- **Commits** : Conventional Commits, corps français, `Refs #490` en pied.

---

## Structure des fichiers

| Fichier | Responsabilité | État |
| --- | --- | --- |
| `lib/benevoles/brouillon.ts` | Pur. Type `Brouillon`, initialisation depuis une `Participation`, détection de divergence, validation de saisie, plan d'enregistrement, rebasage après succès partiel. | Créer |
| `lib/benevoles/brouillon.test.ts` | Tests purs (node). | Créer |
| `lib/benevoles/file.ts` | Pur. Choix de l'entrée suivante après retrait. | Créer |
| `lib/benevoles/file.test.ts` | Tests purs (node). | Créer |
| `components/benevoles/useFileValidation.ts` | Chargement, listes, sélection, enchaînement, compteur de session, toasts, texte d'annonce. | Créer |
| `components/benevoles/useFileValidation.test.tsx` | Tests hook (jsdom). | Créer |
| `components/benevoles/useBrouillon.ts` | État du formulaire unique, `enregistrer()`, `validerLeResultat()`. | Créer |
| `components/benevoles/useBrouillon.test.tsx` | Tests hook (jsdom). | Créer |
| `components/benevoles/ChampsParticipation.tsx` | Les cinq champs éditables + valeurs d'origine. Présentationnel. | Créer |
| `components/benevoles/ChampsParticipation.test.tsx` | Tests composant. | Créer |
| `components/benevoles/ReattributionField.tsx` | Recherche d'athlète, choix **différé** (aucune écriture). | Créer |
| `components/benevoles/ReattributionField.test.tsx` | Tests composant. | Créer |
| `hooks/useEstCompact.ts` | `true` sous le point de rupture `md` (767 px). | Créer |
| `components/benevoles/ParticipationPanel.tsx` | Présentation du détail, zone d'erreur unique, barre d'action collante. | Réécrire (393 l. → ~180) |
| `components/benevoles/ParticipationPanel.test.tsx` | Tests réécrits. | Réécrire |
| `components/benevoles/ValidationQueue.tsx` | Compteur de session, état vide de réussite. | Modifier |
| `components/benevoles/ValidationQueue.test.tsx` | Tests ajoutés. | Modifier |
| `app/benevoles/page.tsx` | Câblage du hook de file, feuille mobile, annonce a11y, garde-fou brouillon sale. | Réécrire (134 l. → ~120) |
| `app/benevoles/page.test.tsx` | Tests d'intégration de l'écran. | Créer |

---

## Task 1: Module pur du brouillon

**Files:**
- Create: `lib/benevoles/brouillon.ts`
- Test: `lib/benevoles/brouillon.test.ts`

**Interfaces:**
- Consumes: `Participation`, `AthleteBrief` de `@/lib/types`.
- Produces:
  - `type Brouillon = { nom_epreuve: string; bib_number: string; rank_overall: string; club: string; category: string; athlete_cible: AthleteBrief | null }`
  - `type Etape = { type: "nom_epreuve"; nom: string } | { type: "champs"; champs: ChampsModifies } | { type: "reattribution"; athleteId: number }`
  - `type ChampsModifies = { bib_number?: string | null; rank_overall?: number | null; club?: string | null; category?: string | null }`
  - `brouillonDepuis(p: Participation): Brouillon`
  - `estSale(b: Brouillon, p: Participation): boolean`
  - `erreurDeSaisie(b: Brouillon): string | null`
  - `planEnregistrement(b: Brouillon, p: Participation): Etape[]`
  - `rebaser(b: Brouillon, p: Participation, reussies: Etape["type"][]): Brouillon`
  - `LIBELLE_ETAPE: Record<Etape["type"], string>`

- [ ] **Step 1: Write the failing test**

Create `lib/benevoles/brouillon.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";
import {
  brouillonDepuis,
  erreurDeSaisie,
  estSale,
  planEnregistrement,
  rebaser,
} from "./brouillon";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };
const AUTRE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 10,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V2 M",
    bib_number: "412",
    rank_overall: 37,
    rank_category: null,
    rank_gender: null,
    total_time: "02:14:53",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

describe("brouillonDepuis", () => {
  it("rend les champs absents en chaîne vide plutôt qu'en null", () => {
    const b = brouillonDepuis(participation({ bib_number: null, rank_overall: null, club: null, category: null }));
    expect(b).toEqual({
      nom_epreuve: "Triathlon de Nantes",
      bib_number: "",
      rank_overall: "",
      club: "",
      category: "",
      athlete_cible: null,
    });
  });
});

describe("estSale", () => {
  it("est faux sur un brouillon jamais touché", () => {
    const p = participation();
    expect(estSale(brouillonDepuis(p), p)).toBe(false);
  });

  it("est vrai dès qu'un champ diverge", () => {
    const p = participation();
    expect(estSale({ ...brouillonDepuis(p), bib_number: "413" }, p)).toBe(true);
  });

  it("est vrai dès qu'un athlète cible est choisi", () => {
    const p = participation();
    expect(estSale({ ...brouillonDepuis(p), athlete_cible: AUTRE }, p)).toBe(true);
  });

  it("ignore un athlète cible identique à l'athlète courant", () => {
    const p = participation();
    expect(estSale({ ...brouillonDepuis(p), athlete_cible: ATHLETE }, p)).toBe(false);
  });
});

describe("erreurDeSaisie", () => {
  it("refuse un nom d'épreuve vide", () => {
    const b = { ...brouillonDepuis(participation()), nom_epreuve: "   " };
    expect(erreurDeSaisie(b)).toBe("Le nom de l'épreuve ne peut pas être vide.");
  });

  it("refuse une place au général qui n'est pas un entier positif", () => {
    const b = { ...brouillonDepuis(participation()), rank_overall: "0" };
    expect(erreurDeSaisie(b)).toBe("La place au général doit être un entier supérieur à zéro.");
  });

  it("accepte une place au général vide", () => {
    const b = { ...brouillonDepuis(participation()), rank_overall: "" };
    expect(erreurDeSaisie(b)).toBeNull();
  });
});

describe("planEnregistrement", () => {
  it("ne produit aucune étape sur un brouillon identique à l'origine", () => {
    const p = participation();
    expect(planEnregistrement(brouillonDepuis(p), p)).toEqual([]);
  });

  it("n'envoie que les champs qui ont bougé", () => {
    const p = participation();
    const plan = planEnregistrement({ ...brouillonDepuis(p), bib_number: "413" }, p);
    expect(plan).toEqual([{ type: "champs", champs: { bib_number: "413" } }]);
  });

  it("envoie null pour un champ effacé", () => {
    const p = participation();
    const plan = planEnregistrement({ ...brouillonDepuis(p), club: "" }, p);
    expect(plan).toEqual([{ type: "champs", champs: { club: null } }]);
  });

  it("convertit la place au général en nombre", () => {
    const p = participation();
    const plan = planEnregistrement({ ...brouillonDepuis(p), rank_overall: "12" }, p);
    expect(plan).toEqual([{ type: "champs", champs: { rank_overall: 12 } }]);
  });

  it("ordonne renommage, puis champs, puis réattribution", () => {
    const p = participation();
    const plan = planEnregistrement(
      { ...brouillonDepuis(p), nom_epreuve: "Triathlon de Nantes 2026", bib_number: "413", athlete_cible: AUTRE },
      p,
    );
    expect(plan.map((e) => e.type)).toEqual(["nom_epreuve", "champs", "reattribution"]);
    expect(plan[0]).toEqual({ type: "nom_epreuve", nom: "Triathlon de Nantes 2026" });
    expect(plan[2]).toEqual({ type: "reattribution", athleteId: 2 });
  });
});

describe("rebaser", () => {
  it("repose les champs enregistrés sur la participation renvoyée et garde les autres", () => {
    const p = participation();
    const sale = { ...brouillonDepuis(p), nom_epreuve: "Nouveau nom", bib_number: "413" };
    const apres = participation({ bib_number: "413" });

    const rebase = rebaser(sale, apres, ["champs"]);

    expect(rebase.bib_number).toBe("413");
    expect(estSale(rebase, apres)).toBe(true);
    expect(rebase.nom_epreuve).toBe("Nouveau nom");
  });

  it("efface l'athlète cible quand la réattribution est passée", () => {
    const p = participation();
    const sale = { ...brouillonDepuis(p), athlete_cible: AUTRE };
    expect(rebaser(sale, participation({ athlete: AUTRE }), ["reattribution"]).athlete_cible).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- lib/benevoles/brouillon.test.ts`
Expected: FAIL — `Failed to resolve import "./brouillon"`.

- [ ] **Step 3: Write minimal implementation**

Create `lib/benevoles/brouillon.ts`:

```ts
import type { AthleteBrief, Participation } from "@/lib/types";

/** Formulaire unique du panneau bénévole (#490, PROF-10) : un seul état,
 *  un seul enregistrement. Ce module est **pur** — ni React, ni réseau — pour
 *  que l'ordre des appels et le rattrapage d'un échec partiel se testent sans
 *  monter d'écran. */
export type Brouillon = {
  nom_epreuve: string;
  /** Chaînes et non nombres : les champs sont des `<input>`, et « vide »
   *  (effacement demandé) ne s'exprime pas en `number`. */
  bib_number: string;
  rank_overall: string;
  club: string;
  category: string;
  /** `null` = aucune réattribution demandée. Le choix est **différé** : il
   *  n'écrit qu'à l'enregistrement. */
  athlete_cible: AthleteBrief | null;
};

export type ChampsModifies = {
  bib_number?: string | null;
  rank_overall?: number | null;
  club?: string | null;
  category?: string | null;
};

export type Etape =
  | { type: "nom_epreuve"; nom: string }
  | { type: "champs"; champs: ChampsModifies }
  | { type: "reattribution"; athleteId: number };

/** Ce que l'erreur affiche quand une étape échoue : une zone d'erreur unique
 *  doit dire *laquelle*. */
export const LIBELLE_ETAPE: Record<Etape["type"], string> = {
  nom_epreuve: "Le nom de l'épreuve n'a pas pu être enregistré",
  champs: "Les champs n'ont pas pu être enregistrés",
  reattribution: "La réattribution n'a pas pu être enregistrée",
};

/** Les quatre champs portés par `PATCH /benevoles/participations/{id}`. */
const CHAMPS = ["bib_number", "rank_overall", "club", "category"] as const;

function texte(valeur: string | number | null | undefined): string {
  return valeur == null ? "" : String(valeur);
}

export function brouillonDepuis(participation: Participation): Brouillon {
  return {
    nom_epreuve: participation.course.name,
    bib_number: texte(participation.bib_number),
    rank_overall: texte(participation.rank_overall),
    club: texte(participation.club),
    category: texte(participation.category),
    athlete_cible: null,
  };
}

export function estSale(brouillon: Brouillon, participation: Participation): boolean {
  const origine = brouillonDepuis(participation);
  const champDiverge = (["nom_epreuve", ...CHAMPS] as const).some(
    (cle) => brouillon[cle].trim() !== origine[cle].trim(),
  );
  const reattribue =
    brouillon.athlete_cible != null && brouillon.athlete_cible.id !== participation.athlete.id;
  return champDiverge || reattribue;
}

export function erreurDeSaisie(brouillon: Brouillon): string | null {
  if (!brouillon.nom_epreuve.trim()) {
    return "Le nom de l'épreuve ne peut pas être vide.";
  }
  const place = brouillon.rank_overall.trim();
  if (place && (!/^\d+$/.test(place) || Number(place) < 1)) {
    return "La place au général doit être un entier supérieur à zéro.";
  }
  return null;
}

export function planEnregistrement(brouillon: Brouillon, participation: Participation): Etape[] {
  const origine = brouillonDepuis(participation);
  const plan: Etape[] = [];

  const nom = brouillon.nom_epreuve.trim();
  if (nom && nom !== origine.nom_epreuve.trim()) {
    plan.push({ type: "nom_epreuve", nom });
  }

  const champs: ChampsModifies = {};
  for (const cle of CHAMPS) {
    const valeur = brouillon[cle].trim();
    if (valeur === origine[cle].trim()) continue;
    // `null` et non `""` : le backend est nullable partout, et effacer un
    // dossard est un geste légitime du bénévole.
    champs[cle] = (cle === "rank_overall" ? (valeur ? Number(valeur) : null) : valeur || null) as never;
  }
  if (Object.keys(champs).length > 0) {
    plan.push({ type: "champs", champs });
  }

  if (brouillon.athlete_cible && brouillon.athlete_cible.id !== participation.athlete.id) {
    plan.push({ type: "reattribution", athleteId: brouillon.athlete_cible.id });
  }

  return plan;
}

/** Après un échec partiel, ce qui est passé est commité côté serveur : on
 *  repose ces champs sur la participation renvoyée, et on ne garde sale que ce
 *  qui n'a pas pu partir. */
export function rebaser(
  brouillon: Brouillon,
  participation: Participation,
  reussies: Etape["type"][],
): Brouillon {
  const origine = brouillonDepuis(participation);
  const rebase = { ...brouillon };
  if (reussies.includes("nom_epreuve")) rebase.nom_epreuve = origine.nom_epreuve;
  if (reussies.includes("champs")) {
    for (const cle of CHAMPS) rebase[cle] = origine[cle];
  }
  if (reussies.includes("reattribution")) rebase.athlete_cible = null;
  return rebase;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- lib/benevoles/brouillon.test.ts`
Expected: PASS — 15 tests.

- [ ] **Step 5: Commit**

```bash
git add lib/benevoles/brouillon.ts lib/benevoles/brouillon.test.ts
git commit -m "feat(490): brouillon unique du panneau bénévole, pur et testable

Diff, validation de saisie, plan d'enregistrement ordonné et rebasage
après échec partiel — sans React ni réseau.

Refs #490"
```

---

## Task 2: Choix de l'entrée suivante

**Files:**
- Create: `lib/benevoles/file.ts`
- Test: `lib/benevoles/file.test.ts`

**Interfaces:**
- Consumes: `Participation` de `@/lib/types`.
- Produces: `suivantApresRetrait(liste: Participation[], idRetire: number): number | null`

- [ ] **Step 1: Write the failing test**

Create `lib/benevoles/file.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { Participation } from "@/lib/types";
import { suivantApresRetrait } from "./file";

/** Seul l'`id` compte ici : la fonction ne lit rien d'autre. */
const liste = (...ids: number[]) => ids.map((id) => ({ id }) as Participation);

describe("suivantApresRetrait", () => {
  it("prend l'entrée qui glisse dans la place libérée", () => {
    expect(suivantApresRetrait(liste(1, 2, 3), 2)).toBe(3);
  });

  it("prend la précédente quand la dernière est retirée", () => {
    expect(suivantApresRetrait(liste(1, 2, 3), 3)).toBe(2);
  });

  it("rend null quand la file se vide", () => {
    expect(suivantApresRetrait(liste(1), 1)).toBeNull();
  });

  it("rend null quand l'entrée retirée n'était pas dans cette liste", () => {
    expect(suivantApresRetrait(liste(1, 2), 9)).toBeNull();
  });

  it("garde la première quand c'est la première qui part", () => {
    expect(suivantApresRetrait(liste(1, 2, 3), 1)).toBe(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- lib/benevoles/file.test.ts`
Expected: FAIL — `Failed to resolve import "./file"`.

- [ ] **Step 3: Write minimal implementation**

Create `lib/benevoles/file.ts`:

```ts
import type { Participation } from "@/lib/types";

/**
 * L'entrée à sélectionner après en avoir retiré une (#490, PROF-9).
 *
 * Celle qui prend la place libérée, à défaut la précédente, à défaut rien —
 * de sorte que `selectedId === null` avec une file non vide devienne un état
 * impossible, et que le bénévole n'ait plus à repointer à la main après chaque
 * validation.
 */
export function suivantApresRetrait(liste: Participation[], idRetire: number): number | null {
  const index = liste.findIndex((p) => p.id === idRetire);
  if (index === -1) return null;
  const restants = liste.filter((p) => p.id !== idRetire);
  if (restants.length === 0) return null;
  return (restants[index] ?? restants[restants.length - 1]).id;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- lib/benevoles/file.test.ts`
Expected: PASS — 5 tests.

- [ ] **Step 5: Commit**

```bash
git add lib/benevoles/file.ts lib/benevoles/file.test.ts
git commit -m "feat(490): choix de l'entrée suivante après retrait de la file

Refs #490"
```

---

## Task 3: Hook de file — enchaînement, compteur, toasts

**Files:**
- Create: `components/benevoles/useFileValidation.ts`
- Test: `components/benevoles/useFileValidation.test.tsx`

**Interfaces:**
- Consumes: `suivantApresRetrait` de `@/lib/benevoles/file` (Task 2) ; `apiClient`, `ApiError` de `@/lib/api/client` ; `toast` de `sonner`.
- Produces:
  ```ts
  type EtatFile = "chargement" | "gate" | "file" | "erreur";
  function useFileValidation(): {
    etat: EtatFile;
    participations: Participation[];
    rejetees: Participation[];
    selectedId: number | null;
    selectionnee: Participation | null;
    traitees: number;
    annonce: string;
    charger: () => Promise<void>;
    selectionner: (id: number) => void;
    surChangement: (maj: Participation) => void;
    surSessionExpiree: () => void;
  }
  ```

- [ ] **Step 1: Write the failing test**

Create `components/benevoles/useFileValidation.test.tsx`:

```tsx
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";

const { getBenevoleQueue, getBenevoleRejected, toastSuccess } = vi.hoisted(() => ({
  getBenevoleQueue: vi.fn(),
  getBenevoleRejected: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getBenevoleQueue, getBenevoleRejected } };
});
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: vi.fn() } }));

import { ApiError } from "@/lib/api/client";
import { useFileValidation } from "./useFileValidation";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };

function participation(id: number, over: Partial<Participation> = {}): Participation {
  return {
    id,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: null,
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

/** Monte le hook avec une file de trois entrées déjà chargée. */
async function monter(file = [participation(1), participation(2), participation(3)]) {
  getBenevoleQueue.mockResolvedValue(file);
  getBenevoleRejected.mockResolvedValue([]);
  const rendu = renderHook(() => useFileValidation());
  await waitFor(() => expect(rendu.result.current.etat).toBe("file"));
  return rendu;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useFileValidation", () => {
  it("charge la file et les non conformes", async () => {
    const { result } = await monter();
    expect(result.current.participations).toHaveLength(3);
    expect(result.current.rejetees).toHaveLength(0);
  });

  it("bascule sur la garde d'accès quand l'API répond 401", async () => {
    getBenevoleQueue.mockRejectedValue(new ApiError(401, "non autorisé"));
    getBenevoleRejected.mockRejectedValue(new ApiError(401, "non autorisé"));
    const { result } = renderHook(() => useFileValidation());
    await waitFor(() => expect(result.current.etat).toBe("gate"));
  });

  it("sélectionne l'entrée suivante après une validation", async () => {
    const { result } = await monter();
    act(() => result.current.selectionner(2));
    act(() => result.current.surChangement(participation(2, { is_pending_validation: false })));

    expect(result.current.selectedId).toBe(3);
    expect(result.current.participations.map((p) => p.id)).toEqual([1, 3]);
  });

  it("compte les entrées traitées dans la session", async () => {
    const { result } = await monter();
    expect(result.current.traitees).toBe(0);
    act(() => result.current.surChangement(participation(1, { is_pending_validation: false })));
    act(() => result.current.surChangement(participation(2, { is_rejected: true })));
    expect(result.current.traitees).toBe(2);
  });

  it("annonce le reste de la file après une validation", async () => {
    const { result } = await monter();
    act(() => result.current.surChangement(participation(1, { is_pending_validation: false })));
    expect(toastSuccess).toHaveBeenCalledWith("Résultat validé — 2 restants.");
    expect(result.current.annonce).toBe("Résultat validé — 2 restants.");
  });

  it("laisse la file vide et sans sélection quand la dernière entrée est validée", async () => {
    const { result } = await monter([participation(1)]);
    act(() => result.current.selectionner(1));
    act(() => result.current.surChangement(participation(1, { is_pending_validation: false })));

    expect(result.current.participations).toHaveLength(0);
    expect(result.current.selectedId).toBeNull();
    expect(toastSuccess).toHaveBeenCalledWith("Résultat validé — file vide.");
  });

  it("fait passer une entrée rejetée dans les non conformes et enchaîne", async () => {
    const { result } = await monter();
    act(() => result.current.selectionner(1));
    act(() => result.current.surChangement(participation(1, { is_rejected: true })));

    expect(result.current.participations.map((p) => p.id)).toEqual([2, 3]);
    expect(result.current.rejetees.map((p) => p.id)).toEqual([1]);
    expect(result.current.selectedId).toBe(2);
  });

  it("ne compte ni n'enchaîne sur un simple enregistrement de champs", async () => {
    const { result } = await monter();
    act(() => result.current.selectionner(2));
    act(() => result.current.surChangement(participation(2, { bib_number: "413" })));

    expect(result.current.selectedId).toBe(2);
    expect(result.current.traitees).toBe(0);
    expect(result.current.selectionnee?.bib_number).toBe("413");
  });

  it("ramène une entrée dé-rejetée dans la file sans la compter", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1)]);
    getBenevoleRejected.mockResolvedValue([participation(5, { is_rejected: true })]);
    const { result } = renderHook(() => useFileValidation());
    await waitFor(() => expect(result.current.etat).toBe("file"));

    act(() => result.current.surChangement(participation(5, { is_rejected: false })));

    expect(result.current.participations.map((p) => p.id)).toEqual([5, 1]);
    expect(result.current.rejetees).toHaveLength(0);
    expect(result.current.traitees).toBe(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/benevoles/useFileValidation.test.tsx`
Expected: FAIL — `Failed to resolve import "./useFileValidation"`.

- [ ] **Step 3: Write minimal implementation**

Create `components/benevoles/useFileValidation.ts`:

```ts
"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { apiClient, ApiError } from "@/lib/api/client";
import { suivantApresRetrait } from "@/lib/benevoles/file";
import type { Participation } from "@/lib/types";

export type EtatFile = "chargement" | "gate" | "file" | "erreur";

/** Reste à traiter, dit en français plutôt qu'en nombre nu. */
function reste(nombre: number): string {
  if (nombre === 0) return "file vide.";
  return nombre === 1 ? "1 restant." : `${nombre} restants.`;
}

/**
 * La file de validation bénévole et son enchaînement (#490, PROF-9).
 *
 * Le point clé est `surChangement` : jusqu'à #490 il remettait `selectedId` à
 * `null` après chaque validation, ce qui obligeait à repointer l'entrée
 * suivante à la main — le geste le plus fréquent de l'écran était le plus
 * coûteux.
 */
export function useFileValidation() {
  const [etat, setEtat] = useState<EtatFile>("chargement");
  const [participations, setParticipations] = useState<Participation[]>([]);
  const [rejetees, setRejetees] = useState<Participation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [traitees, setTraitees] = useState(0);
  const [annonce, setAnnonce] = useState("");

  const charger = useCallback(async () => {
    setEtat("chargement");
    try {
      const [resultats, rejets] = await Promise.all([
        apiClient.getBenevoleQueue(),
        apiClient.getBenevoleRejected(),
      ]);
      setParticipations(resultats);
      setRejetees(rejets);
      setEtat("file");
    } catch (err) {
      setEtat(err instanceof ApiError && err.status === 401 ? "gate" : "erreur");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  /** Retire l'entrée de la file, enchaîne sur la suivante, compte et annonce.
   *
   *  Lit `participations` dans la portée plutôt que via un updater : le toast
   *  est un effet de bord, et React peut rejouer un updater (StrictMode) —
   *  le bénévole verrait deux toasts pour une seule validation. */
  const retirerEtEnchainer = useCallback(
    (id: number, message: (restants: number) => string) => {
      const suivant = suivantApresRetrait(participations, id);
      const restants = participations.filter((p) => p.id !== id);
      setParticipations(restants);
      setSelectedId((courant) => (courant === id || courant === null ? suivant : courant));
      const texte = message(restants.length);
      toast.success(texte);
      setAnnonce(texte);
      setTraitees((n) => n + 1);
    },
    [participations],
  );

  const surChangement = useCallback(
    (maj: Participation) => {
      if (!maj.is_pending_validation) {
        setRejetees((liste) => liste.filter((p) => p.id !== maj.id));
        retirerEtEnchainer(maj.id, (restants) => `Résultat validé — ${reste(restants)}`);
        return;
      }
      if (maj.is_rejected) {
        setRejetees((liste) => [maj, ...liste.filter((p) => p.id !== maj.id)]);
        retirerEtEnchainer(
          maj.id,
          (restants) => `Résultat signalé non conforme — ${reste(restants)}`,
        );
        return;
      }
      // Rejet annulé : revient dans la file sans compter — ce n'est pas un
      // traitement, c'est son annulation.
      if (rejetees.some((p) => p.id === maj.id)) {
        setRejetees((liste) => liste.filter((p) => p.id !== maj.id));
        setParticipations((liste) => [maj, ...liste.filter((p) => p.id !== maj.id)]);
        return;
      }
      // Simple enregistrement de champs : on rafraîchit sur place, sans
      // enchaîner ni compter.
      setParticipations((liste) => liste.map((p) => (p.id === maj.id ? maj : p)));
    },
    [rejetees, retirerEtEnchainer],
  );

  const selectionnee =
    participations.find((p) => p.id === selectedId) ??
    rejetees.find((p) => p.id === selectedId) ??
    null;

  return {
    etat,
    participations,
    rejetees,
    selectedId,
    selectionnee,
    traitees,
    annonce,
    charger,
    selectionner: setSelectedId,
    surChangement,
    /** Cookie expiré ou mot de passe changé pendant que l'écran était ouvert. */
    surSessionExpiree: useCallback(() => setEtat("gate"), []),
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- components/benevoles/useFileValidation.test.tsx`
Expected: PASS — 9 tests.

- [ ] **Step 5: Commit**

```bash
git add components/benevoles/useFileValidation.ts components/benevoles/useFileValidation.test.tsx
git commit -m "feat(490): la file bénévole enchaîne sur l'entrée suivante

Sélection automatique après validation ou rejet, compteur de session,
confirmation brève doublée d'un texte d'annonce pour WCAG 4.1.3.

Refs #490"
```

---

## Task 4: Champ de réattribution différée

**Files:**
- Create: `components/benevoles/ReattributionField.tsx`
- Test: `components/benevoles/ReattributionField.test.tsx`

**Interfaces:**
- Consumes: `apiClient.searchAthletesBenevole` ; `AthleteBrief` de `@/lib/types` ; `Input` de `@/components/tcn`.
- Produces:
  ```tsx
  function ReattributionField(props: {
    athleteActuel: AthleteBrief;
    athleteCible: AthleteBrief | null;
    onChoisir: (athlete: AthleteBrief | null) => void;
    disabled?: boolean;
  }): JSX.Element
  ```

- [ ] **Step 1: Write the failing test**

Create `components/benevoles/ReattributionField.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AthleteBrief } from "@/lib/types";

const { searchAthletesBenevole, reassignParticipationBenevole } = vi.hoisted(() => ({
  searchAthletesBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { searchAthletesBenevole, reassignParticipationBenevole } };
});

import { ReattributionField } from "./ReattributionField";

const ACTUEL: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };
const CIBLE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ReattributionField", () => {
  it("choisit un athlète sans rien écrire côté serveur", async () => {
    const onChoisir = vi.fn();
    searchAthletesBenevole.mockResolvedValue([CIBLE]);
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={onChoisir} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Kerm");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));

    expect(onChoisir).toHaveBeenCalledWith(CIBLE);
    expect(reassignParticipationBenevole).not.toHaveBeenCalled();
  });

  it("annonce le choix en attente à côté de l'athlète d'origine", () => {
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={CIBLE} onChoisir={vi.fn()} />);
    expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument();
    expect(screen.getByText(/Mathieu HERRMANN/)).toBeInTheDocument();
  });

  it("permet d'annuler le choix en attente", async () => {
    const onChoisir = vi.fn();
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={CIBLE} onChoisir={onChoisir} />);
    await userEvent.click(screen.getByRole("button", { name: /Annuler ce choix/ }));
    expect(onChoisir).toHaveBeenCalledWith(null);
  });

  it("distingue une recherche en échec d'une recherche sans résultat", async () => {
    searchAthletesBenevole.mockRejectedValue(new Error("réseau"));
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Kerm");

    await waitFor(() =>
      expect(screen.getByText(/Recherche impossible pour le moment/)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Aucun coureur trouvé/)).not.toBeInTheDocument();
  });

  it("affiche un état vide quand la recherche ne trouve personne", async () => {
    searchAthletesBenevole.mockResolvedValue([]);
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Zzz");

    await waitFor(() => expect(screen.getByText(/Aucun coureur trouvé/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/benevoles/ReattributionField.test.tsx`
Expected: FAIL — `Failed to resolve import "./ReattributionField"`.

- [ ] **Step 3: Write minimal implementation**

Create `components/benevoles/ReattributionField.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button, Input } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import type { AthleteBrief } from "@/lib/types";

const nomComplet = (a: AthleteBrief) => `${a.prenom} ${a.nom}`;

/**
 * Recherche d'athlète et **choix différé** (#490, PROF-10).
 *
 * Jusqu'à #490 le clic sur un résultat écrivait immédiatement : c'était le
 * quatrième geste d'écriture non hiérarchisé du panneau. Ici il ne fait que
 * *choisir* ; l'enregistrement unique applique.
 */
export function ReattributionField({
  athleteActuel,
  athleteCible,
  onChoisir,
  disabled,
}: {
  athleteActuel: AthleteBrief;
  athleteCible: AthleteBrief | null;
  onChoisir: (athlete: AthleteBrief | null) => void;
  disabled?: boolean;
}) {
  const [recherche, setRecherche] = useState("");
  const [resultats, setResultats] = useState<AthleteBrief[] | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function rechercher(valeur: string) {
    setRecherche(valeur);
    setErreur(null);
    if (valeur.trim().length < 2) {
      setResultats(null);
      return;
    }
    setEnCours(true);
    try {
      setResultats(await apiClient.searchAthletesBenevole(valeur));
    } catch {
      // `null` et non `[]` : rendre une liste vide affichait « aucun coureur
      // trouvé » sur une recherche **en échec** (relevé en revue de #513), et
      // le bénévole en concluait que l'athlète n'existe pas.
      setResultats(null);
      setErreur("Recherche impossible pour le moment. Réessayez dans un instant.");
    } finally {
      setEnCours(false);
    }
  }

  function choisir(athlete: AthleteBrief) {
    setRecherche("");
    setResultats(null);
    onChoisir(athlete);
  }

  if (athleteCible) {
    return (
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Réattribuer à</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <strong>{nomComplet(athleteCible)}</strong>
          <span style={{ fontSize: 13, color: "var(--tcn-text-faint)" }}>
            au lieu de {nomComplet(athleteActuel)}
          </span>
          <Button variant="ghost" onClick={() => onChoisir(null)} disabled={disabled}>
            Annuler ce choix
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <label
        htmlFor="benevole-reattribution"
        style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}
      >
        Réattribuer à
      </label>
      <Input
        id="benevole-reattribution"
        value={recherche}
        onChange={(e) => rechercher(e.target.value)}
        placeholder="Nom du coureur"
        disabled={disabled}
        aria-describedby={erreur ? "benevole-reattribution-erreur" : undefined}
        style={{ width: "100%" }}
      />
      {enCours && (
        <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, marginTop: 8 }}>Recherche…</div>
      )}
      {!enCours && resultats !== null && resultats.length === 0 && (
        <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, marginTop: 8 }}>
          Aucun coureur trouvé.
        </div>
      )}
      {!enCours && resultats !== null && resultats.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
          {resultats.map((athlete) => (
            <button
              key={athlete.id}
              type="button"
              className="tcn-rowlink"
              onClick={() => choisir(athlete)}
              disabled={disabled}
              style={{
                textAlign: "left",
                padding: "8px 12px",
                minHeight: 44,
                border: "1px solid var(--tcn-border)",
                borderRadius: "var(--tcn-radius-md)",
                background: "var(--tcn-surface)",
              }}
            >
              {nomComplet(athlete)}
              {athlete.club && <span style={{ color: "var(--tcn-text-faint)" }}> · {athlete.club}</span>}
            </button>
          ))}
        </div>
      )}
      {erreur && (
        <div
          id="benevole-reattribution-erreur"
          role="alert"
          style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}
        >
          {erreur}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- components/benevoles/ReattributionField.test.tsx`
Expected: PASS — 5 tests.

- [ ] **Step 5: Commit**

```bash
git add components/benevoles/ReattributionField.tsx components/benevoles/ReattributionField.test.tsx
git commit -m "feat(490): la réattribution choisit sans écrire

Le clic sur un résultat de recherche entre dans le brouillon ; c'est
l'enregistrement unique qui applique.

Refs #490"
```

---

## Task 5: Champs éditables et valeurs d'origine

**Files:**
- Create: `components/benevoles/ChampsParticipation.tsx`
- Test: `components/benevoles/ChampsParticipation.test.tsx`

**Interfaces:**
- Consumes: `Brouillon`, `brouillonDepuis` de `@/lib/benevoles/brouillon` (Task 1) ; `Input` de `@/components/tcn`.
- Produces:
  ```tsx
  function ChampsParticipation(props: {
    brouillon: Brouillon;
    origine: Participation;
    onChange: (patch: Partial<Brouillon>) => void;
    disabled?: boolean;
  }): JSX.Element
  ```

- [ ] **Step 1: Write the failing test**

Create `components/benevoles/ChampsParticipation.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { brouillonDepuis } from "@/lib/benevoles/brouillon";
import type { AthleteBrief, Participation } from "@/lib/types";
import { ChampsParticipation } from "./ChampsParticipation";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 10,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V2 M",
    bib_number: "412",
    rank_overall: 37,
    rank_category: null,
    rank_gender: null,
    total_time: "02:14:53",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

describe("ChampsParticipation", () => {
  it("rend les cinq champs éditables", () => {
    const p = participation();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={vi.fn()} />);

    expect(screen.getByLabelText(/Nom de l'épreuve/)).toHaveValue("Triathlon de Nantes");
    expect(screen.getByLabelText(/Dossard/)).toHaveValue("412");
    expect(screen.getByLabelText(/Place au général/)).toHaveValue(37);
    expect(screen.getByLabelText("Club")).toHaveValue("TCN");
    expect(screen.getByLabelText(/Catégorie/)).toHaveValue("V2 M");
  });

  it("n'affiche aucune valeur d'origine tant que rien n'a bougé", () => {
    const p = participation();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={vi.fn()} />);
    expect(screen.queryByText(/Valeur d'origine/)).not.toBeInTheDocument();
  });

  it("affiche la valeur d'origine du seul champ modifié", () => {
    const p = participation();
    render(
      <ChampsParticipation
        brouillon={{ ...brouillonDepuis(p), bib_number: "413" }}
        origine={p}
        onChange={vi.fn()}
      />,
    );
    const origines = screen.getAllByText(/Valeur d'origine/);
    expect(origines).toHaveLength(1);
    expect(origines[0]).toHaveTextContent("Valeur d'origine : 412");
  });

  it("dit « vide » plutôt que rien pour une origine absente", () => {
    const p = participation({ club: null });
    render(
      <ChampsParticipation
        brouillon={{ ...brouillonDepuis(p), club: "TCN" }}
        origine={p}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/Valeur d'origine : vide/)).toBeInTheDocument();
  });

  it("remonte chaque frappe au parent", async () => {
    const p = participation({ bib_number: null });
    const onChange = vi.fn();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={onChange} />);

    await userEvent.type(screen.getByLabelText(/Dossard/), "4");

    expect(onChange).toHaveBeenCalledWith({ bib_number: "4" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/benevoles/ChampsParticipation.test.tsx`
Expected: FAIL — `Failed to resolve import "./ChampsParticipation"`.

- [ ] **Step 3: Write minimal implementation**

Create `components/benevoles/ChampsParticipation.tsx`:

```tsx
"use client";

import { Input } from "@/components/tcn";
import { brouillonDepuis, type Brouillon } from "@/lib/benevoles/brouillon";
import type { Participation } from "@/lib/types";

/** Les cinq champs du brouillon, dans l'ordre de lecture du panneau. */
const CHAMPS = [
  { cle: "nom_epreuve", id: "benevole-nom-epreuve", label: "Nom de l'épreuve", pleineLargeur: true },
  { cle: "bib_number", id: "benevole-dossard", label: "Dossard" },
  { cle: "rank_overall", id: "benevole-place", label: "Place au général", type: "number" },
  { cle: "club", id: "benevole-club", label: "Club" },
  { cle: "category", id: "benevole-categorie", label: "Catégorie" },
] as const satisfies ReadonlyArray<{
  cle: keyof Omit<Brouillon, "athlete_cible">;
  id: string;
  label: string;
  type?: string;
  pleineLargeur?: boolean;
}>;

/**
 * Les champs éditables du panneau bénévole, avec la **valeur d'origine à côté
 * des seuls champs modifiés** (#490, PROF-10).
 *
 * Purement présentationnel : il ne sait ni enregistrer ni valider. La
 * `Participation` complète est déjà en mémoire, donc la comparaison ne coûte
 * aucun appel.
 */
export function ChampsParticipation({
  brouillon,
  origine,
  onChange,
  disabled,
}: {
  brouillon: Brouillon;
  origine: Participation;
  onChange: (patch: Partial<Brouillon>) => void;
  disabled?: boolean;
}) {
  const valeursOrigine = brouillonDepuis(origine);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
      {CHAMPS.map(({ cle, id, label, ...reste }) => {
        const modifie = brouillon[cle].trim() !== valeursOrigine[cle].trim();
        const type = "type" in reste ? reste.type : undefined;
        return (
          <div
            key={cle}
            style={"pleineLargeur" in reste && reste.pleineLargeur ? { gridColumn: "1 / -1" } : undefined}
          >
            <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              {label}
            </label>
            <Input
              id={id}
              type={type}
              value={brouillon[cle]}
              disabled={disabled}
              onChange={(e) => onChange({ [cle]: e.target.value } as Partial<Brouillon>)}
              style={{ width: "100%" }}
            />
            {modifie && (
              <div style={{ fontSize: 12, color: "var(--tcn-text-faint)", marginTop: 4 }}>
                Valeur d&apos;origine : {valeursOrigine[cle].trim() || "vide"}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- components/benevoles/ChampsParticipation.test.tsx`
Expected: PASS — 5 tests.

- [ ] **Step 5: Commit**

```bash
git add components/benevoles/ChampsParticipation.tsx components/benevoles/ChampsParticipation.test.tsx
git commit -m "feat(490): les champs du panneau affichent leur valeur d'origine

Refs #490"
```

---

## Task 6: Hook du brouillon — un seul enregistrement

**Files:**
- Create: `components/benevoles/useBrouillon.ts`
- Test: `components/benevoles/useBrouillon.test.tsx`

**Interfaces:**
- Consumes: `Brouillon`, `Etape`, `brouillonDepuis`, `erreurDeSaisie`, `estSale`, `planEnregistrement`, `rebaser`, `LIBELLE_ETAPE` de `@/lib/benevoles/brouillon` (Task 1) ; `apiClient`, `ApiError`.
- Produces:
  ```ts
  function useBrouillon(
    participation: Participation,
    options: { onChanged: (p: Participation) => void; onSessionExpired?: () => void },
  ): {
    brouillon: Brouillon;
    modifier: (patch: Partial<Brouillon>) => void;
    sale: boolean;
    erreur: string | null;
    enCours: boolean;
    enregistrer: () => Promise<boolean>;
    validerLeResultat: () => Promise<void>;
  }
  ```

- [ ] **Step 1: Write the failing test**

Create `components/benevoles/useBrouillon.test.tsx`:

```tsx
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";

const {
  renameCourseBenevole,
  updateParticipationFieldsBenevole,
  reassignParticipationBenevole,
  validateParticipationBenevole,
} = vi.hoisted(() => ({
  renameCourseBenevole: vi.fn(),
  updateParticipationFieldsBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
  validateParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      renameCourseBenevole,
      updateParticipationFieldsBenevole,
      reassignParticipationBenevole,
      validateParticipationBenevole,
    },
  };
});

import { ApiError } from "@/lib/api/client";
import { useBrouillon } from "./useBrouillon";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };
const AUTRE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 10,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V2 M",
    bib_number: "412",
    rank_overall: 37,
    rank_category: null,
    rank_gender: null,
    total_time: "02:14:53",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

function monter(p = participation()) {
  const onChanged = vi.fn();
  const onSessionExpired = vi.fn();
  const rendu = renderHook(() => useBrouillon(p, { onChanged, onSessionExpired }));
  return { ...rendu, onChanged, onSessionExpired, participation: p };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useBrouillon", () => {
  it("part propre et devient sale à la première modification", () => {
    const { result } = monter();
    expect(result.current.sale).toBe(false);
    act(() => result.current.modifier({ bib_number: "413" }));
    expect(result.current.sale).toBe(true);
  });

  it("n'appelle rien quand rien n'a bougé", async () => {
    const { result } = monter();
    await act(async () => {
      expect(await result.current.enregistrer()).toBe(true);
    });
    expect(updateParticipationFieldsBenevole).not.toHaveBeenCalled();
  });

  it("n'appelle que la route dont les champs ont bougé", async () => {
    const { result, onChanged } = monter();
    updateParticipationFieldsBenevole.mockResolvedValue(participation({ bib_number: "413" }));

    act(() => result.current.modifier({ bib_number: "413" }));
    await act(async () => void (await result.current.enregistrer()));

    expect(updateParticipationFieldsBenevole).toHaveBeenCalledWith(10, { bib_number: "413" });
    expect(renameCourseBenevole).not.toHaveBeenCalled();
    expect(reassignParticipationBenevole).not.toHaveBeenCalled();
    expect(onChanged).toHaveBeenCalledWith(participation({ bib_number: "413" }));
    expect(result.current.sale).toBe(false);
  });

  it("enchaîne renommage, champs et réattribution dans cet ordre", async () => {
    const { result } = monter();
    const ordre: string[] = [];
    renameCourseBenevole.mockImplementation(async () => {
      ordre.push("nom");
      return { ...participation().course, name: "Nouveau nom" };
    });
    updateParticipationFieldsBenevole.mockImplementation(async () => {
      ordre.push("champs");
      return participation({ bib_number: "413" });
    });
    reassignParticipationBenevole.mockImplementation(async () => {
      ordre.push("reattribution");
      return participation({ athlete: AUTRE, bib_number: "413" });
    });

    act(() =>
      result.current.modifier({ nom_epreuve: "Nouveau nom", bib_number: "413", athlete_cible: AUTRE }),
    );
    await act(async () => void (await result.current.enregistrer()));

    expect(ordre).toEqual(["nom", "champs", "reattribution"]);
  });

  it("garde sale ce qui n'a pas pu partir après un échec partiel", async () => {
    const { result, onChanged } = monter();
    renameCourseBenevole.mockResolvedValue({ ...participation().course, name: "Nouveau nom" });
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(409, "Ce dossard est déjà pris."));

    act(() => result.current.modifier({ nom_epreuve: "Nouveau nom", bib_number: "413" }));
    await act(async () => {
      expect(await result.current.enregistrer()).toBe(false);
    });

    expect(result.current.erreur).toBe(
      "Les champs n'ont pas pu être enregistrés : Ce dossard est déjà pris.",
    );
    expect(result.current.brouillon.nom_epreuve).toBe("Nouveau nom");
    expect(result.current.brouillon.bib_number).toBe("413");
    // Le renommage est commité : le parent le sait, même si l'ensemble a échoué.
    expect(onChanged).toHaveBeenCalled();
  });

  it("refuse d'enregistrer une saisie invalide sans appeler le réseau", async () => {
    const { result } = monter();
    act(() => result.current.modifier({ nom_epreuve: "   " }));
    await act(async () => {
      expect(await result.current.enregistrer()).toBe(false);
    });
    expect(result.current.erreur).toBe("Le nom de l'épreuve ne peut pas être vide.");
    expect(renameCourseBenevole).not.toHaveBeenCalled();
  });

  it("enregistre d'abord, puis valide", async () => {
    const { result } = monter();
    const ordre: string[] = [];
    updateParticipationFieldsBenevole.mockImplementation(async () => {
      ordre.push("champs");
      return participation({ bib_number: "413" });
    });
    validateParticipationBenevole.mockImplementation(async () => {
      ordre.push("validation");
      return participation({ bib_number: "413", is_pending_validation: false });
    });

    act(() => result.current.modifier({ bib_number: "413" }));
    await act(async () => void (await result.current.validerLeResultat()));

    expect(ordre).toEqual(["champs", "validation"]);
  });

  it("abandonne la validation quand l'enregistrement échoue", async () => {
    const { result } = monter();
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(409, "Ce dossard est déjà pris."));

    act(() => result.current.modifier({ bib_number: "413" }));
    await act(async () => void (await result.current.validerLeResultat()));

    expect(validateParticipationBenevole).not.toHaveBeenCalled();
    expect(result.current.erreur).toContain("Ce dossard est déjà pris.");
  });

  it("prévient d'une session expirée plutôt que d'afficher une erreur générique", async () => {
    const { result, onSessionExpired } = monter();
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(401, "non autorisé"));

    act(() => result.current.modifier({ bib_number: "413" }));
    await act(async () => void (await result.current.enregistrer()));

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalled());
    expect(result.current.erreur).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/benevoles/useBrouillon.test.tsx`
Expected: FAIL — `Failed to resolve import "./useBrouillon"`.

- [ ] **Step 3: Write minimal implementation**

Create `components/benevoles/useBrouillon.ts`:

```ts
"use client";

import { useCallback, useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import {
  brouillonDepuis,
  erreurDeSaisie,
  estSale,
  LIBELLE_ETAPE,
  planEnregistrement,
  rebaser,
  type Brouillon,
  type Etape,
} from "@/lib/benevoles/brouillon";
import type { Participation } from "@/lib/types";

/**
 * L'état du formulaire unique du panneau bénévole (#490, PROF-10).
 *
 * Un seul brouillon, un seul `enregistrer()`, une seule zone d'erreur — contre
 * quatre gestes d'écriture indépendants jusqu'ici, dont aucun ne signalait
 * qu'on l'avait oublié avant de valider.
 */
export function useBrouillon(
  participation: Participation,
  { onChanged, onSessionExpired }: {
    onChanged: (p: Participation) => void;
    onSessionExpired?: () => void;
  },
) {
  const [brouillon, setBrouillon] = useState<Brouillon>(() => brouillonDepuis(participation));
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  const modifier = useCallback((patch: Partial<Brouillon>) => {
    setErreur(null);
    setBrouillon((courant) => ({ ...courant, ...patch }));
  }, []);

  /** Exécute une étape et rend la participation dans son état d'après. */
  async function executer(etape: Etape, courante: Participation): Promise<Participation> {
    switch (etape.type) {
      case "nom_epreuve": {
        const course = await apiClient.renameCourseBenevole(courante.course.id, etape.nom);
        return { ...courante, course };
      }
      case "champs":
        return apiClient.updateParticipationFieldsBenevole(courante.id, etape.champs);
      case "reattribution":
        return apiClient.reassignParticipationBenevole(courante.id, etape.athleteId);
    }
  }

  const enregistrer = useCallback(async (): Promise<boolean> => {
    setErreur(null);

    const invalide = erreurDeSaisie(brouillon);
    if (invalide) {
      setErreur(invalide);
      return false;
    }

    const plan = planEnregistrement(brouillon, participation);
    if (plan.length === 0) return true;

    setEnCours(true);
    let courante = participation;
    const reussies: Etape["type"][] = [];
    try {
      for (const etape of plan) {
        try {
          courante = await executer(etape, courante);
          reussies.push(etape.type);
        } catch (err) {
          // Une session expirée prévient le parent plutôt que d'afficher une
          // erreur générique sur un geste qui ne peut plus aboutir — sinon le
          // bénévole reste bloqué jusqu'au rechargement manuel (revue de #271).
          if (err instanceof ApiError && err.status === 401) {
            onSessionExpired?.();
            return false;
          }
          const detail = err instanceof ApiError ? err.message : "Réessayez plus tard.";
          setErreur(`${LIBELLE_ETAPE[etape.type]} : ${detail}`);
          return false;
        }
      }
      return true;
    } finally {
      setEnCours(false);
      // Ce qui est passé est commité côté serveur, même si la suite a échoué :
      // le brouillon se repose dessus, le parent apprend le nouvel état.
      if (reussies.length > 0) {
        setBrouillon((b) => rebaser(b, courante, reussies));
        onChanged(courante);
      }
    }
  }, [brouillon, participation, onChanged, onSessionExpired]);

  const validerLeResultat = useCallback(async () => {
    if (!(await enregistrer())) return;
    setEnCours(true);
    try {
      onChanged(await apiClient.validateParticipationBenevole(participation.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onSessionExpired?.();
        return;
      }
      setErreur(err instanceof ApiError ? err.message : "La validation a échoué. Réessayez plus tard.");
    } finally {
      setEnCours(false);
    }
  }, [enregistrer, participation.id, onChanged, onSessionExpired]);

  return {
    brouillon,
    modifier,
    sale: estSale(brouillon, participation),
    erreur,
    enCours,
    enregistrer,
    validerLeResultat,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- components/benevoles/useBrouillon.test.tsx`
Expected: PASS — 9 tests.

- [ ] **Step 5: Commit**

```bash
git add components/benevoles/useBrouillon.ts components/benevoles/useBrouillon.test.tsx
git commit -m "feat(490): un seul état de formulaire et un seul enregistrement

Le brouillon n'appelle que les routes dont les champs ont bougé, dans un
ordre fixe, se rebase sur ce qui est passé en cas d'échec partiel, et la
validation enregistre d'abord — le dossard saisi sans clic n'est plus
emporté en silence.

Refs #490"
```

---

## Task 7: Panneau réécrit — zone d'erreur unique et barre collante

**Files:**
- Modify (réécriture complète) : `components/benevoles/ParticipationPanel.tsx`
- Modify (réécriture complète) : `components/benevoles/ParticipationPanel.test.tsx`

**Interfaces:**
- Consumes: `useBrouillon` (Task 6), `ChampsParticipation` (Task 5), `ReattributionField` (Task 4).
- Produces: `ParticipationPanel` garde sa signature actuelle — `{ participation, onChanged, onSessionExpired? }` — plus `onBrouillonSale?: (sale: boolean) => void` pour que la page pose son garde-fou (Task 9).

**Note pour l'implémenteur :** les tests actuels du fichier cherchent « Enregistrer le nom » et « Enregistrer les modifications ». Ces boutons **disparaissent** ; le fichier de test est remplacé, pas amendé. Les trois cas de conflit 409 (nom, dossard, réattribution) survivent, avec une nouvelle cible : la zone d'erreur unique.

- [ ] **Step 1: Write the failing test**

Replace the entire content of `components/benevoles/ParticipationPanel.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";

const {
  validateParticipationBenevole,
  renameCourseBenevole,
  reassignParticipationBenevole,
  searchAthletesBenevole,
  updateParticipationFieldsBenevole,
  rejectParticipationBenevole,
  unrejectParticipationBenevole,
} = vi.hoisted(() => ({
  validateParticipationBenevole: vi.fn(),
  renameCourseBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
  searchAthletesBenevole: vi.fn(),
  updateParticipationFieldsBenevole: vi.fn(),
  rejectParticipationBenevole: vi.fn(),
  unrejectParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      validateParticipationBenevole,
      renameCourseBenevole,
      reassignParticipationBenevole,
      searchAthletesBenevole,
      updateParticipationFieldsBenevole,
      rejectParticipationBenevole,
      unrejectParticipationBenevole,
    },
  };
});

import { ApiError } from "@/lib/api/client";
import { ParticipationPanel } from "./ParticipationPanel";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };
const AUTRE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 10,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V2 M",
    bib_number: "412",
    rank_overall: 37,
    rank_category: null,
    rank_gender: null,
    total_time: "02:14:53",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    evidence_url: "https://example.test/resultats",
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ParticipationPanel — lecture", () => {
  it("affiche l'athlète, l'épreuve, le temps et le lien de la pièce justificative", () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    expect(screen.getByText("Mathieu HERRMANN")).toBeInTheDocument();
    expect(screen.getByText(/Triathlon de Nantes/)).toBeInTheDocument();
    expect(screen.getByText("02:14:53")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Lien vers les résultats/ })).toHaveAttribute(
      "href",
      "https://example.test/resultats",
    );
  });

  it("n'affiche aucun lien si evidence_url est absent", () => {
    render(<ParticipationPanel participation={participation({ evidence_url: null })} onChanged={vi.fn()} />);
    expect(screen.queryByRole("link", { name: /Lien vers les résultats/ })).not.toBeInTheDocument();
  });

  it("distingue un résultat collectif par son nom d'équipe", () => {
    render(
      <ParticipationPanel participation={participation({ team_name: "Les Requins" })} onChanged={vi.fn()} />,
    );
    expect(screen.getByText("Les Requins")).toBeInTheDocument();
  });
});

describe("ParticipationPanel — enregistrement unique", () => {
  it("n'offre plus qu'un seul bouton d'enregistrement", () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /Enregistrer le nom/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Enregistrer les modifications/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeInTheDocument();
  });

  it("signale les modifications non enregistrées dès la première frappe", async () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    expect(screen.queryByText(/Modifications non enregistrées/)).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");

    expect(screen.getByText(/Modifications non enregistrées/)).toBeInTheDocument();
  });

  it("enregistre le nom d'épreuve et les champs en un seul geste", async () => {
    renameCourseBenevole.mockResolvedValue({ ...participation().course, name: "Triathlon de Nantes 2026" });
    updateParticipationFieldsBenevole.mockResolvedValue(participation({ bib_number: "4123" }));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Nom de l'épreuve/), " 2026");
    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(renameCourseBenevole).toHaveBeenCalledWith(99, "Triathlon de Nantes 2026"));
    expect(updateParticipationFieldsBenevole).toHaveBeenCalledWith(10, { bib_number: "4123" });
  });

  it("valide en enregistrant d'abord le dossard saisi", async () => {
    updateParticipationFieldsBenevole.mockResolvedValue(participation({ bib_number: "4123" }));
    validateParticipationBenevole.mockResolvedValue(
      participation({ bib_number: "4123", is_pending_validation: false }),
    );
    const onChanged = vi.fn();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() => expect(validateParticipationBenevole).toHaveBeenCalledWith(10));
    expect(updateParticipationFieldsBenevole).toHaveBeenCalledWith(10, { bib_number: "4123" });
  });

  it("réattribue au moment de l'enregistrement, pas au clic sur le résultat", async () => {
    searchAthletesBenevole.mockResolvedValue([AUTRE]);
    reassignParticipationBenevole.mockResolvedValue(participation({ athlete: AUTRE }));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Kerm");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    expect(reassignParticipationBenevole).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(reassignParticipationBenevole).toHaveBeenCalledWith(10, 2));
  });
});

describe("ParticipationPanel — erreurs", () => {
  it("nomme l'étape en échec dans une zone d'erreur unique", async () => {
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(409, "Ce dossard est déjà pris."));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Les champs n'ont pas pu être enregistrés : Ce dossard est déjà pris.",
      ),
    );
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("signale une collision de renommage en français", async () => {
    renameCourseBenevole.mockRejectedValue(new ApiError(409, "Une autre épreuve porte déjà ce nom."));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Nom de l'épreuve/), " 2026");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Une autre épreuve porte déjà ce nom."),
    );
  });

  it("signale un conflit de réattribution en français", async () => {
    searchAthletesBenevole.mockResolvedValue([AUTRE]);
    reassignParticipationBenevole.mockRejectedValue(
      new ApiError(409, "Ce coureur a déjà un résultat sur cette épreuve."),
    );
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Kerm");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Ce coureur a déjà un résultat sur cette épreuve.",
      ),
    );
  });

  it("prévient le parent d'une session expirée plutôt que d'afficher une erreur générique", async () => {
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(401, "non autorisé"));
    const onSessionExpired = vi.fn();
    render(
      <ParticipationPanel
        participation={participation()}
        onChanged={vi.fn()}
        onSessionExpired={onSessionExpired}
      />,
    );

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("ParticipationPanel — rejet", () => {
  it("signale non conforme après confirmation", async () => {
    rejectParticipationBenevole.mockResolvedValue(participation({ is_rejected: true }));
    const onChanged = vi.fn();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await userEvent.click(screen.getByRole("button", { name: /Signaler non conforme/ }));
    await userEvent.click(screen.getByRole("button", { name: /Confirmer/ }));

    await waitFor(() => expect(rejectParticipationBenevole).toHaveBeenCalledWith(10));
  });

  it("n'appelle rien si le signalement n'est pas confirmé", async () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Signaler non conforme/ }));
    expect(rejectParticipationBenevole).not.toHaveBeenCalled();
  });

  it("laisse une entrée rejetée en lecture seule", () => {
    render(
      <ParticipationPanel participation={participation({ is_rejected: true })} onChanged={vi.fn()} />,
    );
    expect(screen.queryByLabelText(/Dossard/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Valider ce résultat/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Annuler le rejet/ })).toBeInTheDocument();
  });

  it("rouvre l'édition une fois le rejet annulé", () => {
    render(
      <ParticipationPanel participation={participation({ is_rejected: false })} onChanged={vi.fn()} />,
    );
    expect(screen.getByLabelText(/Dossard/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Valider ce résultat/ })).toBeInTheDocument();
  });
});

describe("ParticipationPanel — remontée de l'état sale", () => {
  it("prévient le parent quand le brouillon devient sale", async () => {
    const onBrouillonSale = vi.fn();
    render(
      <ParticipationPanel
        participation={participation()}
        onChanged={vi.fn()}
        onBrouillonSale={onBrouillonSale}
      />,
    );

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");

    await waitFor(() => expect(onBrouillonSale).toHaveBeenLastCalledWith(true));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/benevoles/ParticipationPanel.test.tsx`
Expected: FAIL — le panneau actuel n'a ni bouton « Enregistrer » unique, ni bandeau « Modifications non enregistrées », ni prop `onBrouillonSale`.

- [ ] **Step 3: Write minimal implementation**

Replace the entire content of `components/benevoles/ParticipationPanel.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Button, Card } from "@/components/tcn";
import { apiClient, ApiError } from "@/lib/api/client";
import type { Participation } from "@/lib/types";
import { formatEventName } from "@/lib/utils/event";
import { isHttpUrl } from "@/lib/utils/url";
import { ChampsParticipation } from "./ChampsParticipation";
import { ReattributionField } from "./ReattributionField";
import { useBrouillon } from "./useBrouillon";

/**
 * Détail d'un résultat en attente : relecture, correction, validation (#271).
 *
 * Depuis #490 (PROF-10) le panneau n'a plus qu'**un** état de formulaire, **un**
 * enregistrement et **une** zone d'erreur, et son action primaire vit dans une
 * barre collante plutôt qu'en dernière position du DOM.
 */
export function ParticipationPanel({
  participation,
  onChanged,
  onSessionExpired,
  onBrouillonSale,
}: {
  participation: Participation;
  onChanged: (updated: Participation) => void;
  /** Le cookie a expiré ou le mot de passe a changé pendant que l'écran était ouvert. */
  onSessionExpired?: () => void;
  /** La page en fait son garde-fou : on ne quitte pas une entrée sale sans confirmer. */
  onBrouillonSale?: (sale: boolean) => void;
}) {
  const { brouillon, modifier, sale, erreur, enCours, enregistrer, validerLeResultat } = useBrouillon(
    participation,
    { onChanged, onSessionExpired },
  );

  const [confirmationRejet, setConfirmationRejet] = useState(false);
  const [erreurRejet, setErreurRejet] = useState<string | null>(null);
  const [enCoursRejet, setEnCoursRejet] = useState(false);

  useEffect(() => {
    onBrouillonSale?.(sale);
  }, [sale, onBrouillonSale]);

  async function agirSurLeRejet(action: "rejeter" | "annuler") {
    setErreurRejet(null);
    setEnCoursRejet(true);
    try {
      onChanged(
        action === "rejeter"
          ? await apiClient.rejectParticipationBenevole(participation.id)
          : await apiClient.unrejectParticipationBenevole(participation.id),
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onSessionExpired?.();
        return;
      }
      setErreurRejet(err instanceof ApiError ? err.message : "L'opération a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursRejet(false);
      setConfirmationRejet(false);
    }
  }

  const rejetee = participation.is_rejected === true;
  const occupe = enCours || enCoursRejet;

  return (
    <Card padding={24}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div>
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 20, color: "var(--tcn-ink)", fontWeight: 400, margin: 0 }}>
            {participation.athlete.prenom} {participation.athlete.nom}
          </h2>
          <div style={{ fontSize: 14, color: "var(--tcn-text-faint)" }}>
            {formatEventName(participation.course.name, participation.course.is_relay)}
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 24px", fontSize: 14 }}>
          <div>
            <span style={{ color: "var(--tcn-text-faint)" }}>Temps : </span>
            <strong>{participation.total_time ?? "—"}</strong>
          </div>
          {participation.team_name && (
            <div>
              <span style={{ color: "var(--tcn-text-faint)" }}>Équipe : </span>
              <strong>{participation.team_name}</strong>
            </div>
          )}
          {isHttpUrl(participation.evidence_url) && (
            <div>
              <a href={participation.evidence_url!} target="_blank" rel="noopener noreferrer" className="tcn-rowlink hover:underline">
                Lien vers les résultats ↗
              </a>
            </div>
          )}
        </div>

        {participation.splits && Object.keys(participation.splits).length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 18px", fontSize: 13 }}>
            {Object.entries(participation.splits).map(([cle, valeur]) => (
              <div key={cle}>
                <span style={{ color: "var(--tcn-text-faint)" }}>{cle} : </span>
                <strong>{valeur}</strong>
              </div>
            ))}
          </div>
        )}

        {rejetee ? (
          <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16, color: "var(--tcn-text-faint)", fontSize: 14 }}>
            Annulez d&apos;abord le rejet pour modifier ce résultat.
          </div>
        ) : (
          <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16, display: "flex", flexDirection: "column", gap: 16 }}>
            <ChampsParticipation
              brouillon={brouillon}
              origine={participation}
              onChange={modifier}
              disabled={occupe}
            />
            <ReattributionField
              athleteActuel={participation.athlete}
              athleteCible={brouillon.athlete_cible}
              onChoisir={(athlete) => modifier({ athlete_cible: athlete })}
              disabled={occupe}
            />
          </div>
        )}

        {/* Barre d'action collante : l'action primaire est unique, visible et
            sur le chemin de lecture — elle était la dernière du DOM, donc hors
            écran au chargement sur mobile (#490, PROF-10). */}
        <div
          style={{
            position: "sticky",
            bottom: 0,
            background: "var(--tcn-surface)",
            borderTop: "1px solid var(--tcn-border)",
            paddingTop: 16,
            marginTop: 4,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {sale && (
            <div style={{ fontSize: 13, color: "var(--tcn-text-body)", fontWeight: 600 }}>
              Modifications non enregistrées
            </div>
          )}
          {erreur && (
            <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13 }}>
              {erreur}
            </div>
          )}
          {!rejetee && (
            <>
              <Button onClick={validerLeResultat} disabled={occupe} style={{ width: "100%" }}>
                {enCours ? "Enregistrement…" : "Valider ce résultat"}
              </Button>
              <Button variant="secondary" onClick={enregistrer} disabled={occupe || !sale} style={{ width: "100%" }}>
                Enregistrer
              </Button>
            </>
          )}
          {rejetee ? (
            <Button variant="secondary" onClick={() => agirSurLeRejet("annuler")} disabled={occupe} style={{ width: "100%" }}>
              {enCoursRejet ? "Annulation…" : "Annuler le rejet"}
            </Button>
          ) : !confirmationRejet ? (
            <Button
              variant="secondary"
              onClick={() => setConfirmationRejet(true)}
              disabled={occupe}
              style={{ width: "100%", color: "var(--tcn-danger-text)", borderColor: "var(--tcn-danger-border)" }}
            >
              Signaler non conforme
            </Button>
          ) : (
            <div style={{ display: "flex", gap: 8 }}>
              <Button
                variant="secondary"
                onClick={() => agirSurLeRejet("rejeter")}
                disabled={occupe}
                style={{ flex: 1, color: "var(--tcn-danger-text)", borderColor: "var(--tcn-danger-border)" }}
              >
                {enCoursRejet ? "Signalement…" : "Confirmer ?"}
              </Button>
              <Button variant="ghost" onClick={() => setConfirmationRejet(false)} disabled={occupe} style={{ flex: 1 }}>
                Annuler
              </Button>
            </div>
          )}
          {erreurRejet && (
            <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13 }}>
              {erreurRejet}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- components/benevoles/ParticipationPanel.test.tsx`
Expected: PASS — 17 tests.

Then run the whole suite to catch collateral damage: `npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add components/benevoles/ParticipationPanel.tsx components/benevoles/ParticipationPanel.test.tsx
git commit -m "feat(490): panneau bénévole à zone d'erreur unique et barre collante

Quatre gestes d'écriture indépendants deviennent un formulaire et un
enregistrement ; l'action primaire remonte dans une barre collante.

Refs #490"
```

---

## Task 8: File — compteur de session et état vide de réussite

**Files:**
- Modify: `components/benevoles/ValidationQueue.tsx`
- Modify: `components/benevoles/ValidationQueue.test.tsx`

**Interfaces:**
- Produces: `ValidationQueue` prend une prop de plus — `traitees?: number`.

- [ ] **Step 1: Write the failing test**

Append to `components/benevoles/ValidationQueue.test.tsx` (avant la dernière accolade du fichier, dans un nouveau `describe`) :

```tsx
describe("ValidationQueue — progression (#490, PROF-9)", () => {
  it("n'affiche pas de compteur tant que rien n'a été traité", () => {
    render(<ValidationQueue participations={[]} selectedId={null} onSelect={vi.fn()} traitees={0} />);
    expect(screen.queryByText(/traité/)).not.toBeInTheDocument();
  });

  it("compte les entrées traitées dans la session", () => {
    render(<ValidationQueue participations={[]} selectedId={null} onSelect={vi.fn()} traitees={7} />);
    expect(screen.getByText("7 traités")).toBeInTheDocument();
  });

  it("accorde le compteur au singulier", () => {
    render(<ValidationQueue participations={[]} selectedId={null} onSelect={vi.fn()} traitees={1} />);
    expect(screen.getByText("1 traité")).toBeInTheDocument();
  });

  it("fait de la file épuisée un état de réussite", () => {
    render(<ValidationQueue participations={[]} selectedId={null} onSelect={vi.fn()} traitees={3} />);
    expect(screen.getByText("File vide, merci !")).toBeInTheDocument();
  });

  it("garde un état vide neutre sur les non conformes", async () => {
    render(<ValidationQueue participations={[]} rejected={[]} selectedId={null} onSelect={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Non conformes/ }));
    expect(screen.getByText("Aucun résultat signalé non conforme")).toBeInTheDocument();
    expect(screen.queryByText("File vide, merci !")).not.toBeInTheDocument();
  });
});
```

**Note :** le test existant « affiche un état vide quand la file est vide » attend l'ancien libellé « Aucun résultat en attente de validation ». Le remplacer par l'assertion `File vide, merci !` — même intention, nouveau libellé.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/benevoles/ValidationQueue.test.tsx`
Expected: FAIL — `traitees` n'existe pas, et l'état vide dit encore « Aucun résultat en attente de validation ».

- [ ] **Step 3: Write minimal implementation**

In `components/benevoles/ValidationQueue.tsx`, add `traitees` to the props signature and render both changes:

```tsx
export function ValidationQueue({
  participations,
  rejected = [],
  selectedId,
  onSelect,
  traitees = 0,
}: {
  participations: Participation[];
  rejected?: Participation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  /** Entrées traitées depuis l'ouverture de l'écran (#490, PROF-9). Non
   *  persisté : c'est un encouragement, pas une donnée. */
  traitees?: number;
}) {
```

Add the counter at the end of the tabs row, after the « Non conformes » button and inside the same flex container:

```tsx
        {traitees > 0 && (
          <span style={{ marginLeft: "auto", alignSelf: "center", fontSize: 13, color: "var(--tcn-text-faint)" }}>
            {traitees} traité{traitees > 1 ? "s" : ""}
          </span>
        )}
```

Replace the `EmptyState` title expression so the exhausted queue reads as a success:

```tsx
          <EmptyState
            bare
            title={onglet === "file" ? "File vide, merci !" : "Aucun résultat signalé non conforme"}
            description={
              onglet === "file" ? "Tous les résultats déclarés ont été relus." : undefined
            }
          />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- components/benevoles/ValidationQueue.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add components/benevoles/ValidationQueue.tsx components/benevoles/ValidationQueue.test.tsx
git commit -m "feat(490): compteur de session et file épuisée en état de réussite

Refs #490"
```

---

## Task 9: Écran — câblage, feuille mobile, garde-fou

**Files:**
- Create: `hooks/useEstCompact.ts`
- Modify (réécriture complète) : `app/benevoles/page.tsx`
- Create: `app/benevoles/page.test.tsx`

**Interfaces:**
- Consumes: `useFileValidation` (Task 3), `ParticipationPanel` avec `onBrouillonSale` (Task 7), `ValidationQueue` avec `traitees` (Task 8), `AnnonceStatut` de `@/components/tcn`, `Sheet`/`SheetContent`/`SheetTitle` de `@/components/ui/sheet`.
- Produces: `useEstCompact(): boolean` — `true` sous 768 px.

- [ ] **Step 1: Write the failing test**

Create `app/benevoles/page.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";

const {
  getBenevoleQueue,
  getBenevoleRejected,
  validateParticipationBenevole,
  searchAthletesBenevole,
  updateParticipationFieldsBenevole,
} = vi.hoisted(() => ({
  getBenevoleQueue: vi.fn(),
  getBenevoleRejected: vi.fn(),
  validateParticipationBenevole: vi.fn(),
  searchAthletesBenevole: vi.fn(),
  updateParticipationFieldsBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getBenevoleQueue,
      getBenevoleRejected,
      validateParticipationBenevole,
      searchAthletesBenevole,
      updateParticipationFieldsBenevole,
    },
  };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import BenevolesPage from "./page";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };

function participation(id: number, over: Partial<Participation> = {}): Participation {
  return {
    id,
    athlete: { ...ATHLETE, id, prenom: `Coureur${id}` },
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: null,
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

/** Le panneau n'est en feuille que sous `md` : par défaut on simule le desktop. */
function simulerLargeur(compact: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: compact,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  simulerLargeur(false);
  getBenevoleQueue.mockResolvedValue([participation(1), participation(2), participation(3)]);
  getBenevoleRejected.mockResolvedValue([]);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BenevolesPage", () => {
  it("enchaîne sur l'entrée suivante après une validation", async () => {
    validateParticipationBenevole.mockResolvedValue(participation(2, { is_pending_validation: false }));
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur2 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    // Le panneau ne repart pas sur l'état vide : il montre déjà la suivante.
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 2, name: /Coureur3/ })).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Sélectionnez un résultat/)).not.toBeInTheDocument();
  });

  it("annonce le reste de la file aux lecteurs d'écran", async () => {
    validateParticipationBenevole.mockResolvedValue(participation(1, { is_pending_validation: false }));
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Résultat validé — 2 restants."),
    );
  });

  it("montre l'état de réussite quand la file est épuisée", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1)]);
    validateParticipationBenevole.mockResolvedValue(participation(1, { is_pending_validation: false }));
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() => expect(screen.getByText("File vide, merci !")).toBeInTheDocument());
  });

  it("demande confirmation avant de quitter une entrée aux modifications non enregistrées", async () => {
    const confirmer = vi.fn().mockReturnValue(false);
    vi.stubGlobal("confirm", confirmer);
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));

    expect(confirmer).toHaveBeenCalled();
    // Refus : on reste sur l'entrée en cours, la saisie n'est pas perdue.
    expect(screen.getByRole("heading", { level: 2, name: /Coureur1/ })).toBeInTheDocument();
  });

  it("ouvre le panneau en feuille sous le point de rupture md", async () => {
    simulerLargeur(true);
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  });

  it("garde le panneau dans la grille au-dessus de md", async () => {
    render(<BenevolesPage />);
    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));

    expect(screen.getByRole("heading", { level: 2, name: /Coureur1/ })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- app/benevoles/page.test.tsx`
Expected: FAIL — la page remet encore `selectedId` à `null`, n'a ni annonce, ni feuille, ni garde-fou.

- [ ] **Step 3: Write minimal implementation**

Create `hooks/useEstCompact.ts`:

```ts
"use client";

import { useEffect, useState } from "react";

/** Le point de rupture `md` de Tailwind, en requête média. */
const COMPACT = "(max-width: 767px)";

/**
 * `true` sous le point de rupture `md`.
 *
 * L'état initial est `false` **et non** la vraie valeur : la page est rendue
 * côté serveur, où `matchMedia` n'existe pas, et partir de la vraie valeur
 * produirait une non-concordance d'hydratation.
 */
export function useEstCompact(): boolean {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const requete = window.matchMedia(COMPACT);
    setCompact(requete.matches);
    const surChangement = (e: MediaQueryListEvent) => setCompact(e.matches);
    requete.addEventListener("change", surChangement);
    return () => requete.removeEventListener("change", surChangement);
  }, []);

  return compact;
}
```

Replace the entire content of `app/benevoles/page.tsx`:

```tsx
"use client";

import { useCallback, useRef, useState } from "react";
import { AccessGate } from "@/components/benevoles/AccessGate";
import { ParticipationPanel } from "@/components/benevoles/ParticipationPanel";
import { useFileValidation } from "@/components/benevoles/useFileValidation";
import { ValidationQueue } from "@/components/benevoles/ValidationQueue";
import { AnnonceStatut, Eyebrow, Button } from "@/components/tcn";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useEstCompact } from "@/hooks/useEstCompact";
import type { Participation } from "@/lib/types";

/**
 * Page de vérification des résultats par les bénévoles (#271).
 *
 * Hors `/admin/*` et hors `nav.config.ts` — accès direct par URL communiquée
 * aux bénévoles, protégé par mot de passe partagé plutôt que par SSO
 * (research.md §D1 de la feature).
 *
 * Depuis #490 (PROF-9) la file s'enchaîne : la validation d'une entrée
 * sélectionne la suivante, au lieu de laisser le bénévole repointer à la main.
 */
export default function BenevolesPage() {
  const file = useFileValidation();
  const compact = useEstCompact();
  const [feuilleOuverte, setFeuilleOuverte] = useState(false);
  /** Une ref plutôt qu'un état : le garde-fou est lu dans un gestionnaire de
   *  clic, jamais rendu — un état ne ferait que déclencher un rendu de plus. */
  const brouillonSale = useRef(false);

  const surBrouillonSale = useCallback((sale: boolean) => {
    brouillonSale.current = sale;
  }, []);

  function selectionner(id: number) {
    if (id !== file.selectedId && brouillonSale.current) {
      const ok = window.confirm(
        "Ce résultat porte des modifications non enregistrées. Les abandonner ?",
      );
      if (!ok) return;
    }
    brouillonSale.current = false;
    file.selectionner(id);
    if (compact) setFeuilleOuverte(true);
  }

  function surChangement(maj: Participation) {
    brouillonSale.current = false;
    file.surChangement(maj);
  }

  if (file.etat === "chargement") {
    return (
      <div style={{ maxWidth: 480, margin: "80px auto", textAlign: "center", color: "var(--tcn-text-faint)" }}>
        Chargement…
      </div>
    );
  }

  if (file.etat === "gate") {
    return <AccessGate onSuccess={file.charger} />;
  }

  if (file.etat === "erreur") {
    return (
      <div style={{ maxWidth: 480, margin: "80px auto", textAlign: "center", color: "var(--tcn-text-faint)" }}>
        <div style={{ marginBottom: 16 }}>
          La file de validation n&apos;a pas pu être chargée. Réessayez plus tard.
        </div>
        <Button variant="secondary" onClick={file.charger}>
          Réessayer
        </Button>
      </div>
    );
  }

  const panneau = file.selectionnee ? (
    <ParticipationPanel
      key={file.selectionnee.id}
      participation={file.selectionnee}
      onChanged={surChangement}
      onSessionExpired={file.surSessionExpiree}
      onBrouillonSale={surBrouillonSale}
    />
  ) : null;

  return (
    <div style={{ maxWidth: 1100, margin: "40px auto", padding: "0 24px" }}>
      <Eyebrow style={{ marginBottom: 6 }}>Bénévoles</Eyebrow>
      <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(26px, 4vw, 34px)", color: "var(--tcn-ink)", marginBottom: 24, fontWeight: 400 }}>
        Vérification des résultats
      </h1>
      {/* Le toast passe inaperçu d'un lecteur d'écran : la même phrase vit ici
          en région `status` (WCAG 4.1.3, patron `AnnonceStatut`). */}
      <AnnonceStatut texte={file.annonce} />
      <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-[minmax(280px,360px)_1fr]">
        <ValidationQueue
          participations={file.participations}
          rejected={file.rejetees}
          selectedId={file.selectedId}
          onSelect={selectionner}
          traitees={file.traitees}
        />
        {compact ? (
          <Sheet open={feuilleOuverte && panneau !== null} onOpenChange={setFeuilleOuverte}>
            <SheetContent side="right" className="w-full max-w-[520px] overflow-y-auto p-4">
              <SheetTitle style={{ fontSize: 0 }}>Détail du résultat</SheetTitle>
              {panneau}
            </SheetContent>
          </Sheet>
        ) : (
          (panneau ?? (
            <div style={{ color: "var(--tcn-text-faint)", fontSize: 14, padding: 24 }}>
              Sélectionnez un résultat dans la file pour le relire.
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- app/benevoles/page.test.tsx`
Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add hooks/useEstCompact.ts app/benevoles/page.tsx app/benevoles/page.test.tsx
git commit -m "feat(490): écran bénévole enchaîné, en feuille sous md

Câblage du hook de file, annonce a11y du reste, garde-fou sur brouillon
sale, et panneau en feuille sur mobile plutôt que sous toute la file.

Refs #490"
```

---

## Task 10: Vérification de bout en bout

**Files:**
- Modify: aucun fichier a priori — cette tâche corrige ce que la vérification révèle.

- [ ] **Step 1: Run the whole test suite**

Run: `npm test`
Expected: PASS, sans test ignoré ni fichier orphelin (`test/environments.test.ts` doit rester vert : tout nouveau `.test.tsx` est réclamé par le projet `jsdom`, tout nouveau `.test.ts` par `node`).

- [ ] **Step 2: Lint**

Run: `npm run lint`
Expected: aucune erreur. Points de vigilance connus sur ce périmètre : `react-hooks/exhaustive-deps` sur les `useCallback` du hook de file, et `react-hooks/set-state-in-effect` sur le chargement initial (déjà désactivé ligne à ligne dans le code existant — reprendre le même commentaire, pas une désactivation de fichier).

- [ ] **Step 3: Strict build**

Run: `npm run build`
Expected: succès. Le build est strict TS + RSC ; une prop oubliée sur `ValidationQueue` ou `ParticipationPanel` ne rougit qu'ici.

- [ ] **Step 4: Vérifier qu'aucun mort ne subsiste**

Run: `grep -rn "Enregistrer le nom\|Enregistrer les modifications" app components lib`
Expected: aucun résultat. Ces deux libellés sont supprimés, pas conservés.

- [ ] **Step 5: Commit d'éventuels correctifs**

```bash
git add -A
git commit -m "fix(490): suites de la vérification de bout en bout

Refs #490"
```

(Ne pas créer de commit vide s'il n'y a rien à corriger.)

---

## Fin de branche

Hors du périmètre des tâches, mais partie du cycle (`docs/WORKFLOW-IA.md`), **sur déclenchement de l'utilisateur** :

1. `requesting-code-review`
2. sous-agent `ui-ux-review` — la branche touche `frontend/`
3. `verification-before-completion`
4. `finishing-a-development-branch`

La PR doit porter `Closes #490` (jeton machine anglais ; le reste de la description en français).
