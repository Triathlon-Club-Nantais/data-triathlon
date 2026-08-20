# Accélérer et stabiliser les suites de tests (#508) — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ramener la passe de tests locale de ~2 min 53 à ~1 min 58 en parallélisant pytest et en sortant de jsdom les 31 fichiers de test front qui n'ont pas besoin de DOM, sans réécrire une seule assertion.

**Architecture :** quatre changements de configuration et un déplacement de fixture. `backend/pyproject.toml` gagne un défaut parallèle ; `frontend/vitest.config.ts` passe de un environnement global à deux projets vitest dont la partition est *structurelle* ; un test garde-fou interdit qu'un fichier de test échappe aux deux projets ; `backend/tests/test_migrations.py` mutualise 13 montées Alembic identiques en une seule.

**Tech Stack :** pytest 8 + pytest-xdist, uv (PEP 735 `[dependency-groups]`), Alembic, SQLite ; Vitest 4.1.10 (`test.projects`), tinyglobby, TypeScript strict.

**Spec :** `docs/superpowers/specs/2026-08-20-suites-de-tests-design.md`, lui-même adossé au sondage `docs/superpowers/specs/2026-08-20-suites-de-tests-sondage.md`, qui **prime sur ce plan**. Toute divergence de chiffre se tranche en re-sondant, jamais en ajustant le plan.

## Global Constraints

- **Le sondage prime.** Aucun chiffre de ce plan ne se recopie dans un commit sans avoir été remesuré ; les mesures d'après-coup suivent le protocole du sondage (seuil de charge < 2,0 sur 12 cœurs, 2 répétitions, **minimum** retenu, charge consignée).
- **`uv sync --locked` en CI** (`.github/workflows/ci.yml:32`) : ajouter une dépendance backend **oblige** à régénérer `backend/uv.lock` dans le même commit, sinon la CI échoue avant d'exécuter un seul test.
- **`npm ci` en CI** (`.github/workflows/ci.yml:68`) : ajouter une dépendance front **oblige** à régénérer `frontend/package-lock.json` dans le même commit.
- **Langue** (Principe I) : identifiants, noms de fichiers et docstrings techniques en anglais ; descriptions `it(...)` / docstrings de règle métier en français. C'est la convention en place — cf. `frontend/scripts/exit-code.test.mjs` et `frontend/test/smoke.test.ts`, qui portent des `it("propage le code d'une sortie normale")`.
- **Aucune assertion existante ne change.** Tout est de la configuration, sauf la tâche 3 qui déplace une fixture sans toucher au corps des tests. Si une assertion doit bouger pour qu'une tâche passe, la tâche est fausse — s'arrêter et le dire.
- **Pas de couche de compatibilité** : les docblocks `@vitest-environment` rendus redondants sont supprimés, pas laissés « au cas où ».
- **Ne pas toucher** `maxWorkers`, `testTimeout`, `--pool=threads`, ni les tests marqués `integration` (cf. « Hors périmètre » du design).

## File Structure

| Fichier | Sort | Responsabilité |
| --- | --- | --- |
| `backend/pyproject.toml` | modifié | `pytest-xdist` dans le groupe `dev` ; `addopts = "-v"` → `addopts = "-n 4"` |
| `backend/uv.lock` | régénéré | verrou de la nouvelle dépendance (`uv sync --locked` en CI) |
| `backend/tests/test_migrations.py` | modifié | fixture `base_migree` de portée module ; 13 tests basculés, 16 inchangés |
| `backend/AGENTS.md` | modifié | note d'usage : le défaut parallèle et l'échappatoire `-n 0` |
| `frontend/vitest.config.ts` | modifié | deux projets `jsdom` / `node`, partition structurelle |
| `frontend/test/environments.test.ts` | **créé** | garde-fou : chaque fichier de test réclamé par exactement un projet |
| `frontend/package.json` + `package-lock.json` | modifiés | `tinyglobby` promu en `devDependency` explicite |
| `frontend/next.config.test.ts` | modifié | docblock `@vitest-environment node` retiré |
| `frontend/app/globals.test.ts` | modifié | docblock retiré |
| `frontend/scripts/backend-url.test.mjs` | modifié | docblock retiré |
| `frontend/scripts/exit-code.test.mjs` | modifié | docblock retiré |
| `frontend/AGENTS.md` | modifié | note : deux projets, et où vit la liste jsdom |
| `AGENTS.md` (racine) | modifié **sur place** | le fichier est à 199 lignes pour un plafond de 200 : **ne pas ajouter de ligne**, seul le commentaire de fin de ligne 104 change |
| `docs/superpowers/specs/2026-08-20-suites-de-tests-sondage.md` | modifié | section « Après » avec les chiffres remesurés |

Ordre des tâches : **levier 5+3 → levier 1 → levier 4 → mesures et docs → commentaire d'issue**. Le levier 5 d'abord parce qu'il est à risque nul et qu'il change la référence de tous les chiffres suivants.

---

### Task 1 : Levier 5 + 3 — défaut parallèle et silencieux côté backend

Les deux leviers tiennent en **une** ligne de **un** fichier : les séparer imposerait deux cycles de mesure pour une seule modification. Le levier 5 (retirer `-v`) vaut 19 s à lui seul, le levier 3 (xdist) 30 s de plus.

**Files:**
- Modify: `backend/pyproject.toml:37-41` (groupe `dev`) et `backend/pyproject.toml:51` (`addopts`)
- Regenerate: `backend/uv.lock`
- Modify: `backend/AGENTS.md` (dernière puce, `tests/`)
- Modify: `AGENTS.md:104` (sur place, sans ajouter de ligne)

**Interfaces:**
- Consumes: rien.
- Produces: le défaut `-n 4` que toutes les tâches suivantes subissent. **Les tâches 2 à 4 exécutent donc pytest en parallèle** ; une exécution ciblée coûte ~1,35 s de démarrage, et `-n 0` la rend.

**Il n'y a pas de test unitaire à écrire ici, et il ne faut pas en inventer un.** Un test qui affirmerait `addopts == "-n 4"` ne vérifierait que lui-même. Ce qui est réellement en jeu, c'est la **sûreté du parallélisme** : un test qui dépend de l'ordre d'exécution ou d'un état partagé entre workers ne passe plus. La vérification est donc l'exécution répétée de la suite, et c'est l'étape 4 qui la porte.

- [ ] **Step 1 : Ajouter pytest-xdist au groupe dev**

Depuis `backend/` :

```bash
uv add --dev "pytest-xdist>=3.8.0"
```

`uv add --dev` écrit dans `[dependency-groups] dev` (PEP 735) **et** régénère `uv.lock` — c'est ce qui satisfait le `uv sync --locked` de la CI. Vérifier ensuite que le groupe `dev` de `backend/pyproject.toml` ressemble à :

```toml
# PEP 735 : installé par `uv sync`, écarté par `uv sync --no-dev` (Render, Docker).
[dependency-groups]
dev = [
    "pytest>=8.3.4",
    "pytest-xdist>=3.8.0",
    "respx>=0.21.1",
    "ruff>=0.16.3",
]
```

Si `uv add` a rangé la ligne ailleurs que dans l'ordre alphabétique, la remettre à sa place à la main : la liste est triée.

- [ ] **Step 2 : Mesurer l'état de départ, sous protocole**

Avant de changer `addopts`. Depuis `backend/` :

```bash
awk '{print $1}' /proc/loadavg   # doit être < 2,0 ; sinon attendre
time uv run pytest -m "not integration"
```

Noter la durée et la charge. C'est la référence `-v` du sondage (96 s au repos). Si le relevé s'en écarte de plus de ~20 %, **la machine n'est pas au repos** : ne pas continuer, attendre, et re-mesurer.

- [ ] **Step 3 : Remplacer `addopts`**

Dans `backend/pyproject.toml`, remplacer la ligne 51 :

```toml
addopts = "-v"
```

par :

```toml
# `-v` coûtait 19 s sur 3656 tests (20 % de la suite), sortie redirigée — et
# davantage dans un terminal qui doit rendre 3656 lignes.
#
# `-n 4` et non `auto` : le plateau xdist est **plat** de 4 à 12 workers (44 à
# 49 s), donc la valeur ne se choisit pas sur la vitesse. 4 workers laissent
# 8 cœurs libres et n'entrent pas dans le régime de saturation qui a produit une
# erreur à n=12 ; et sur le runner CI à 4 vCPU, `-n 4` et `auto` coïncident.
#
# Le prix : ~1,35 s de démarrage sur une **exécution ciblée** (0,40 s → 1,75 s
# pour un seul fichier). `-n 0` le rend, et rétablit au passage `--pdb` et une
# sortie non entrelacée. Mesures : docs/superpowers/specs/2026-08-20-suites-de-tests-sondage.md
addopts = "-n 4"
```

- [ ] **Step 4 : Vérifier — suite verte, deux fois, et l'échappatoire intacte**

```bash
uv run pytest -m "not integration"
```

Attendu : `3656 passed, 74 deselected`, sans `-v` (une ligne de points par worker, pas 3656 lignes).

**La relancer une seconde fois.** Deux exécutions vertes d'affilée, c'est ce qui distingue « la suite supporte le parallélisme » de « la distribution de ce tirage était favorable ». Un échec qui n'apparaît qu'à l'une des deux est un test dépendant de l'ordre : le signaler, ne pas le contourner en baissant le nombre de workers.

Puis l'échappatoire et la boucle ciblée :

```bash
uv run pytest -m "not integration" -n 0        # séquentiel, doit rester vert
uv run pytest tests/test_health.py             # ~1,75 s : la pénalité annoncée
uv run pytest tests/test_health.py -n 0        # ~0,40 s : elle est bien rendue
uv run pytest -m integration --collect-only -q # la collecte réseau reste saine
uv run ruff check .
```

- [ ] **Step 5 : Mesurer l'arrivée, sous protocole**

```bash
awk '{print $1}' /proc/loadavg
time uv run pytest -m "not integration"
```

Attendu : ~47 s (contre ~96 s à l'étape 2). Consigner durée **et** charge — ils partiront dans la tâche 4.

- [ ] **Step 6 : Documenter l'usage là où il se lit**

Dans `backend/AGENTS.md`, compléter la dernière puce (`tests/`) :

```markdown
- `tests/` — `test_repositories/`, `test_services/`, `test_api/`, `test_cli/`… (≈745 tests).
  **La suite tourne en parallèle par défaut** (`addopts = "-n 4"`, #508) : la sortie
  de plusieurs workers s'entrelace et `--pdb` ne s'attache plus. `-n 0` rétablit
  les deux, au prix de ~30 s sur la suite complète — et l'ôte des ~1,35 s que
  xdist coûte à une exécution d'un seul fichier.
```

Dans `AGENTS.md` à la racine, **modifier la ligne 104 sur place** (le fichier est à 199 lignes pour un plafond de 200 : aucune ligne à ajouter) :

```
uv run pytest -m "not integration"                 # tests unitaires (sans réseau) — 4 workers ; -n 0 pour séquentiel
```

- [ ] **Step 7 : Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/AGENTS.md AGENTS.md
git commit -m "perf(508): defaut pytest parallele et silencieux

Retire -v d'addopts (19 s, 20 % de la suite, sortie pourtant redirigee)
et pose -n 4 via pytest-xdist. Un seul defaut pour local et CI : ce qui
casse ici casse la-bas.

-n 4 et non auto : le plateau est plat de 4 a 12 workers, donc la valeur
se choisit sur la robustesse. 4 workers laissent 8 coeurs libres, la ou
n=12 a produit une erreur sous charge ; et sur le runner CI a 4 vCPU les
deux coincident.

Mesure : 96 s -> 47 s au repos. Prix assume : ~1,35 s sur une execution
ciblee, que -n 0 rend.

Refs #508

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2 : Levier 1 — deux projets vitest, node par défaut, et son garde-fou

**Files:**
- Modify: `frontend/package.json` (+ `package-lock.json` régénéré)
- Create: `frontend/test/environments.test.ts`
- Modify: `frontend/vitest.config.ts` (remplacement intégral)
- Modify: `frontend/next.config.test.ts:1`, `frontend/app/globals.test.ts:1`, `frontend/scripts/backend-url.test.mjs:1`, `frontend/scripts/exit-code.test.mjs:1` (retrait du docblock)
- Modify: `frontend/AGENTS.md`

**Interfaces:**
- Consumes: rien de la tâche 1.
- Produces: deux projets nommés `jsdom` et `node`, sélectionnables par `npx vitest run --project node`. `frontend/vitest.config.ts` **n'exporte rien d'autre que son `default`** — un export nommé y déclenche un avertissement rollup `MIXED_EXPORTS` répété à chaque exécution. Le garde-fou lit donc tout depuis l'objet de config.

Ordre imposé par le design : le garde-fou s'écrit et **échoue avant** la configuration.

- [ ] **Step 1 : Promouvoir tinyglobby en dépendance explicite**

Depuis `frontend/` :

```bash
npm install --save-dev tinyglobby@^0.2.17
```

`tinyglobby` est déjà dans l'arbre — c'est le moteur de glob de vitest lui-même. On le déclare parce qu'un test qui en dépend ne doit pas reposer sur l'arbre d'un tiers. Il embarque ses propres types (`dist/index.d.cts`), donc **aucun `@types/*` à ajouter** : vérifié sous `moduleResolution: "bundler"`.

- [ ] **Step 2 : Écrire le garde-fou (il doit échouer)**

Créer `frontend/test/environments.test.ts` :

```ts
import { fileURLToPath } from "node:url";
import { glob } from "tinyglobby";
import { configDefaults } from "vitest/config";
import { describe, expect, it } from "vitest";

import config from "../vitest.config";

const RACINE = fileURLToPath(new URL("..", import.meta.url));

type ProjetLu = { nom: string; include: string[]; exclude: string[] };

/**
 * Reads the two vitest projects from the config actually in force.
 *
 * On lit la config plutôt qu'une constante partagée : c'est ce que vitest
 * exécute qui doit être vérifié, pas une liste que la config pourrait cesser
 * d'utiliser sans que rien ne rougisse.
 */
function projetsDeLaConfig(): ProjetLu[] {
  const projets = config.test?.projects;
  if (!projets) {
    throw new Error("vitest.config.ts ne déclare aucun test.projects");
  }
  return projets.map((projet) => {
    const test = (projet as { test?: Partial<ProjetLu> & { name?: string } }).test;
    if (!test?.name || !test.include || !test.exclude) {
      throw new Error(
        "chaque projet doit déclarer name, include et exclude explicitement" +
          " — le garde-fou ne peut pas vérifier une partition implicite",
      );
    }
    return { nom: test.name, include: test.include, exclude: test.exclude };
  });
}

/** Les fichiers que chaque projet réclame, globés avec ses propres motifs. */
async function revendications(): Promise<Map<string, string[]>> {
  const parFichier = new Map<string, string[]>();
  for (const projet of projetsDeLaConfig()) {
    const fichiers = await glob(projet.include, { cwd: RACINE, ignore: projet.exclude });
    for (const fichier of fichiers) {
      parFichier.set(fichier, [...(parFichier.get(fichier) ?? []), projet.nom]);
    }
  }
  return parFichier;
}

describe("partition des fichiers de test entre les projets vitest", () => {
  it("réclame chaque fichier de test par exactement un projet", async () => {
    const parFichier = await revendications();

    // Référence : le `include` par défaut de **vitest**, importé et non recopié.
    // Une liste d'extensions réécrite à la main (`**/*.test.ts` + `.tsx`)
    // reproduirait l'angle mort qu'on couvre ici — c'est exactement elle qui
    // laisserait les deux scripts/*.test.mjs réclamés par personne.
    const exclusions = config.test?.exclude;
    expect(exclusions, "la config doit porter un exclude commun").toBeDefined();
    const univers = await glob(configDefaults.include, {
      cwd: RACINE,
      ignore: exclusions as string[],
    });

    // Un fichier réclamé par aucun projet ne s'exécute jamais : la suite reste
    // verte en vérifiant un fichier de moins. Le dépôt a déjà payé cette forme
    // de panne (#300), où `npm test` collectait la suite d'un worktree imbriqué.
    const orphelins = univers.filter((fichier) => !parFichier.has(fichier));
    expect(orphelins).toEqual([]);

    // Réclamé deux fois, il s'exécute deux fois, dans deux environnements.
    const partages = [...parFichier].filter(([, projets]) => projets.length > 1);
    expect(partages).toEqual([]);

    // Garde-fou du garde-fou : un univers vide passerait les deux assertions
    // ci-dessus sans rien vérifier.
    expect(univers.length).toBeGreaterThan(100);
  });

  it("range les deux scripts/*.test.mjs sous node", async () => {
    const parFichier = await revendications();

    // Ces deux-là sont le piège nommé du sondage : un `grep` restreint aux
    // .ts/.tsx les manque, et ils portent leur annotation en commentaire de
    // ligne. On les cite donc par leur nom.
    expect(parFichier.get("scripts/backend-url.test.mjs")).toEqual(["node"]);
    expect(parFichier.get("scripts/exit-code.test.mjs")).toEqual(["node"]);
  });
});
```

- [ ] **Step 3 : Le voir échouer, pour la bonne raison**

```bash
npx vitest run test/environments.test.ts
```

Attendu : **FAIL**, avec `vitest.config.ts ne déclare aucun test.projects`. Si le message diffère (par exemple une erreur de résolution de `tinyglobby`), c'est l'étape 1 qui a échoué, pas le garde-fou.

- [ ] **Step 4 : Écrire la config à deux projets**

Remplacer intégralement `frontend/vitest.config.ts` :

```ts
import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Les seuls fichiers de test qui ont besoin d'un DOM : tous les `.test.tsx`,
// plus trois `.test.ts` nommés un par un. Tout le reste tourne sous `node`, 4x
// plus rapide sur cette tranche (8 s → 2 s sur 27 fichiers).
//
// Le défaut est `node` à cause du **mode de défaillance**, pas de la vitesse :
// un test à DOM qui atterrit là échoue tout de suite sur « document is not
// defined ». Avec jsdom par défaut, l'oubli inverse est silencieux — le test
// passe, et coûte une seconde par exécution, pour toujours.
const GLOBS_JSDOM = [
  "**/*.test.tsx",
  "hooks/useRescrapeStream.test.ts",
  "lib/queries/admin.test.ts",
  "lib/queries/auth.test.ts",
];

// Les exclusions par défaut ne couvrent pas les dossiers en « . » : un
// worktree créé sous frontend/.claude/ ajoutait sa propre suite à la
// collecte (52 fichiers de plus, cf. #300). On reprend les défauts, sans
// quoi node_modules rentrerait.
const EXCLUDE = [...configDefaults.exclude, "**/.claude/**"];

// Ne rien exporter d'autre que ce `default` : un export nommé fait émettre à
// rollup un avertissement MIXED_EXPORTS à chaque exécution de la suite.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
  test: {
    globals: true,
    setupFiles: ["./test/setup.ts"],
    exclude: EXCLUDE,
    // `environmentMatchGlobs` a été **supprimé** de vitest 4 (pas déprécié) :
    // `projects` est la seule route. `extends: true` fait hériter chaque projet
    // des `plugins`, du `resolve.alias` et des options `test` ci-dessus.
    projects: [
      {
        extends: true,
        test: {
          name: "jsdom",
          environment: "jsdom",
          include: GLOBS_JSDOM,
          exclude: EXCLUDE,
        },
      },
      {
        extends: true,
        test: {
          name: "node",
          environment: "node",
          // `node` prend le `include` par défaut de vitest **moins** les globs
          // jsdom. La partition est ainsi *structurelle* : tout fichier que
          // vitest collecte tombe dans exactement un projet. Deux listes
          // disjointes tenues à la main donneraient le même résultat aujourd'hui
          // et divergeraient au premier ajout — `test/environments.test.ts` est
          // là pour que cette divergence rougisse.
          include: configDefaults.include,
          exclude: [...EXCLUDE, ...GLOBS_JSDOM],
        },
      },
    ],
  },
});
```

`test/setup.ts` reste **inchangé** : ses gardes `typeof document !== "undefined"` et `typeof Element !== "undefined"` ont été posées pour les tests d'outillage en environnement node, et servent ici sans modification.

- [ ] **Step 5 : Le voir passer**

```bash
npx vitest run test/environments.test.ts
```

Attendu : **2 passed**. Puis vérifier la partition réelle, qui doit reproduire le sondage :

```bash
npx vitest list --filesOnly --json > /tmp/508-partition.json
node -e "const j=require('/tmp/508-partition.json');
const p={}; for(const e of j) p[e.projectName]=(p[e.projectName]??0)+1;
console.log('entrées:', j.length, p, 'distincts:', new Set(j.map(e=>e.file)).size);"
```

Attendu, mot pour mot : `entrées: 118 { jsdom: 87, node: 31 } distincts: 118`.

- [ ] **Step 6 : Prouver que le garde-fou a des dents**

Un garde-fou jamais vu rougir ne garde rien. Reproduire à la main l'erreur qu'il existe pour attraper — remplacer, dans le projet `node`, `include: configDefaults.include` par la formulation naturelle :

```ts
          include: ["**/*.test.ts"],
```

puis :

```bash
npx vitest run test/environments.test.ts
```

Attendu : **FAIL**, `orphelins` valant `["scripts/backend-url.test.mjs", "scripts/exit-code.test.mjs"]`, et le second test rouge aussi. **Rétablir `configDefaults.include`** et re-vérifier le vert avant de continuer.

- [ ] **Step 7 : Retirer les quatre docblocks devenus redondants**

Les quatre fichiers concernés sont tous dans le projet `node` par leur glob. Leur docblock n'est pas de l'information morte, c'est un **override actif** qui prime sur la config du projet : laissé en place, il ferait taire un futur déplacement de fichier vers `jsdom`, et la panne serait incompréhensible.

Supprimer la première ligne — `// @vitest-environment node` — de chacun de :

- `frontend/next.config.test.ts`
- `frontend/app/globals.test.ts`
- `frontend/scripts/backend-url.test.mjs`
- `frontend/scripts/exit-code.test.mjs`

*(Le design ne nommait que les deux premiers : les deux `.mjs` n'avaient été découverts qu'ensuite, et le même raisonnement s'y applique mot pour mot.)*

- [ ] **Step 8 : Vérifier la suite entière**

```bash
npx vitest run
npm run lint
npm run build
```

Attendu : **939 tests, 118 fichiers, tous verts** — le même compte qu'avant le changement. Un compte inférieur signifie qu'un fichier a cessé d'être collecté : c'est la panne que tout ce dispositif existe pour empêcher, et elle s'arrête ici.

- [ ] **Step 9 : Documenter où vit la liste**

Dans `frontend/AGENTS.md`, ajouter une puce à la section « Architecture frontend », après celle de `next.config.ts` :

```markdown
- **Deux projets vitest, `node` par défaut** (#508) — `vitest.config.ts` ne pose
  plus un environnement global : `jsdom` prend les `.test.tsx` et trois
  `.test.ts` nommés dans `GLOBS_JSDOM`, `node` prend tout le reste (le `include`
  par défaut de vitest **moins** ces globs, pour que la partition soit
  structurelle plutôt que tenue à la main). Un test à DOM oublié dans `node`
  échoue franchement sur « document is not defined » ; c'est le sens de
  l'orientation, l'oubli inverse étant silencieux. `test/environments.test.ts`
  vérifie que chaque fichier est réclamé par **exactement un** projet — ni zéro
  (jamais exécuté, cf. #300), ni deux. Cibler un projet :
  `npx vitest run --project node`.
```

- [ ] **Step 10 : Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts \
        frontend/test/environments.test.ts frontend/next.config.test.ts \
        frontend/app/globals.test.ts frontend/scripts/backend-url.test.mjs \
        frontend/scripts/exit-code.test.mjs frontend/AGENTS.md
git commit -m "perf(508): deux projets vitest, node par defaut

environmentMatchGlobs a ete supprime de vitest 4 : la structure passe par
test.projects. jsdom prend les .test.tsx et trois .test.ts nommes, node
prend le include par defaut de vitest moins ces globs — la partition est
donc structurelle et non deux listes tenues a la main.

node par defaut se choisit sur le mode de defaillance, pas sur la vitesse :
un test a DOM oublie la echoue sur « document is not defined », alors que
l'oubli inverse est silencieux et coute une seconde par execution.

test/environments.test.ts verifie que chaque fichier est reclame par
exactement un projet. Sans lui, un include en **/*.test.ts laisserait les
deux scripts/*.test.mjs reclames par personne, donc jamais executes, et la
suite resterait verte en verifiant deux fichiers de moins (#300).

Retire les quatre docblocks @vitest-environment devenus redondants : ce
sont des overrides actifs, pas de l'information morte.

Refs #508

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3 : Levier 4 — une seule montée Alembic pour les 13 tests inspecteurs

**Files:**
- Modify: `backend/tests/test_migrations.py` (ajout de la fixture après `sqlite_url`, ligne 30 ; puis 13 signatures de test)

**Interfaces:**
- Consumes: le défaut `-n 4` de la tâche 1. **Conséquence directe** : une fixture de portée module posant `DATABASE_URL` la laisserait fuir vers les autres tests du même worker xdist — d'où la restauration immédiate à l'étape 1.
- Produces: `base_migree` (fixture, `scope="module"`) → `str`, l'URL SQLite d'une base déjà montée à `head`.

**Le décompte qui gouverne cette tâche est 13 / 15 / 1**, pas le 15 / 14 qu'annonçaient les premières versions du sondage et du design — voir la correction en tête du sondage. 13 tests partagent, 15 ne peuvent pas, et 1 ne partage pas *par choix*.

- [ ] **Step 1 : Écrire la fixture**

Dans `backend/tests/test_migrations.py`, juste après la fixture `sqlite_url` (après la ligne 29) :

```python
@pytest.fixture(scope="module")
def base_migree(tmp_path_factory):
    """Base SQLite montée à `head` **une seule fois** pour tout le module.

    Les 13 tests qui la prennent ne font qu'**inspecter le schéma** : aucun
    n'écrit. Répéter `upgrade head` pour chacun coûtait ~0,6 s par test sans rien
    vérifier de plus, la montée étant identique à chaque fois (#508).

    Celui qui aurait besoin d'écrire, de semer à une révision intermédiaire ou de
    descendre reprend `sqlite_url`, qui rend une base neuve par test.

    `DATABASE_URL` n'est posée que le temps de la montée : `alembic/env.py` la lit
    via `get_settings()`, mais les inspections passent ensuite par l'URL explicite.
    La laisser en place à portée module la ferait fuir vers les autres tests
    exécutés par le même worker xdist.
    """
    url = f"sqlite:///{tmp_path_factory.mktemp('migrations') / 'migration.db'}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URL", url)
        get_settings.cache_clear()
        command.upgrade(_alembic_config(), "head")
    get_settings.cache_clear()
    return url
```

`pytest.MonkeyPatch.context()` et non la fixture `monkeypatch` : celle-ci est de portée fonction et pytest refuserait de l'injecter ici. Le `with` restaure la variable à la sortie, ce qui *est* l'étape 4 du design.

- [ ] **Step 2 : Basculer les 13 tests inspecteurs**

Pour chacun des 13 tests ci-dessous, et **uniquement** ceux-là : remplacer le paramètre `sqlite_url` par `base_migree`, supprimer la ligne `command.upgrade(_alembic_config(), "head")`, et remplacer chaque occurrence de `sqlite_url` **dans le corps** par `base_migree`. Aucune assertion ne change.

| ligne | test |
| --- | --- |
| 56 | `test_upgrade_head_creates_the_group_tables` |
| 107 | `test_les_tables_d_authentification_sont_creees` |
| 112 | `test_users_ne_porte_aucune_colonne_de_role` |
| 158 | `test_les_tables_du_rbac_sont_creees` |
| 177 | `test_la_migration_seme_exactement_trois_roles_systeme` |
| 197 | `test_admin_est_le_seul_superutilisateur_et_ne_porte_aucun_code` |
| 216 | `test_moderator_porte_ses_deux_codes_couples` |
| 234 | `test_validator_porte_le_seul_pouvoir_de_qualite` |
| 246 | `test_l_organisation_du_club_est_semee` |
| 301 | `test_la_table_des_adresses_autorisees_est_creee` |
| 380 | `test_upgrade_head_creates_the_course_sources_table` |
| 441 | `test_upgrade_head_adds_manual_result_validation_columns` |
| 583 | `test_scraped_at_devient_nullable` |

Deux exemples complets, pour lever toute ambiguïté. Avant :

```python
def test_les_tables_d_authentification_sont_creees(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    assert {"users", "identities", "user_sessions"} <= _tables(sqlite_url)
```

Après :

```python
def test_les_tables_d_authentification_sont_creees(base_migree):
    assert {"users", "identities", "user_sessions"} <= _tables(base_migree)
```

Avant :

```python
def test_l_organisation_du_club_est_semee(sqlite_url):
    """`user_roles.organisation_id` est non nul : sans elle, aucune attribution."""
    command.upgrade(_alembic_config(), "head")

    assert _lignes(sqlite_url, "SELECT slug FROM organisations") == [("tcn",)]
```

Après :

```python
def test_l_organisation_du_club_est_semee(base_migree):
    """`user_roles.organisation_id` est non nul : sans elle, aucune attribution."""
    assert _lignes(base_migree, "SELECT slug FROM organisations") == [("tcn",)]
```

- [ ] **Step 3 : Ne PAS toucher aux 16 autres**

Liste explicite, pour qu'un doute se lève par lecture et non par essai. **15 ne peuvent pas partager :**

- `test_upgrade_ne_desactive_pas_les_loggers_existants` (82) — observe l'effet de bord du `fileConfig()` d'une montée **en cours de processus** ; sans montée dans le test, il ne vérifie plus rien.
- `test_la_reprise_importe_les_adresses_de_l_environnement` (306) — exige `AUTH_ALLOWED_EMAILS` posée **avant** la montée.
- `test_la_reprise_n_ecrit_rien_sans_variable` (328) — exige son **absence** avant la montée.
- `test_le_renommage_de_is_reliable_conserve_les_donnees` (253), `test_the_data_migration_gives_each_imported_course_one_active_source` (395), `test_a_course_without_source_url_gets_no_source` (419), `test_les_participations_existantes_ne_deviennent_pas_pendantes` (450) — sèment des données à une révision intermédiaire.
- Les **huit** cycles `downgrade`/`upgrade` : lignes 123, 140, 282, 337, 502, 531, 546, 589.

**Et un ne partage pas par choix** : `test_upgrade_head_sur_base_vierge` (46). Il pourrait techniquement, mais il est le seul à porter la preuve du chemin vierge → `head`. Il garde sa propre base pour que cette preuve ne dépende d'aucun état partagé.

- [ ] **Step 4 : Vérifier**

```bash
uv run pytest tests/test_migrations.py -n 0
```

Attendu : **29 passed**, ni un de plus ni un de moins, et nettement plus vite que les 18,2 s de départ (~11 s attendues : 12 montées de moins).

`-n 0` est délibéré ici : la fixture est de portée **module**, et l'on veut voir les 29 tests dans un seul processus. Puis la suite complète, dans son défaut parallèle :

```bash
uv run pytest -m "not integration"
uv run ruff check .
```

Attendu : `3656 passed`. `ruff` attrape en particulier un `sqlite_url` resté dans un corps devenu `base_migree` (F821).

- [ ] **Step 5 : Prouver que la fixture partagée ne court-circuite rien**

C'est le risque propre de cette tâche, et le design l'exige explicitement : une fixture partagée qui ferait passer un test sans le vérifier. **Muter à la main** une assertion d'un test basculé — par exemple, dans `test_l_organisation_du_club_est_semee`, remplacer `[("tcn",)]` par `[("pas-le-tcn",)]` :

```bash
uv run pytest tests/test_migrations.py::test_l_organisation_du_club_est_semee -n 0
```

Attendu : **FAIL**. Rétablir l'assertion, re-vérifier le vert. Si la mutation passe, la bascule est fausse : s'arrêter.

- [ ] **Step 6 : Commit**

```bash
git add backend/tests/test_migrations.py
git commit -m "perf(508): mutualise la montee Alembic des 13 tests inspecteurs

test_migrations.py rejouait `upgrade head` 29 fois pour 29 tests, alors
que 13 d'entre eux ne font qu'inspecter le schema qui en resulte. Une
fixture de portee module monte une fois ; les 13 la prennent, aucune
assertion ne bouge.

Les 15 qui sement a une revision intermediaire, cyclent en
downgrade/upgrade ou dependent d'une variable posee avant la montee
gardent sqlite_url. test_upgrade_head_sur_base_vierge aussi, mais par
choix : il est le seul a prouver le chemin vierge -> head, et cette
preuve ne doit dependre d'aucun etat partage.

DATABASE_URL n'est posee que le temps de la montee : a portee module elle
fuirait vers les autres tests du meme worker xdist.

Refs #508

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4 : Levier 2 — cinq exécutions, puis les chiffres d'après-coup

Le levier 2 ne devient pas du code : `maxWorkers` n'est pas touché. Son livrable est une **preuve de stabilité** et la mise à jour du sondage. Le sondage lui-même écrit que « 2 exécutions front vertes ne sont pas une preuve » et demande 5 exécutions consécutives au repos, au délai par défaut.

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-suites-de-tests-sondage.md` — nouvelle section « Après », **et** correction des chiffres que la remesure démentirait. Deux leviers sont concernés, chacun à **deux** endroits :
  - **levier 5**, si l'A/B ne reproduit pas son coût : la phrase « **`-v` coûte 19 s, soit 20 %** » de la section Backend, et la ligne « 5 — retirer `-v` » du tableau « Verdicts par levier » ;
  - **levier 4**, si la remesure ne reproduit pas les 18,2 s : la phrase « `tests/test_migrations.py` : **29 tests en 18,2 s** » de la section Backend, et la ligne « 4 — tests de migration » du même tableau.

**Interfaces:**
- Consumes: l'état final des tâches 1 à 3.
- Produces: les chiffres qui iront dans le commentaire de la tâche 5.

- [ ] **Step 1 : Écrire le banc de mesure d'après-coup**

Le protocole doit être **exécuté**, pas cité. Créer `/tmp/bench-508-apres.sh` — hors dépôt : c'est de l'outillage de mesure, pas du code produit.

```bash
#!/usr/bin/env bash
# Mesure d'après-coup #508, sous le protocole du sondage : refus au-dessus du
# seuil de charge, N répétitions, on retient le MINIMUM (le bruit d'une machine
# partagée ne peut qu'ajouter du temps, jamais en retirer).
set -u
RACINE=/home/mherrmann/work/tcn/data-triathlon/.claude/worktrees/508-test-suites-perf
SEUIL=2.0

charge() { awk '{print $1}' /proc/loadavg; }

attendre_repos() {
  for _ in $(seq 1 60); do
    c=$(charge)
    if awk -v c="$c" -v s="$SEUIL" 'BEGIN{exit !(c < s)}'; then return 0; fi
    sleep 10
  done
  echo "ABANDON : charge restée >= $SEUIL"
  exit 1
}

# `duree` par le compteur SECONDS de bash : rediriger stderr vers /dev/null
# avalerait la sortie de /usr/bin/time, qui écrit là (piège du sondage).
mesurer() {
  etiquette="$1"; reps="$2"; shift 2
  meilleur=""
  for r in $(seq 1 "$reps"); do
    attendre_repos
    c_avant=$(charge)
    debut=$SECONDS
    "$@" >/tmp/bench-508-apres.log 2>&1
    code=$?
    duree=$(( SECONDS - debut ))
    echo "  $etiquette rep$r : ${duree}s (charge avant $c_avant, code $code)"
    if [ "$code" -ne 0 ]; then
      echo "  !! ROUGE à la répétition $r — voir /tmp/bench-508-apres.log"
    fi
    if [ -z "$meilleur" ] || [ "$duree" -lt "$meilleur" ]; then meilleur="$duree"; fi
  done
  echo "$etiquette MIN ${meilleur}s"
}

cd "$RACINE/backend" || exit 1
echo "=== backend, défaut -n 4 ==="
mesurer "back" 2 uv run pytest -m "not integration"

# L'A/B du levier 5, ajouté après la tâche 1 : ses relevés n=1 ont donné `-v`
# **plus rapide** que sans `-v` (60,42 s contre 72,48 s), ce qui est
# causalement impossible et laisse le « 19 s, 20 % » du sondage sans appui.
# Les deux bras sont séquentiels, donc comparables aux 96 s / 77 s d'origine.
echo "=== levier 5 : A/B de -v, sous protocole ==="
mesurer "back-avec-v" 2 uv run pytest -m "not integration" -o addopts=-v
mesurer "back-sans-v" 2 uv run pytest -m "not integration" -o addopts=

# Le levier 4 se remesure lui aussi, et pour la même raison : la tâche 3 a
# relevé sa référence à **7,95 s** là où le sondage annonce **18,2 s** pour le
# même fichier — facteur 2,3. Ici l'écart est causalement cohérent (une charge
# extérieure ne peut qu'ajouter du temps, et le sondage a été relevé sur une
# machine chargée), mais ses deux relevés à elle sont n=1 : rien n'est établi
# sous protocole, ni l'avant ni l'après.
echo "=== levier 4 : test_migrations.py seul, sequentiel ==="
mesurer "migrations" 2 uv run pytest tests/test_migrations.py -n 0

cd "$RACINE/frontend" || exit 1
echo "=== frontend, deux projets, 5 exécutions (levier 2) ==="
mesurer "front" 5 npx vitest run
```

- [ ] **Step 2 : L'exécuter**

```bash
chmod +x /tmp/bench-508-apres.sh && /tmp/bench-508-apres.sh
```

Les **5** exécutions front doivent être vertes, au délai par **défaut** (`npm test` vaut `vitest run` sans `--testTimeout`). Si l'une rougit, le sondage change de conclusion : `maxWorkers` se rouvre, et cette tâche s'arrête pour en reparler — c'est la clause explicite du design, pas une décision à prendre seul.

- [ ] **Step 3 : Consigner les chiffres dans le sondage**

Ajouter à `docs/superpowers/specs/2026-08-20-suites-de-tests-sondage.md`, avant la section « Ce que ce sondage ne dit pas ». Remplacer chaque `<…>` par la valeur **mesurée** — ce sont les seules valeurs de ce plan qui ne sont pas connues d'avance.

```markdown
## Après (mesuré le <date>, mêmes protocole et machine)

| | avant | après |
| --- | --- | --- |
| Suite back complète | 96 s | **<…> s** |
| Suite front complète | 77 s | **<…> s** |
| **Passe locale complète** | **2 min 53** | **<…>** |
| `tests/test_migrations.py` seul, `-n 0` | 18,2 s | **<…> s** |
| Flakiness front | 0 échec sur 2 | **<…> échec(s) sur 5**, au défaut de 5 s |

Le levier 2 est tranché par la ligne du bas : <verdict en une phrase>.

<Si la remesure de `test_migrations.py` ne retrouve pas les 18,2 s de la colonne
« avant », remplacer cette valeur par la valeur mesurée sur la branche, et
corriger les deux endroits du levier 4 listés plus haut. Le gain du levier reste
celui que la remesure établit, avant → après, et non celui qu'annonçait le
sondage.>

### Le coût de `-v`, remesuré

Les relevés de la tâche 1 (n=1) donnaient `-v` **plus rapide** que sans `-v`,
ce qui est causalement impossible : l'A/B a donc été rejoué sous protocole,
les deux bras séquentiels.

| | mesuré |
| --- | --- |
| séquentiel, `-o addopts=-v` | **<…> s** |
| séquentiel, `-o addopts=` | **<…> s** |
| **coût de `-v`** | **<…> s, soit <…> %** |

<Une phrase : le « 19 s, 20 % » annoncé plus haut est confirmé, ou il est
corrigé à cette valeur — et dans ce second cas, corriger aussi la ligne du
levier 5 du tableau « Verdicts par levier » et la phrase « **`-v` coûte 19 s,
soit 20 %** » de la section Backend, qui deviennent faux. Le commit `c05cd67`
de la tâche 1 ne chiffre volontairement pas ce coût et renvoie ici : le sondage
est l'autorité vivante.>
```

- [ ] **Step 4 : Commit**

```bash
git add docs/superpowers/specs/2026-08-20-suites-de-tests-sondage.md
git commit -m "docs(508): chiffres d'apres-coup et 5 executions front

Mesures prises sous le protocole du sondage — seuil de charge,
repetitions, minimum retenu — et non a la va-vite : sans quoi cette
branche referait l'erreur qu'elle corrige.

Les 5 executions front consecutives au repos, au delai par defaut,
tranchent le levier 2. maxWorkers reste intouche.

Refs #508

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5 : Corriger la prémisse de l'issue #508

**Ce n'est pas une tâche de code, et elle est publique : ne pas l'exécuter sans accord explicite de l'utilisateur.** Elle est décrite ici pour ne pas être oubliée, pas pour être déroulée d'office.

Le design en fait le livrable du levier 2 : « sans ça, le prochain à la lire reconstruira un raisonnement sur 8 minutes qui n'existent pas. »

- [ ] **Step 1 : Demander l'accord**, puis publier un commentaire sur l'issue #508 disant, en français :
  - que ses relevés ont été pris sur une machine saturée (`load average` 29,55 sur 12 cœurs) et surestiment le coût d'un facteur ~2,8 ;
  - les chiffres au repos, avant et après, tirés de la tâche 4 ;
  - que le levier 2 ne reproduit pas au repos et que `maxWorkers` n'a donc pas été touché ;
  - que le levier 5, classé « marginal » par l'issue, valait en fait 20 % ;
  - le lien vers le sondage et le design.

- [ ] **Step 2 : Fin de branche**, dans l'ordre prescrit par `AGENTS.md` : `requesting-code-review` → `verification-before-completion` → `finishing-a-development-branch`.

Point à soumettre à l'utilisateur plutôt qu'à trancher seul : la branche touche `frontend/`, ce qui appelle normalement le sous-agent `ui-ux-review` après la revue de code. Or elle **ne change aucun rendu** — seulement la configuration de test. Demander si la revue UI/UX se justifie ici.

---

## Self-Review

**Couverture de la spec**, section par section :

| Section du design | Tâche |
| --- | --- |
| 1 — `pyproject.toml`, xdist et silence | Task 1 (dont le commentaire portant plateau, pénalité 1,35 s, `-n 0`) |
| 1 — écarté : désactivation auto depuis `conftest.py` | non implémenté, comme demandé |
| 2 — deux projets, node par défaut | Task 2 steps 4, et la partition structurelle |
| 2 — les deux `.test.mjs` couverts | Task 2 steps 2 (2ᵉ test), 5 (compte 31), 6 (mutation) |
| 2 — docblocks retirés | Task 2 step 7 (étendu de 2 à 4 fichiers, motif donné) |
| 3 — garde-fou, glob de vitest importé | Task 2 steps 2-3-6 |
| 4 — fixture `base_migree` en 5 étapes | Task 3 step 1 |
| 5 — levier 2 sans code, sondage comme livrable | Task 4, et Task 5 pour le commentaire |
| Vérification — suites, ruff, eslint, build | Task 1 step 4, Task 2 step 8, Task 3 step 4 |
| Vérification — chiffres remesurés sous protocole | Task 4 steps 1-3 |
| Vérification — mutation à la main du levier 4 | Task 3 step 5 |
| Vérification — 5 exécutions front | Task 4 step 2 |

**Écarts assumés par rapport au design, et pourquoi :**

1. **13 / 15 / 1 au lieu de 15 / 14.** L'énumération des 29 fonctions contredit le décompte initial. Le sondage et le design ont été corrigés (commit `83e110d`) plutôt que contournés, puisque le sondage prime.
2. **Quatre docblocks retirés au lieu de deux.** Les deux `.mjs` n'étaient pas connus quand la section 2 a été écrite ; son raisonnement s'y applique identiquement, et un docblock résiduel est un override actif, pas un commentaire.
3. **Pas de `picomatch`, seulement `tinyglobby`.** Glober une fois par projet donne le même résultat sans réimplémenter de règle de correspondance — vérifié.
4. **`vitest.config.ts` n'exporte rien de nommé.** Un export nommé y déclenche un `MIXED_EXPORTS` de rollup à chaque exécution ; le garde-fou lit donc l'objet de config, ce qui le rend au passage plus fidèle à ce qui s'exécute.

**Balayage des placeholders :** les seuls `<…>` du plan sont dans le gabarit de tableau de la tâche 4 step 3, et c'est délibéré — ce sont les valeurs que la mesure doit produire. Toute autre valeur du plan est une attente vérifiable (`3656 passed`, `939 tests`, `118 fichiers`, `{ jsdom: 87, node: 31 }`, `29 passed`).

**Cohérence des noms**, d'une tâche à l'autre : `base_migree` (fixture pytest), `sqlite_url` (fixture existante, conservée), `GLOBS_JSDOM` (constante locale, non exportée), `EXCLUDE` (constante locale), noms de projets `jsdom` et `node`, `projetsDeLaConfig()` et `revendications()` (helpers du garde-fou), `/tmp/bench-508-apres.sh`.

**Ce qui a été éprouvé avant l'écriture du plan**, et n'est donc pas à re-découvrir : la forme `test.projects` + `extends: true` hérite bien de `plugins: [react()]` et de `resolve.alias` (31 fichiers node verts, 61 tests jsdom verts) ; `configDefaults.include` est exporté par `vitest/config` ; `tinyglobby` porte ses types sous `moduleResolution: "bundler"` ; la partition rend 118 / 87 / 31 sans doublon ; et le garde-fou rougit sur `["**/*.test.ts"]` en désignant les deux `.test.mjs`.
