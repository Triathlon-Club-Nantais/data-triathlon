# Propager l'athlète retenu (#503) — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** qu'un athlète retenu n'ait plus à retaper son nom — une pastille qui pré-remplit le filtre de `/resultats`, sa ligne reconnaissable et atteignable dans le classement d'une épreuve, un raccourci vers ses résultats dans la tuile du rail.

**Architecture:** trois surfaces front, aucune touche au backend. Un hook `useSelectedAthlete()` ajouté à côté du stock `localStorage` existant sert les trois. Chaque geste est proposé, déclenché par un clic, et révoqué par une commande déjà à l'écran.

**Tech Stack:** Next.js 16 (App Router), TypeScript strict, React 19 (`useSyncExternalStore`), Vitest + Testing Library, Tailwind + tokens `--tcn-*`.

**Spec:** `docs/superpowers/specs/2026-08-25-athlete-retenu-propagation-design.md`

## Global Constraints

- **Toutes les commandes se lancent depuis `frontend/`.** Tests : `npm test -- <chemin>`. Lint : `npm run lint`. Build : `npm run build`.
- **Aucun changement backend.** Aucune route, aucun paramètre d'API n'est ajouté ni modifié. Si une tâche semble en demander un, c'est que le plan est faux — s'arrêter et le dire.
- **Pas de cookie miroir de l'athlète retenu** (#467). Le stock `tcn-athlete` se lit côté client uniquement. Ne jamais l'envoyer au serveur, ne jamais le lire dans un composant serveur.
- **Aucun filtre appliqué au chargement.** Chaque geste de ce lot exige un clic.
- **Langue** (Principe I de la constitution) : **français** pour tout ce que l'utilisateur lit et pour les commentaires de règle métier ; **English** pour les préfixes de commit. Les identifiants nouveaux suivent la campagne de renommage : nommer en anglais sauf vocabulaire métier.
- **Vouvoiement** sur toute copie publique (`frontend/AGENTS.md`, #478). Le mot que l'utilisateur lit est **« épreuve »**, jamais « course ».
- **Le nom complet vient toujours de `nomComplet(athlete)`**, jamais d'un recollage local : `prenom` et `nom` restent séparés dans le stock (#264).
- **Commits** : Conventional Commits, un par tâche, terminés par
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

## Structure des fichiers

| Fichier | Responsabilité | Nature |
| --- | --- | --- |
| `components/layout/AthletePicker.tsx` | stock de l'athlète retenu + ses hooks de lecture | modifié (Tâche 1) |
| `components/layout/AthletePicker.test.tsx` | tests du stock et des hooks | modifié (Tâche 1) |
| `components/results/ResultsFilters.tsx` | filtres de `/resultats`, dont la pastille | modifié (Tâche 2) |
| `components/results/ResultsFilters.test.tsx` | tests des filtres | modifié (Tâche 2) |
| `components/results/RaceFinishers.tsx` | classement d'une épreuve : ligne mise en avant, « aller à ma ligne », état vide | modifié (Tâches 3 et 4) |
| `components/results/RaceFinishers.test.tsx` | tests du classement | modifié (Tâches 3 et 4) |
| `components/layout/AppNav.tsx` | tuile de l'athlète retenu dans le rail | modifié (Tâche 5) |
| `components/layout/AppNav.test.tsx` | tests du rail | modifié (Tâche 5) |
| `frontend/AGENTS.md` | contexte durable du front | modifié (Tâche 6) |

Aucun fichier créé : les quatre surfaces existent, et chacune porte déjà son fichier de test. Le hook partagé vit auprès du stock qu'il lit, pas dans un `hooks/` séparé — c'est l'emplacement qu'a choisi `useIsSelectedAthlete`, son jumeau.

---

### Task 1: le hook `useSelectedAthlete()`

**Files:**
- Modify: `frontend/components/layout/AthletePicker.tsx:94-100` (juste après `useIsSelectedAthlete`)
- Test: `frontend/components/layout/AthletePicker.test.tsx`

**Interfaces:**
- Consommé : `STORE`, `readAthlete()`, `subscribeAthlete()`, `PickedAthlete` — tous déjà dans le fichier.
- Produit : `export function useSelectedAthlete(): PickedAthlete | null` — utilisé par les tâches 2, 3, 4 et 5.

**Pourquoi un cache** : `useSyncExternalStore` appelle `getSnapshot` à chaque rendu et compare le résultat au précédent avec `Object.is`. `readAthlete()` reconstruit un objet neuf à chaque appel, donc jamais `Object.is`-égal au précédent : React rendrait en boucle et lèverait « The result of getSnapshot should be cached to avoid an infinite loop ». C'est exactement pour l'éviter que `useIsSelectedAthlete` rend un booléen — le commentaire du fichier le dit déjà.

- [ ] **Step 1: Write the failing tests**

Ajouter à la fin de `frontend/components/layout/AthletePicker.test.tsx` (le `beforeEach` du fichier fournit déjà un `localStorage` déterministe) :

```tsx
function SondeAthlete() {
  const athlete = useSelectedAthlete();
  return <div data-testid="sonde">{athlete ? nomComplet(athlete) : "aucun"}</div>;
}

describe("useSelectedAthlete", () => {
  it("rend null quand aucun athlète n'est retenu", () => {
    render(<SondeAthlete />);
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");
  });

  it("rend l'athlète retenu sans boucler — le snapshot est mémorisé", () => {
    // Sans cache, `getSnapshot` rendrait un objet neuf à chaque rendu et React
    // lèverait « The result of getSnapshot should be cached to avoid an
    // infinite loop » : ce rendu, en StrictMode (deux passes), est la seule
    // façon d'établir la stabilité de la référence depuis l'extérieur.
    writeAthlete(ATHLETE);
    render(
      <StrictMode>
        <SondeAthlete />
      </StrictMode>,
    );
    expect(screen.getByTestId("sonde")).toHaveTextContent("Marie Gaudin");
  });

  it("se resynchronise quand le stock change, sans remontage", () => {
    render(<SondeAthlete />);
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");

    act(() => writeAthlete(ATHLETE));
    expect(screen.getByTestId("sonde")).toHaveTextContent("Marie Gaudin");

    act(() => clearAthlete());
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");
  });
});
```

Compléter les imports en tête du fichier :

```tsx
import { StrictMode } from "react";
import {
  readAthlete,
  writeAthlete,
  clearAthlete,
  nomComplet,
  useSelectedAthlete,
  AthletePicker,
} from "./AthletePicker";
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- components/layout/AthletePicker.test.tsx`
Expected: FAIL — `useSelectedAthlete is not a function` (l'export n'existe pas encore).

- [ ] **Step 3: Write the implementation**

Dans `frontend/components/layout/AthletePicker.tsx`, insérer **après** `useIsSelectedAthlete` (l. 100) :

```tsx
/**
 * Dernier instantané du stock, mémorisé au niveau du module.
 *
 * `useSyncExternalStore` compare le retour de `getSnapshot` au précédent avec
 * `Object.is` : rendre le résultat de `readAthlete()`, qui reconstruit un
 * objet à chaque lecture, ferait rendre React en boucle. On ne ré-analyse donc
 * que si la chaîne brute a changé — la clé de cache est le texte du stock,
 * seule chose qui change vraiment.
 */
let brutMemorise: string | null = null;
let athleteMemorise: PickedAthlete | null = null;

function snapshotAthlete(): PickedAthlete | null {
  let brut: string | null;
  try {
    brut = window.localStorage.getItem(STORE);
  } catch {
    // Mode privé, quota : pas de stock lisible, donc pas d'athlète retenu.
    return null;
  }
  if (brut !== brutMemorise) {
    brutMemorise = brut;
    athleteMemorise = readAthlete();
  }
  return athleteMemorise;
}

/**
 * L'athlète retenu lui-même, côté client uniquement — le pendant de
 * `useIsSelectedAthlete` pour les écrans qui ont besoin de son **nom** et non
 * d'un booléen : la pastille de `/resultats`, le raccourci du rail et le saut
 * vers sa ligne dans un classement (#503). Même arbitrage qu'en #467 : le
 * stock se lit là où il vit, jamais par un cookie miroir.
 */
export function useSelectedAthlete(): PickedAthlete | null {
  return useSyncExternalStore(subscribeAthlete, snapshotAthlete, () => null);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/layout/AthletePicker.test.tsx`
Expected: PASS, tous les tests du fichier compris.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/AthletePicker.tsx frontend/components/layout/AthletePicker.test.tsx
git commit -m "$(cat <<'EOF'
feat(503): un hook qui rend l'athlète retenu, pas seulement un booléen

useIsSelectedAthlete ne répond qu'à « est-ce lui ? ». Les trois gestes de
NAV-10 ont besoin de son nom. Le snapshot est mémorisé sur la chaîne brute du
stock, sans quoi useSyncExternalStore rend en boucle.

Refs #503

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: la pastille « Mes résultats » sur `/resultats`

**Files:**
- Modify: `frontend/components/results/ResultsFilters.tsx` (fonction `apply`, l. 62-79 ; bouton « Filtrer », l. ~205 ; champ « Athlète », l. ~172-181)
- Test: `frontend/components/results/ResultsFilters.test.tsx`

**Interfaces:**
- Consomme : `useSelectedAthlete()`, `nomComplet()` (Tâche 1).
- Produit : rien pour les tâches suivantes.

**Piège à traiter en premier** : `apply` va prendre un paramètre optionnel, or le bouton « Filtrer » est câblé `onClick={apply}` — React lui passerait alors l'événement souris comme nom d'athlète. Ce site d'appel **doit** devenir `onClick={() => apply()}` dans la même tâche.

- [ ] **Step 1: Write the failing tests**

Ajouter à `frontend/components/results/ResultsFilters.test.tsx`. Le fichier mocke déjà `next/navigation` (`push`, `replace`, `searchParams` mutable) ; il faut y ajouter un stock `localStorage` déterministe, comme dans `AthletePicker.test.tsx` :

```tsx
import { nomComplet, writeAthlete } from "@/components/layout/AthletePicker";

const JEAN = { id: 12, prenom: "Jean", nom: "Dupont" };

describe("ResultsFilters — pastille de l'athlète retenu (NAV-10, #503)", () => {
  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
    searchParams = new URLSearchParams();
    const stock = new Map<string, string>();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: (cle: string) => stock.get(cle) ?? null,
        setItem: (cle: string, valeur: string) => void stock.set(cle, valeur),
        removeItem: (cle: string) => void stock.delete(cle),
        clear: () => stock.clear(),
      },
    });
  });

  it("ne propose rien quand aucun athlète n'est retenu", () => {
    render(<ResultsFilters />);
    expect(screen.queryByRole("button", { name: /Mes résultats/ })).not.toBeInTheDocument();
  });

  it("propose le filtre sans jamais l'appliquer au chargement", () => {
    writeAthlete(JEAN);
    render(<ResultsFilters />);

    expect(screen.getByRole("button", { name: "Mes résultats — Jean Dupont" })).toBeInTheDocument();
    // Le cœur de NAV-10 : proposé, jamais posé en silence.
    expect(push).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  it("pose ?name=<nom complet> au clic, les autres filtres conservés", async () => {
    writeAthlete(JEAN);
    searchParams = new URLSearchParams("event_type=triathlon-m&scope=club");
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Mes résultats — Jean Dupont" }));

    expect(push).toHaveBeenCalledWith(expect.stringContaining("name=Jean+Dupont"));
    expect(push).toHaveBeenCalledWith(expect.stringContaining("event_type=triathlon-m"));
    expect(push).toHaveBeenCalledWith(expect.stringContaining("scope=club"));
  });

  it("disparaît une fois le filtre posé — le chip actif porte déjà la révocation", () => {
    writeAthlete(JEAN);
    searchParams = new URLSearchParams(`name=${nomComplet(JEAN)}`);
    render(<ResultsFilters />);

    expect(screen.queryByRole("button", { name: /Mes résultats/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retirer Athlète : Jean Dupont" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- components/results/ResultsFilters.test.tsx`
Expected: FAIL — « Unable to find an accessible element with the role "button" and name "Mes résultats — Jean Dupont" ».

- [ ] **Step 3: Write the implementation**

3a. Imports en tête de `ResultsFilters.tsx` :

```tsx
import { Avatar } from "@/components/tcn";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
```

3b. Dans `ResultsFilters()`, après `const [volet, setVolet] = useState(false);` :

```tsx
  // Athlète retenu (#467) : lu côté client, jamais par un cookie miroir. La
  // pastille n'est proposée que tant que le filtre ne vaut pas déjà ce nom —
  // une fois posé, le chip « Athlète : … ✕ » porte seul la révocation, et deux
  // commandes pour le même état se contrediraient (NAV-10, #503).
  const athleteRetenu = useSelectedAthlete();
  const nomRetenu = athleteRetenu ? nomComplet(athleteRetenu) : null;
  const proposePastille = nomRetenu !== null && sp.get("name") !== nomRetenu;
```

3c. Rendre `apply` capable de porter un nom imposé — l'état `name` n'étant pas encore à jour au moment du clic :

```tsx
  function apply(nomImpose?: string) {
    const nomApplique = nomImpose ?? name;
    const activeFilters = Object.fromEntries(
      Object.entries({ name: nomApplique, event_name: eventName, event_type: eventType, date_from: dateFrom, date_to: dateTo })
        .filter(([, v]) => v !== ""),
    );
    captureEvent("results_filter_applied", {
      filter_count: Object.keys(activeFilters).length,
      has_athlete_filter: !!nomApplique,
      has_event_name_filter: !!eventName,
      has_event_type_filter: !!eventType,
      has_date_filter: !!(dateFrom || dateTo),
    });
    push({
      name: nomApplique,
      event_name: eventName,
      event_type: eventType,
      date_from: dateFrom,
      date_to: dateTo,
    });
  }
```

3d. **Corriger le site d'appel qui passerait l'événement souris comme nom** — le bouton « Filtrer » (l. ~205) :

```tsx
            <Button className="hidden sm:inline-flex" onClick={() => apply()}>
              Filtrer
            </Button>
```

(Les deux `onKeyDown={(e) => e.key === "Enter" && apply()}` et les `onClick={() => { apply(); setVolet(false); }}` du volet appellent déjà `apply()` sans argument : ne pas y toucher.)

3e. La pastille, **dans** le `Field` du champ « Athlète », juste après l'`Input` :

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
            {proposePastille && (
              <button
                type="button"
                onClick={() => {
                  setName(nomRetenu);
                  apply(nomRetenu);
                }}
                aria-label={`Mes résultats — ${nomRetenu}`}
                className="flex min-h-6 items-center gap-1.5 self-start text-xs font-bold text-[var(--tcn-orange-deep)]"
              >
                <Avatar name={nomRetenu} size={18} />
                Mes résultats
              </button>
            )}
          </Field>
```

`--tcn-orange-deep`, pas `--tcn-orange` : à 12 px ce n'est pas du « texte large », donc le seuil est 4,5:1 — même cause commune que le club TCN du classement (#465). `min-h-6` (24 px) est le plancher tactile WCAG 2.2 2.5.8.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/results/ResultsFilters.test.tsx`
Expected: PASS, y compris les tests de recherche live déjà en place (ils passent par `apply()` sans argument).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/ResultsFilters.tsx frontend/components/results/ResultsFilters.test.tsx
git commit -m "$(cat <<'EOF'
feat(503): une pastille qui propose mes résultats, sans les imposer

/resultats expose un filtre par nom que rien ne pré-remplissait. La pastille
le pose d'un clic et s'efface aussitôt : le chip actif porte la révocation.
Rien n'est appliqué au chargement.

Refs #503

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: la ligne de l'athlète retenu, reconnaissable dans le classement

**Files:**
- Modify: `frontend/components/results/RaceFinishers.tsx` (corps de `RaceFinishers`, l. ~106-140 ; boucle des lignes, l. ~285-325)
- Test: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consomme : `useSelectedAthlete()`, `nomComplet()` (Tâche 1).
- Produit : la liaison locale `athleteRetenu` du composant, réutilisée par la Tâche 4.

**Deux contraintes de conception à ne pas contourner :**
1. **Un seul appel de hook**, en tête du composant. `useIsSelectedAthlete(p.athlete.id)` ne peut pas être appelé dans le `.map` des lignes — les hooks ne s'appellent pas dans une boucle. On compare donc `athleteRetenu?.id === p.athlete.id`.
2. **Le liseré orange gauche est déjà pris** par `is_tcn` : lui faire porter un second sens rendrait les deux illisibles. D'où un fond et un chip textuel. Le chip n'est pas décoratif — la couleur seule échouerait WCAG 1.4.1.

- [ ] **Step 1: Write the failing tests**

Ajouter à `frontend/components/results/RaceFinishers.test.tsx` :

```tsx
import { writeAthlete } from "@/components/layout/AthletePicker";

describe("RaceFinishers — ma ligne dans le classement (NAV-10, #503)", () => {
  beforeEach(() => {
    const stock = new Map<string, string>();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: (cle: string) => stock.get(cle) ?? null,
        setItem: (cle: string, valeur: string) => void stock.set(cle, valeur),
        removeItem: (cle: string) => void stock.delete(cle),
        clear: () => stock.clear(),
      },
    });
  });

  it("ne marque aucune ligne quand aucun athlète n'est retenu", () => {
    afficher();
    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
  });

  it("marque la seule ligne de l'athlète retenu, d'un chip et non de la couleur seule", () => {
    // `p({ id, nom })` donne `athlete.id === id` : l'athlète retenu est donc
    // celui de la ligne 3 (DNFGUY) — un abandon reste ma ligne.
    writeAthlete({ id: 3, prenom: "T", nom: "DNFGUY" });
    afficher();

    const marques = screen.getAllByText("Vous");
    expect(marques).toHaveLength(1);
    // WCAG 1.4.1 : le chip est le signifiant, le fond ne fait que l'appuyer.
    expect(marques[0].closest("[role='button']")).toHaveTextContent("DNFGUY");
  });

  it("peint le fond de ma ligne, y compris sur un non-finisher", () => {
    writeAthlete({ id: 3, prenom: "T", nom: "DNFGUY" });
    afficher();

    const ligne = screen.getByText("Vous").closest("[role='button']") as HTMLElement;
    expect(ligne.style.background).toBe("var(--tcn-orange-08)");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: FAIL — « Unable to find an element with the text: Vous ».

- [ ] **Step 3: Write the implementation**

3a. Import en tête de `RaceFinishers.tsx` :

```tsx
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
```

3b. Dans le corps de `RaceFinishers`, après `const [tri, setTri] = useState(...)` :

```tsx
  // Athlète retenu (#467) : lu côté client, sur les seules lignes de la
  // tranche affichée — c'est tout ce que le client tient. Un seul appel, en
  // tête : un hook ne s'appelle pas dans la boucle des lignes.
  const athleteRetenu = useSelectedAthlete();
```

3c. Dans la boucle `lignes.map((p) => { … })`, après `const own = p.is_tcn;` :

```tsx
            const moi = athleteRetenu?.id === p.athlete.id;
```

3d. Le fond de la ligne — remplacer la propriété `background` du `style` de la ligne :

```tsx
                  // Ma ligne prime sur le gris des non-finishers : un athlète
                  // qui a abandonné reste l'athlète retenu, et « c'est vous »
                  // est l'information qu'il cherche.
                  background: moi
                    ? "var(--tcn-orange-08)"
                    : nf
                      ? "color-mix(in srgb, var(--tcn-grey-400) 15%, transparent)"
                      : undefined,
```

3e. La cellule du nom devient une rangée flex, pour que le chip ne soit pas rogné par l'ellipse du nom — remplacer la cellule actuelle :

```tsx
                <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "var(--tcn-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{name}</span>
                  {/* Le chip, pas le fond, est le signifiant : la couleur seule
                      échouerait WCAG 1.4.1. `flex: none` pour qu'il survive à
                      un nom long, dont c'est l'ellipse qui cède. */}
                  {moi && (
                    <span
                      style={{
                        flex: "none",
                        padding: "1px 7px",
                        borderRadius: "var(--tcn-radius-sm)",
                        background: "var(--tcn-orange-deep)",
                        color: "#fff",
                        fontFamily: "var(--tcn-font-cond)",
                        fontWeight: 700,
                        fontSize: 11,
                        letterSpacing: ".04em",
                      }}
                    >
                      Vous
                    </span>
                  )}
                </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS, les tests existants du fichier compris (le test du club TCN cible `screen.getByText("TRIATHLON CLUB NANTAIS")`, pas la cellule du nom).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "$(cat <<'EOF'
feat(503): ma ligne se reconnaît dans le classement

Le liseré gauche dit déjà « club TCN » : un second sens l'aurait rendu
illisible. Ma ligne prend un fond et un chip « Vous » — le chip parce que la
couleur seule échoue WCAG 1.4.1 —, et il prime sur le gris des abandons.

Refs #503

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: « Aller à ma ligne » et son impasse

**Files:**
- Modify: `frontend/components/results/RaceFinishers.tsx` (en-tête de la carte, l. ~217-253 ; états vides, l. ~326-373)
- Test: `frontend/components/results/RaceFinishers.test.tsx`

**Interfaces:**
- Consomme : `athleteRetenu` et `nomComplet()` (Tâche 3), `naviguer()` (déjà dans le fichier).
- Produit : rien pour les tâches suivantes.

**Pourquoi une recherche et pas un saut de page** : l'ordre d'affichage est une propriété de la requête SQL (`_ordre_affichage` — finishers par rang, puis DNF/DSQ/DNS par temps). `orderParticipations` a été **supprimée** côté front en #163 parce qu'elle ne sait pas le reproduire. Calculer « ma page » demanderait soit une route neuve, soit de télécharger tout le classement (1,15 Mo mesuré) pour ne faire que compter. `q` atteint la ligne quelle que soit sa page, à coût nul, et le bandeau « X résultats sur N pour « Nom » · Effacer » de #485 le nomme et l'annule.

Le bouton est rendu **dès qu'un athlète est retenu**, sans condition sur sa présence dans l'épreuve : le front ne peut pas la connaître avant de chercher. C'est l'état vide qui absorbe l'impasse.

- [ ] **Step 1: Write the failing tests**

Ajouter au `describe` créé en Tâche 3 (son `beforeEach` fournit déjà le stock) :

```tsx
  it("n'offre pas le saut quand aucun athlète n'est retenu", () => {
    afficher();
    expect(screen.queryByRole("button", { name: /Aller à ma ligne/ })).not.toBeInTheDocument();
  });

  it("cherche mon nom complet dans le classement, page courante indifférente", async () => {
    writeAthlete({ id: 3, prenom: "Thomas", nom: "DNFGUY" });
    searchParams = new URLSearchParams("page=4");
    afficher({ page: 4 });

    await userEvent.click(screen.getByRole("button", { name: "Aller à ma ligne — Thomas DNFGUY" }));

    // La recherche remet à la page 1 : `naviguer` retire `page`.
    expect(push).toHaveBeenCalledWith("/courses/1?q=Thomas+DNFGUY");
  });

  it("nomme l'athlète quand il ne figure pas sur l'épreuve, plutôt qu'un échec de recherche", async () => {
    writeAthlete({ id: 99, prenom: "Marie", nom: "GAUDIN" });
    searchParams = new URLSearchParams("q=Marie GAUDIN");
    afficher({ participations: [], total: 0 });

    expect(screen.getByText("Marie GAUDIN ne figure pas sur cette épreuve")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Voir tous les participants" }));
    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("garde l'état vide générique pour une recherche qui n'est pas la mienne", () => {
    writeAthlete({ id: 99, prenom: "Marie", nom: "GAUDIN" });
    searchParams = new URLSearchParams("q=zzz");
    afficher({ participations: [], total: 0 });

    expect(screen.getByText("Aucun athlète ne correspond à cette recherche")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: FAIL — bouton « Aller à ma ligne — Thomas DNFGUY » introuvable.

- [ ] **Step 3: Write the implementation**

3a. Le bouton, dans l'en-tête de la carte, **après** le `</form>` de recherche et avant le `<SegmentedControl>` :

```tsx
          {athleteRetenu && (
            <button
              type="button"
              onClick={() => naviguer({ q: nomComplet(athleteRetenu) })}
              aria-label={`Aller à ma ligne — ${nomComplet(athleteRetenu)}`}
              style={{ height: 34, padding: "0 12px", fontSize: 13, fontWeight: 700, borderRadius: 8, border: "1.5px solid var(--tcn-orange-deep)", background: "var(--tcn-surface)", color: "var(--tcn-orange-deep)", cursor: "pointer" }}
            >
              Aller à ma ligne
            </button>
          )}
```

3b. L'état vide de l'impasse, **avant** la branche `rechercheUrl` générique de la cascade — l'ordre compte, la branche générique attraperait tout :

```tsx
            ) : rechercheUrl && athleteRetenu && rechercheUrl === nomComplet(athleteRetenu) ? (
              // « Aller à ma ligne » ne peut pas savoir d'avance si l'athlète
              // retenu a couru : ici, il n'a pas couru. Le dire, plutôt que
              // d'annoncer un échec de recherche que personne n'a lancée.
              <EmptyState
                bare
                title={`${nomComplet(athleteRetenu)} ne figure pas sur cette épreuve`}
                action={
                  <button
                    type="button"
                    onClick={() => naviguer({ q: null })}
                    style={STYLE_BOUTON_ABSENCE}
                  >
                    Voir tous les participants
                  </button>
                }
              />
            ) : rechercheUrl ? (
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/results/RaceFinishers.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/results/RaceFinishers.tsx frontend/components/results/RaceFinishers.test.tsx
git commit -m "$(cat <<'EOF'
feat(503): aller à ma ligne, quelle que soit sa page

L'ordre d'affichage est une propriété de la requête SQL depuis #163 : le front
ne sait pas calculer « ma page ». La recherche existante y mène à coût nul, et
le bandeau de #485 la nomme et l'annule. Absent de l'épreuve, l'état vide le
dit au lieu d'annoncer un échec de recherche.

Refs #503

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: le raccourci de la tuile du rail

**Files:**
- Modify: `frontend/components/layout/AppNav.tsx:528-613` (la tuile de l'athlète retenu dans `NavContent`)
- Test: `frontend/components/layout/AppNav.test.tsx`

**Interfaces:**
- Consomme : `athlete` (prop déjà reçue par `NavContent`), `nomComplet()`.
- Produit : rien.

La tuile passe en colonne. La rangée actuelle — avatar, prénom, croix — ne change pas ; un lien texte s'ajoute en dessous, **rail déplié et tiroir mobile seulement**, comme la croix : replié, la tuile fait 44 px et l'avatar l'occupe entière.

- [ ] **Step 1: Write the failing tests**

Ajouter à `frontend/components/layout/AppNav.test.tsx` :

```tsx
describe("AppNav — raccourci « Mes résultats » de la tuile (NAV-10, #503)", () => {
  const JEAN = { id: 12, prenom: "Jean", nom: "Dupont" };

  it("pointe vers /resultats avec le nom complet pré-rempli", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null, { initialExpanded: true });

    const lien = await screen.findByRole("link", { name: "Mes résultats — Jean Dupont" });
    expect(lien).toHaveAttribute("href", "/resultats?name=Jean%20Dupont");
  });

  it("ne prefetche pas la destination, comme le lien de profil voisin (#425)", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null, { initialExpanded: true });

    const lien = await screen.findByRole("link", { name: "Mes résultats — Jean Dupont" });
    expect(lien).toHaveAttribute("data-prefetch", "false");
  });

  it("n'existe pas sans athlète retenu", async () => {
    afficher(null, { initialExpanded: true });
    await screen.findByRole("link", { name: "Ajouter une épreuve" });
    expect(screen.queryByRole("link", { name: /Mes résultats/ })).not.toBeInTheDocument();
  });

  it("n'existe pas sur le rail replié, où la tuile se réduit à l'avatar", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null, { initialExpanded: false });

    expect(await screen.findByRole("link", { name: "Mon profil — Jean Dupont" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Mes résultats/ })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- components/layout/AppNav.test.tsx`
Expected: FAIL — lien « Mes résultats — Jean Dupont » introuvable.

- [ ] **Step 3: Write the implementation**

Dans `NavContent`, remplacer le conteneur `{athlete && (<div style={{ display: "flex", alignItems: "center", … }}>` par un conteneur en colonne qui garde la rangée existante intacte :

```tsx
        {athlete && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              padding: expanded ? "0 8px 6px" : 0,
              borderRadius: "var(--tcn-radius-lg)",
              background: "var(--tcn-orange-08)",
              border: "1.5px solid var(--tcn-orange-12)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10, height: 44, justifyContent: justify }}>
              {/* … la rangée existante, inchangée : Tooltip/avatar, prénom, croix … */}
            </div>
            {/* Le raccourci vers les résultats pré-filtrés (#503) : offert au
                seul rail déplié, comme la croix — replié, la tuile fait 44 px.
                `prefetch={false}` pour la même raison que le lien de profil
                voisin (#425) : un athlète épinglé n'est pas une destination
                probable. Le nom complet dans le nom accessible, jamais le
                prénom seul : un libellé de lien se lit hors contexte. */}
            {expanded && (
              <Link
                href={`/resultats?name=${encodeURIComponent(nomComplet(athlete))}`}
                prefetch={false}
                onClick={onNavigate}
                aria-label={`Mes résultats — ${nomComplet(athlete)}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  // 36 px : au-dessus du plancher tactile WCAG 2.2 2.5.8
                  // (24 px) sans doubler la hauteur de la tuile comme le
                  // ferait la grille à 44 px du rail.
                  minHeight: 36,
                  padding: "0 4px",
                  fontWeight: 700,
                  fontSize: 13,
                  color: "var(--tcn-orange-deep)",
                  textDecoration: "none",
                }}
              >
                Mes résultats
              </Link>
            )}
          </div>
        )}
```

Points de vigilance : la rangée intérieure reprend `gap: 10`, `height: 44` et `justifyContent: justify` de l'ancien conteneur ; le `padding`, le fond, la bordure et le rayon montent sur le conteneur extérieur. Le `justify` replié (`center`) doit rester sur la rangée, pas sur la colonne.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/layout/AppNav.test.tsx`
Expected: PASS, les tests de la croix de désélection et du prefetch de « Mon profil » compris.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/AppNav.tsx frontend/components/layout/AppNav.test.tsx
git commit -m "$(cat <<'EOF'
feat(503): la tuile du rail mène aussi à mes résultats

Une seconde ligne sous la rangée existante, rail déplié seulement — replié, la
tuile fait 44 px et l'avatar l'occupe entière. Le nom complet dans le nom
accessible : un libellé de lien se lit hors contexte.

Refs #503

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: vérification d'ensemble et contexte durable

**Files:**
- Modify: `frontend/AGENTS.md` (section de l'athlète retenu, après le bloc « L'athlète retenu ne franchit pas la frontière serveur », l. ~276)

**Interfaces:** aucune.

- [ ] **Step 1: Lancer la suite front entière**

Run: `npm test`
Expected: PASS. Une régression ici signale un test existant qui s'appuyait sur la cellule du nom du classement ou sur la forme de la tuile du rail — la corriger, ne pas la contourner.

- [ ] **Step 2: Lint et build**

Run: `npm run lint && npm run build`
Expected: aucun avertissement ESLint, build prod OK (TS strict + RSC).

Le build est la vraie garde ici : `useSelectedAthlete` ne doit jamais être appelé depuis un composant serveur. S'il l'était, le build le dirait.

- [ ] **Step 3: Consigner le contexte durable**

Ajouter à `frontend/AGENTS.md`, juste après le bloc de #467 :

```markdown
- **Les trois surfaces qui propagent l'athlète retenu** (#503) — la pastille
  « Mes résultats » de `/resultats`, la ligne marquée « Vous » et le bouton
  « Aller à ma ligne » du classement d'épreuve, le raccourci de la tuile du
  rail. Toutes lisent `useSelectedAthlete()`
  (`components/layout/AthletePicker.tsx`, à côté de `useIsSelectedAthlete`),
  dont le snapshot est **mémorisé sur la chaîne brute du stock** :
  `readAthlete()` reconstruit un objet à chaque lecture, et le rendre tel quel
  fait rendre `useSyncExternalStore` en boucle. Trois invariants :
  **aucun filtre n'est appliqué au chargement** — chaque geste demande un clic
  et se révoque par une commande déjà à l'écran (le chip `Athlète : … ✕`, le
  bandeau « … · Effacer » de #485) ; **le liseré orange gauche du classement
  reste réservé à `is_tcn`**, d'où le fond `--tcn-orange-08` et le chip
  « Vous », qui porte le sens que la couleur seule ne peut pas porter
  (WCAG 1.4.1) ; et **« Aller à ma ligne » cherche, il ne saute pas** —
  l'ordre d'affichage est une propriété de la requête SQL depuis #163, le
  front ne sait pas calculer « ma page », et `q` y mène à coût backend nul.
```

- [ ] **Step 4: Commit**

```bash
git add frontend/AGENTS.md
git commit -m "$(cat <<'EOF'
docs(503): les trois invariants de la propagation de l'athlète retenu

Refs #503

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Fin de branche

Hors des tâches, dans l'ordre imposé par `AGENTS.md` :

1. `superpowers:requesting-code-review`
2. le sous-agent `ui-ux-review` — la branche touche `frontend/`. Il jugera notamment la hauteur de 36 px du raccourci du rail et le contraste du chip « Vous ».
3. `superpowers:verification-before-completion`
4. `superpowers:finishing-a-development-branch` — la PR porte `Closes #503` (mot-clé anglais, jeton machine), le reste de la description en français.

## Auto-revue du plan

- **Couverture de la spec** : socle → T1 ; volet 1 → T2 ; volet 2, mise en avant → T3, saut et impasse → T4 ; volet 3 → T5 ; tests des quatre fichiers → répartis dans T1-T5, suite entière en T6.
- **Cohérence des noms** : `useSelectedAthlete` (T1) est le seul nom d'export ajouté ; `nomComplet` et `PickedAthlete` sont préexistants ; `athleteRetenu` désigne la même liaison en T3 et T4 ; `moi` et `nomRetenu` sont locaux à un fichier.
- **Piège consigné** : `onClick={apply}` → `onClick={() => apply()}` en T2, sans quoi l'événement souris devient un nom d'athlète.
- **Hors périmètre** : `/dashboard` (#502) et les listes du club (#504), chacun sur sa branche.
