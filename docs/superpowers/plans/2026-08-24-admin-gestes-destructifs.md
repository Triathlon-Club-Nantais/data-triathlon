# Une seule grammaire pour les gestes destructifs de l'admin — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner aux cinq écrans d'administration une seule règle de couleur et un seul mécanisme de confirmation pour les gestes destructifs, et sortir les deux purges globales de l'écran de correction des épreuves.

**Architecture:** Un composant `DangerConfirm` dans `components/admin/`, exposé sous deux formes — déclarative pour les trois gestes qui chiffrent leur impact avant d'agir, impérative (`useDangerConfirm()`, une promesse) pour les quatre gestes simples qui appelaient `window.confirm`. Les deux purges déménagent vers une route `/admin/maintenance` annoncée par un OU de deux pouvoirs.

**Tech Stack:** Next.js 16 (App Router), TypeScript, Tailwind v4, Base UI (`@base-ui/react` — **pas** Radix), TanStack Query v5, Vitest + Testing Library, sonner pour les toasts.

**Spec:** `docs/superpowers/specs/2026-08-24-admin-gestes-destructifs-design.md`

## Global Constraints

- **Langue** (Principe I de la constitution) : **français** pour tout ce qui est visible ou métier — libellés, `aria-label`, messages, commentaires de règle. **English** pour la couche technique invisible : noms de tests (`it("…")` reste en français ici, c'est l'usage du dépôt — vérifier le fichier voisin), préfixes de commits Conventional Commits.
- **La règle de couleur**, verbatim : `variant="destructive"` **et** confirmation dès qu'un geste ferme un accès ou détruit une donnée. Neutre et sans confirmation pour tout ce qui se refait.
- **Une seule exception**, à commenter là où elle s'applique : la croix de retrait de rôle est `ghost` au repos, `destructive` au `hover` et au `focus-visible`.
- **Jamais `window.confirm`** dans le code livré à la fin de ce plan. À la dernière tâche, `grep -rn "window.confirm" frontend/app frontend/components frontend/lib` doit ne rien rendre hors des tests supprimés.
- **Ne pas préserver la compatibilité ascendante** : on supprime les chemins remplacés, on n'ajoute pas de repli.
- **Base UI, pas Radix** : `Dialog` s'ouvre par `open` / `onOpenChange`, `DialogContent` accepte `showCloseButton`.
- Commandes, depuis `frontend/` : `npm test` (vitest run), `npx vitest run <fichier>` pour un seul, `npm run lint`, `npm run build`.
- Tests unitaires **sans réseau** : `apiClient` est toujours mocké via `vi.hoisted` + `vi.mock("@/lib/api/client", …)`, patron visible dans `components/admin/GroupsTable.test.tsx:11-27`.

---

## Structure des fichiers

**Créés**
- `frontend/components/admin/DangerConfirm.tsx` — le composant déclaratif *et* le provider/hook impératif. Un seul fichier : le hook n'existe que pour rendre ce composant-là, les séparer obligerait à exporter des types intermédiaires pour rien.
- `frontend/components/admin/DangerConfirm.test.tsx`
- `frontend/app/admin/maintenance/page.tsx`

**Modifiés**
- `frontend/app/admin/layout.tsx` — monte le provider
- `frontend/app/admin/courses/page.tsx` — perd les deux cartes de purge
- `frontend/components/layout/nav.config.ts` — `permission?: string | string[]`, `estVisible`, entrée `a-maintenance`
- `frontend/components/admin/WipeCoursesCard.tsx`, `WipeParticipationsCard.tsx` — réécrites sur `DangerConfirm`
- `frontend/components/admin/DeleteCourseDialog.tsx` — réécrit sur `DangerConfirm`
- `frontend/components/admin/AllowedEmailsTable.tsx` — `destructive` + hook
- `frontend/components/admin/GroupsTable.tsx` — `destructive` + hook + refus annoncé
- `frontend/components/admin/RolePermissionsEditor.tsx` — deux `window.confirm` → hook
- `frontend/components/admin/UserRolesTable.tsx` — confirmation nominative + rouge au survol
- `frontend/AGENTS.md` — la règle, écrite une fois
- Les suites de tests correspondantes

---

## Un écart désormais reporté dans le design

Le design annonce une **infobulle** sur le bouton « Supprimer » d'un groupe peuplé. Un bouton `disabled` ne reçoit ni survol ni focus (`buttonVariants` pose `disabled:pointer-events-none`, et un `<button disabled>` sort du parcours clavier) : l'infobulle ne s'ouvrirait jamais. La tâche 7 enveloppe donc le bouton désactivé dans un `<span tabIndex={0}>` qui porte le déclencheur — le patron documenté pour ce cas, survol **et** clavier compris. Le bouton reste réellement inerte.

---

### Task 1: Le composant `DangerConfirm`

**Files:**
- Create: `frontend/components/admin/DangerConfirm.tsx`
- Test: `frontend/components/admin/DangerConfirm.test.tsx`

**Interfaces:**
- Consumes: `components/ui/{dialog,button,input}` déjà présents.
- Produces:
  ```ts
  type DangerConfirmProps = {
    open: boolean;
    onOpenChange: (ouvert: boolean) => void;
    titre: string;
    description?: ReactNode;
    avertissement?: ReactNode;
    motDeConfirmation?: string;
    actionBloquee?: boolean;
    libelleAction?: string;   // défaut : "Supprimer définitivement"
    enAttente?: boolean;
    onConfirm: () => void | Promise<void>;
    children?: ReactNode;
  };
  export function DangerConfirm(props: DangerConfirmProps): JSX.Element;
  ```

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `frontend/components/admin/DangerConfirm.test.tsx` :

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { DangerConfirm } from "./DangerConfirm";

describe("DangerConfirm", () => {
  it("rend le titre et le libellé d'action demandés", () => {
    render(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Retirer « a@b.fr » ?" libelleAction="Retirer" onConfirm={vi.fn()} />,
    );
    expect(screen.getByText("Retirer « a@b.fr » ?")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retirer" })).toBeTruthy();
  });

  it("agit au clic quand aucun mot n'est exigé", async () => {
    const onConfirm = vi.fn();
    render(<DangerConfirm open onOpenChange={vi.fn()} titre="Supprimer ?" onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: "Supprimer définitivement" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("garde l'action inerte tant que le mot exigé n'est pas tapé", async () => {
    const onConfirm = vi.fn();
    render(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Purger ?" motDeConfirmation="SUPPRIMER" onConfirm={onConfirm} />,
    );
    const action = screen.getByRole("button", { name: "Supprimer définitivement" });
    expect(action.hasAttribute("disabled")).toBe(true);

    await userEvent.type(screen.getByLabelText(/Tapez/), "SUPPRIM");
    expect(action.hasAttribute("disabled")).toBe(true);

    await userEvent.type(screen.getByLabelText(/Tapez/), "ER");
    expect(action.hasAttribute("disabled")).toBe(false);
    await userEvent.click(action);
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("garde l'action inerte tant que `actionBloquee` vaut vrai, mot tapé ou non", () => {
    render(<DangerConfirm open onOpenChange={vi.fn()} titre="Purger ?" actionBloquee onConfirm={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Supprimer définitivement" }).hasAttribute("disabled")).toBe(true);
  });

  it("ferme sans agir sur « Renoncer »", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(<DangerConfirm open onOpenChange={onOpenChange} titre="Supprimer ?" onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("oublie la saisie entre deux ouvertures", async () => {
    const { rerender } = render(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Purger ?" motDeConfirmation="SUPPRIMER" onConfirm={vi.fn()} />,
    );
    await userEvent.type(screen.getByLabelText(/Tapez/), "SUPPRIMER");
    rerender(
      <DangerConfirm open={false} onOpenChange={vi.fn()} titre="Purger ?" motDeConfirmation="SUPPRIMER" onConfirm={vi.fn()} />,
    );
    rerender(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Purger ?" motDeConfirmation="SUPPRIMER" onConfirm={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Supprimer définitivement" }).hasAttribute("disabled")).toBe(true);
  });

  it("affiche l'avertissement et le corps chiffré qu'on lui passe", () => {
    render(
      <DangerConfirm open onOpenChange={vi.fn()} titre="Retirer ?" avertissement="Ce rôle est le vôtre." onConfirm={vi.fn()}>
        <p>12 résultats seront détruits.</p>
      </DangerConfirm>,
    );
    expect(screen.getByText("Ce rôle est le vôtre.")).toBeTruthy();
    expect(screen.getByText("12 résultats seront détruits.")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd frontend && npx vitest run components/admin/DangerConfirm.test.tsx`
Expected: FAIL — `Failed to resolve import "./DangerConfirm"`.

- [ ] **Step 3: Écrire le composant**

Créer `frontend/components/admin/DangerConfirm.tsx` :

```tsx
"use client";
import { useEffect, useId, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

export type DangerConfirmProps = {
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
  /** Question fermée, nommant sa cible : « Retirer « a@b.fr » ? ». */
  titre: string;
  description?: ReactNode;
  /**
   * Ce que l'appelant sait de particulier sur *ce* clic-ci — « Ce rôle est le
   * vôtre ». Distinct de `description`, qui décrit le geste en général.
   */
  avertissement?: ReactNode;
  /**
   * Mot à recopier pour activer l'action. Réservé aux gestes dont la portée est
   * la base entière : l'exiger partout le viderait de son sens.
   */
  motDeConfirmation?: string;
  /** L'action reste inerte — typiquement, le chiffrage d'impact n'est pas arrivé. */
  actionBloquee?: boolean;
  libelleAction?: string;
  enAttente?: boolean;
  onConfirm: () => void | Promise<void>;
  /** Le corps chiffré, quand le geste annonce son ampleur avant d'agir. */
  children?: ReactNode;
};

/**
 * Le seul mécanisme de confirmation des gestes destructifs de l'administration
 * (#499, `ADM-8`).
 *
 * **Le `Dialog` du produit, jamais le `confirm` du navigateur** : ce dernier
 * n'est ni traduisible, ni stylable, ni testable au même titre. Quatre
 * mécanismes coexistaient pour un même verbe ; il n'en reste qu'un.
 *
 * Deux formes d'appel pour un seul rendu — celle-ci, déclarative, pour les
 * gestes qui chiffrent leur impact avant d'agir ; `useDangerConfirm` pour les
 * gestes simples, qui appelaient `window.confirm`.
 *
 * Vit dans `components/admin/` et non dans `ui/` ou `tcn/` : tous ses appelants
 * sont sous `/admin`, ce qui laisse intacte la frontière gelée par #460.
 */
export function DangerConfirm({
  open,
  onOpenChange,
  titre,
  description,
  avertissement,
  motDeConfirmation,
  actionBloquee = false,
  libelleAction = "Supprimer définitivement",
  enAttente = false,
  onConfirm,
  children,
}: DangerConfirmProps) {
  const [saisie, setSaisie] = useState("");
  const champ = useId();

  // La saisie ne survit pas à une fermeture : rouvrir sur un mot déjà tapé
  // rendrait le garde-fou décoratif.
  useEffect(() => {
    if (!open) setSaisie("");
  }, [open]);

  const motManquant = motDeConfirmation !== undefined && saisie !== motDeConfirmation;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titre}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        {avertissement && <p className="text-sm text-destructive">{avertissement}</p>}

        {children}

        {motDeConfirmation !== undefined && (
          <label className="block space-y-1 text-sm" htmlFor={champ}>
            Tapez <strong>{motDeConfirmation}</strong> pour activer la confirmation.
            <Input
              id={champ}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
          </label>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Renoncer
          </Button>
          <Button
            variant="destructive"
            onClick={() => void onConfirm()}
            disabled={enAttente || actionBloquee || motManquant}
          >
            {libelleAction}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/admin/DangerConfirm.test.tsx`
Expected: PASS, 7 tests.

Si `getByLabelText(/Tapez/)` ne trouve rien, c'est que le `<label>` n'entoure pas l'`Input` **et** que le `htmlFor`/`id` ne correspondent pas — vérifier que `useId()` alimente bien les deux.

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run lint
git add components/admin/DangerConfirm.tsx components/admin/DangerConfirm.test.tsx
git commit -m "feat(499): add the single DangerConfirm dialog for destructive admin gestures"
```

---

### Task 2: Le hook impératif `useDangerConfirm` et son provider

**Files:**
- Modify: `frontend/components/admin/DangerConfirm.tsx` (ajout au même fichier)
- Modify: `frontend/components/admin/DangerConfirm.test.tsx` (ajout d'un `describe`)
- Modify: `frontend/app/admin/layout.tsx:82` (le `return`)

**Interfaces:**
- Consumes: `DangerConfirm` de la tâche 1.
- Produces:
  ```ts
  type DemandeDeConfirmation = {
    titre: string;
    description?: ReactNode;
    avertissement?: ReactNode;
    libelleAction?: string;
  };
  export function DangerConfirmProvider(props: { children: ReactNode }): JSX.Element;
  export function useDangerConfirm(): (demande: DemandeDeConfirmation) => Promise<boolean>;
  ```

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `frontend/components/admin/DangerConfirm.test.tsx` (et compléter l'import du haut : `import { DangerConfirm, DangerConfirmProvider, useDangerConfirm } from "./DangerConfirm";`) :

```tsx
describe("useDangerConfirm", () => {
  function Cobaye({ journal }: { journal: (verdict: boolean) => void }) {
    const confirmer = useDangerConfirm();
    return (
      <button
        type="button"
        onClick={async () => journal(await confirmer({ titre: "Retirer « a@b.fr » ?", libelleAction: "Retirer" }))}
      >
        Déclencher
      </button>
    );
  }

  function afficher(journal: (verdict: boolean) => void) {
    return render(
      <DangerConfirmProvider>
        <Cobaye journal={journal} />
      </DangerConfirmProvider>,
    );
  }

  it("résout `true` quand on confirme", async () => {
    const journal = vi.fn();
    afficher(journal);
    await userEvent.click(screen.getByRole("button", { name: "Déclencher" }));
    await userEvent.click(screen.getByRole("button", { name: "Retirer" }));
    await waitFor(() => expect(journal).toHaveBeenCalledWith(true));
  });

  it("résout `false` quand on renonce", async () => {
    const journal = vi.fn();
    afficher(journal);
    await userEvent.click(screen.getByRole("button", { name: "Déclencher" }));
    await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
    await waitFor(() => expect(journal).toHaveBeenCalledWith(false));
  });

  it("refuse de servir hors de son provider", () => {
    // Sans le provider, le geste s'exécuterait sans confirmation : mieux vaut
    // un écran cassé au premier rendu qu'une destruction silencieuse.
    const muet = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Cobaye journal={vi.fn()} />)).toThrow(/DangerConfirmProvider/);
    muet.mockRestore();
  });
});
```

Compléter aussi l'import de Testing Library en tête de fichier : `import { render, screen, waitFor } from "@testing-library/react";`

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd frontend && npx vitest run components/admin/DangerConfirm.test.tsx`
Expected: FAIL — `DangerConfirmProvider` et `useDangerConfirm` ne sont pas exportés.

- [ ] **Step 3: Ajouter le provider et le hook**

Ajouter en tête de `DangerConfirm.tsx` les imports manquants :

```tsx
import { createContext, useCallback, useContext, useEffect, useId, useState, type ReactNode } from "react";
```

Puis, à la fin du fichier :

```tsx
export type DemandeDeConfirmation = {
  titre: string;
  description?: ReactNode;
  avertissement?: ReactNode;
  libelleAction?: string;
};

const DangerConfirmContext = createContext<
  ((demande: DemandeDeConfirmation) => Promise<boolean>) | null
>(null);

/**
 * Le dialog partagé des gestes simples — ceux qui n'ont pas d'impact à chiffrer.
 *
 * Un provider et non un `useState` par tableau : sans lui, chaque tableau
 * porterait l'état d'ouverture **et** la ligne visée, dupliqués autant de fois
 * qu'il y a d'écrans. Monté dans `app/admin/layout.tsx`, pas à la racine : tous
 * les appelants sont sous `/admin`.
 */
export function DangerConfirmProvider({ children }: { children: ReactNode }) {
  const [enCours, setEnCours] = useState<{
    demande: DemandeDeConfirmation;
    resoudre: (verdict: boolean) => void;
  } | null>(null);

  const confirmer = useCallback(
    (demande: DemandeDeConfirmation) =>
      new Promise<boolean>((resoudre) => setEnCours({ demande, resoudre })),
    [],
  );

  function repondre(verdict: boolean) {
    enCours?.resoudre(verdict);
    setEnCours(null);
  }

  return (
    <DangerConfirmContext.Provider value={confirmer}>
      {children}
      {enCours && (
        <DangerConfirm
          open
          onOpenChange={(ouvert) => {
            // Échap et clic hors du dialog passent par ici : les deux valent un
            // renoncement, sans quoi la promesse ne se résoudrait jamais et
            // l'appelant resterait suspendu.
            if (!ouvert) repondre(false);
          }}
          titre={enCours.demande.titre}
          description={enCours.demande.description}
          avertissement={enCours.demande.avertissement}
          libelleAction={enCours.demande.libelleAction}
          onConfirm={() => repondre(true)}
        />
      )}
    </DangerConfirmContext.Provider>
  );
}

/**
 * Remplace `window.confirm` un pour un :
 * `if (!(await confirmer({ titre, description, libelleAction }))) return;`
 */
export function useDangerConfirm() {
  const confirmer = useContext(DangerConfirmContext);
  if (!confirmer) {
    throw new Error("useDangerConfirm exige un DangerConfirmProvider au-dessus de lui.");
  }
  return confirmer;
}
```

- [ ] **Step 4: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/admin/DangerConfirm.test.tsx`
Expected: PASS, 10 tests.

- [ ] **Step 5: Monter le provider dans le layout d'administration**

Dans `frontend/app/admin/layout.tsx`, ajouter l'import et remplacer le `return` final :

```tsx
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
```

```tsx
  // Le dialog des gestes destructifs, monté une fois pour toutes les
  // sous-routes (#499). Composant client sous un layout serveur : les enfants
  // rendus par le serveur traversent le provider sans devenir clients.
  return <DangerConfirmProvider>{children}</DangerConfirmProvider>;
```

- [ ] **Step 6: Vérifier que la garde du layout n'a pas bougé**

Run: `cd frontend && npx vitest run app/admin/layout.test.tsx`
Expected: PASS. Si un test comparait le rendu à `children` exactement, l'ajuster pour qu'il vérifie que les enfants sont toujours rendus — la garde, elle, est inchangée.

- [ ] **Step 7: Commit**

```bash
cd frontend && npm run lint
git add components/admin/DangerConfirm.tsx components/admin/DangerConfirm.test.tsx app/admin/layout.tsx app/admin/layout.test.tsx
git commit -m "feat(499): mount the shared danger dialog under the admin layout"
```

---

### Task 3: Une entrée de navigation gardée par un OU de deux pouvoirs

**Files:**
- Modify: `frontend/components/layout/nav.config.ts:50` (type), `:306` (`estVisible`), `:202` (nouvelle entrée en fin de section `admin`)
- Test: `frontend/components/layout/nav.config.test.ts`

**Interfaces:**
- Produces: `NavItem["permission"]` devient `string | string[]` ; l'entrée `a-maintenance` pointe sur `/admin/maintenance`, ce que `ecran("/admin/maintenance")` exigera à la tâche 4.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `frontend/components/layout/nav.config.test.ts` (adapter les imports au fichier existant : il importe déjà `NAV` et, s'il ne l'importe pas, ajouter `estVisible` et `ROLE`) :

```ts
describe("permission en OU", () => {
  const MAINTENANCE = NAV.flatMap((s) => s.items).find((i) => i.id === "a-maintenance")!;

  it("annonce la maintenance à qui ne détient que la purge des résultats", () => {
    expect(estVisible(MAINTENANCE, new Set(["participations:wipe_all"]), ROLE.CONNECTED)).toBe(true);
  });

  it("l'annonce aussi à qui ne détient que la purge des épreuves", () => {
    expect(estVisible(MAINTENANCE, new Set(["courses:wipe_all"]), ROLE.CONNECTED)).toBe(true);
  });

  it("ne l'annonce pas à qui n'a ni l'une ni l'autre", () => {
    expect(estVisible(MAINTENANCE, new Set(["courses:write"]), ROLE.CONNECTED)).toBe(false);
  });
});
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd frontend && npx vitest run components/layout/nav.config.test.ts`
Expected: FAIL — `a-maintenance` est `undefined`, l'accès `!` lève.

- [ ] **Step 3: Élargir le type et le test de visibilité**

Dans `frontend/components/layout/nav.config.ts`, remplacer la ligne `permission?: string;` (`:50`) par :

```ts
  /**
   * Un code, ou plusieurs en **OU** : l'entrée est portée dès que la session en
   * détient un. Le OU sert `/admin/maintenance`, dont les deux purges relèvent
   * de pouvoirs distincts et attribuables séparément (`courses:wipe_all`,
   * `participations:wipe_all`) — n'en nommer qu'un annoncerait l'écran à qui
   * n'y peut rien faire, exactement le défaut que `a-courses` se reproche
   * ci-dessous (ADM-6).
   */
  permission?: string | string[];
```

Puis, dans `estVisible` (`:306`), remplacer la dernière ligne du `return` par :

```ts
    (!item.permission ||
      (Array.isArray(item.permission)
        ? item.permission.some((code) => pouvoirs.has(code))
        : pouvoirs.has(item.permission)))
```

- [ ] **Step 4: Déclarer l'entrée**

Dans la section `admin` (`id: "admin"`), après l'entrée `a-feedback` et avant le `],` qui ferme `items` (autour de `:202`) :

```ts
      // Les deux purges globales vivaient en pied de `/admin/courses`, l'écran
      // où l'on vient corriger une date : feuilleter le catalogue jusqu'au bout
      // menait à un clic de la destruction de toute la base (#499, ADM-7). Un
      // écran à elles, et le voisinage disparaît.
      {
        id: "a-maintenance",
        label: "Maintenance",
        description:
          "Les gestes sans retour : vider les résultats, ou vider le catalogue entier. Rien ici ne se répare — chaque geste annonce son ampleur avant d'agir.",
        href: "/admin/maintenance",
        permission: ["participations:wipe_all", "courses:wipe_all"],
      },
```

- [ ] **Step 5: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/layout/nav.config.test.ts`
Expected: PASS. Le test existant `:22` (`expect(item.permission).toBeTruthy()`) reste vert : un tableau non vide est truthy.

- [ ] **Step 6: Vérifier que rien d'autre ne lit `permission`**

Run: `cd frontend && grep -rn "\.permission\b" app components lib --include='*.ts' --include='*.tsx' | grep -v permissions`
Expected: seulement `nav.config.ts` et `nav.config.test.ts`. Si un autre appelant apparaît, le traiter avant de commiter — le type a changé sous lui.

- [ ] **Step 7: Commit**

```bash
cd frontend && npm run lint && npx vitest run components/layout
git add components/layout/nav.config.ts components/layout/nav.config.test.ts
git commit -m "feat(499): let a nav entry be guarded by any one of several permissions"
```

---

### Task 4: L'écran `/admin/maintenance` et le déménagement des deux purges

**Files:**
- Create: `frontend/app/admin/maintenance/page.tsx`
- Modify: `frontend/components/admin/WipeParticipationsCard.tsx`, `frontend/components/admin/WipeCoursesCard.tsx`
- Modify: `frontend/app/admin/courses/page.tsx:5-6,43-44`
- Test: les deux `Wipe*Card.test.tsx` existants

**Interfaces:**
- Consumes: `DangerConfirm` (tâche 1), `ecran("/admin/maintenance")` (tâche 3).
- Produces: rien de neuf — les deux cartes gardent leur nom et leur garde par pouvoir.

- [ ] **Step 1: Faire échouer les tests existants en les déplaçant vers le nouveau mécanisme**

Les deux suites `WipeCoursesCard.test.tsx` et `WipeParticipationsCard.test.tsx` couvrent déjà le chiffrage, le mot à taper et le refus quand le pouvoir manque. Elles doivent rester vertes **après** réécriture : c'est le filet. Ajouter à chacune un test qui échoue aujourd'hui, celui de l'oubli de la saisie — comportement que le composant partagé apporte :

```tsx
it("oublie le mot tapé si on renonce puis rouvre", async () => {
  afficher(); // helper existant du fichier
  await userEvent.click(await screen.findByRole("button", { name: /Purger tous les résultats/ }));
  await userEvent.type(await screen.findByLabelText(/Tapez/), "SUPPRIMER");
  await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
  await userEvent.click(screen.getByRole("button", { name: /Purger tous les résultats/ }));
  expect(
    (await screen.findByRole("button", { name: "Purger définitivement" })).hasAttribute("disabled"),
  ).toBe(true);
});
```

Dans `WipeCoursesCard.test.tsx`, remplacer « Purger tous les résultats » par « Supprimer toutes les épreuves » et « Purger définitivement » par « Supprimer définitivement ».

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd frontend && npx vitest run components/admin/WipeParticipationsCard.test.tsx components/admin/WipeCoursesCard.test.tsx`
Expected: FAIL sur les deux nouveaux tests — la saisie survit aujourd'hui à la fermeture par « Renoncer » seulement grâce à `fermer()`, mais pas quand le dialog se referme autrement ; et surtout, le comportement doit venir du composant partagé.

- [ ] **Step 3: Réécrire `WipeParticipationsCard` sur `DangerConfirm`**

Remplacer le corps de `frontend/components/admin/WipeParticipationsCard.tsx` (garder le docstring existant en tête, en remplaçant la phrase « Vit au bas de `/admin/courses`… » par « Vit sur `/admin/maintenance` (#499) : le geste n'a rien à faire sur l'écran où l'on corrige une date. ») :

```tsx
"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useParticipationsWipeImpact, useWipeAllParticipations } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";

const MOT_DE_CONFIRMATION = "SUPPRIMER";

export function WipeParticipationsCard() {
  const [ouvert, setOuvert] = useState(false);
  const session = useSession();
  const impact = useParticipationsWipeImpact(ouvert);
  const purge = useWipeAllParticipations();

  const peutPurger = session.data?.permissions.includes("participations:wipe_all") ?? false;
  if (!peutPurger) return null;

  async function confirmer() {
    try {
      await purge.mutateAsync();
      toast.success("Tous les résultats ont été supprimés.");
      setOuvert(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <>
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Purger les résultats</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[var(--tcn-text-faint)] text-sm">
            Vide entièrement les résultats pour repartir d&apos;une base propre —
            avant un rescrape complet, par exemple. Les épreuves et leurs sources
            restent intactes ; seuls les résultats et les fiches coureur qu&apos;ils
            laissent vides sont détruits.
          </p>
          <Button variant="destructive" onClick={() => setOuvert(true)}>
            Purger tous les résultats
          </Button>
        </CardContent>
      </Card>

      <DangerConfirm
        open={ouvert}
        onOpenChange={setOuvert}
        titre="Purger tous les résultats ?"
        description={
          <>
            Cette action est <strong>irréversible</strong>. Les épreuves et leurs
            sources restent en base : un rescrape pourra les réimporter aussitôt.
          </>
        }
        motDeConfirmation={MOT_DE_CONFIRMATION}
        actionBloquee={!impact.data}
        libelleAction="Purger définitivement"
        enAttente={purge.isPending}
        onConfirm={confirmer}
      >
        {impact.isLoading && <Skeleton className="h-16 w-full" />}

        {impact.error && (
          <p className="text-sm text-destructive">
            L&apos;ampleur de la purge n&apos;a pas pu être chiffrée. Par prudence,
            la purge n&apos;est pas proposée — réessayez plus tard.
          </p>
        )}

        {impact.data && (
          <ul className="space-y-1 text-sm">
            <li>
              <strong>{impact.data.participations}</strong> résultat
              {impact.data.participations === 1 ? " sera détruit" : "s seront détruits"}.
            </li>
            <li>
              <strong>{impact.data.athletes}</strong> fiche
              {impact.data.athletes === 1
                ? " coureur sera retirée"
                : "s coureur seront retirées"}
              .
            </li>
          </ul>
        )}
      </DangerConfirm>
    </>
  );
}
```

Note : l'action reste inerte tant que `impact.data` est absent — c'est ce que faisait le rendu conditionnel du bouton, désormais porté par `actionBloquee`. Si un test existant vérifiait l'**absence** du bouton avant chiffrage, le réécrire pour vérifier qu'il est `disabled` : un bouton visible mais inerte dit mieux ce qui se passe qu'un bouton absent.

- [ ] **Step 4: Réécrire `WipeCoursesCard` de la même façon**

Même transformation, en gardant ses propres textes : titre `"Supprimer toutes les épreuves ?"`, libellé d'action `"Supprimer définitivement"`, toast `"Toutes les épreuves ont été supprimées."`, sa liste chiffrée à trois éléments (`courses`, `participations`, `athletes`), sa `description` propre, et sa carte « Repartir de zéro ». Le hook d'impact est `useCoursesWipeImpact`, la mutation `useWipeAllCourses`, le pouvoir `courses:wipe_all`.

- [ ] **Step 5: Créer l'écran**

Créer `frontend/app/admin/maintenance/page.tsx` :

```tsx
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { WipeCoursesCard } from "@/components/admin/WipeCoursesCard";
import { WipeParticipationsCard } from "@/components/admin/WipeParticipationsCard";

/**
 * Les gestes sans retour, et rien d'autre (#499, `ADM-7`).
 *
 * Ces deux purges vivaient en pied de `/admin/courses`, sous le tableau où l'on
 * vient corriger la date d'une épreuve : trois `Card` dans le même `space-y-6`,
 * donc un administrateur qui feuillette le catalogue jusqu'à la dernière page
 * et fait défiler se retrouvait à un clic de la destruction de toute la base.
 * Les replier sur place aurait caché le voisinage sans le supprimer.
 *
 * Aucune garde ici : le `layout.tsx` de `/admin` couvre ses sous-routes, chaque
 * carte teste son propre pouvoir, et la protection réelle est côté serveur.
 */
export default function AdminMaintenancePage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/maintenance")} />
        <section aria-labelledby="zone-de-dangers" className="space-y-6">
          <h2 id="zone-de-dangers" className="font-heading text-lg text-destructive">
            Zone de dangers — gestes sans retour
          </h2>
          <WipeParticipationsCard />
          <WipeCoursesCard />
        </section>
      </div>
    </PageShell>
  );
}
```

- [ ] **Step 6: Vider le pied de `/admin/courses`**

Dans `frontend/app/admin/courses/page.tsx`, supprimer les deux lignes d'import de `WipeCoursesCard` et `WipeParticipationsCard`, et les deux lignes `<WipeParticipationsCard />` / `<WipeCoursesCard />` du JSX. Ajouter au docstring de la page :

```
 * Les deux purges globales ont quitté ce pied de page pour `/admin/maintenance`
 * (#499) : on ne détruit pas la base depuis l'écran où l'on corrige une date.
```

- [ ] **Step 7: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/admin/WipeParticipationsCard.test.tsx components/admin/WipeCoursesCard.test.tsx`
Expected: PASS.

Run: `cd frontend && npm run build`
Expected: succès — c'est ce qui prouve que `ecran("/admin/maintenance")` trouve son entrée (il lève sinon).

- [ ] **Step 8: Commit**

```bash
cd frontend && npm run lint
git add app/admin/maintenance app/admin/courses/page.tsx components/admin/WipeCoursesCard.tsx components/admin/WipeParticipationsCard.tsx components/admin/WipeCoursesCard.test.tsx components/admin/WipeParticipationsCard.test.tsx
git commit -m "feat(499): move both global wipes to a dedicated maintenance screen"
```

---

### Task 5: `DeleteCourseDialog` sur le mécanisme partagé

**Files:**
- Modify: `frontend/components/admin/DeleteCourseDialog.tsx`
- Test: `frontend/components/admin/DeleteCourseDialog.test.tsx`

**Interfaces:**
- Consumes: `DangerConfirm`.
- Produces: l'API publique du composant ne bouge pas — `{ course, open, onOpenChange }`. `CoursesAdminTable` n'est pas touché.

- [ ] **Step 1: Vérifier le filet avant de toucher**

Run: `cd frontend && npx vitest run components/admin/DeleteCourseDialog.test.tsx`
Expected: PASS. Ces tests décrivent le comportement à conserver ; ils ne doivent pas changer, sauf si l'un d'eux vérifie l'absence du bouton d'action avant chiffrage — auquel cas le réécrire en `disabled`, comme à la tâche 4.

- [ ] **Step 2: Réécrire le rendu**

Remplacer tout le JSX retourné par :

```tsx
  return (
    <DangerConfirm
      open={open}
      onOpenChange={onOpenChange}
      titre={`Supprimer « ${course.name} » ?`}
      description={
        <>
          Cette action est <strong>irréversible</strong>. Elle restera tracée dans le
          journal d&apos;administration, mais rien ne permettra de revenir en arrière.
        </>
      }
      actionBloquee={!impact.data}
      enAttente={suppression.isPending}
      onConfirm={confirmer}
    >
      {impact.isLoading && <Skeleton className="h-16 w-full" />}

      {impact.error && (
        <p className="text-sm text-destructive">
          L&apos;ampleur de la suppression n&apos;a pas pu être chiffrée. Par prudence,
          la suppression n&apos;est pas proposée — réessayez plus tard.
        </p>
      )}

      {impact.data && (
        <ul className="space-y-1 text-sm">
          <li>
            <strong>{impact.data.participations}</strong> résultat
            {impact.data.participations === 1 ? " sera détruit" : "s seront détruits"}.
          </li>
          <li>
            <strong>{impact.data.athletes}</strong> fiche
            {impact.data.athletes === 1
              ? " coureur ne conservera plus aucun résultat et sera retirée"
              : "s coureur ne conserveront plus aucun résultat et seront retirées"}
            .
          </li>
        </ul>
      )}
    </DangerConfirm>
  );
```

Remplacer les imports de `Button` et des sept sous-composants de `Dialog` par le seul :

```tsx
import { DangerConfirm } from "@/components/admin/DangerConfirm";
```

`Skeleton` et `toast` restent. Ajouter au docstring, après le paragraphe « Aucun bouton d'annulation » :

```
 * Passé sur `DangerConfirm` (#499) : la coquille, les libellés et la place du
 * bouton de renoncement sont désormais les mêmes que pour tous les autres
 * gestes destructifs de l'administration.
```

- [ ] **Step 3: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/admin/DeleteCourseDialog.test.tsx components/admin/CoursesAdminTable.test.tsx`
Expected: PASS sur les deux — le second prouve que l'API du composant n'a pas bougé.

- [ ] **Step 4: Commit**

```bash
cd frontend && npm run lint
git add components/admin/DeleteCourseDialog.tsx components/admin/DeleteCourseDialog.test.tsx
git commit -m "refactor(499): rebuild the course deletion dialog on DangerConfirm"
```

---

### Task 6: `AllowedEmailsTable` — le rouge sur « Retirer », le dialog à la place de `window.confirm`

**Files:**
- Modify: `frontend/components/admin/AllowedEmailsTable.tsx:80-98` (la fonction `supprimer`), `:228-237` (le bouton)
- Test: `frontend/components/admin/AllowedEmailsTable.test.tsx`

**Interfaces:**
- Consumes: `useDangerConfirm()` de la tâche 2.

- [ ] **Step 1: Réécrire les tests qui simulent `window.confirm`**

Dans `frontend/components/admin/AllowedEmailsTable.test.tsx` :

1. Supprimer tout `vi.spyOn(window, "confirm")` / `window.confirm = vi.fn()`.
2. Envelopper le rendu du helper d'affichage dans le provider :

```tsx
import { DangerConfirmProvider } from "./DangerConfirm";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <AllowedEmailsTable />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}
```

3. Dans les tests de retrait, cliquer « Retirer » **puis** confirmer dans le dialog. Ajouter ces deux tests :

```tsx
it("ne retire rien tant que la confirmation n'est pas donnée", async () => {
  afficher();
  await userEvent.click((await screen.findAllByRole("button", { name: "Retirer" }))[0]);
  expect(screen.getByText(/Retirer « .+ » \?/)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
  expect(removeAllowedEmail).not.toHaveBeenCalled();
});

it("retire l'adresse une fois la confirmation donnée", async () => {
  removeAllowedEmail.mockResolvedValue(undefined);
  afficher();
  await userEvent.click((await screen.findAllByRole("button", { name: "Retirer" }))[0]);
  // Le bouton du dialog porte le même libellé : c'est le dernier rendu.
  const boutons = screen.getAllByRole("button", { name: "Retirer" });
  await userEvent.click(boutons[boutons.length - 1]);
  await waitFor(() => expect(removeAllowedEmail).toHaveBeenCalled());
});

it("laisse « Fermer les sessions » neutre et sans confirmation", async () => {
  revokeSessions.mockResolvedValue({ sessions: 1, accounts: 1 });
  afficher();
  await userEvent.click((await screen.findAllByRole("button", { name: /Fermer les sessions/ }))[0]);
  await waitFor(() => expect(revokeSessions).toHaveBeenCalled());
});
```

Adapter les noms des mocks (`removeAllowedEmail`, `revokeSessions`) à ceux déjà déclarés en tête du fichier.

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd frontend && npx vitest run components/admin/AllowedEmailsTable.test.tsx`
Expected: FAIL — `window.confirm is not a function` sous jsdom, ou le dialog attendu ne s'affiche pas.

- [ ] **Step 3: Remplacer `window.confirm` par le hook**

Ajouter l'import et le hook :

```tsx
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
```

```tsx
  const confirmerLeDanger = useDangerConfirm();
```

Remplacer le début de `supprimer` (`:80-89`) par :

```tsx
  async function supprimer(acces: AllowedEmail) {
    // Geste destructif : il ferme un accès et coupe les sessions vivantes. Le
    // dialog du produit et non le `confirm` du navigateur (#499) — ce dernier
    // n'est ni traduisible, ni stylable, ni testable au même titre.
    if (
      !(await confirmerLeDanger({
        titre: `Retirer « ${acces.email} » ?`,
        description: "Ses sessions ouvertes seront fermées immédiatement.",
        libelleAction: "Retirer",
      }))
    ) {
      return;
    }
```

- [ ] **Step 4: Poser le rouge sur « Retirer », et pas sur son voisin**

Remplacer `variant="outline"` par `variant="destructive"` sur le seul bouton « Retirer » (`:230`), et ajouter juste au-dessus :

```tsx
                    {/* `destructive` et son voisin neutre : le geste le plus
                        grave des deux était jusqu'ici le moins signalé (#499,
                        ADM-8). Fermer les sessions se répare par une
                        reconnexion, retirer l'adresse non. */}
```

Ne **pas** toucher au bouton « Fermer les sessions » — son commentaire existant (`:209-214`) reste vrai et explique déjà pourquoi.

- [ ] **Step 5: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/admin/AllowedEmailsTable.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && npm run lint
git add components/admin/AllowedEmailsTable.tsx components/admin/AllowedEmailsTable.test.tsx
git commit -m "feat(499): mark removing an allowed address as destructive and confirm it in-product"
```

---

### Task 7: `GroupsTable` — le rouge, la confirmation, et le refus dit avant le clic

**Files:**
- Modify: `frontend/components/admin/GroupsTable.tsx:67-79` (`detruire`), `:168-179` (le bouton)
- Test: `frontend/components/admin/GroupsTable.test.tsx`

**Interfaces:**
- Consumes: `useDangerConfirm()`, `Tooltip`/`TooltipTrigger`/`TooltipContent` de `components/ui/tooltip`.
- Le champ lu est `groupe.member_count`, déjà rendu dans la colonne « Membres » (`:165`).

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `frontend/components/admin/GroupsTable.test.tsx`, envelopper le helper `afficher()` dans `<DangerConfirmProvider>` (même forme qu'à la tâche 6), puis ajouter :

```tsx
const VIDE: Group = { ...CODIR, id: 4, slug: "officiels", name: "Officiels", member_count: 0 };

it("annonce avant le clic qu'un groupe peuplé ne peut pas être supprimé", async () => {
  listGroups.mockResolvedValue([CODIR]); // member_count: 2
  afficher();
  const bouton = await screen.findByRole("button", { name: "Supprimer le groupe Codir" });
  expect(bouton.hasAttribute("disabled")).toBe(true);
  expect(screen.getByText(/Videz d'abord le groupe \(2 membres\)/)).toBeTruthy();
});

it("exige une confirmation nominative avant de supprimer un groupe vide", async () => {
  listGroups.mockResolvedValue([VIDE]);
  afficher();
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer le groupe Officiels" }));
  expect(screen.getByText("Supprimer « Officiels » ?")).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
  expect(deleteGroup).not.toHaveBeenCalled();
});

it("supprime le groupe vide une fois la confirmation donnée", async () => {
  listGroups.mockResolvedValue([VIDE]);
  deleteGroup.mockResolvedValue(undefined);
  afficher();
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer le groupe Officiels" }));
  await userEvent.click(screen.getByRole("button", { name: "Supprimer définitivement" }));
  await waitFor(() => expect(deleteGroup).toHaveBeenCalledWith(VIDE.id));
});
```

L'infobulle est rendue dans un portail : `screen.getByText` la trouve après ouverture. Si elle n'apparaît qu'au survol, remplacer l'assertion du premier test par un `await userEvent.hover(bouton.parentElement!)` avant le `getByText`.

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd frontend && npx vitest run components/admin/GroupsTable.test.tsx`
Expected: FAIL — le bouton n'est pas désactivé et aucun dialog n'apparaît.

- [ ] **Step 3: Confirmer avant de détruire**

Ajouter les imports :

```tsx
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
```

Déclarer le hook dans le composant : `const confirmerLeDanger = useDangerConfirm();`

Remplacer `detruire` (`:67-79`) par :

```tsx
  async function detruire(groupe: Group) {
    // Le geste détruit un groupe : il se confirme, comme tout ce qui ne se
    // refait pas (#499, ADM-8). L'argument d'avant — « l'API refuse un groupe
    // peuplé, donc rien n'est perdu » — ne tenait que pour les groupes peuplés,
    // dont le bouton est désormais inerte et dit pourquoi.
    if (
      !(await confirmerLeDanger({
        titre: `Supprimer « ${groupe.name} » ?`,
        description: "Le groupe disparaît. Les comptes qui en relevaient ne sont pas touchés.",
      }))
    ) {
      return;
    }
    try {
      await supprimer.mutateAsync(groupe.id);
      toast.success(`« ${groupe.name} » a été supprimé.`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
```

- [ ] **Step 4: Dire le refus avant le clic**

Remplacer le bloc `{peutEcrire && (<Button …>Supprimer</Button>)}` (`:168-179`) par :

```tsx
                    {peutEcrire &&
                      (groupe.member_count > 0 ? (
                        // Le refus du serveur, dit **avant** le clic — même
                        // patron que `raisonDeNonSuppression` de
                        // `RolePermissionsEditor` (#499). Le déclencheur porte
                        // sur un `<span tabIndex={0}>` et non sur le bouton :
                        // un bouton désactivé ne reçoit ni survol ni focus, son
                        // infobulle ne s'ouvrirait jamais.
                        <Tooltip>
                          <TooltipTrigger render={<span tabIndex={0} className="inline-block" />}>
                            <Button
                              size="sm"
                              variant="destructive"
                              aria-label={`Supprimer le groupe ${groupe.name}`}
                              disabled
                            >
                              Supprimer
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent side="left">
                            Videz d&apos;abord le groupe ({groupe.member_count} membre
                            {groupe.member_count === 1 ? "" : "s"}).
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <Button
                          size="sm"
                          variant="destructive"
                          aria-label={`Supprimer le groupe ${groupe.name}`}
                          onClick={() => detruire(groupe)}
                          // Bornée à **cette** ligne : `isPending` seul griserait
                          // tous les boutons du tableau pendant une suppression.
                          disabled={supprimer.isPending && supprimer.variables === groupe.id}
                        >
                          Supprimer
                        </Button>
                      ))}
```

- [ ] **Step 5: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/admin/GroupsTable.test.tsx`
Expected: PASS.

Si le `render=` de `TooltipTrigger` ne compile pas, vérifier la signature dans `components/ui/tooltip.tsx` — le dépôt est sur Base UI, dont l'API de composition est `render={<element />}` et non `asChild`.

- [ ] **Step 6: Commit**

```bash
cd frontend && npm run lint
git add components/admin/GroupsTable.tsx components/admin/GroupsTable.test.tsx
git commit -m "feat(499): confirm group deletion, and say before the click when it will be refused"
```

---

### Task 8: `RolePermissionsEditor` — les deux derniers `window.confirm`

**Files:**
- Modify: `frontend/components/admin/RolePermissionsEditor.tsx:200-212` (`basculerLeStatut`), `:214-215` (`supprimer`), `:369-374` (le bouton « Supprimer »)
- Test: `frontend/components/admin/RolePermissionsEditor.test.tsx:465` et voisins

**Interfaces:**
- Consumes: `useDangerConfirm()`.

- [ ] **Step 1: Réécrire les tests**

Envelopper le helper d'affichage du fichier dans `<DangerConfirmProvider>`, supprimer le mock de `window.confirm` (`:465` et sa mise en place), et remplacer les assertions `expect(window.confirm).toHaveBeenCalled()` par un clic sur le dialog. Ajouter :

```tsx
it("ne supprime le rôle qu'après confirmation", async () => {
  afficher();
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer" }));
  expect(screen.getByText(/Supprimer le rôle « .+ » \?/)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
  expect(deleteRole).not.toHaveBeenCalled();
});

it("confirme la bascule de superutilisateur sans la peindre en rouge", async () => {
  afficher();
  const bascule = await screen.findByRole("button", { name: /superutilisateur/ });
  // Poser le statut n'est ni une fermeture d'accès ni une destruction : la
  // couleur reste neutre, seule la confirmation est due.
  expect(bascule.className).not.toContain("destructive");
  await userEvent.click(bascule);
  await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
  expect(updateRole).not.toHaveBeenCalled();
});
```

Adapter `deleteRole` / `updateRole` aux noms de mocks du fichier, et `afficher()` au helper existant (il faudra peut-être lui passer un rôle non système et une session superutilisateur pour que les deux boutons soient rendus — voir `peutPoserLeStatut` `:414` et `raisonDeNonSuppression`).

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd frontend && npx vitest run components/admin/RolePermissionsEditor.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Remplacer les deux appels**

Ajouter `import { useDangerConfirm } from "@/components/admin/DangerConfirm";` et `const confirmerLeDanger = useDangerConfirm();` dans le composant qui porte `basculerLeStatut` et `supprimer`.

`basculerLeStatut` (`:200-212`) devient :

```tsx
  async function basculerLeStatut() {
    const pose = !base.is_superuser;
    // Confirmé dans les deux sens, mais **neutre** de couleur : ni poser ni
    // retirer le statut ne ferme un accès ni ne détruit une donnée (#499). Le
    // lot n'invente pas une troisième catégorie de gravité pour ce bouton.
    if (
      !(await confirmerLeDanger({
        titre: pose
          ? `Faire de « ${base.name} » un superutilisateur ?`
          : `Retirer le statut de superutilisateur à « ${base.name} » ?`,
        description: pose
          ? "Il franchira tout pouvoir, y compris ceux livrés après lui."
          : "Il ne franchira plus que les pouvoirs qu'il porte explicitement.",
        libelleAction: pose ? "Poser le statut" : "Retirer le statut",
      }))
    ) {
      return;
    }
    await appliquer({ is_superuser: pose }, pose ? "Statut posé." : "Statut retiré.");
  }
```

`supprimer` (`:214-215`) commence désormais par :

```tsx
  async function supprimer() {
    if (
      !(await confirmerLeDanger({
        titre: `Supprimer le rôle « ${role.name} » ?`,
        description: "Ce geste est sans retour.",
      }))
    ) {
      return;
    }
```

- [ ] **Step 4: Poser le rouge sur « Supprimer » seul**

Sur le bouton `:369-374`, remplacer `variant="outline"` par `variant="destructive"`. Ne pas toucher au bouton de bascule (`:346`), qui reste `outline`.

- [ ] **Step 5: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/admin/RolePermissionsEditor.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && npm run lint
git add components/admin/RolePermissionsEditor.tsx components/admin/RolePermissionsEditor.test.tsx
git commit -m "feat(499): move the role editor's two confirmations off window.confirm"
```

---

### Task 9: `UserRolesTable` — confirmer le retrait d'un rôle, et le dire quand c'est le sien

**Files:**
- Modify: `frontend/components/admin/UserRolesTable.tsx:47-57` (`oter`), `:123-134` (la croix)
- Test: `frontend/components/admin/UserRolesTable.test.tsx`

**Interfaces:**
- Consumes: `useDangerConfirm()`, `useSession()` (`@/lib/queries/auth`) — ce dernier n'est **pas** encore importé dans ce fichier.

- [ ] **Step 1: Écrire les tests qui échouent**

Envelopper le helper d'affichage dans `<DangerConfirmProvider>`, puis ajouter :

```tsx
it("ne retire pas le rôle au premier clic", async () => {
  afficher();
  await userEvent.click(await screen.findByRole("button", { name: /Retirer le rôle admin de/ }));
  expect(screen.getByText(/Retirer le rôle « admin » à « .+ » \?/)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
  expect(revokeRole).not.toHaveBeenCalled();
});

it("retire le rôle une fois la confirmation donnée", async () => {
  revokeRole.mockResolvedValue(undefined);
  afficher();
  await userEvent.click(await screen.findByRole("button", { name: /Retirer le rôle admin de/ }));
  await userEvent.click(screen.getByRole("button", { name: "Retirer le rôle" }));
  await waitFor(() => expect(revokeRole).toHaveBeenCalled());
});

it("avertit quand le rôle retiré est le sien", async () => {
  // La session mockée porte l'id de la ligne visée.
  getSession.mockResolvedValue({ ...MOI, id: MOI.id });
  listAdminUsers.mockResolvedValue([{ ...UTILISATEUR, id: MOI.id }]);
  afficher();
  await userEvent.click(await screen.findByRole("button", { name: /Retirer le rôle admin de/ }));
  expect(screen.getByText(/Ce rôle est le vôtre/)).toBeTruthy();
});

it("n'avertit pas quand le rôle retiré est celui d'un autre", async () => {
  getSession.mockResolvedValue({ ...MOI, id: 1 });
  listAdminUsers.mockResolvedValue([{ ...UTILISATEUR, id: 2 }]);
  afficher();
  await userEvent.click(await screen.findByRole("button", { name: /Retirer le rôle admin de/ }));
  expect(screen.queryByText(/Ce rôle est le vôtre/)).toBeNull();
});
```

Adapter `MOI`, `UTILISATEUR`, `revokeRole`, `getSession`, `listAdminUsers` aux fixtures et mocks du fichier.

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd frontend && npx vitest run components/admin/UserRolesTable.test.tsx`
Expected: FAIL — le retrait part au premier clic, aucun dialog.

- [ ] **Step 3: Confirmer, et annoncer le cas « c'est le vôtre »**

Ajouter les imports :

```tsx
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { useSession } from "@/lib/queries/auth";
```

Dans le composant :

```tsx
  const confirmerLeDanger = useDangerConfirm();
  const session = useSession();
```

Remplacer `oter` (`:47-57`) par :

```tsx
  async function oter(utilisateur: AdminUser, role: SessionRole) {
    // Un retrait de rôle ôte des pouvoirs : il se confirme, nommément, comme le
    // retrait d'une adresse autorisée dont la gravité est comparable (#499,
    // ADM-9). Il partait jusqu'ici au premier clic, sans annulation.
    //
    // L'avertissement se borne à ce que le front sait avec certitude — « c'est
    // vous ». Le serveur, lui, refuse par un 409 que l'organisation perde son
    // dernier administrateur actif (`admin_roles.py:182`) : ce prédicat-là est
    // le sien, le recalculer ici le ferait diverger au premier ajustement.
    const cEstMoi = session.data?.id === utilisateur.id;
    if (
      !(await confirmerLeDanger({
        titre: `Retirer le rôle « ${role.name} » à « ${utilisateur.display_name} » ?`,
        description: "Les pouvoirs qu'il portait s'appliquent dès la requête suivante.",
        avertissement: cEstMoi ? (
          <>
            <strong>Ce rôle est le vôtre.</strong> Vous pourriez perdre l&apos;accès à cet écran.
          </>
        ) : undefined,
        libelleAction: "Retirer le rôle",
      }))
    ) {
      return;
    }
    try {
      await retirer.mutateAsync({ userId: utilisateur.id, roleId: role.id });
      toast.success("Rôle retiré.");
    } catch (e) {
      // Le 409 du dernier administrateur porte son message côté serveur, déjà
      // en français ; le front le rend tel quel plutôt que d'en inventer un
      // second, et la liste reste inchangée.
      toast.error((e as Error).message);
    }
  }
```

- [ ] **Step 4: Poser le rouge au survol et au focus**

Sur la croix (`:123-134`), remplacer la ligne `className` par :

```tsx
                                // `ghost` au repos, `destructive` au survol et
                                // au focus : c'est la seule exception à la
                                // règle de couleur (#499), et elle tient à la
                                // densité — une croix par badge, plusieurs
                                // badges par ligne. En rouge permanent, plus
                                // rien ne ressort du tableau ; là, le rouge
                                // arrive au moment où l'on vise.
                                className="rounded-full p-0 text-xs hover:bg-destructive/10 hover:text-destructive focus-visible:bg-destructive/10 focus-visible:text-destructive"
```

- [ ] **Step 5: Lancer les tests jusqu'au vert**

Run: `cd frontend && npx vitest run components/admin/UserRolesTable.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && npm run lint
git add components/admin/UserRolesTable.tsx components/admin/UserRolesTable.test.tsx
git commit -m "feat(499): confirm role revocation by name, and warn when the role is your own"
```

---

### Task 10: Écrire la règle, et prouver qu'elle est tenue

**Files:**
- Modify: `frontend/AGENTS.md`

- [ ] **Step 1: Vérifier qu'il ne reste aucun `window.confirm`**

Run: `cd frontend && grep -rn "window.confirm" app components lib`
Expected: aucune sortie. S'il en reste un, le traiter avec le hook avant de continuer — c'est le cœur du lot.

- [ ] **Step 2: Vérifier que la règle de couleur est tenue partout**

Run: `cd frontend && grep -rn 'variant="outline"' components/admin | grep -iE "supprimer|retirer|purger|vider|fermer"`
Expected: uniquement le bouton « Fermer les sessions » d'`AllowedEmailsTable` (neutre par décision) et les boutons « Renoncer » des dialogs. Tout autre résultat est un geste destructif resté neutre.

- [ ] **Step 3: Écrire la règle**

Ajouter à `frontend/AGENTS.md` une section, à placer près des conventions de composants :

```markdown
## Gestes destructifs

`variant="destructive"` **et** confirmation dès qu'un geste ferme un accès ou
détruit une donnée. Neutre et sans confirmation pour tout ce qui se refait.

La confirmation passe par `components/admin/DangerConfirm.tsx`, jamais par
`window.confirm` — ce dernier n'est ni traduisible, ni stylable, ni testable au
même titre. Deux formes d'appel : `<DangerConfirm>` quand le geste chiffre son
impact avant d'agir, `useDangerConfirm()` — une promesse — pour les autres.

Quand le serveur refusera le geste et que le front le sait, **le dire avant le
clic** : bouton inerte et raison visible, patron de `GroupsTable` et de
`raisonDeNonSuppression` dans `RolePermissionsEditor`. Ne pas recalculer côté
front une règle métier serveur qu'on ne fait que deviner : dans ce cas, laisser
le message du refus faire le travail.

Une seule exception à la couleur, et elle est commentée sur place : la croix de
retrait de rôle d'`UserRolesTable` est `ghost` au repos et `destructive` au
survol et au focus — une croix par badge, plusieurs badges par ligne.

Les gestes sans retour dont la portée est la base entière vivent sur
`/admin/maintenance`, jamais au pied d'un écran d'édition (#499).
```

- [ ] **Step 4: Faire tourner toute la suite**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: tout au vert. Le `build` est ce qui prouve que `ecran("/admin/maintenance")` résout.

- [ ] **Step 5: Commit**

```bash
git add frontend/AGENTS.md
git commit -m "docs(499): write down the one rule for destructive gestures"
```

---

## Fin de branche

Dans l'ordre de `docs/WORKFLOW-IA.md` :

1. `superpowers:requesting-code-review`
2. Le sous-agent `ui-ux-review` — la branche touche `frontend/`. Lecture seule ; il juge du rendu et ne rouvre pas l'identité visuelle.
3. `superpowers:verification-before-completion`
4. `superpowers:finishing-a-development-branch` — la PR lie l'issue par `Closes #499`, le reste de la description en français.

## Ce que ce lot ne fait pas

- La cible de 16 px de la croix de retrait : lot `CIBLE-1`.
- L'identité visuelle (`--tcn-*`, Anton/Barlow) et la frontière `components/tcn/` vs `components/ui/` : gelées par #325 et #460.
- `ADM-1` à `ADM-6` du § 9 de l'audit : leurs propres lots.
