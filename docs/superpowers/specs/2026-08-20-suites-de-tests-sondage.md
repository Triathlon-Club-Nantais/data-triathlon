# Sondage — coût et stabilité réels des suites de tests (#508)

**20/08/2026**, commit `ff26db8`, machine de dev WSL2 12 cœurs.

Ce sondage remesure ce que l'issue #508 avance. Il **prime** sur l'issue, sur le
design et sur le plan : toute divergence se tranche en re-sondant.

## Le résultat qui commande tout le reste

**Les chiffres de l'issue #508 ont été relevés sur une machine saturée par
d'autres processus.** Ils surestiment le coût réel d'un facteur ~2,8 et
attribuent à la configuration une flakiness qui vient de l'extérieur du dépôt.

| | issue #508 | mesuré au repos |
| --- | --- | --- |
| Suite front complète | 265 s | **77 s** |
| Suite back complète | 199 s | **96 s** |
| **Passe locale complète** | **~8 min** | **2 min 53** |
| Flakiness front | 1-2 échecs par exécution, **même à `--testTimeout=30000`** | **0 échec sur 2 exécutions**, 939/939, au **défaut de 5 s** |

`npm test` vaut `vitest run` sans `--testTimeout` : les deux exécutions vertes
ci-dessus l'étaient donc au délai par défaut de 5 s, celui de la CI — là où le
relevé de l'issue échouait à 30 s. Ce n'est pas un délai trop court ni une
contention interne à vitest, c'est la machine partagée.

### Ce qui tournait pendant les mesures de l'issue

Constaté en cours de session, `load average` à **29,55** sur 12 cœurs : deux
`npm install` concurrents (125 % CPU et 12,6 % de RAM chacun), un `bfs` balayant
`/` à 211 %, la suite vitest d'un **autre worktree**, et deux autres sessions
`claude`. La règle « un worktree par issue » (`docs/dev-multi-worktree.md`) rend
cet état non exceptionnel mais **normal** sur cette machine.

Preuve interne que l'environnement n'était pas mesurable : deux exécutions
**identiques** de `pytest -n 12` ont donné **89,7 s** et **131,9 s**, soit 47 %
d'écart, l'une des deux produisant en plus une erreur sur
`test_services/test_admin_actions.py::test_rescrape_termine_et_commite_malgre_un_client_qui_arrete_de_lire`.
Cette erreur **ne reparaît pas au repos**, à aucun nombre de workers.

## Protocole

Sans lui, aucun de ces chiffres n'est opposable :

1. **Seuil de charge** — aucune mesure ne démarre au-dessus de `load average`
   1 min ≥ 2,0 sur 12 cœurs ; le script attend, et abandonne au bout de 10 min.
2. **Répétitions, minimum retenu** — 2 répétitions, on garde la plus rapide. Le
   bruit d'une machine partagée ne peut qu'**ajouter** du temps, jamais en
   retirer : la moyenne mélange le signal et la pollution, le minimum est la
   meilleure estimation du coût propre.
3. **`load average` consigné à côté de chaque relevé**, pour qu'un chiffre
   suspect se disqualifie tout seul.
4. **Vérification préalable** qu'aucun `vitest`, `pytest`, `npm install` ni
   `next dev` étranger au worktree ne tourne.

Deux pièges rencontrés en écrivant le banc, à ne pas refaire :

- Rediriger `stderr` vers `/dev/null` avale aussi la sortie de `/usr/bin/time`,
  qui écrit là. Le compteur `SECONDS` de bash suffit et ne se fait pas manger.
- `-q` n'est **pas** l'état d'arrivée du levier 5 : il est plus silencieux que le
  défaut de pytest et surestime le gain. La bonne neutralisation d'`addopts` est
  `-o addopts=`.

## Backend — 3656 tests

Minimum de 2 répétitions, machine au repos.

| configuration | durée |
| --- | --- |
| `-v` (défaut actuel d'`addopts`) | **96 s** |
| sans `-v` | **77 s** |
| sans `-v`, `-n 4` | **47 s** |
| sans `-v`, `-n 6` | **46 s** |
| sans `-v`, `-n 8` | **44 s** |
| sans `-v`, `-n auto` (=12) | **49 s** |

**`-v` coûte 19 s, soit 20 %**, sortie pourtant redirigée vers un fichier. L'issue
le classe « gain en temps marginal » : c'est faux. Dans un terminal qui doit
rendre 3656 lignes, le coût est supérieur.

**Le plateau xdist est plat de 4 à 12 workers** — 44 à 49 s, tout tient dans le
bruit. La valeur ne se choisit donc **pas** sur la vitesse. Le 2,6× annoncé par
l'issue mesurait un séquentiel gonflé par `-v` contre un parallèle qui ne l'était
pas ; le gain propre de xdist est de **77 → 47 s, soit 1,6×**.

**`-n auto` ne s'effondre pas** au repos (49 s), contrairement à ce que
laissaient croire les relevés sous charge.

### Coût de xdist sur une exécution ciblée

| | durée |
| --- | --- |
| `pytest tests/test_health.py` | **0,40 s** |
| `pytest tests/test_health.py -n 4` | **1,75 s** |

**1,35 s de pénalité sur la boucle la plus serrée**, celle qu'on relance le plus
souvent. C'est le prix de `-n` dans `addopts`, et il se paie aussi quand on ne
demande qu'un test. `-n 0` le rend, et rétablit au passage `--pdb` et une sortie
non entrelacée.

### Le fichier le plus lent

`tests/test_migrations.py` : **29 tests en 18,2 s** (l'issue relevait 27,4 s),
soit ~24 % de la suite séquentielle sans `-v`. Sous `-n 4` il n'est plus le
chemin critique.

Ces 29 tests se scindent nettement à la lecture, en **13 / 15 / 1** :

- **13 ne font qu'un `upgrade head` puis inspectent le schéma** — partageables ;
- **15 ne le sont pas** : semis de données à une révision intermédiaire, cycle
  `downgrade`/`upgrade`, ou dépendance à une variable d'environnement posée
  **avant** la montée ;
- **1 reste à part**, `test_upgrade_head_sur_base_vierge` : c'est lui qui prouve
  le chemin vierge → `head`, et il garde sa propre base pour le prouver seul.

> **Correction.** Une première lecture annonçait ici « 15 partageables sur 14 »,
> décompte repris tel quel par le design. L'**énumération nom par nom** des 29
> fonctions du fichier donne 13 / 15 / 1 — les tests de cycle sont 8 et non 7, et
> les deux tests de reprise des adresses autorisées sont bien non partageables.
> C'est l'énumération qui fait foi ; les deux documents ont été corrigés.

Trois tests méritent une mention parce qu'ils *ressemblent* à des inspecteurs
sans en être : `test_upgrade_ne_desactive_pas_les_loggers_existants` observe
l'effet de bord du `fileConfig()` d'une montée **en cours de processus**,
`test_la_reprise_importe_les_adresses_de_l_environnement` exige une variable
d'environnement posée **avant** la montée, et
`test_la_reprise_n_ecrit_rien_sans_variable` exige son absence.

## Frontend — 939 tests, 118 fichiers, **trois** extensions

| configuration | durée |
| --- | --- |
| suite complète, jsdom partout | **77 s** |
| les 27 candidats sous jsdom | **8 s** |
| les 27 candidats sous node | **2 s** |

**4× sur la tranche concernée** (mieux que le 3,1× de l'issue), mais **~6 s sur
la suite complète, soit 8 %**. Le gain du levier 1 n'est pas dans la suite
complète : il est dans la **boucle ciblée**, quand on relance `lib/` en
travaillant dedans.

### Le partage par extension est presque net — et il y a **trois** extensions

Mesuré par absence de `@testing-library`, `document`, `window`, `localStorage`,
`render(` et `screen.` :

| extension | fichiers | environnement requis |
| --- | --- | --- |
| `.test.tsx` | 84 | jsdom, **tous, sans exception** |
| `.test.ts` | 32 | 3 jsdom, 29 node |
| `.test.mjs` | 2 | node, **déjà annotés** |
| **total** | **118** | 87 jsdom, 31 node |

- Les 3 `.test.ts` qui ont besoin du DOM : `hooks/useRescrapeStream.test.ts`,
  `lib/queries/admin.test.ts`, `lib/queries/auth.test.ts`.
- **29 `.test.ts` n'y touchent jamais** — et non 26 : l'issue omet
  `instrumentation-client.test.ts`. Deux portent déjà `@vitest-environment node`
  (`next.config.test.ts`, `app/globals.test.ts`), d'où les **27** candidats de
  l'A/B ci-dessus.
- **Deux `scripts/*.test.mjs` existent** (`backend-url`, `exit-code`) et portent
  déjà `// @vitest-environment node`, en **commentaire de ligne** et non en
  docblock. Un `grep` restreint aux `.ts`/`.tsx` les manque, et un jeu de globs
  bâti sur `**/*.test.ts` + `**/*.test.tsx` les laisserait **réclamés par aucun
  projet, donc jamais exécutés**. C'est le mode de défaillance de #300 : un vert
  qui ne vérifie rien. Le `include` par défaut de vitest,
  `**/*.{test,spec}.?(c|m)[jt]s?(x)`, les couvre aujourd'hui — toute
  reconfiguration doit le couvrir aussi.

### `environmentMatchGlobs` est supprimé, pas déprécié

Vérifié dans les types de **vitest 4.1.10** installé : l'option a entièrement
disparu de `InlineConfig`. `test.projects` est la seule route.

## Verdicts par levier de l'issue

| levier | annoncé | mesuré | verdict |
| --- | --- | --- | --- |
| 5 — retirer `-v` | « marginal », à faire si budget | **19 s, 20 %** | **à faire en premier**, risque nul |
| 3 — xdist | 2,6× | **1,6×** (77 → 47 s) | à faire, valeur **plafonnée** |
| 1 — env. node | 3,1× sur la tranche | **4× sur la tranche, 8 % sur la suite** | à faire, pour la boucle ciblée |
| 4 — tests de migration | 14 % du temps | 18,2 s ; 13 montées mutualisables sur 29 | modeste sous xdist |
| 2 — flakiness | contention interne à vitest, diagnostiquer `maxWorkers` | **ne reproduit pas au repos** | **ne rien changer** à `maxWorkers` |

Le levier 2 n'est pas un changement de configuration : la cause est la
concurrence entre sessions sur la même machine, hors du dépôt. Plafonner
`maxWorkers` coûterait du temps mural au repos pour un bénéfice non mesuré.

## Ce que ce sondage ne dit pas

- **La dégradation gracieuse de `-n 4` sous charge est un raisonnement, pas une
  mesure.** La contention n'a été mesurée qu'à n=12. L'argument est que 4 workers
  laissent 8 cœurs libres et ne peuvent donc pas entrer dans le régime observé.
- **2 exécutions front vertes ne sont pas une preuve de stabilité.** Le dernier
  mot demande 5 exécutions consécutives au repos, au délai par défaut.
- **La CI n'a pas été remesurée.** Le constat de l'issue (55 s pytest, 79 s
  vitest sur le run `32359548399`) vient d'une machine dédiée et n'est pas
  suspect ; il n'a simplement pas été rejoué.
- **`--pool=threads` reste écarté** — la piste mesurée par l'issue (94 fichiers
  en échec sur 117, jsdom non appliqué) n'a pas été rouverte.
