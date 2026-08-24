# Lot #485 — Commandes de liste : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre les commandes de liste honnêtes et atteignables — libellés associés et repli mobile sur `/resultats`, saut de page et choix du nombre de lignes sur le classement, et un cadre qui cesse de contredire la vue filtrée.

**Architecture:** Trois volets sur deux composants clients existants. `ResultsFilters` gagne l'association `htmlFor`/`id` et un `ui/sheet` sous `sm`. Le classement gagne un paramètre d'URL `page_size` (liste blanche partagée dans `lib/pageSize.ts`, transmis par le RSC `courses/[id]/page.tsx`), une barre de commandes extraite dans `ClassementPagination.tsx`, et une ligne d'état qui oppose le total de la sélection à celui de l'épreuve. Aucun changement backend.

**Tech Stack:** Next.js 16 (App Router), TypeScript strict, Tailwind, shadcn/ui + Base UI, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-23-lot-485-commandes-de-liste-design.md`

## Global Constraints

- **Langue** — français pour tout ce que l'utilisateur lit et pour les commentaires de règle métier ; anglais pour les identifiants techniques et les préfixes de commit. Constitution, Principe I.
- **Registre** — vouvoiement sur tout écran public ; l'objet importé se dit « épreuve », jamais « course » (identifiant technique uniquement). `frontend/AGENTS.md`.
- **Identité visuelle non rejugée** — tokens `--tcn-*`, Anton/Barlow. Frontière `components/tcn/` ↔ `components/ui/` non déplacée (#325, #460). Étendre un composant `tcn/` est permis ; le déménager ne l'est pas.
- **TDD non négociable** — test qui échoue d'abord, à chaque tâche (Principe III).
- **Commandes** — depuis `frontend/` : `npm test -- <chemin>` (vitest run), `npm run lint`, `npm run build`.
- **Contrat d'API** — `GET /api/v1/courses/{id}` accepte `page_size` entre 1 et 200, ou `all`. Défaut 20. Aucune modification backend dans ce lot.
- **Commits** — Conventional Commits, un par tâche, suffixés `Refs #485`.

---

### Task 1: Source unique de la taille de tranche, branchée sur le RSC

**Files:**
- Create: `frontend/lib/pageSize.ts`
- Create: `frontend/lib/pageSize.test.ts`
- Modify: `frontend/app/(public_restricted)/courses/[id]/page.tsx`

**Interfaces:**
- Consumes: rien.
- Produces: `PAGE_SIZE_PARAM: "page_size"`, `PAGE_SIZE_OPTIONS: readonly [20, 50, 200, "all"]`, `type PageSize = 20 | 50 | 200 | "all"`, `PAGE_SIZE_DEFAUT: PageSize`, `parsePageSize(raw: string | null | undefined): PageSize`, `pageSizeLabel(taille: PageSize): string`. Consommés par les tâches 5 et 6.

- [ ] **Step 1: Write the failing test**

Créer `frontend/lib/pageSize.test.ts` :

```ts
import { describe, it, expect } from "vitest";
import { parsePageSize, pageSizeLabel, PAGE_SIZE_DEFAUT } from "./pageSize";

describe("parsePageSize", () => {
  it("accepte les quatre tailles proposées", () => {
    expect(parsePageSize("20")).toBe(20);
    expect(parsePageSize("50")).toBe(50);
    expect(parsePageSize("200")).toBe(200);
    expect(parsePageSize("all")).toBe("all");
  });

  it("retombe sur le défaut quand le paramètre est absent ou illisible", () => {
    expect(parsePageSize(undefined)).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize(null)).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("")).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("beaucoup")).toBe(PAGE_SIZE_DEFAUT);
  });

  it("refuse une taille hors liste, même acceptée par le backend", () => {
    // Le backend accepte 1..200 : sans liste blanche, `page_size=137`
    // afficherait une taille que le sélecteur ne sait pas représenter.
    expect(parsePageSize("137")).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("500")).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("0")).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("-20")).toBe(PAGE_SIZE_DEFAUT);
  });
});

describe("pageSizeLabel", () => {
  it("nomme les tailles chiffrées et l'échappatoire", () => {
    expect(pageSizeLabel(50)).toBe("50 lignes");
    expect(pageSizeLabel("all")).toBe("Tout");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- lib/pageSize.test.ts`
Expected: FAIL — « Failed to resolve import "./pageSize" ».

- [ ] **Step 3: Write minimal implementation**

Créer `frontend/lib/pageSize.ts` :

```ts
/** Nom du paramètre d'URL portant la taille de tranche du classement. */
export const PAGE_SIZE_PARAM = "page_size";

/**
 * Tailles proposées par le sélecteur du classement.
 *
 * `all` est l'échappatoire **contractuelle** de l'API (`backend/app/api/AGENTS.md`) :
 * c'est elle qui rend le tri client exact et le Ctrl+F du navigateur utilisable
 * sur une grosse épreuve.
 */
export const PAGE_SIZE_OPTIONS = [20, 50, 200, "all"] as const;

export type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];

/** Taille par défaut, alignée sur celle du backend. */
export const PAGE_SIZE_DEFAUT: PageSize = 20;

/**
 * Liste blanche : toute valeur hors des options vaut le défaut.
 *
 * Le backend accepte 1 à 200, mais le sélecteur ne sait représenter que ces
 * quatre valeurs — une URL bricolée le désaccorderait sinon, affichant une
 * taille qu'aucune option ne porte.
 */
export function parsePageSize(raw: string | null | undefined): PageSize {
  if (raw === "all") return "all";
  const n = Number(raw);
  const connue = PAGE_SIZE_OPTIONS.find((o) => o === n);
  return connue ?? PAGE_SIZE_DEFAUT;
}

/** Libellé d'une option dans le sélecteur. */
export function pageSizeLabel(taille: PageSize): string {
  return taille === "all" ? "Tout" : `${taille} lignes`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- lib/pageSize.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Brancher le RSC sur la liste blanche**

Dans `frontend/app/(public_restricted)/courses/[id]/page.tsx`, ajouter l'import :

```ts
import { PAGE_SIZE_PARAM, parsePageSize } from "@/lib/pageSize";
```

Puis, dans `CoursePage`, juste après `const scope = scopeFromParam(sp[SCOPE_PARAM]);` :

```ts
  // Liste blanche : le sélecteur du classement ne sait représenter que quatre
  // tailles, une URL bricolée le désaccorderait (cf. `lib/pageSize.ts`).
  const pageSize = parsePageSize(sp[PAGE_SIZE_PARAM]);
```

Et remplacer l'appel `apiServer.getCourse` :

```ts
    apiServer.getCourse(Number(id), { page, page_size: pageSize, q, scope }).catch(rendreNullSi404),
```

- [ ] **Step 6: Vérifier que le build type-checke**

Run: `npm run build`
Expected: succès. `CourseQuery.page_size` accepte déjà `number | "all"` (`lib/types.ts:470`), aucune modification de type n'est nécessaire.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/pageSize.ts frontend/lib/pageSize.test.ts "frontend/app/(public_restricted)/courses/[id]/page.tsx"
git commit -m "feat(frontend): paramètre d'URL page_size sur le classement

Refs #485"
```

---

### Task 2: Les cinq filtres de `/resultats` portent un libellé associé

**Files:**
- Modify: `frontend/components/results/ResultsFilters.tsx`
- Test: `frontend/components/results/ResultsFilters.test.tsx`

**Interfaces:**
- Consumes: rien.
- Produces: `Field` prend désormais `{ id, label, children }` et rend `<label id={`${id}-label`} htmlFor={id}>`. Les identifiants sont `filtre-athlete`, `filtre-epreuve`, `filtre-discipline`, `filtre-date-du`, `filtre-date-au`. La tâche 3 les suffixe.

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `frontend/components/results/ResultsFilters.test.tsx` :

```tsx
describe("ResultsFilters — libellés associés (WCAG 3.3.2)", () => {
  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
    searchParams = new URLSearchParams();
  });

  it("associe chacun des cinq libellés à son champ", () => {
    render(<ResultsFilters />);

    // Un `<label>` posé à côté d'un `<input>` n'est pas un libellé : un lecteur
    // d'écran annonçait « Du » et « Au » comme deux champs de date anonymes.
    expect(screen.getByLabelText("Athlète")).toBeInTheDocument();
    expect(screen.getByLabelText("Épreuve")).toBeInTheDocument();
    expect(screen.getByLabelText("Discipline")).toBeInTheDocument();
    expect(screen.getByLabelText("Du")).toBeInTheDocument();
    expect(screen.getByLabelText("Au")).toBeInTheDocument();
  });

  it("associe les deux dates par htmlFor/id, pas par proximité", () => {
    render(<ResultsFilters />);

    const du = screen.getByLabelText("Du");
    expect(du).toHaveAttribute("type", "date");
    expect(du.id).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/results/ResultsFilters.test.tsx`
Expected: FAIL — « Unable to find a label with the text of: Athlète ».

- [ ] **Step 3: Write minimal implementation**

Dans `frontend/components/results/ResultsFilters.tsx`, remplacer le composant `Field` en bas de fichier :

```tsx
/**
 * Libellé **associé** à son champ, et non simplement posé au-dessus.
 *
 * `htmlFor` ne désigne que les contrôles de formulaire étiquetables : le
 * `SelectTrigger` de Base UI étant un `<button>`, il se référence par
 * `aria-labelledby` sur l'`id` du libellé, d'où le `${id}-label`.
 */
function Field({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex w-full flex-col gap-1.5 sm:w-auto">
      <label
        id={`${id}-label`}
        htmlFor={id}
        className="text-xs font-medium text-[var(--tcn-text-faint)]"
      >
        {label}
      </label>
      {children}
    </div>
  );
}
```

Puis, dans le JSX, donner à chaque `Field` son `id` et le reporter sur le contrôle :

```tsx
          <Field id="filtre-athlete" label="Athlète">
            <Input
              id="filtre-athlete"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && apply()}
              placeholder="Rechercher un athlète"
              className="w-full sm:w-48"
            />
          </Field>
          <Field id="filtre-epreuve" label="Épreuve">
            <Input
              id="filtre-epreuve"
              value={eventName}
              onChange={(e) => setEventName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && apply()}
              placeholder="Rechercher une épreuve"
              className="w-full sm:w-48"
            />
          </Field>
          <Field id="filtre-discipline" label="Discipline">
            <Select
              value={eventType || ALL}
              onValueChange={(v) => setEventType(v === ALL ? "" : (v as string))}
            >
              <SelectTrigger
                id="filtre-discipline"
                aria-labelledby="filtre-discipline-label"
                className="h-9 w-full sm:w-48"
              >
                <SelectValue placeholder="Toutes les disciplines">
                  {(v) =>
                    !v || v === ALL ? "Toutes les disciplines" : eventTypeLabel(v as string)
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Toutes les disciplines</SelectItem>
                {EVENT_TYPE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field id="filtre-date-du" label="Du">
            <Input
              id="filtre-date-du"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full sm:w-40"
            />
          </Field>
          <Field id="filtre-date-au" label="Au">
            <Input
              id="filtre-date-au"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full sm:w-40"
            />
          </Field>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- components/results/ResultsFilters.test.tsx`
Expected: PASS, y compris les tests de recherche live existants (ils ciblent les placeholders, inchangés).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/ResultsFilters.tsx frontend/components/results/ResultsFilters.test.tsx
git commit -m "fix(a11y): associer chaque libellé de filtre à son champ sur /resultats

WCAG 3.3.2 : les cinq libellés étaient des frères de leur champ, sans
htmlFor/id — un lecteur d'écran annonçait des champs anonymes.

Refs #485"
```

---

### Task 3: Sous `sm`, quatre filtres se replient dans un volet

**Files:**
- Modify: `frontend/components/results/ResultsFilters.tsx`
- Test: `frontend/components/results/ResultsFilters.test.tsx`

**Interfaces:**
- Consumes: `Field` de la tâche 2.
- Produces: `ChampsReplies` (composant module-level de `ResultsFilters.tsx`), signature exacte donnée à l'étape 3. Rien d'autre n'en dépend.

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/results/ResultsFilters.test.tsx` :

```tsx
describe("ResultsFilters — volet mobile", () => {
  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
    searchParams = new URLSearchParams();
  });

  it("porte le nombre de filtres repliés actifs, athlète non compté", () => {
    // « Athlète » reste visible hors du volet : il ne fait pas partie du compte.
    searchParams = new URLSearchParams("name=marie&event_type=triathlon-m&date_from=2026-01-01");
    render(<ResultsFilters />);

    expect(screen.getByRole("button", { name: "Filtres (2)" })).toBeInTheDocument();
  });

  it("n'affiche aucun compte quand aucun filtre replié n'est actif", () => {
    searchParams = new URLSearchParams("name=marie");
    render(<ResultsFilters />);

    expect(screen.getByRole("button", { name: "Filtres" })).toBeInTheDocument();
  });

  it("ouvre le volet et y rend les quatre champs repliés", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    // Deux rendus du même champ : l'inline (masqué sous `sm`) et celui du volet.
    expect(screen.getAllByLabelText("Épreuve")).toHaveLength(2);
    expect(screen.getAllByLabelText("Du")).toHaveLength(2);
  });

  it("ne duplique aucun identifiant entre le rendu inline et celui du volet", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    await screen.findByRole("dialog");

    const ids = screen.getAllByLabelText("Épreuve").map((champ) => champ.id);
    expect(new Set(ids).size).toBe(2);
  });

  it("« Appliquer » pousse l'URL et ferme le volet", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    await screen.findByRole("dialog");
    const [, epreuveVolet] = screen.getAllByLabelText("Épreuve");
    fireEvent.change(epreuveVolet, { target: { value: "nantes" } });
    await userEvent.click(screen.getByRole("button", { name: "Appliquer" }));

    expect(push).toHaveBeenCalledWith(expect.stringContaining("event_name=nantes"));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/results/ResultsFilters.test.tsx`
Expected: FAIL — « Unable to find role="button" and name "Filtres (2)" ».

- [ ] **Step 3: Write minimal implementation**

Dans `frontend/components/results/ResultsFilters.tsx`, ajouter les imports :

```tsx
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { SlidersHorizontal } from "lucide-react";
```

Ajouter, à côté des autres `useState` de `ResultsFilters` :

```tsx
  const [volet, setVolet] = useState(false);

  // Compte des filtres **repliés** actifs, athlète exclu : il reste visible
  // hors du volet, le compter ferait mentir le bouton.
  const nbReplies = ["event_name", "event_type", "date_from", "date_to"].filter((cle) =>
    sp.get(cle),
  ).length;
```

Extraire les quatre champs repliables dans un composant **module-level** (jamais défini dans le corps de `ResultsFilters` : redéfini à chaque rendu, il remonterait les champs et volerait le focus en pleine frappe) :

```tsx
/**
 * Les quatre filtres repliables, rendus **deux fois** : inline au-dessus de
 * `sm`, dans le volet en dessous. Le suffixe garde les identifiants uniques ;
 * l'état vit chez le parent, les deux rendus affichent donc la même saisie.
 *
 * C'est ce qui évite un `useMediaQuery` : un hook média rendrait la disposition
 * dépendante de l'hydratation, avec le flash que cela implique sur les filtres,
 * première chose vue de l'écran.
 */
function ChampsReplies({
  suffixe,
  eventName,
  setEventName,
  eventType,
  setEventType,
  dateFrom,
  setDateFrom,
  dateTo,
  setDateTo,
  onValider,
}: {
  suffixe: string;
  eventName: string;
  setEventName: (v: string) => void;
  eventType: string;
  setEventType: (v: string) => void;
  dateFrom: string;
  setDateFrom: (v: string) => void;
  dateTo: string;
  setDateTo: (v: string) => void;
  onValider: () => void;
}) {
  return (
    <>
      <Field id={`filtre-epreuve-${suffixe}`} label="Épreuve">
        <Input
          id={`filtre-epreuve-${suffixe}`}
          value={eventName}
          onChange={(e) => setEventName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onValider()}
          placeholder="Rechercher une épreuve"
          className="w-full sm:w-48"
        />
      </Field>
      <Field id={`filtre-discipline-${suffixe}`} label="Discipline">
        <Select
          value={eventType || ALL}
          onValueChange={(v) => setEventType(v === ALL ? "" : (v as string))}
        >
          <SelectTrigger
            id={`filtre-discipline-${suffixe}`}
            aria-labelledby={`filtre-discipline-${suffixe}-label`}
            className="h-9 w-full sm:w-48"
          >
            <SelectValue placeholder="Toutes les disciplines">
              {(v) => (!v || v === ALL ? "Toutes les disciplines" : eventTypeLabel(v as string))}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toutes les disciplines</SelectItem>
            {EVENT_TYPE_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field id={`filtre-date-du-${suffixe}`} label="Du">
        <Input
          id={`filtre-date-du-${suffixe}`}
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="w-full sm:w-40"
        />
      </Field>
      <Field id={`filtre-date-au-${suffixe}`} label="Au">
        <Input
          id={`filtre-date-au-${suffixe}`}
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="w-full sm:w-40"
        />
      </Field>
    </>
  );
}
```

Remplacer, dans le JSX de `ResultsFilters`, les quatre `Field` (Épreuve, Discipline, Du, Au) et le bloc de boutons par :

```tsx
          <div className="hidden sm:contents">
            <ChampsReplies
              suffixe="inline"
              eventName={eventName}
              setEventName={setEventName}
              eventType={eventType}
              setEventType={setEventType}
              dateFrom={dateFrom}
              setDateFrom={setDateFrom}
              dateTo={dateTo}
              setDateTo={setDateTo}
              onValider={apply}
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="sm:hidden" onClick={() => setVolet(true)}>
              <SlidersHorizontal className="size-4" />
              {nbReplies > 0 ? `Filtres (${nbReplies})` : "Filtres"}
            </Button>
            {/* « Filtrer » ne sert plus sous `sm` : le champ athlète y filtre en
                direct (#383) et le volet a son propre « Appliquer ». */}
            <Button className="hidden sm:inline-flex" onClick={apply}>
              Filtrer
            </Button>
            {active.length > 0 && (
              <Button variant="ghost" onClick={reset}>
                Réinitialiser
              </Button>
            )}
          </div>
```

Puis, juste avant la fermeture de `</CardContent>`, ajouter le volet :

```tsx
        <Sheet open={volet} onOpenChange={setVolet}>
          <SheetContent side="right" className="w-80 overflow-y-auto">
            <SheetTitle>Filtres</SheetTitle>
            <div className="flex flex-col gap-3">
              <ChampsReplies
                suffixe="volet"
                eventName={eventName}
                setEventName={setEventName}
                eventType={eventType}
                setEventType={setEventType}
                dateFrom={dateFrom}
                setDateFrom={setDateFrom}
                dateTo={dateTo}
                setDateTo={setDateTo}
                onValider={() => {
                  apply();
                  setVolet(false);
                }}
              />
            </div>
            <div className="mt-auto flex gap-2">
              {/* Application à la validation, jamais à la frappe : discipline et
                  dates ne s'appliquent que sur demande explicite (#387). */}
              <Button
                className="flex-1"
                onClick={() => {
                  apply();
                  setVolet(false);
                }}
              >
                Appliquer
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  reset();
                  setVolet(false);
                }}
              >
                Réinitialiser
              </Button>
            </div>
          </SheetContent>
        </Sheet>
```

Le bouton « Filtrer » du test existant (« le bouton Filtrer applique toujours via push ») reste présent dans le DOM sous `hidden sm:inline-flex` : Tailwind ne s'applique pas en jsdom, le test reste vert.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- components/results/ResultsFilters.test.tsx`
Expected: PASS, tests existants compris.

- [ ] **Step 5: Lint**

Run: `npm run lint`
Expected: aucun avertissement sur `ResultsFilters.tsx`.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/results/ResultsFilters.tsx frontend/components/results/ResultsFilters.test.tsx
git commit -m "feat(frontend): replier quatre filtres dans un volet sous sm sur /resultats

Cinq champs et deux boutons occupaient tout le premier écran d'un
téléphone avant le moindre résultat.

Refs #485"
```

---

### Task 4: Extraire la pagination du classement, sans changer son comportement

**Files:**
- Create: `frontend/components/results/ClassementPagination.tsx`
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Test: `frontend/components/results/RaceFinishers.test.tsx` (aucune modification — c'est le filet)

**Interfaces:**
- Consumes: rien.
- Produces: `ClassementPagination({ page, nbPages, lienVers })`, avec `lienVers: (modifications: Record<string, string | null>) => string`. Les tâches 5 et 6 lui ajoutent des props.

- [ ] **Step 1: Vérifier que le filet est vert avant de bouger**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS. Les six tests de pagination existants sont la spécification de cette extraction ; ils ne doivent pas être modifiés.

- [ ] **Step 2: Créer le fichier**

Créer `frontend/components/results/ClassementPagination.tsx` en y déplaçant **à l'identique** la fonction `Pagination` de `RaceFinishers.tsx`, renommée et exportée :

```tsx
"use client";
import Link from "next/link";

/**
 * Commandes de pagination du classement, en liens et non en boutons :
 * ouvrables en nouvel onglet, utilisables au clavier et fonctionnels avant
 * hydratation.
 */
export function ClassementPagination({
  page,
  nbPages,
  lienVers,
}: {
  page: number;
  nbPages: number;
  lienVers: (modifications: Record<string, string | null>) => string;
}) {
  const style = {
    padding: "6px 14px",
    fontSize: 13,
    fontWeight: 700,
    borderRadius: 8,
    border: "1px solid var(--tcn-border)",
    color: "var(--tcn-ink)",
  } as const;
  const inactif = { ...style, color: "var(--tcn-text-faint)", opacity: 0.5 };
  // Hors bornes, « Précédent » ramène à la dernière page réelle : reculer d'un
  // cran depuis la page 99 999 ferait traverser 99 908 pages vides.
  const precedente = Math.min(page - 1, nbPages);

  return (
    <nav
      aria-label="Pagination du classement"
      style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, padding: "14px 24px", borderTop: "1px solid var(--tcn-border)" }}
    >
      {page > 1 ? (
        <Link
          href={lienVers({ page: precedente === 1 ? null : String(precedente) })}
          style={style}
          rel="prev"
        >
          ‹ Précédent
        </Link>
      ) : (
        <span style={inactif} aria-disabled="true">‹ Précédent</span>
      )}
      <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }} aria-current="page">
        Page {page} sur {nbPages}
      </span>
      {page < nbPages ? (
        <Link href={lienVers({ page: String(page + 1) })} style={style} rel="next">
          Suivant ›
        </Link>
      ) : (
        <span style={inactif} aria-disabled="true">Suivant ›</span>
      )}
    </nav>
  );
}
```

- [ ] **Step 3: Brancher `RaceFinishers` dessus**

Dans `frontend/components/results/RaceFinishers.tsx` : supprimer la fonction locale `Pagination` (bloc complet), ajouter l'import

```tsx
import { ClassementPagination } from "@/components/results/ClassementPagination";
```

et remplacer l'usage :

```tsx
      {nbPages > 1 && <ClassementPagination page={page} nbPages={nbPages} lienVers={lienVers} />}
```

- [ ] **Step 4: Run tests to verify nothing moved**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS, mêmes tests, aucun modifié.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/ClassementPagination.tsx frontend/components/results/RaceFinishers.tsx
git commit -m "refactor(frontend): extraire ClassementPagination de RaceFinishers

Sans changement de comportement — les tests de pagination existants
tiennent l'extraction.

Refs #485"
```

---

### Task 5: Un sélecteur 20 / 50 / 200 / Tout, toujours visible

**Files:**
- Modify: `frontend/components/results/ClassementPagination.tsx`
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Test: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consumes: `PAGE_SIZE_OPTIONS`, `PAGE_SIZE_PARAM`, `PageSize`, `parsePageSize`, `pageSizeLabel` (tâche 1) ; `ClassementPagination` (tâche 4).
- Produces: `ClassementPagination({ page, nbPages, lienVers, tailleCourante, onTaille })` où `tailleCourante: PageSize` et `onTaille: (taille: PageSize) => void`.

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/results/RaceFinishers.test.tsx`, après le bloc « Pagination » :

```tsx
  // ── Taille de tranche ──────────────────────────────────────────────────────

  it("propose les quatre tailles de tranche, même quand tout tient en une page", () => {
    afficher({ total: 3, pageSize: 20 });

    const selecteur = screen.getByLabelText("Lignes par page");
    expect(selecteur).toBeInTheDocument();
    expect(
      Array.from(selecteur.querySelectorAll("option")).map((o) => o.textContent),
    ).toEqual(["20 lignes", "50 lignes", "200 lignes", "Tout"]);
  });

  it("pousse la taille choisie dans l'URL et revient à la première page", async () => {
    searchParams = new URLSearchParams("page=7");
    afficher({ total: 900, pageSize: 20, page: 7 });

    await userEvent.selectOptions(screen.getByLabelText("Lignes par page"), "200");

    expect(push).toHaveBeenCalledWith("/courses/1?page_size=200");
  });

  it("retire le paramètre quand on revient à la taille par défaut", async () => {
    searchParams = new URLSearchParams("page_size=200");
    afficher({ total: 900, pageSize: 200, page: 1 });

    await userEvent.selectOptions(screen.getByLabelText("Lignes par page"), "20");

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("garde le sélecteur mais retire la navigation de pages quand tout est demandé", () => {
    searchParams = new URLSearchParams("page_size=all");
    afficher({ total: 900, pageSize: null, page: 1 });

    expect(screen.getByLabelText("Lignes par page")).toHaveValue("all");
    expect(screen.queryByRole("navigation", { name: /pagination/i })).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: FAIL — « Unable to find a label with the text of: Lignes par page ».

- [ ] **Step 3: Write minimal implementation**

Dans `ClassementPagination.tsx`, ajouter l'import et enrichir la signature. Le composant rend désormais **toujours** une barre de commandes ; la navigation de pages n'y apparaît que si `nbPages > 1` :

```tsx
import { PAGE_SIZE_OPTIONS, pageSizeLabel, type PageSize } from "@/lib/pageSize";
```

```tsx
export function ClassementPagination({
  page,
  nbPages,
  lienVers,
  tailleCourante,
  onTaille,
}: {
  page: number;
  nbPages: number;
  lienVers: (modifications: Record<string, string | null>) => string;
  tailleCourante: PageSize;
  onTaille: (taille: PageSize) => void;
}) {
```

Remplacer le `<nav>` racine par un conteneur portant les deux zones :

```tsx
  return (
    <div style={{ borderTop: "1px solid var(--tcn-border)" }}>
      {nbPages > 1 && (
        <nav
          aria-label="Pagination du classement"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, padding: "14px 24px", flexWrap: "wrap" }}
        >
          {page > 1 ? (
            <Link
              href={lienVers({ page: precedente === 1 ? null : String(precedente) })}
              style={style}
              rel="prev"
            >
              ‹ Précédent
            </Link>
          ) : (
            <span style={inactif} aria-disabled="true">‹ Précédent</span>
          )}
          <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }} aria-current="page">
            Page {page} sur {nbPages}
          </span>
          {page < nbPages ? (
            <Link href={lienVers({ page: String(page + 1) })} style={style} rel="next">
              Suivant ›
            </Link>
          ) : (
            <span style={inactif} aria-disabled="true">Suivant ›</span>
          )}
        </nav>
      )}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "10px 24px", fontSize: 13, color: "var(--tcn-text-muted)" }}>
        <label htmlFor="classement-taille">Lignes par page</label>
        <select
          id="classement-taille"
          value={String(tailleCourante)}
          onChange={(e) => onTaille(e.target.value === "all" ? "all" : (Number(e.target.value) as PageSize))}
          // Plancher tactile WCAG 2.2 2.5.8 (#479).
          style={{ minHeight: 28, padding: "2px 8px", fontSize: 13, borderRadius: 8, border: "1px solid var(--tcn-border)", background: "var(--tcn-surface)", color: "var(--tcn-ink)" }}
        >
          {PAGE_SIZE_OPTIONS.map((o) => (
            <option key={String(o)} value={String(o)}>
              {pageSizeLabel(o)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
```

Un `<select>` natif, et non le `Select` de Base UI : `RaceFinishers` est en style inline pur, et le natif porte son clavier, son libellé et son rendu mobile sans une ligne de plus.

Dans `RaceFinishers.tsx`, ajouter l'import :

```tsx
import { PAGE_SIZE_DEFAUT, PAGE_SIZE_PARAM, parsePageSize, type PageSize } from "@/lib/pageSize";
```

Calculer la taille courante à côté de `filtreClub` :

```tsx
  // La taille vient de l'URL, pas de la prop `pageSize` : sous `all`, le
  // backend renvoie `null` et le sélecteur n'aurait plus quoi afficher.
  const tailleCourante = parsePageSize(searchParams.get(PAGE_SIZE_PARAM));
```

Et remplacer l'appel par une barre **toujours rendue** :

```tsx
      <ClassementPagination
        page={page}
        nbPages={nbPages}
        lienVers={lienVers}
        tailleCourante={tailleCourante}
        onTaille={(taille) =>
          naviguer({ [PAGE_SIZE_PARAM]: taille === PAGE_SIZE_DEFAUT ? null : String(taille) })
        }
      />
```

`naviguer` remet déjà `page` à `null` : changer la taille renvoie donc en première page, la position courante n'ayant pas d'équivalent d'une taille à l'autre.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS. Le test existant « ne rend aucun contrôle de pagination quand la sélection tient en une page » interroge `role="navigation"`, absent quand `nbPages === 1` : il reste vert malgré la barre désormais présente.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/ClassementPagination.tsx frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "feat(frontend): sélecteur 20/50/200/Tout sur le classement

Refs #485"
```

---

### Task 6: Saut de page validable, première et dernière

**Files:**
- Modify: `frontend/components/results/ClassementPagination.tsx`
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Test: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consumes: `ClassementPagination` (tâche 5).
- Produces: `ClassementPagination({ …, onAllerPage })` avec `onAllerPage: (n: number) => void`.

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/results/RaceFinishers.test.tsx` :

```tsx
  // ── Saut de page ───────────────────────────────────────────────────────────

  it("rend des liens vers la première et la dernière page", () => {
    afficher({ total: 860, pageSize: 20, page: 21 });

    expect(screen.getByRole("link", { name: /Première/ })).toHaveAttribute("href", "/courses/1");
    expect(screen.getByRole("link", { name: /Dernière/ })).toHaveAttribute("href", "/courses/1?page=43");
  });

  it("saute à la page saisie sans perdre la recherche ni le filtre", async () => {
    searchParams = new URLSearchParams("q=dupont&scope=club");
    afficher({ total: 860, pageSize: 20, page: 1 });

    const champ = screen.getByLabelText("Aller à la page");
    await userEvent.clear(champ);
    await userEvent.type(champ, "22");
    await userEvent.click(screen.getByRole("button", { name: "Aller" }));

    const url = push.mock.calls.at(-1)?.[0] ?? "";
    expect(url).toContain("q=dupont");
    expect(url).toContain("scope=club");
    expect(url).toContain("page=22");
  });

  it("ramène une saisie hors bornes dans le classement plutôt que de la refuser", async () => {
    // « 99 » sur 43 pages veut dire « la fin ».
    afficher({ total: 860, pageSize: 20, page: 1 });

    const champ = screen.getByLabelText("Aller à la page");
    await userEvent.clear(champ);
    await userEvent.type(champ, "99");
    await userEvent.click(screen.getByRole("button", { name: "Aller" }));

    expect(push).toHaveBeenCalledWith("/courses/1?page=43");
  });

  it("omet le paramètre page quand on saute à la première", async () => {
    afficher({ total: 860, pageSize: 20, page: 5 });

    const champ = screen.getByLabelText("Aller à la page");
    await userEvent.clear(champ);
    await userEvent.type(champ, "1");
    await userEvent.click(screen.getByRole("button", { name: "Aller" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("porte les autres paramètres en champs cachés, pour un saut sans JavaScript", () => {
    searchParams = new URLSearchParams("q=dupont&page_size=50");
    afficher({ total: 860, pageSize: 50, page: 2 });

    const form = screen.getByLabelText("Aller à la page").closest("form")!;
    expect(form).toHaveAttribute("method", "get");
    // `toHaveValue` ne lit pas un champ caché : on interroge l'attribut.
    expect(form.querySelector('input[name="q"]')).toHaveAttribute("value", "dupont");
    expect(form.querySelector('input[name="page_size"]')).toHaveAttribute("value", "50");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: FAIL — « Unable to find a label with the text of: Aller à la page ».

- [ ] **Step 3: Write minimal implementation**

Dans `ClassementPagination.tsx`, ajouter les imports :

```tsx
import { useSearchParams } from "next/navigation";
import { useState } from "react";
```

Ajouter `onAllerPage` à la signature :

```tsx
  onAllerPage,
}: {
  …
  onAllerPage: (n: number) => void;
}) {
```

Dans le corps, avant le `return` :

```tsx
  const searchParams = useSearchParams();
  const [saisie, setSaisie] = useState(String(page));
  const [dernierePage, setDernierePage] = useState(page);

  // L'URL est la vérité : après un « Précédent » du navigateur, le champ suit.
  // Même patron d'état dérivé que la recherche de `RaceFinishers`.
  if (page !== dernierePage) {
    setDernierePage(page);
    setSaisie(String(page));
  }

  // Les autres paramètres voyagent en champs cachés : le saut fonctionne alors
  // aussi en soumission native, avant hydratation, sans perdre la recherche.
  const autresParametres = Array.from(searchParams.entries()).filter(([cle]) => cle !== "page");

  function surSoumission(e: React.FormEvent) {
    e.preventDefault();
    // Hors bornes, on ramène dans le classement : « 99 » sur 43 pages veut dire
    // « la fin », le refuser ne rendrait service à personne.
    const n = Math.min(Math.max(1, Math.trunc(Number(saisie)) || 1), nbPages);
    onAllerPage(n);
  }
```

Remplacer le contenu du `<nav>` par la barre complète :

```tsx
        <nav
          aria-label="Pagination du classement"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, padding: "14px 24px", flexWrap: "wrap" }}
        >
          {page > 1 ? (
            <Link href={lienVers({ page: null })} style={style}>‹‹ Première</Link>
          ) : (
            <span style={inactif} aria-disabled="true">‹‹ Première</span>
          )}
          {page > 1 ? (
            <Link
              href={lienVers({ page: precedente === 1 ? null : String(precedente) })}
              style={style}
              rel="prev"
            >
              ‹ Précédent
            </Link>
          ) : (
            <span style={inactif} aria-disabled="true">‹ Précédent</span>
          )}
          <form method="get" onSubmit={surSoumission} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--tcn-text-muted)" }}>
            {autresParametres.map(([cle, valeur]) => (
              <input key={cle} type="hidden" name={cle} value={valeur} />
            ))}
            <label htmlFor="classement-page">Aller à la page</label>
            <input
              id="classement-page"
              name="page"
              type="number"
              inputMode="numeric"
              min={1}
              max={nbPages}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              style={{ width: 68, minHeight: 28, padding: "2px 8px", fontSize: 13, borderRadius: 8, border: "1px solid var(--tcn-border)", background: "var(--tcn-surface)", color: "var(--tcn-ink)" }}
            />
            <span>sur {nbPages}</span>
            {/* Bouton de soumission explicite : sans lui, la soumission
                implicite par Entrée dépend du nombre de champs du formulaire et
                n'existe pas du tout au doigt. Il porte aussi le saut sans
                JavaScript. */}
            <button type="submit" style={{ ...style, background: "var(--tcn-fill)", cursor: "pointer" }}>
              Aller
            </button>
          </form>
          {page < nbPages ? (
            <Link href={lienVers({ page: String(page + 1) })} style={style} rel="next">Suivant ›</Link>
          ) : (
            <span style={inactif} aria-disabled="true">Suivant ›</span>
          )}
          {page < nbPages ? (
            <Link href={lienVers({ page: String(nbPages) })} style={style}>Dernière ››</Link>
          ) : (
            <span style={inactif} aria-disabled="true">Dernière ››</span>
          )}
        </nav>
```

Le `<span aria-current="page">Page {page} sur {nbPages}</span>` disparaît : le champ le remplace, et il porte désormais le libellé. Le test existant « rend des liens Précédent / Suivant portant le numéro de page » attend `screen.getByText("Page 3 sur 5")` — **le mettre à jour** dans le même commit :

```tsx
  it("rend des liens « Précédent » / « Suivant » portant le numéro de page", () => {
    afficher({ total: 100, pageSize: 20, page: 3 });

    expect(screen.getByLabelText("Aller à la page")).toHaveValue(3);
    expect(screen.getByText("sur 5")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Précédent/ })).toHaveAttribute("href", "/courses/1?page=2");
    expect(screen.getByRole("link", { name: /Suivant/ })).toHaveAttribute("href", "/courses/1?page=4");
  });
```

Attention au test existant « désactive « Précédent » en première page » : il attend `queryByRole("link", { name: /Précédent/ })` absent. « ‹‹ Première » ne matche pas `/Précédent/`, il reste vert.

Dans `RaceFinishers.tsx`, ajouter la fonction de saut à côté de `naviguer` :

```tsx
  /** Saut direct à une page, la recherche et le filtre en cours conservés. */
  function naviguerPage(n: number) {
    startTransition(() => router.push(lienVers({ page: n === 1 ? null : String(n) })));
  }
```

et la passer au composant :

```tsx
        onAllerPage={naviguerPage}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS, y compris le test de pagination mis à jour.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/ClassementPagination.tsx frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "feat(frontend): saut de page, première et dernière sur le classement

43 pages ne s'atteignaient qu'un cran à la fois : 21 clics pour le
milieu du classement.

Refs #485"
```

---

### Task 7: La vue filtrée se nomme

**Files:**
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Test: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consumes: `CLUB_NAME` (`@/lib/club`), déjà importé dans `RaceFinishers.tsx`.
- Produces: rien de réutilisable hors du composant.

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/results/RaceFinishers.test.tsx` :

```tsx
  // ── Cadre de la vue filtrée (RES-9) ────────────────────────────────────────

  it("oppose le total de la sélection à celui de l'épreuve après une recherche", () => {
    searchParams = new URLSearchParams("q=kermarrec");
    afficher({ summary: synthese({ total: 498 }), total: 2 });

    expect(screen.getByText(/2 résultats/)).toBeInTheDocument();
    expect(screen.getByText(/sur 498/)).toBeInTheDocument();
    expect(screen.getByText(/kermarrec/)).toBeInTheDocument();
  });

  it("nomme le filtre club dans la ligne d'état", () => {
    searchParams = new URLSearchParams(`${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ summary: synthese({ total: 498, tcn_count: 12 }), total: 12 });

    expect(screen.getByText(/Triathlon Club Nantais/)).toBeInTheDocument();
  });

  it("ne rend aucune ligne d'état en vue complète", () => {
    afficher({ total: 3 });

    expect(screen.queryByRole("button", { name: "Effacer" })).not.toBeInTheDocument();
  });

  it("« Effacer » retire la recherche et le filtre d'un coup", async () => {
    searchParams = new URLSearchParams(`q=kermarrec&${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ summary: synthese({ total: 498 }), total: 1 });

    await userEvent.click(screen.getByRole("button", { name: "Effacer" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("situe le pied de carte sur l'épreuve entière, pas sur la sélection", () => {
    searchParams = new URLSearchParams("q=kermarrec");
    afficher({ total: 2 });

    expect(screen.getByText(/Sur l'ensemble de l'épreuve/)).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: FAIL — « Unable to find an element with the text: /2 résultats/ ».

- [ ] **Step 3: Write minimal implementation**

Dans `RaceFinishers.tsx`, ajouter une fonction module-level, à côté de `resumeEpreuve` :

```tsx
/**
 * Cadre de la vue filtrée : ce qu'on regarde, et sur quoi.
 *
 * `total` est le total de la **sélection**, `totalEpreuve` celui de l'épreuve
 * entière — c'est leur opposition qui manquait, l'écran affirmant « 498
 * participants » sous deux lignes de résultats.
 */
function libelleSelection(total: number, totalEpreuve: number, recherche: string, filtreClub: boolean): string {
  const tete = `${total} résultat${total > 1 ? "s" : ""} sur ${totalEpreuve}`;
  const morceaux = [];
  if (recherche) morceaux.push(`pour « ${recherche} »`);
  if (filtreClub) morceaux.push(`du ${CLUB_NAME}`);
  return `${tete} ${morceaux.join(", ")}`;
}
```

Insérer la ligne d'état juste après le `</div>` fermant l'en-tête de carte (celui qui porte « Classement » et le segmenté), avant le conteneur `overflowX: "auto"` :

```tsx
      {(rechercheUrl || filtreClub) && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: "10px 26px", borderBottom: "1px solid var(--tcn-border)", fontSize: 13, color: "var(--tcn-text-body)" }}>
          <span>{libelleSelection(total, summary.total, rechercheUrl, filtreClub)}</span>
          <button
            type="button"
            onClick={() => naviguer({ q: null, [SCOPE_PARAM]: null })}
            style={{ background: "none", border: "none", padding: "4px 0", minHeight: 24, font: "inherit", fontWeight: 700, color: "var(--tcn-ink)", textDecoration: "underline", cursor: "pointer" }}
          >
            Effacer
          </button>
        </div>
      )}
```

Enfin, dans le pied de carte, séparer le préfixe du résumé pour ne pas casser les quatre tests qui comparent `resumeEpreuve` au texte exact d'un nœud :

```tsx
      <div style={{ padding: "16px 24px", borderTop: "1px solid var(--tcn-border)", textAlign: "center", fontSize: 13, color: "var(--tcn-text-faint)" }}>
        <span>Sur l&apos;ensemble de l&apos;épreuve : </span>
        <span>{resumeEpreuve(summary)}</span>
      </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS, y compris les quatre tests existants du pied de carte (`getByText("3 participants · 1 finisher · 2 abandons")` cible le second `<span>`, dont le texte est inchangé).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "feat(frontend): nommer la vue filtrée du classement

Deux lignes affichées sous un écran qui annonçait « 498 participants ».

Refs #485"
```

---

### Task 8: Deux absences distinctes, deux messages distincts

**Files:**
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Test: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consumes: `CLUB_NAME`, `SCOPE_PARAM` (déjà importés).
- Produces: rien.

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/results/RaceFinishers.test.tsx` :

```tsx
  it("ne parle pas de recherche quand seul le filtre club est actif", () => {
    // Course sans athlète TCN : « Aucun athlète ne correspond à cette recherche »
    // alors qu'aucune recherche n'a été faite.
    searchParams = new URLSearchParams(`${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ participations: [], total: 0, summary: synthese({ total: 498, tcn_count: 0 }) });

    expect(
      screen.getByText(`Aucun athlète du ${CLUB_NAME} sur cette épreuve`),
    ).toBeInTheDocument();
    expect(screen.queryByText(/correspond à cette recherche/)).not.toBeInTheDocument();
  });

  it("offre la sortie du filtre club depuis son message d'absence", async () => {
    searchParams = new URLSearchParams(`${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ participations: [], total: 0, summary: synthese({ total: 498, tcn_count: 0 }) });

    await userEvent.click(screen.getByRole("button", { name: "Voir tous les participants" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("garde le message de recherche quand une recherche a bien eu lieu", () => {
    searchParams = new URLSearchParams("q=zzz");
    afficher({ participations: [], total: 0 });

    expect(screen.getByText("Aucun athlète ne correspond à cette recherche")).toBeInTheDocument();
  });
```

`CLUB_NAME` doit être importé en haut du fichier de test : `import { CLUB_NAME } from "@/lib/club";`.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: FAIL — le message trouvé est « Aucun athlète ne correspond à cette recherche ».

- [ ] **Step 3: Write minimal implementation**

Dans `RaceFinishers.tsx`, remplacer la branche `rechercheUrl || filtreClub` du bloc d'absence par deux branches :

```tsx
            ) : rechercheUrl ? (
              <EmptyState
                bare
                title="Aucun athlète ne correspond à cette recherche"
                action={
                  <button
                    type="button"
                    onClick={() => naviguer({ q: null })}
                    style={{ background: "none", border: "none", padding: 0, font: "inherit", fontWeight: 700, color: "var(--tcn-ink)", cursor: "pointer" }}
                  >
                    Effacer la recherche
                  </button>
                }
              />
            ) : filtreClub ? (
              <EmptyState
                bare
                title={`Aucun athlète du ${CLUB_NAME} sur cette épreuve`}
                action={
                  <button
                    type="button"
                    onClick={() => naviguer({ [SCOPE_PARAM]: null })}
                    style={{ background: "none", border: "none", padding: 0, font: "inherit", fontWeight: 700, color: "var(--tcn-ink)", cursor: "pointer" }}
                  >
                    Voir tous les participants
                  </button>
                }
              />
            ) : (
```

« Effacer la recherche » ne retire plus que la recherche : sous filtre club, retirer les deux d'un geste nommé « la recherche » ferait plus que ce qu'il annonce. La ligne d'état de la tâche 7 porte le « Effacer » qui, lui, retire tout.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "fix(frontend): distinguer l'absence de résultat du filtre club de celle d'une recherche

Refs #485"
```

---

### Task 9: L'onglet TCN se grise quand il n'a personne à montrer

**Files:**
- Modify: `frontend/components/tcn/SegmentedControl.tsx`
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Test: `frontend/components/tcn/SegmentedControl.test.tsx`
- Test: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consumes: `SegmentedControl` (tâche 0 — existant).
- Produces: le type `Option` de `SegmentedControl` gagne `disabled?: boolean`.

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/tcn/SegmentedControl.test.tsx` :

```tsx
  it("n'appelle pas onChange sur une option désactivée", async () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        value="all"
        onChange={onChange}
        options={[
          { value: "all", label: "Tous" },
          { value: "tcn", label: "TCN", disabled: true },
        ]}
      />,
    );

    const tcn = screen.getByRole("button", { name: "TCN" });
    expect(tcn).toHaveAttribute("aria-disabled", "true");

    await userEvent.click(tcn);
    expect(onChange).not.toHaveBeenCalled();
  });
```

Et à `frontend/components/results/RaceFinishers.test.tsx` :

```tsx
  it("grise l'onglet club quand l'épreuve ne compte aucun athlète TCN", () => {
    afficher({ summary: synthese({ total: 498, tcn_count: 0 }) });

    expect(screen.getByRole("button", { name: /Triathlon Club Nantais \(0\)/ })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("laisse l'onglet club actif dès qu'un athlète TCN figure sur l'épreuve", () => {
    afficher({ summary: synthese({ total: 498, tcn_count: 3 }) });

    expect(screen.getByRole("button", { name: /Triathlon Club Nantais \(3\)/ })).not.toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- components/tcn/SegmentedControl.test.tsx components/results/RaceFinishers.test.tsx`
Expected: FAIL — `aria-disabled` absent, et `onChange` appelé.

- [ ] **Step 3: Write minimal implementation**

Dans `frontend/components/tcn/SegmentedControl.tsx`, étendre le type d'option :

```tsx
type Option = string | { value: string; label: ReactNode; dot?: boolean; disabled?: boolean };
```

Dans la boucle, lire l'état et neutraliser le bouton :

```tsx
        const desactive = typeof opt === "object" ? !!opt.disabled : false;
```

puis, sur le `<button>` :

```tsx
            aria-pressed={active}
            aria-disabled={desactive || undefined}
            onClick={() => {
              // `aria-disabled` plutôt que `disabled` : un segment retiré du
              // parcours clavier disparaîtrait aussi de l'annonce, alors qu'il
              // porte une information — le club n'a personne sur l'épreuve.
              if (!desactive) onChange(val);
            }}
```

et, dans le `style` du bouton, après `...skin` :

```tsx
              ...(desactive ? { opacity: 0.5, cursor: "not-allowed" } : null),
```

Dans `RaceFinishers.tsx`, marquer l'option :

```tsx
              { value: "tcn", label: `${CLUB_NAME} (${summary.tcn_count})`, dot: true, disabled: summary.tcn_count === 0 },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/tcn/SegmentedControl.test.tsx components/results/RaceFinishers.test.tsx`
Expected: PASS. Une URL portant déjà `scope=club` sur une épreuve à zéro athlète TCN rend l'onglet actif **et** désactivé ; « Tous les participants » reste cliquable, la sortie est donc ouverte.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/tcn/SegmentedControl.tsx frontend/components/tcn/SegmentedControl.test.tsx frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "feat(frontend): griser l'onglet club quand l'épreuve n'a aucun athlète TCN

Refs #485"
```

---

### Task 10: Le tri dit sur quoi il porte

**Files:**
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Test: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consumes: `EnteteTriable` et `AnnonceStatut` (existants dans `RaceFinishers.tsx`).
- Produces: `EnteteTriable` gagne une prop `perimetre: string` (chaîne vide quand le tri est global).

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/results/RaceFinishers.test.tsx` :

```tsx
  it("annonce le périmètre du tri : la tranche affichée, pas le classement", async () => {
    afficher({ total: 860, pageSize: 20 });

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps total/ }));

    expect(
      screen.getByRole("status").textContent,
    ).toContain("sur les 3 lignes affichées");
  });

  it("ne mentionne aucun périmètre quand tout le classement est affiché", async () => {
    searchParams = new URLSearchParams("page_size=all");
    afficher({ total: 3, pageSize: null });

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps total/ }));

    expect(screen.getByRole("status").textContent).not.toContain("lignes affichées");
  });

  it("porte le périmètre jusque dans l'aria-label des en-têtes", () => {
    afficher({ total: 860, pageSize: 20 });

    expect(
      screen.getByRole("button", { name: "Trier par temps total, croissant, sur les 3 lignes affichées" }),
    ).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: FAIL — l'annonce ne contient pas « sur les 3 lignes affichées ».

- [ ] **Step 3: Write minimal implementation**

Dans `RaceFinishers.tsx`, après le calcul de `lignes`, ajouter :

```tsx
  // Le tri par en-tête ne porte que sur la tranche affichée. Sur 43 pages, le
  // taire rendrait le classement trompeur ; sous `page_size=all`, il n'y a rien
  // à dire, le tri est global.
  const perimetreTri = pageSize == null ? "" : `, sur les ${lignes.length} lignes affichées`;
```

Compléter le texte annoncé :

```tsx
  const texteAnnonce =
    `${lignes.length} résultat${lignes.length > 1 ? "s" : ""} affiché${lignes.length > 1 ? "s" : ""}` +
    (libelleTri
      ? `, trié par ${libelleTri}, ${tri!.direction === "asc" ? "croissant" : "décroissant"}${perimetreTri}`
      : "");
```

Passer le périmètre aux deux usages d'`EnteteTriable` :

```tsx
              <EnteteTriable cle={CLE_TEMPS_TOTAL} libelle="Temps total" ariaSujet="temps total" tri={tri} onTrier={trierSur} perimetre={perimetreTri} />
```

```tsx
                <EnteteTriable cle={s.key} libelle={s.label} ariaSujet={`temps ${s.label}`} tri={tri} onTrier={trierSur} perimetre={perimetreTri} />
```

Et dans `EnteteTriable`, ajouter la prop et l'inclure dans le libellé :

```tsx
  perimetre,
}: {
  cle: string;
  libelle: string;
  ariaSujet: string;
  tri: { cle: string; direction: "asc" | "desc" } | null;
  onTrier: (cle: string) => void;
  perimetre: string;
}) {
```

```tsx
      aria-label={`Trier par ${ariaSujet}, ${prochaineDirection === "asc" ? "croissant" : "décroissant"}${perimetre}`}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS.

- [ ] **Step 5: Vérification d'ensemble**

Run: `npm test`
Expected: toute la suite verte.

Run: `npm run lint && npm run build`
Expected: aucun avertissement, build prod réussi.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "fix(a11y): annoncer le périmètre du tri du classement

Le tri par en-tête ne porte que sur la tranche affichée — trompeur sur
43 pages tant qu'il ne le disait pas.

Refs #485"
```

---

## Fin de branche

Une fois les dix tâches vertes, dérouler la fin de branche commune aux trois voies (`AGENTS.md`) :

1. `superpowers:requesting-code-review`
2. sous-agent `ui-ux-review` — la branche touche `frontend/`
3. `superpowers:verification-before-completion`
4. `superpowers:finishing-a-development-branch`

La PR se lie à l'issue par `Closes #485` — jeton machine, en anglais, le reste de la description en français.
