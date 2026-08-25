# Profil athlète — en-tête et tuiles : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sur `/club`, chaque décompte de podium dit sur quelle portée il porte et la liste n'est plus tronquée en silence ; sur `/athletes/[id]`, l'en-tête dit de quel athlète il s'agit et les tuiles ne montrent plus que ce qui est certain.

**Architecture:** Trois retouches indépendantes de rendu, aucune modification d'agrégat. `PROF-3` réutilise le slot `delta` de `StatCard` et les libellés de `lib/labels.ts` déjà en place, plus un état local d'extension dans `PodiumsList`. `PROF-4` extrait la décision « quelles tuiles » de `page.tsx` vers une fonction pure `lib/utils/athlete-stats.ts`, la page ne fait plus que rendre. `PROF-5` remplace un bloc en styles inline par le `PageHeader` partagé posé par #475.

**Tech Stack:** Next.js 16 (App Router, RSC), TypeScript, Tailwind, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-08-25-profil-athlete-en-tete-et-tuiles-design.md`

**Issue:** [#488](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/488) — lot de l'epic #460.

## Global Constraints

- **Identité visuelle non rejugée** (#325) : variables `--tcn-*`, polices Anton/Barlow. Aucune nouvelle couleur, aucune nouvelle police.
- **Frontière `components/tcn/` vs `components/ui/` non rejugée** (#325, #460) : on n'ajoute ni ne déplace de composant entre les deux.
- **Français** pour tout ce qui est visible ou métier (libellés, microcopie, commentaires de règle métier). **English** pour la couche technique invisible (préfixes Conventional Commits). Les identifiants de code de ce lot suivent le français déjà en place dans `frontend/` (`APERCU_ROSTER`, `AnnonceStatut`…).
- **Toutes les commandes depuis `frontend/`.**
- **Tests** : `npm test` (vitest run). Un fichier seul : `npx vitest run <chemin>`.
- **Lint** : `npm run lint` avant chaque commit qui touche du `.tsx`.
- **Commits** : Conventional Commits, préfixés du numéro d'issue — `feat(488): …`, `fix(488): …`, `test(488): …`. Terminer chaque message par :
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  ```
- **Aucun « — » nu** ne doit rester sur le profil d'un athlète sous le seuil : c'est le critère d'acceptation central de `PROF-4`.

---

## Structure des fichiers

| Fichier | Responsabilité | Tâche |
| --- | --- | --- |
| `frontend/components/club/ClubPodiumKpi.tsx` | KPI Podiums — porte désormais sa portée en `delta` | 1 |
| `frontend/components/club/ClubDashboard.tsx` | Tableau de bord club — nomme la portée du roster | 2 |
| `frontend/components/club/PodiumsList.tsx` | Liste des podiums — extension totale sur demande | 3 |
| `frontend/lib/utils/athlete-stats.ts` *(créé)* | Fonction pure : quel régime de tuiles, et lesquelles | 4 |
| `frontend/app/(public_restricted)/athletes/[id]/page.tsx` | Rendu : tuiles selon le régime (t. 5), en-tête (t. 6) | 5, 6 |

Les tâches 1, 2 et 3 sont mutuellement indépendantes et indépendantes de 4-6. Les tâches 5 et 6 touchent le même fichier et se font dans l'ordre.

---

### Task 1: Le KPI Podiums dit sa portée

**Files:**
- Modify: `frontend/components/club/ClubPodiumKpi.tsx`
- Test: `frontend/components/club/ClubPodiumKpi.test.tsx`

**Interfaces:**
- Consumes: `rankTypeLabel(t: RankType, opts?: { form?: "short" | "long" }): string` de `@/lib/labels` — déjà existant. En `form: "long"` il rend `"général"`, `"catégorie"`, `"genre"`, `"général, genre ou catégorie"`.
- Produces: rien pour les tâches suivantes.

**Contexte pour l'implémenteur :** `StatCard` (`components/tcn/StatCard.tsx`) a un slot `delta` rendu en petit sous le nombre. Le composant `StatCardsRank` du dashboard s'en sert déjà pour écrire « 12 · général ». On applique exactement le même geste ici — c'est le précédent à imiter, pas une invention.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin du `describe` existant de `frontend/components/club/ClubPodiumKpi.test.tsx` :

```tsx
  // #488 (PROF-3) : le KPI et le roster comptent les podiums différemment et
  // les deux sont justes. Faute de le dire, basculer le toggle faisait bouger
  // un nombre et pas l'autre. La portée voyage donc avec le chiffre.
  it("nomme la portée du décompte, mode par mode (PROF-3, #488)", () => {
    searchParams = new URLSearchParams();
    const { unmount } = render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("général")).toBeInTheDocument();
    unmount();

    searchParams = new URLSearchParams("rank=category");
    const b = render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("catégorie")).toBeInTheDocument();
    b.unmount();

    searchParams = new URLSearchParams("rank=gender");
    const c = render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("genre")).toBeInTheDocument();
    c.unmount();

    searchParams = new URLSearchParams("rank=all");
    render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("général, genre ou catégorie")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `npx vitest run components/club/ClubPodiumKpi.test.tsx`
Expected: FAIL — `Unable to find an element with the text: général`.

- [ ] **Step 3: Implémenter**

Dans `frontend/components/club/ClubPodiumKpi.tsx`, ajouter l'import et la prop :

```tsx
import { rankTypeLabel } from "@/lib/labels";
```

et remplacer le `return` par :

```tsx
  // `accent={false}` comme les trois KPI SSR de `ClubDashboard` : le trait
  // orange reste à la seule tuile mise en avant (« Résultats »).
  // Le `delta` nomme la portée du décompte (#488, PROF-3) : le roster deux
  // blocs plus bas compte sur les trois portées cumulées, sans condition. Les
  // deux nombres sont justes et incomparables — chacun porte donc le sien.
  // Même geste que `StatCardsRank`, qui écrit déjà « 12 · général ».
  return (
    <StatCard
      label="Podiums"
      value={count}
      accent={false}
      delta={rankTypeLabel(rankType, { form: "long" })}
    />
  );
```

- [ ] **Step 4: Lancer les tests et vérifier qu'ils passent**

Run: `npx vitest run components/club/ClubPodiumKpi.test.tsx`
Expected: PASS, tous les tests du fichier.

- [ ] **Step 5: Lint et commit**

```bash
npm run lint
git add components/club/ClubPodiumKpi.tsx components/club/ClubPodiumKpi.test.tsx
git commit -m "$(cat <<'EOF'
feat(488): le KPI Podiums porte la portée de son décompte

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Le roster nomme sa portée

**Files:**
- Modify: `frontend/components/club/ClubDashboard.tsx`
- Test: `frontend/components/club/ClubDashboard.test.tsx`

**Interfaces:**
- Consumes: rien de la tâche 1.
- Produces: rien pour les tâches suivantes.

**Contexte pour l'implémenteur :** la section « Les athlètes les plus actifs » a un `h2` suivi d'un lien « Voir saison par saison → », le tout dans un `div.flex.items-baseline.justify-between`. Chaque carte du roster affiche « N épreuves · M podiums » plus des badges ventilés par portée. Ces M cumulent les trois portées **sans condition** (`buildRoster`, `club-aggregate.ts`) et ne bougent pas avec `?rank=` — on le dit, on ne change aucun chiffre.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `frontend/components/club/ClubDashboard.test.tsx`, à l'intérieur du `describe` principal existant (réutiliser la fixture de participations déjà en place dans le fichier — si elle est locale à un test, l'extraire en constante au niveau du `describe` avant d'ajouter celui-ci) :

```tsx
  // #488 (PROF-3) : les podiums du roster cumulent les trois portées sans
  // condition, quand le KPI plus haut suit `?rank=`. Le dire est ce qui
  // manquait — aucun chiffre ne change.
  it("nomme la portée des podiums du roster (PROF-3, #488)", () => {
    render(<ClubDashboard stats={STATS} participations={PARTS} />);

    expect(screen.getByText("podiums toutes portées confondues")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `npx vitest run components/club/ClubDashboard.test.tsx`
Expected: FAIL — `Unable to find an element with the text: podiums toutes portées confondues`.

- [ ] **Step 3: Implémenter**

Dans `frontend/components/club/ClubDashboard.tsx`, section Roster, remplacer le `div` d'en-tête de section par un bloc à deux lignes :

```tsx
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h2 className="font-heading text-lg font-semibold">
              {roster.length > APERCU_ROSTER ? "Les athlètes les plus actifs" : "Athlètes du club"}
            </h2>
            {/* #488 (PROF-3) : `buildRoster` compte les podiums sur les trois
                portées sans condition, quand le KPI « Podiums » plus haut suit
                `?rank=`. Les deux nombres sont justes et incomparables ; sans
                cette ligne, basculer le toggle faisait bouger l'un et pas
                l'autre, sans explication à l'écran. */}
            <p className="text-sm text-[var(--tcn-text-faint)]">
              podiums toutes portées confondues
            </p>
          </div>
          {/* Inconditionnel : « les deux écrans reliés dans les deux sens »
              est une garantie de navigation, elle ne peut pas s'éteindre sous
              13 athlètes. Le libellé dit la destination et non un décompte —
              /club/athletes ouvre sur la saison en cours seule, quand
              `roster.length` agrège toutes les saisons ; le total du club vit
              dans le KPI « Athlètes », qui le tient déjà. */}
          <Link
            href="/club/athletes"
            className="shrink-0 text-sm font-medium text-accent-ink hover:underline"
          >
            Voir saison par saison →
          </Link>
        </div>
```

- [ ] **Step 4: Lancer les tests et vérifier qu'ils passent**

Run: `npx vitest run components/club/ClubDashboard.test.tsx`
Expected: PASS, tous les tests du fichier.

- [ ] **Step 5: Lint et commit**

```bash
npm run lint
git add components/club/ClubDashboard.tsx components/club/ClubDashboard.test.tsx
git commit -m "$(cat <<'EOF'
feat(488): la section roster nomme la portée de ses podiums

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: La liste des podiums s'ouvre en entier

**Files:**
- Modify: `frontend/components/club/PodiumsList.tsx`
- Test: `frontend/components/club/PodiumsList.test.tsx`

**Interfaces:**
- Consumes: rien des tâches 1-2.
- Produces: rien pour les tâches suivantes.

**Contexte pour l'implémenteur :** `PodiumsList` est déjà un composant client (`"use client"`). Il tronque à 6 en dur alors que le KPI en annonce 12 — sans le dire. On ajoute un `useState` d'extension et un bouton qui dit combien il reste. L'`AnnonceStatut` en place reflète déjà `podiums.length`, donc l'annonce WCAG 4.1.3 suit sans code supplémentaire : ne pas la dupliquer.

Pas de plafond à l'extension : le tri est rang croissant, le meilleur reste en haut, et qui clique demande la liste.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `frontend/components/club/PodiumsList.test.tsx`. La fixture `PARTS` du fichier ne contient que 3 participations : il faut une fixture large, locale à ce `describe`.

```tsx
describe("PodiumsList — extension de la liste (PROF-3, #488)", () => {
  // 9 podiums scratch : au-delà de l'aperçu de 6, donc 3 restants.
  const NEUF = Array.from({ length: 9 }, (_, i) => part({ id: i + 1, rank_overall: 1 }));

  it("n'offre pas d'extension quand tout tient dans l'aperçu", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={NEUF.slice(0, 6)} />);

    expect(screen.queryByRole("button", { name: /Voir les/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
  });

  it("dit combien de podiums restent sous l'aperçu", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={NEUF} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByRole("button", { name: "Voir les 3 autres podiums" })).toBeInTheDocument();
  });

  it("ouvre la liste entière au clic, et l'annonce suit", async () => {
    searchParams = new URLSearchParams();
    const user = userEvent.setup();
    render(<PodiumsList participations={NEUF} />);

    await user.click(screen.getByRole("button", { name: "Voir les 3 autres podiums" }));

    expect(screen.getAllByRole("listitem")).toHaveLength(9);
    expect(screen.queryByRole("button", { name: /Voir les/ })).not.toBeInTheDocument();
    // L'`AnnonceStatut` en place reflète le décompte affiché : l'extension est
    // annoncée sans région live supplémentaire (WCAG 4.1.3, cf. #477).
    expect(screen.getByText("9 podiums affichés")).toBeInTheDocument();
  });

  it("accorde le singulier quand il ne reste qu'un podium", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={NEUF.slice(0, 7)} />);

    expect(screen.getByRole("button", { name: "Voir l'autre podium" })).toBeInTheDocument();
  });
});
```

Ajouter l'import de `userEvent` en tête de fichier s'il n'y est pas déjà :

```tsx
import userEvent from "@testing-library/user-event";
```

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `npx vitest run components/club/PodiumsList.test.tsx`
Expected: FAIL — les quatre nouveaux tests échouent (`Unable to find an accessible element with the role "button"` pour trois d'entre eux ; `expected length 6 to be 9` pour le troisième si le bouton était trouvé).

- [ ] **Step 3: Implémenter**

Dans `frontend/components/club/PodiumsList.tsx` :

Ajouter `useState` à l'import React et déclarer la constante d'aperçu au niveau module, sous les imports :

```tsx
import { useMemo, useState } from "react";
```

```tsx
/**
 * Taille de l'aperçu de la liste (#488, PROF-3). Le KPI « Podiums » deux blocs
 * plus haut annonce le total ; tronquer sans le dire faisait mentir la moitié
 * de l'écran. Le bouton d'extension dit combien il reste, et ouvre tout.
 */
const APERCU_PODIUMS = 6;
```

Dans le composant, remplacer le `useMemo` par le couple état + calcul :

```tsx
  const [etendu, setEtendu] = useState(false);
  const tous = useMemo(() => listPodiums(participations, rankType), [participations, rankType]);
  const podiums = etendu ? tous : tous.slice(0, APERCU_PODIUMS);
  const restants = tous.length - podiums.length;
```

Puis, dans le `return` final, après la balise `</ul>` fermante et **à l'intérieur** du fragment :

```tsx
      {restants > 0 && (
        <button
          type="button"
          onClick={() => setEtendu(true)}
          className="mt-3 text-sm font-medium text-accent-ink hover:underline"
        >
          {restants > 1 ? `Voir les ${restants} autres podiums` : "Voir l'autre podium"}
        </button>
      )}
```

- [ ] **Step 4: Lancer les tests et vérifier qu'ils passent**

Run: `npx vitest run components/club/PodiumsList.test.tsx`
Expected: PASS, tous les tests du fichier — les anciens compris (ils utilisent 3 participations, sous l'aperçu, donc sans bouton).

- [ ] **Step 5: Lint et commit**

```bash
npm run lint
git add components/club/PodiumsList.tsx components/club/PodiumsList.test.tsx
git commit -m "$(cat <<'EOF'
feat(488): la liste des podiums s'ouvre en entier au lieu de tronquer en silence

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `athlete-stats.ts` — quel régime de tuiles, et lesquelles

**Files:**
- Create: `frontend/lib/utils/athlete-stats.ts`
- Test: `frontend/lib/utils/athlete-stats.test.ts` *(créé)*

**Interfaces:**
- Consumes: `formatToken(eventType, distanceKm)` et `ordinalFr(n)` de `@/lib/utils/format` ; `formatDate(d)` de `@/lib/utils/date` ; le type `Participation` de `@/lib/types`.
- Produces — **la tâche 5 s'appuie sur ces noms exacts** :
  ```ts
  export const SEUIL_TUILES_COMPLETES = 3;
  export interface TuileResume { label: string; value: string; hint: string | null }
  export interface ResumeAthlete {
    regime: "complet" | "reduit" | "vide";
    validees: Participation[];
    enAttente: number;
    tuiles: TuileResume[];
  }
  export function resumeAthlete(participations: Participation[]): ResumeAthlete;
  ```

**Contexte pour l'implémenteur :** 47 % des membres n'ont qu'une course. La grille de 5 tuiles leur rend deux « — » nus et deux tautologies. On ne répare pas les cinq tuiles au cas par cas — on décide en amont, dans une fonction pure, s'il faut le jeu complet ou un jeu réduit qui ne dit que ce qui est certain.

Règles, dans cet ordre :

1. `validees` = les participations sans `is_pending_validation` (même filtre que les KPI actuels depuis #438). `enAttente` = le reste.
2. `validees.length === 0` → `regime: "vide"`, `tuiles: []`. La page décide quoi rendre (rien, ou une ligne d'explication si `enAttente > 0`).
3. `validees.length >= SEUIL_TUILES_COMPLETES` → `regime: "complet"`, `tuiles: []`. La page rend les cinq tuiles actuelles, inchangées.
4. Sinon → `regime: "reduit"` et les tuiles ci-dessous, dans l'ordre, chacune omise si sa donnée manque. Elles portent sur la **dernière participation validée** (`course.event_date` le plus grand ; à date égale ou absente, la dernière du tableau) :
   - `Épreuves` = le décompte ; `hint` = `"N en attente de validation"` si `enAttente > 0`, sinon `null`.
   - `Discipline` = `formatToken(course.event_type, course.distance_km)` ; `hint` = `course.name`. **Omise** si le jeton vaut `"—"` (c'est le repli de `formatToken` quand il ne reconnaît rien).
   - `Temps` = `total_time` ; `hint` = `formatDate(course.event_date)` ou `null`. Si `total_time` est absent, la tuile devient `Place` = `ordinalFr(rank_overall)` ; `hint` = `"sur N classés"` si `course_finishers` est renseigné, sinon la date. Si `total_time` **et** `rank_overall` manquent, aucune des deux n'est rendue.

`value` reste court à dessein : `StatCard` le rend en 68 px display sans clamp, un nom d'épreuve y déborde. C'est pour ça que le nom va en `hint`.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `frontend/lib/utils/athlete-stats.test.ts` :

```ts
import { describe, it, expect } from "vitest";
import type { Participation } from "@/lib/types";
import { resumeAthlete, SEUIL_TUILES_COMPLETES } from "./athlete-stats";

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: {
      id: over.id,
      name: `Course ${over.id}`,
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
      ...(over.course ?? {}),
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: over.total_time === undefined ? "01:59:00" : over.total_time,
    status: "finisher",
    is_relay: false,
    is_pending_validation: over.is_pending_validation ?? false,
    splits: null,
    created_at: null,
    course_finishers: over.course_finishers,
  } as Participation;
}

const tuile = (r: ReturnType<typeof resumeAthlete>, label: string) =>
  r.tuiles.find((t) => t.label === label);

describe("resumeAthlete — régimes (#488, PROF-4)", () => {
  it("aucune participation : régime vide, aucune tuile", () => {
    const r = resumeAthlete([]);

    expect(r.regime).toBe("vide");
    expect(r.tuiles).toEqual([]);
    expect(r.enAttente).toBe(0);
  });

  it("que des participations en attente : régime vide, mais le compte en attente est porté", () => {
    const r = resumeAthlete([part({ id: 1, is_pending_validation: true })]);

    expect(r.regime).toBe("vide");
    expect(r.validees).toHaveLength(0);
    expect(r.enAttente).toBe(1);
  });

  it(`${SEUIL_TUILES_COMPLETES} épreuves validées : régime complet, la page garde ses cinq tuiles`, () => {
    const r = resumeAthlete([part({ id: 1 }), part({ id: 2 }), part({ id: 3 })]);

    expect(r.regime).toBe("complet");
    expect(r.tuiles).toEqual([]);
    expect(r.validees).toHaveLength(3);
  });

  it("une épreuve validée avec temps : Épreuves, Discipline, Temps — et rien d'autre", () => {
    const r = resumeAthlete([
      part({ id: 1, total_time: "01:02:03", course: { name: "Triathlon de Nantes" } as Participation["course"] }),
    ]);

    expect(r.regime).toBe("reduit");
    expect(r.tuiles.map((t) => t.label)).toEqual(["Épreuves", "Discipline", "Temps"]);
    expect(tuile(r, "Épreuves")).toMatchObject({ value: "1", hint: null });
    expect(tuile(r, "Discipline")).toMatchObject({ value: "M", hint: "Triathlon de Nantes" });
    expect(tuile(r, "Temps")).toMatchObject({ value: "01:02:03", hint: "16/05/2026" });
    // Le critère central de PROF-4 : aucune tuile ne rend un tiret nu.
    expect(r.tuiles.every((t) => t.value !== "—")).toBe(true);
  });

  it("sans temps mais avec un rang : la tuile Temps devient Place, rapportée au champ", () => {
    const r = resumeAthlete([part({ id: 1, total_time: null, rank_overall: 12, course_finishers: 300 })]);

    expect(r.tuiles.map((t) => t.label)).toEqual(["Épreuves", "Discipline", "Place"]);
    expect(tuile(r, "Place")).toMatchObject({ value: "12e", hint: "sur 300 classés" });
  });

  it("sans temps ni rang : ni Temps ni Place, jamais un tiret", () => {
    const r = resumeAthlete([part({ id: 1, total_time: null, rank_overall: null })]);

    expect(r.tuiles.map((t) => t.label)).toEqual(["Épreuves", "Discipline"]);
  });

  it("discipline non reconnue : la tuile est omise plutôt que rendue vide", () => {
    const r = resumeAthlete([
      part({ id: 1, course: { event_type: "", distance_km: null } as unknown as Participation["course"] }),
    ]);

    expect(tuile(r, "Discipline")).toBeUndefined();
  });

  it("deux épreuves : les tuiles portent la plus récente", () => {
    const r = resumeAthlete([
      part({ id: 1, total_time: "05:00:00", course: { event_date: "2024-03-01", name: "Ancienne" } as Participation["course"] }),
      part({ id: 2, total_time: "04:00:00", course: { event_date: "2026-06-01", name: "Récente" } as Participation["course"] }),
    ]);

    expect(r.regime).toBe("reduit");
    expect(tuile(r, "Discipline")?.hint).toBe("Récente");
    expect(tuile(r, "Temps")?.value).toBe("04:00:00");
  });

  it("les participations en attente ne comptent ni dans le régime ni dans les tuiles", () => {
    const r = resumeAthlete([
      part({ id: 1, total_time: "01:00:00" }),
      part({ id: 2, is_pending_validation: true }),
      part({ id: 3, is_pending_validation: true }),
    ]);

    expect(r.regime).toBe("reduit");
    expect(tuile(r, "Épreuves")).toMatchObject({ value: "1", hint: "2 en attente de validation" });
  });
});
```

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `npx vitest run lib/utils/athlete-stats.test.ts`
Expected: FAIL — `Failed to resolve import "./athlete-stats"`.

- [ ] **Step 3: Implémenter**

Créer `frontend/lib/utils/athlete-stats.ts` :

```ts
// Décide quelles tuiles de KPI le profil d'un athlète peut honnêtement rendre.
// Fonction pure et testable — la page ne fait que rendre ce qu'elle reçoit.
import type { Participation } from "@/lib/types";
import { formatToken, ordinalFr } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";

/**
 * Sous ce nombre d'épreuves validées, la grille de cinq tuiles ne dit plus
 * rien : « Meilleure place » et « Top 10 » y répètent l'unique course, et
 * « Meilleur ratio » comme « Format favori » retombent sur un tiret nu. 164 des
 * 350 membres — 47 % — sont dans ce cas (#488, PROF-4).
 */
export const SEUIL_TUILES_COMPLETES = 3;

export interface TuileResume {
  label: string;
  /** Volontairement court : `StatCard` rend `value` en 68 px display sans clamp. */
  value: string;
  hint: string | null;
}

export interface ResumeAthlete {
  /**
   * `complet` : les cinq tuiles habituelles. `reduit` : ce qui est certain de
   * la dernière épreuve. `vide` : rien de validé, donc aucune tuile.
   */
  regime: "complet" | "reduit" | "vide";
  validees: Participation[];
  enAttente: number;
  /** Tuiles du régime `reduit` uniquement — vide dans les deux autres. */
  tuiles: TuileResume[];
}

/** La plus récente par date d'épreuve ; à date égale ou absente, la dernière reçue. */
function derniere(parts: Participation[]): Participation {
  let best = parts[0];
  for (const p of parts) {
    if ((p.course?.event_date ?? "") >= (best.course?.event_date ?? "")) best = p;
  }
  return best;
}

export function resumeAthlete(participations: Participation[]): ResumeAthlete {
  // Même filtre que les KPI depuis #438 : une saisie manuelle en attente de
  // validation ne doit pas peser sur les chiffres avant vérification.
  const validees = participations.filter((p) => !p.is_pending_validation);
  const enAttente = participations.length - validees.length;

  if (validees.length === 0) return { regime: "vide", validees, enAttente, tuiles: [] };
  if (validees.length >= SEUIL_TUILES_COMPLETES) {
    return { regime: "complet", validees, enAttente, tuiles: [] };
  }

  const p = derniere(validees);
  const date = formatDate(p.course?.event_date) || null;
  const tuiles: TuileResume[] = [
    {
      label: "Épreuves",
      value: String(validees.length),
      hint: enAttente > 0 ? `${enAttente} en attente de validation` : null,
    },
  ];

  // `formatToken` retombe sur « — » quand il ne reconnaît rien : dans ce cas la
  // tuile disparaît au lieu d'afficher un tiret nu, ce que PROF-4 interdit.
  const discipline = formatToken(p.course?.event_type, p.course?.distance_km);
  if (discipline !== "—") {
    tuiles.push({ label: "Discipline", value: discipline, hint: p.course?.name ?? null });
  }

  if (p.total_time) {
    tuiles.push({ label: "Temps", value: p.total_time, hint: date });
  } else if (p.rank_overall != null && p.rank_overall >= 1) {
    // Repli sur la place, qui reste un fait de cette course-là — et non une
    // « meilleure place » qui ne compare rien.
    tuiles.push({
      label: "Place",
      value: ordinalFr(p.rank_overall),
      hint: p.course_finishers ? `sur ${p.course_finishers} classés` : date,
    });
  }

  return { regime: "reduit", validees, enAttente, tuiles };
}
```

- [ ] **Step 4: Lancer les tests et vérifier qu'ils passent**

Run: `npx vitest run lib/utils/athlete-stats.test.ts`
Expected: PASS, les neuf tests.

- [ ] **Step 5: Lint et commit**

```bash
npm run lint
git add lib/utils/athlete-stats.ts lib/utils/athlete-stats.test.ts
git commit -m "$(cat <<'EOF'
feat(488): athlete-stats décide quelles tuiles un profil peut honnêtement rendre

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Le profil rend le régime de tuiles qui lui correspond

**Files:**
- Modify: `frontend/app/(public_restricted)/athletes/[id]/page.tsx`
- Test: `frontend/app/(public_restricted)/athletes/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `resumeAthlete`, `SEUIL_TUILES_COMPLETES` et le type `ResumeAthlete` de la tâche 4 — signatures exactes dans son bloc **Produces**.
- Produces: rien pour la tâche 6, qui touche un autre bloc du même fichier.

**Contexte pour l'implémenteur :** cette tâche **casse quatre tests existants** de `page.test.tsx`, et c'est attendu : ils affirment la présence des cinq tuiles avec 1 ou 2 participations, ce qui passe désormais sous le seuil. Ils ne testent pas le seuil, ils testent le ratio et l'exclusion des participations en attente — on leur donne 3 participations validées pour qu'ils continuent de tester ce qu'ils testent. Un cinquième (`n'inclut pas une participation en attente…`) tombe en régime `vide` et se réécrit.

Ne pas ajouter d'appel à l'action pour le régime `vide` : `EventsTable` rend déjà l'`EmptyState` « Aucun résultat pour cet athlète » avec son lien « Ajouter un résultat → » (ETAT-3). Un second CTA sur le même écran serait un doublon.

- [ ] **Step 1: Réparer les tests existants que le seuil déplace**

Dans `frontend/app/(public_restricted)/athletes/[id]/page.test.tsx` :

a. `it("retient le meilleur ratio, pas la meilleure place")` — porter la fixture à trois participations validées :

```tsx
    await renderAthlete([
      part({ id: 1, rank_overall: 42, course_finishers: 300 }),
      part({ id: 2, rank_overall: 20, course_finishers: 80 }),
      // #488 : le régime complet des cinq tuiles commence à 3 épreuves validées.
      part({ id: 3, rank_overall: 60, course_finishers: 90 }),
    ]);
```

b. `it("retombe sur la place seule quand le classement est incohérent")` — même traitement, en gardant l'incohérence sur la participation testée :

```tsx
    await renderAthlete([
      part({ id: 1, rank_overall: 42, course_finishers: 20 }),
      part({ id: 2, rank_overall: 50, course_finishers: 20 }),
      part({ id: 3, rank_overall: 60, course_finishers: 20 }),
    ]);
```

c. `it("compte les StatCard sur les participations validées, malgré une en attente (#438)")` — trois validées plus l'attente :

```tsx
    await renderAthlete([
      part({ id: 1, rank_overall: 5, course_finishers: 50 }),
      part({ id: 3, rank_overall: 9, course_finishers: 50 }),
      part({ id: 4, rank_overall: 30, course_finishers: 50 }),
      part({ id: 2, is_pending_validation: true, rank_overall: 1, course_finishers: 50 }),
    ]);

    const episCard = screen.getByText("Épreuves").parentElement?.parentElement;
    expect(within(episCard as HTMLElement).getByText("3")).toBeInTheDocument();
    expect(within(episCard as HTMLElement).getByText("1 en attente de validation")).toBeInTheDocument();

    // La meilleure place validée est 5, pas le rang 1 de la participation en attente.
    const placeCard = screen.getByText("Meilleure place").parentElement?.parentElement;
    expect(within(placeCard as HTMLElement).getByText("5")).toBeInTheDocument();
```

d. `it("n'inclut pas une participation en attente de validation dans les 5 StatCard (#438)")` — la seule participation étant en attente, il n'y a plus de grille du tout. Remplacer le test entier par :

```tsx
  it("ne rend aucune tuile quand la seule participation est en attente, et dit pourquoi (#438, #488)", async () => {
    const { container } = await renderAthlete([
      part({ id: 1, is_pending_validation: true, rank_overall: 1, course_finishers: 50 }),
    ]);

    // Aucune tuile : sans résultat validé, les cinq KPI ne rendaient que des
    // zéros et des tirets. Une ligne explique l'absence plutôt que de la subir.
    expect(screen.queryByText("Meilleure place")).not.toBeInTheDocument();
    expect(screen.queryByText("Meilleur ratio")).not.toBeInTheDocument();
    expect(screen.queryByText("Format favori")).not.toBeInTheDocument();
    expect(
      screen.getByText("Aucun résultat validé pour l'instant — 1 en attente de validation."),
    ).toBeInTheDocument();

    // Le tableau détaillé, lui, continue d'afficher la participation en
    // attente, badge compris.
    const pendingRow = container.querySelector<HTMLElement>("a[href='/courses/1/participations/1']");
    expect(pendingRow).not.toBeNull();
    expect(within(pendingRow as HTMLElement).getByText("En attente de validation")).toBeInTheDocument();
  });
```

e. `it("n'affiche pas de repère « en attente » sur « Épreuves » quand tout est validé (#438)")` — inchangé : la tuile `Épreuves` existe aussi en régime réduit, sans `hint`. Le vérifier au step 4 plutôt que de le modifier à l'aveugle.

- [ ] **Step 2: Écrire les tests du nouveau comportement**

Ajouter à `page.test.tsx`, dans un `describe` dédié au niveau racine du fichier :

```tsx
describe("AthletePage — tuiles proportionnées au volume (PROF-4, #488)", () => {
  it("sous le seuil, ne rend que ce qui est certain — et aucun tiret nu", async () => {
    await renderAthlete([
      part({
        id: 1,
        rank_overall: 12,
        course_finishers: 300,
        course: { name: "Triathlon de Nantes" } as Participation["course"],
      }),
    ]);

    expect(screen.getByText("Épreuves")).toBeInTheDocument();
    expect(screen.getByText("Discipline")).toBeInTheDocument();
    expect(screen.getByText("Temps")).toBeInTheDocument();
    expect(screen.queryByText("Meilleure place")).not.toBeInTheDocument();
    expect(screen.queryByText("Meilleur ratio")).not.toBeInTheDocument();
    expect(screen.queryByText("Top 10")).not.toBeInTheDocument();
    expect(screen.queryByText("Format favori")).not.toBeInTheDocument();

    // Le critère central de PROF-4, scopé à la grille : le tableau plus bas a
    // ses propres tirets légitimes (finisher sans rang, AC3 de #438).
    const grille = screen.getByText("Épreuves").closest("div.grid");
    expect(grille).not.toBeNull();
    expect(grille?.textContent).not.toContain("—");
  });

  it("sous le seuil, propose d'ajouter une épreuve", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 12 })]);

    expect(screen.getByRole("link", { name: /Ajouter une épreuve/ })).toHaveAttribute("href", "/ajouter");
  });

  it("sans aucune participation, ne rend ni tuile ni second appel à l'action", async () => {
    await renderAthlete([]);

    expect(screen.queryByText("Épreuves")).not.toBeInTheDocument();
    // L'`EmptyState` d'`EventsTable` (ETAT-3) porte déjà le seul CTA de l'écran.
    expect(screen.queryByRole("link", { name: /Ajouter une épreuve/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ajouter un résultat/ })).toBeInTheDocument();
  });

  it("au seuil, retrouve les cinq tuiles", async () => {
    await renderAthlete([
      part({ id: 1, rank_overall: 12, course_finishers: 300 }),
      part({ id: 2, rank_overall: 20, course_finishers: 300 }),
      part({ id: 3, rank_overall: 30, course_finishers: 300 }),
    ]);

    for (const label of ["Épreuves", "Meilleure place", "Meilleur ratio", "Top 10", "Format favori"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });
});
```

- [ ] **Step 3: Lancer les tests et vérifier qu'ils échouent**

Run: `npx vitest run "app/(public_restricted)/athletes/[id]/page.test.tsx"`
Expected: FAIL — les quatre nouveaux tests échouent, ainsi que le test réécrit du point (d).

- [ ] **Step 4: Implémenter**

Dans `frontend/app/(public_restricted)/athletes/[id]/page.tsx` :

Ajouter les imports :

```tsx
import Link from "next/link";
import { resumeAthlete } from "@/lib/utils/athlete-stats";
```

Remplacer le calcul de `validated` / `pendingCount` par l'appel à la fonction pure, en gardant le reste des calculs qui n'ont de sens qu'en régime complet :

```tsx
  // Les tuiles ne portent que sur les participations déjà validées : une saisie
  // manuelle « en attente de validation » (#270) ne doit pas fausser les KPI
  // avant qu'un bénévole ne l'ait vérifiée (#438). Le tableau détaillé plus bas,
  // lui, continue d'afficher `participations` au complet.
  // Le **régime** de tuiles, lui, suit le volume : sous 3 épreuves, les cinq
  // tuiles habituelles ne rendent que des tautologies et des tirets (#488).
  const resume = resumeAthlete(participations);
  const { validees: validated, enAttente: pendingCount } = resume;
```

Puis remplacer le bloc `<div className="mb-6 grid …">` par le rendu conditionnel :

```tsx
      {resume.regime === "reduit" && (
        <div className="mb-6 space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {resume.tuiles.map((t) => (
              <StatCard key={t.label} label={t.label} value={t.value} hint={t.hint} accent={false} />
            ))}
          </div>
          <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
            Ajouter une épreuve →
          </Link>
        </div>
      )}

      {/* Régime vide avec des participations en attente : le tableau plus bas
          montre bien des lignes, il faut donc dire pourquoi les chiffres, eux,
          sont absents. Sans participation du tout, l'`EmptyState`
          d'`EventsTable` (ETAT-3) porte déjà le message et le seul CTA. */}
      {resume.regime === "vide" && pendingCount > 0 && (
        <p className="mb-6 text-sm text-[var(--tcn-text-faint)]">
          Aucun résultat validé pour l&apos;instant — {pendingCount} en attente de validation.
        </p>
      )}

      {resume.regime === "complet" && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard
            label="Épreuves"
            value={validated.length}
            // Le tableau plus bas montre aussi les participations en attente de
            // validation (#270) : sans ce repère, un « 0 » ou un compte plus bas
            // que le nombre de lignes du tableau peut se lire comme une absence
            // de résultat plutôt que comme une validation encore à faire (#438).
            hint={pendingCount > 0 ? `${pendingCount} en attente de validation` : null}
            accent={false}
          />
          <StatCard label="Meilleure place" value={best ?? "—"} valueColor="var(--tcn-orange)" accent={false} />
          <StatCard
            label="Meilleur ratio"
            value={topRatio ? `Top ${topRatio.ratio.percent}%` : "—"}
            hint={topRatio ? `${ordinalFr(topRatio.ratio.rank)} sur ${topRatio.ratio.total}` : null}
            valueColor="var(--tcn-orange)"
            accent={false}
          />
          <StatCard label="Top 10" value={top10} accent={false} />
          <StatCard label="Format favori" value={favFormat} accent={false} />
        </div>
      )}
```

Ce bloc reprend les cinq `StatCard` **telles quelles** depuis le fichier actuel : les calculs `best`, `top10`, `favFormat` et `topRatio` restent en place au-dessus, inchangés.

- [ ] **Step 5: Lancer les tests et vérifier qu'ils passent**

Run: `npx vitest run "app/(public_restricted)/athletes/[id]/page.test.tsx"`
Expected: PASS, tous les tests du fichier. Si `n'affiche pas de repère « en attente » …` échoue, c'est que la tuile `Épreuves` du régime réduit porte un `hint` à tort — vérifier que `enAttente` vaut bien 0 dans ce cas.

- [ ] **Step 6: Lint et commit**

```bash
npm run lint
git add "app/(public_restricted)/athletes/[id]/page.tsx" "app/(public_restricted)/athletes/[id]/page.test.tsx"
git commit -m "$(cat <<'EOF'
feat(488): sous 3 épreuves, le profil ne montre que ce qui est certain

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: L'en-tête du profil dit de quel athlète il s'agit

**Files:**
- Modify: `frontend/app/(public_restricted)/athletes/[id]/page.tsx`
- Test: `frontend/app/(public_restricted)/athletes/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `PageHeader` de `@/components/layout/PageHeader` — props `title`, `eyebrow`, `description`, `actions`, `backHref`, `backLabel`, `className`, `children`. `MetaPill` de `@/components/tcn` — props `label`, `children`, `accent`, `dot`, `href`, `title`, `style`. `genderShort(gender)` de `@/lib/utils/format`. `resume.validees` de la tâche 4 (déjà en place dans le fichier après la tâche 5).
- Produces: rien.

**Contexte pour l'implémenteur :** aujourd'hui l'en-tête n'affiche que le nom et « Résultats enregistrés ». Les homonymes existent dans ce jeu de données (« Hadrien KERMARREC » face à « FLEURY hadrien / jean-baptiste . KERMARREC ») : arrivé sur le profil, on ne peut plus vérifier qu'on est sur le bon. `AthleteBrief` porte `gender` et `club` ; la **catégorie** n'y est pas — elle vit sur la participation (`p.category`) et change avec l'âge, donc on prend celle de la dernière participation validée, avec son année en `title` pour dire qu'elle date.

`PageHeader` n'a pas de slot image : `AthleteAvatar` reste **frère** du composant dans un flex, plutôt que d'ajouter une prop `media` au composant partagé pour un unique appelant.

- [ ] **Step 1: Écrire les tests qui échouent**

**Préalable — la fixture ne sait pas porter de catégorie.** Dans `page.test.tsx`, `part()` écrit `category: null` en dur. Le rendre surchargeable :

```tsx
    category: over.category ?? null,
```

Puis ajouter, dans un `describe` dédié au niveau racine :

```tsx
describe("AthletePage — l'en-tête identifie l'athlète (PROF-5, #488)", () => {
  it("affiche le club en surtitre, le genre et la catégorie en pastilles", async () => {
    // Un club distinct de « TCN » : la valeur voyage aussi dans la
    // participation, et on veut viser le surtitre sans ambiguïté.
    getAthlete.mockResolvedValue({
      athlete: { ...ATHLETE, club: "Triathlon Club Nantais" },
      participations: [part({ id: 1, rank_overall: 12, category: "V2H" })],
    });
    render(await AthletePage({ params: Promise.resolve({ id: "7" }) }));

    expect(screen.getByText("Triathlon Club Nantais")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Jean DUPONT" })).toBeInTheDocument();
    // Les pastilles rendent `<span>{label}</span>{valeur}` : on vise le
    // contenu du chip, pas un nœud texte isolé — « M » vaut aussi pour le
    // jeton de discipline de la tuile « Discipline » juste en dessous.
    expect(screen.getByText("Catégorie").parentElement).toHaveTextContent("V2H");
    expect(screen.getByText("Genre").parentElement).toHaveTextContent("M");
  });

  it("offre un retour vers la liste des athlètes du club", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 12 })]);

    expect(screen.getByRole("link", { name: /Athlètes du club/ })).toHaveAttribute(
      "href",
      "/club/athletes",
    );
  });

  it("retombe sur « Résultats enregistrés » quand l'athlète n'a pas de club", async () => {
    getAthlete.mockResolvedValue({
      athlete: { ...ATHLETE, club: null },
      participations: [part({ id: 1, rank_overall: 12 })],
    });
    render(await AthletePage({ params: Promise.resolve({ id: "7" }) }));

    expect(screen.getByText("Résultats enregistrés")).toBeInTheDocument();
  });

  it("omet la pastille de catégorie quand aucune participation n'en porte", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 12 })]);

    expect(screen.queryByText("Catégorie")).not.toBeInTheDocument();
    // Le genre, lui, vient de l'athlète et reste affiché.
    expect(screen.getByText("Genre").parentElement).toHaveTextContent("M");
  });
});
```

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `npx vitest run "app/(public_restricted)/athletes/[id]/page.test.tsx"`
Expected: FAIL — `Unable to find an element with the text: TCN` et `Unable to find an accessible element with the role "link" and name /Athlètes du club/`.

- [ ] **Step 3: Implémenter**

Dans `frontend/app/(public_restricted)/athletes/[id]/page.tsx` :

Ajouter aux imports :

```tsx
import { StatCard, MetaPill } from "@/components/tcn";
import { PageHeader } from "@/components/layout/PageHeader";
import { formatToken, genderShort, ordinalFr } from "@/lib/utils/format";
```

(`Eyebrow` n'est plus utilisé — retirer l'import.)

Calculer la catégorie, sous l'appel à `resumeAthlete` :

```tsx
  // La catégorie n'est pas sur l'athlète : elle vit sur la participation et
  // change avec l'âge. On prend celle de la dernière épreuve validée, et son
  // année part en `title` de la pastille pour dire de quand elle date (#488).
  const derniereValidee = [...validated].sort((a, b) =>
    (b.course?.event_date ?? "").localeCompare(a.course?.event_date ?? ""),
  )[0];
  const categorie = derniereValidee?.category ?? null;
  const anneeCategorie = derniereValidee?.course?.event_date?.slice(0, 4) ?? null;
```

Remplacer tout le bloc d'en-tête en styles inline (du `<div style={{ display: "flex", alignItems: "center", gap: 20 …` jusqu'à son `</div>` fermant) par :

```tsx
      <div className="mb-7 flex flex-wrap items-start gap-5">
        <AthleteAvatar athleteId={athlete.id} name={fullName} />
        <PageHeader
          className="min-w-0 flex-1"
          backHref="/club/athletes"
          backLabel="Athlètes du club"
          // Le club en surtitre plutôt qu'un « Résultats enregistrés » qui ne
          // distinguait rien : les homonymes existent dans ce jeu de données, et
          // arrivé sur le profil on ne pouvait plus vérifier qu'on était sur le
          // bon (#488, PROF-5). Repli sur l'ancien surtitre sans club connu.
          eyebrow={athlete.club ?? "Résultats enregistrés"}
          title={fullName}
          actions={
            <>
              <AthleteSelection athlete={{ id: athlete.id, prenom: athlete.prenom, nom: athlete.nom }} />
              <AthleteAdminPanel
                athlete={{ id: athlete.id, nom: athlete.nom, prenom: athlete.prenom, club: athlete.club }}
              />
            </>
          }
        >
          {(categorie || athlete.gender) && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {categorie && (
                <MetaPill
                  label="Catégorie"
                  title={anneeCategorie ? `Catégorie relevée en ${anneeCategorie}` : undefined}
                >
                  {categorie}
                </MetaPill>
              )}
              {athlete.gender && <MetaPill label="Genre">{genderShort(athlete.gender)}</MetaPill>}
            </div>
          )}
        </PageHeader>
      </div>
```

- [ ] **Step 4: Lancer les tests et vérifier qu'ils passent**

Run: `npx vitest run "app/(public_restricted)/athletes/[id]/page.test.tsx"`
Expected: PASS, tous les tests du fichier — y compris les trois anciens qui vérifient le `h1`, le bouton « Choisir cet athlète » et la pastille « C'est vous », que le slot `actions` continue de rendre.

- [ ] **Step 5: Vérifier la suite complète et le build**

```bash
npm test
npm run lint
npm run build
```

Expected: tests verts, aucune erreur de lint, build réussi (TypeScript strict + RSC).

- [ ] **Step 6: Commit**

```bash
git add "app/(public_restricted)/athletes/[id]/page.tsx" "app/(public_restricted)/athletes/[id]/page.test.tsx"
git commit -m "$(cat <<'EOF'
feat(488): l'en-tête du profil dit le club, la catégorie et le genre

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Fin de branche

Une fois les six tâches vertes, dérouler la fin de branche commune de `docs/WORKFLOW-IA.md` :

1. `superpowers:requesting-code-review`
2. Le sous-agent `ui-ux-review` — la branche touche `frontend/`. Points à lui soumettre explicitement : la lisibilité de la ligne « podiums toutes portées confondues » sous le `h2` du roster, l'alignement vertical du bloc `AthleteSelection` (colonne de 300 px de large) dans le slot `actions` de `PageHeader`, et la grille à trois tuiles du régime réduit sur mobile.
3. `superpowers:verification-before-completion`
4. `superpowers:finishing-a-development-branch` — la PR lie l'issue avec `Closes #488`.
