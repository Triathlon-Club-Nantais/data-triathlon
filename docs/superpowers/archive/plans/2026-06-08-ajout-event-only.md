# Refonte ajout « event-only » — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aligner le formulaire d'ajout de `frontend-v2` sur le flux event-only de backend-v2 : coller une URL → importer directement l'épreuve (SSE), supprimer l'étage de prévisualisation athlète-unique (champ « Dossard » + bouton « Analyser » + carte « Vérification ») qui reposait sur un endpoint `/scrape` inexistant.

**Architecture:** `ScrapeForm` passe de « scrape un athlète par dossard → preview → save → import » à « importer l'épreuve en un clic (SSE) ». La saisie manuelle (`ManualResultForm` → `POST /participations`) reste le fallback. Sur échec réel de l'import (option A), on signale le fournisseur (`reportPendingProvider`) et on ouvre la saisie manuelle. La méthode morte `apiClient.scrape()` est supprimée.

**Tech Stack:** Next.js 16 (App Router), TypeScript, React, @tanstack/react-query, Vitest + Testing Library, sonner.

Spec de référence : `docs/superpowers/specs/2026-06-08-ajout-event-only-design.md`.

Toutes les commandes se lancent depuis `frontend-v2/`.

---

## File Structure

- **Modifier** `frontend-v2/components/scrape/ScrapeForm.tsx` — réécriture du flux event-only ; suppression de l'état `bib`, de l'état `preview`, du composant `PreviewEditor`, du helper `Labeled` et du callback `scrape()`.
- **Modifier** `frontend-v2/lib/api/client.ts` — suppression de la méthode `scrape()`.
- **Modifier** `frontend-v2/app/ajouter/page.tsx` — reformuler la description (plus de « résultat prévisualisé »).
- **Créer** `frontend-v2/components/scrape/ScrapeForm.test.tsx` — couverture du nouveau comportement.

Composants conservés sans changement : `ProviderDetector`, `ManualResultForm`, `ImportProgress`, `useImportStream`, `useSaveParticipation`, `apiClient.reportPendingProvider`.

---

## Task 1: Test du nouveau comportement de ScrapeForm

**Files:**
- Test (create): `frontend-v2/components/scrape/ScrapeForm.test.tsx`

- [ ] **Step 1: Écrire le fichier de test (échouera car ScrapeForm n'a pas encore le nouveau comportement)**

Créer `frontend-v2/components/scrape/ScrapeForm.test.tsx` avec exactement :

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock contrôlable du hook d'import (état mutable + spies).
const importMock = vi.hoisted(() => {
  let state = {
    running: false,
    phase: "idle" as string,
    message: "",
    total: 0,
    progress: 0,
    imported: 0,
    skipped: 0,
    cached: false,
    error: null as string | null,
  };
  return {
    start: vi.fn(),
    reset: vi.fn(),
    get: () => state,
    set: (patch: Partial<typeof state>) => {
      state = { ...state, ...patch };
    },
  };
});

vi.mock("@/hooks/useImportStream", () => ({
  useImportStream: () => ({
    state: importMock.get(),
    start: importMock.start,
    reset: importMock.reset,
  }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    detectProvider: vi.fn().mockResolvedValue({ provider: "klikego" }),
    reportPendingProvider: vi.fn().mockResolvedValue({}),
    saveParticipation: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { ScrapeForm } from "./ScrapeForm";
import { apiClient } from "@/lib/api/client";

function renderForm() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={qc}>
      <ScrapeForm />
    </QueryClientProvider>,
  );
  return {
    ...utils,
    rerenderForm: () =>
      utils.rerender(
        <QueryClientProvider client={qc}>
          <ScrapeForm />
        </QueryClientProvider>,
      ),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  importMock.set({ running: false, phase: "idle", error: null });
});

describe("ScrapeForm (event-only)", () => {
  it("ne propose plus le champ Dossard ni le bouton Analyser de l'étape source", () => {
    renderForm();
    expect(screen.queryByText("Dossard (optionnel)")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Analyser" }),
    ).not.toBeInTheDocument();
  });

  it("lance l'import direct de l'épreuve au clic", async () => {
    renderForm();
    await userEvent.type(
      screen.getByPlaceholderText("https://…"),
      "http://klikego.test/ev",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Importer l'épreuve" }),
    );
    expect(importMock.start).toHaveBeenCalledWith("http://klikego.test/ev");
  });

  it("ouvre la saisie manuelle au clic sur le bouton dédié", async () => {
    renderForm();
    await userEvent.click(
      screen.getByRole("button", { name: "Saisie manuelle" }),
    );
    expect(
      screen.getByRole("button", { name: "Enregistrer le résultat" }),
    ).toBeInTheDocument();
  });

  it("sur échec d'import, signale le fournisseur et bascule en saisie manuelle", async () => {
    const { rerenderForm } = renderForm();
    await userEvent.type(
      screen.getByPlaceholderText("https://…"),
      "http://x.test/ev",
    );
    importMock.set({ phase: "error", error: "boom" });
    rerenderForm();
    await waitFor(() =>
      expect(apiClient.reportPendingProvider).toHaveBeenCalledWith(
        "http://x.test/ev",
      ),
    );
    expect(
      screen.getByRole("button", { name: "Enregistrer le résultat" }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `npm test -- ScrapeForm`
Expected: ÉCHEC. Les assertions sur « Importer l'épreuve » et l'absence de « Analyser »/« Dossard (optionnel) » échouent car l'ancien `ScrapeForm` expose encore le bouton « Analyser », le champ « Dossard (optionnel) » et n'a pas de bouton « Importer l'épreuve ».

- [ ] **Step 3: Commit du test**

```bash
git add frontend-v2/components/scrape/ScrapeForm.test.tsx
git commit -m "test(frontend-v2): comportement event-only attendu du formulaire d'ajout"
```

---

## Task 2: Réécrire ScrapeForm en flux event-only

**Files:**
- Modify (réécriture complète): `frontend-v2/components/scrape/ScrapeForm.tsx`

- [ ] **Step 1: Remplacer tout le contenu de `frontend-v2/components/scrape/ScrapeForm.tsx`**

```tsx
"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { useSaveParticipation } from "@/lib/queries/participations";
import { useImportStream } from "@/hooks/useImportStream";
import { ProviderDetector } from "./ProviderDetector";
import { ImportProgress } from "./ImportProgress";
import { ManualResultForm } from "./ManualResultForm";
import type { ScrapedPreview } from "@/lib/types";

export function ScrapeForm() {
  const [url, setUrl] = useState("");
  const [manual, setManual] = useState(false);
  // Garde anti double-signalement pour une même URL en échec.
  const reportedRef = useRef<string | null>(null);

  const save = useSaveParticipation();
  const importStream = useImportStream();
  const { phase, error, running } = importStream.state;

  const startImport = useCallback(() => {
    reportedRef.current = null;
    setManual(false);
    importStream.start(url);
  }, [url, importStream]);

  // Option A : sur échec réel de l'import, signaler le fournisseur et proposer la saisie manuelle.
  useEffect(() => {
    if (phase !== "error" || reportedRef.current === url) return;
    reportedRef.current = url;
    toast.error(error ?? "Import impossible");
    apiClient.reportPendingProvider(url).catch(() => {});
    setManual(true);
  }, [phase, error, url]);

  const persist = useCallback(
    async (data: Partial<ScrapedPreview>) => {
      try {
        await save.mutateAsync(data);
        toast.success("Résultat enregistré.");
        setManual(false);
      } catch (e) {
        toast.error((e as Error).message);
      }
    },
    [save],
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4">
          <StepHeader n={1} title="Source" hint="URL de chronométrage de l'épreuve" />
          <div className="flex flex-col gap-1.5">
            <Label>URL de chronométrage</Label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
            />
            <ProviderDetector url={url} />
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <Button onClick={startImport} disabled={!url || running}>
              {running ? "Import…" : "Importer l'épreuve"}
            </Button>
            <Button variant="outline" onClick={() => setManual((m) => !m)}>
              Saisie manuelle
            </Button>
          </div>
        </CardContent>
      </Card>

      {manual && (
        <Card>
          <CardContent className="space-y-4">
            <StepHeader n={2} title="Saisie manuelle" hint="Renseignez le résultat à la main" />
            <ManualResultForm defaultUrl={url} onSubmit={persist} submitting={save.isPending} />
          </CardContent>
        </Card>
      )}

      <ImportProgress state={importStream.state} />
    </div>
  );
}

function StepHeader({ n, title, hint }: { n: number; title: string; hint: string }) {
  return (
    <div className="flex items-center gap-3 border-b pb-3">
      <span className="grid size-7 shrink-0 place-content-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
        {n}
      </span>
      <div>
        <h3 className="font-heading font-semibold leading-tight">{title}</h3>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
    </div>
  );
}
```

Note : ce remplacement supprime l'état `bib`, l'état `preview`, le callback `scrape()`, le composant `PreviewEditor` et le helper `Labeled` (devenus inutiles). Les imports `Input`/`Label` restent utilisés par l'étape source.

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils passent**

Run: `npm test -- ScrapeForm`
Expected: PASS — les 4 tests verts.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/components/scrape/ScrapeForm.tsx
git commit -m "refactor(frontend-v2): formulaire d'ajout en flux event-only"
```

---

## Task 3: Supprimer la méthode morte `apiClient.scrape`

**Files:**
- Modify: `frontend-v2/lib/api/client.ts` (bloc `scrape:` aux lignes ~39-43)

- [ ] **Step 1: Retirer la méthode `scrape` de l'objet `apiClient`**

Supprimer exactement ce bloc dans `frontend-v2/lib/api/client.ts` :

```ts
  scrape: (url: string, bib: string | null = null) =>
    request<ScrapedPreview>("/scrape", {
      method: "POST",
      body: JSON.stringify({ url, bib }),
    }),

```

L'objet `apiClient` doit alors commencer directement par `detectProvider: ...`. L'import de type `ScrapedPreview` reste utilisé par `saveParticipation`/`listParticipations` — **ne pas** le retirer.

- [ ] **Step 2: Vérifier qu'aucune référence ne subsiste**

Run: `grep -rn "apiClient.scrape\b\|\.scrape(" frontend-v2/components frontend-v2/app frontend-v2/lib frontend-v2/hooks`
Expected: aucune ligne (la seule occurrence historique était dans `ScrapeForm.tsx`, déjà réécrit).

- [ ] **Step 3: Vérifier la compilation TypeScript**

Run: `npm run lint`
Expected: PASS, aucune erreur de variable/import inutilisé.

- [ ] **Step 4: Commit**

```bash
git add frontend-v2/lib/api/client.ts
git commit -m "refactor(frontend-v2): retire apiClient.scrape (endpoint /scrape supprimé en v2)"
```

---

## Task 4: Reformuler la description de la page Ajouter

**Files:**
- Modify: `frontend-v2/app/ajouter/page.tsx:9`

- [ ] **Step 1: Remplacer la prop `description`**

Dans `frontend-v2/app/ajouter/page.tsx`, remplacer :

```tsx
        description="Collez l'URL de chronométrage d'une épreuve. Le résultat de l'athlète est prévisualisé, puis tous les participants sont importés en arrière-plan."
```

par :

```tsx
        description="Collez l'URL de chronométrage d'une épreuve : tous les participants sont importés en arrière-plan. Pour un fournisseur non supporté, utilisez la saisie manuelle."
```

- [ ] **Step 2: Commit**

```bash
git add frontend-v2/app/ajouter/page.tsx
git commit -m "docs(frontend-v2): description page Ajouter alignée sur le flux event-only"
```

---

## Task 5: Vérification complète

- [ ] **Step 1: Suite de tests complète**

Run: `npm test`
Expected: PASS — l'ancienne suite (33 tests) + les 4 nouveaux tests ScrapeForm, tous verts.

- [ ] **Step 2: Lint**

Run: `npm run lint`
Expected: PASS, aucun warning/erreur.

- [ ] **Step 3: Build production**

Run: `npm run build`
Expected: build réussi (TS strict + RSC), aucune erreur de type ni d'import non résolu.

- [ ] **Step 4: Commit éventuel** (uniquement si une correction a été nécessaire ci-dessus ; sinon rien à committer)

```bash
git status   # vérifier qu'il ne reste pas de modifications non committées
```

---

## Self-Review

- **Couverture spec** : suppression dossard/preview (Task 2), suppression `apiClient.scrape` (Task 3), gestion d'erreur option A — report sur échec d'import + bascule manuelle (Task 2, effet `useEffect` + test Task 1 step 1), reformulation copy page Ajouter (Task 4), conservation `ProviderDetector`/`ManualResultForm`/`ImportProgress`/`useImportStream`/`reportPendingProvider` (inchangés). Tous les points de la spec sont couverts.
- **Placeholders** : aucun TBD/TODO ; tout le code (composant, test, edits) est fourni intégralement.
- **Cohérence des types** : `importStream.state` expose `{ running, phase, error }` (cf. `hooks/useImportStream.ts` `ImportState`) ; `phase === "error"` et `state.error` sont bien les champs réels du hook. `reportPendingProvider(url: string)` et `mutateAsync(data: Partial<ScrapedPreview>)` correspondent aux signatures existantes. Le mock de test reproduit le même contrat (`state`/`start`/`reset`).
