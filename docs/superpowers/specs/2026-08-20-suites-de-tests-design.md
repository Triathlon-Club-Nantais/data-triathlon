# Design — accélérer et stabiliser les suites de tests (#508)

**20/08/2026.** Base de mesure :
`2026-08-20-suites-de-tests-sondage.md`, qui **prime** sur ce document. Aucun
chiffre n'est recopié ici ; toute divergence se tranche en re-sondant.

## Le problème, tel que le sondage le redéfinit

L'issue #508 vise une passe locale de ~8 min. Au repos, elle en coûte **2 min
53** : ses relevés ont été pris sur une machine saturée par d'autres sessions.
Le plus gros levier de la boucle locale n'est donc **pas dans ce dépôt** — c'est
de ne pas faire tourner plusieurs sessions d'agent sur les mêmes 12 cœurs, et
aucun changement de configuration ne rendra ce facteur 2,8.

Ce qui reste à gagner dans le dépôt est réel mais borné : **~2 min 53 → ~1 min
58** (47 s de back sous `-n 4`, ~71 s de front une fois les 27 fichiers sortis de
jsdom), soit ~1,5×. C'est une **extrapolation** à partir des A/B du sondage, à
re-vérifier à l'implémentation, pas une mesure. Le design assume ce périmètre
plutôt que de promettre l'écart de l'issue.

Un objectif se déplace au passage. La suite complète n'est pas la seule boucle
qui compte : la **boucle ciblée** — relancer un dossier en travaillant dedans —
est celle qu'on parcourt des dizaines de fois par heure. C'est là que le levier 1
gagne 4× et là que xdist en coûte.

## Décisions

### 1. `backend/pyproject.toml` — parallélisme et silence

`pytest-xdist>=3.8.0` rejoint le groupe `dev` (PEP 735), donc `uv sync` en dev et
jamais `uv sync --no-dev` de Render.

`addopts = "-v"` devient `addopts = "-n 4"`. Deux changements en un seul endroit,
et **un seul défaut pour local et CI** : ce qui casse ici casse là-bas.

Pourquoi **4** et non `auto`, alors qu'`auto` est plus rapide de 3 s au repos :

- Le plateau est plat de 4 à 12 workers, donc l'écart est du bruit — la valeur ne
  se choisit pas sur la vitesse.
- 4 workers laissent 8 cœurs libres et ne peuvent pas entrer dans le régime de
  saturation qui a produit une erreur à n=12. Sur cette machine, plusieurs
  sessions concurrentes est l'état normal.
- Sur le runner CI à 4 vCPU, `-n 4` et `auto` **coïncident**. Fixer 4 ne coûte
  donc rien à la CI et lui évite de dépendre de la taille du runner.

Le commentaire qui accompagne la valeur porte ce qui ne se lit pas dans un `4` :
la platitude du plateau, la **pénalité de 1,35 s sur une exécution ciblée**, et
`-n 0` comme échappatoire — qui rétablit aussi `--pdb` et une sortie non
entrelacée.

L'arbitrage est explicite : on paie ~1,35 s sur chaque exécution ciblée pour en
gagner 30 sur la complète. Il est défendable, pas gratuit, et le commentaire dit
comment le défaire.

**Écarté** : détecter dans un `conftest.py` qu'on ne demande que quelques tests
pour désactiver xdist à la volée. C'est l'indirection spéculative que les
principes de conception refusent, pour économiser un drapeau documenté.

### 2. `frontend/vitest.config.ts` — deux projets, node par défaut

`environmentMatchGlobs` étant supprimé de vitest 4, la structure passe par
`test.projects` :

- projet **`jsdom`** — `**/*.test.tsx`, plus les **3** `.test.ts` à DOM nommés un
  par un ;
- projet **`node`** — tout le reste, `.test.ts` **et `.test.mjs`**.

Les deux `scripts/*.test.mjs` sont le piège de cette section. Un jeu de globs
bâti sur `**/*.test.ts` + `**/*.test.tsx` — la formulation naturelle — les
laisserait réclamés par **aucun** projet, donc jamais exécutés, et la suite
resterait verte en vérifiant deux fichiers de moins. Le `include` par défaut de
vitest, `**/*.{test,spec}.?(c|m)[jt]s?(x)`, les couvre aujourd'hui ; la
reconfiguration doit le couvrir aussi. Ce piège a été trouvé en écrivant ce
design, pas en exécutant la suite — ce qui est précisément l'argument de la
section 3.

`plugins`, `resolve.alias`, `setupFiles` et l'exclusion `**/.claude/**` restent
communs. `test/setup.ts` fonctionne déjà des deux côtés : ses gardes
`typeof document !== "undefined"` et `typeof Element !== "undefined"` ont été
posées pour les tests d'outillage en environnement node, elles servent ici sans
modification.

**Ce qui décide de l'orientation, c'est le mode de défaillance, pas la vitesse.**
Avec node par défaut, un futur test à DOM oublié échoue immédiatement sur
`document is not defined`. Avec jsdom par défaut — et c'est le cas aujourd'hui —
l'oubli inverse est **silencieux** : le test passe, et coûte une seconde par
exécution, pour toujours. C'est le « rien n'empêche d'oublier le prochain » de
l'issue, et le seul agencement qui s'en sort est celui où le défaut est le moins
cher et l'exception bruyante.

Les docblocks `@vitest-environment node` de `next.config.test.ts` et
`app/globals.test.ts` deviennent redondants et **disparaissent** : ces fichiers
sont des `.test.ts`, donc déjà dans le projet `node`. Pas de couche de
compatibilité.

### 3. `frontend/test/environments.test.ts` — le garde-fou

Un test qui globe tous les fichiers de test du dépôt et affirme que **chacun est
réclamé par exactement un projet** — ni zéro, ni deux.

Son glob de référence est celui de vitest lui-même,
`**/*.{test,spec}.?(c|m)[jt]s?(x)`, et non une liste d'extensions réécrite à la
main : recopier `ts` et `tsx` dans le garde-fou reproduirait l'angle mort qu'il
est censé couvrir, et un `.test.cjs` futur passerait sous les deux.

C'est l'artefact TDD du levier 1, et il couvre un mode de défaillance que ni les
docblocks ni les globs n'attrapent : un fichier de test dans un dossier neuf que
**aucun** projet ne réclame, donc jamais exécuté, donc vert sans rien vérifier.
Le dépôt a déjà payé cette forme de défaillance une fois — #300, où `npm test`
collectait 52 fichiers d'un worktree imbriqué et où un vert ne disait plus ce
qu'on croyait.

Il s'écrit et échoue **avant** la configuration de la section 2.

### 4. `backend/tests/test_migrations.py` — une montée partagée

Une fixture de **portée module**, `base_migree` :

1. `tmp_path_factory` pour une base jetable,
2. pose `DATABASE_URL`, vide le cache de `get_settings`,
3. `upgrade head` **une fois**,
4. **restaure la variable et re-vide le cache aussitôt**,
5. rend l'URL.

L'étape 4 n'est pas cosmétique : l'inspection se fait sur l'URL explicite, la
variable n'est plus nécessaire après la montée, et une `DATABASE_URL` posée à
portée module fuirait vers les autres tests exécutés par le même worker xdist.

Les **15** tests purement inspecteurs de schéma la prennent ; les **14** autres
gardent `sqlite_url` par test, inchangés — dont les trois faux amis relevés par
le sondage (l'effet de bord de `fileConfig()`, et les deux qui dépendent de la
présence ou de l'absence d'`AUTH_ALLOWED_EMAILS` **avant** la montée).

Ce qu'on perd, et il faut l'écrire : chacun de ces 15 tests ne prouve plus à lui
seul qu'`upgrade head` part d'une base vierge — un seul le prouve, les autres
inspectent son résultat. Ce qu'on garde : les assertions mot pour mot, et une
détection qui reste immédiate, la fixture emportant les 15 d'un coup si la montée
casse. La docstring pose la contrainte d'usage : **ces 15 lisent le schéma, aucun
n'écrit** ; celui qui aurait besoin d'écrire reprend `sqlite_url`.

### 5. Le levier 2 ne devient pas du code

`maxWorkers` **n'est pas touché**. La flakiness ne reproduit pas machine au
repos, au délai par défaut de 5 s, là où l'issue échouait à 30 s : la cause est
la concurrence entre sessions, hors du dépôt. Plafonner `maxWorkers` coûterait du
temps mural au repos contre un bénéfice non mesuré — et masquerait la vraie
cause, qui est une règle d'usage de la machine.

Le livrable du levier 2 est le **sondage** lui-même, plus un commentaire sur
l'issue #508 corrigeant sa prémisse : sans ça, le prochain à la lire
reconstruira un raisonnement sur 8 minutes qui n'existent pas.

## Vérification

- Les deux suites vertes, `ruff` et `eslint` verts, `npm run build` vert.
- Les références d'après-coup remesurées **sous le protocole du sondage** — seuil
  de charge, répétitions, minimum retenu — et non à la va-vite ; sans quoi cette
  branche referait l'erreur qu'elle corrige.
- Levier 4 vérifié par une **mutation à la main** : casser une assertion d'un des
  15 tests partagés doit faire rougir. Une fixture partagée qui court-circuite
  une vérification est exactement le risque du levier, et le seul moyen de savoir
  est de l'éprouver.
- Levier 2 : **5 exécutions front consécutives au repos**, au délai par défaut.
  Si l'une rougit, le sondage change de conclusion et `maxWorkers` se rouvre.

## Hors périmètre

- `maxWorkers` et `testTimeout` — cf. section 5.
- `--pool=threads` : la piste écartée par l'issue (94 fichiers en échec sur 117,
  jsdom non appliqué) reste écartée. C'est un chantier, pas un drapeau.
- Les tests marqués `integration` : ni en CI, ni dans la boucle locale par
  défaut.
- Le temps de `npm run build` et de `tsc`.
- **Réécrire des tests pour les rendre plus rapides.** Tout est de la
  configuration, sauf le levier 4 — qui déplace une fixture sans toucher à une
  seule assertion. Une suite réécrite pour gagner des secondes perd en valeur ce
  qu'elle gagne en vitesse.
