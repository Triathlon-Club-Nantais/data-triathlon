# Sondage — coût et stabilité réels des suites de tests (#508)

**20/08/2026**, commit `ff26db8`, machine de dev WSL2 12 cœurs.

Ce sondage remesure ce que l'issue #508 avance. Il **prime** sur l'issue, sur le
design et sur le plan : toute divergence se tranche en re-sondant.

## Le résultat qui commande tout le reste

**Les chiffres de l'issue #508 ont été relevés sur une machine saturée par
d'autres processus.** Ils surestiment le coût réel d'un facteur ~3 et
attribuent à la configuration une flakiness qui vient de l'extérieur du dépôt.

| | issue #508 | mesuré au repos |
| --- | --- | --- |
| Suite front complète | 265 s | **77 s** |
| Suite back complète | 199 s | **96 s** — voir ci-dessous |
| **Passe locale complète** | **~8 min** | **2 min 53** — voir ci-dessous |
| Flakiness front | 1-2 échecs par exécution, **même à `--testTimeout=30000`** | **0 échec sur 2 exécutions**, 939/939, au **défaut de 5 s** |

**Les deux valeurs marquées « voir ci-dessous » sont elles-mêmes gonflées.** La
back séquentielle avec `-v` — l'état d'alors — a été remesurée à **58,2 s** au
repos, en bras entrelacés (§ Après), et non 96 s ; la passe locale complète en
dérive et vaut ~**2 min 15**. La surestimation de l'issue est donc plus forte
que ce que la colonne de droite laisse croire : **~3,4×** de part et d'autre
(265 / 77 et 199 / 58,2). Le batch de relevés du § Backend est conservé tel
quel, parce qu'il reste cohérent avec lui-même et que sa valeur est le
**plateau** qu'il établit, non ses durées absolues.

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
   **Exception mesurée : `tests/test_migrations.py` a une variance à queue lourde
   sur cette machine (I/O SQLite sous WSL2)** : 7,96 / 8,02 / **16,86 s** à charge
   0,75 — un facteur 2 entre deux exécutions identiques. Comme il appartient à
   la suite complète, il y injecte jusqu'à ±9 s — davantage que la plupart des
   effets qu'on cherche à mesurer. Conséquences : le minimum se prend sur **≥ 3** répétitions et non 2,
   et tout A/B de suite complète s'exécute en bras **entrelacés** (A B A B) plutôt
   que AA puis BB — sans quoi le bruit de queue produit des écarts causalement
   impossibles, ce qui s'est produit deux fois sur cette branche.
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

**Les deux premières lignes n'ont pas résisté à la remesure** : au repos, en bras
entrelacés, le séquentiel vaut **58,2 s** avec `-v` et **57,9 s** sans (§ Après).
Les deux relevés ci-dessus sont donc gonflés — 96 s pour un bras qui en vaut 58 —
et l'écart de 19 s qu'ils affichent tient dans le bruit décrit au § Protocole. Le
reste du tableau garde sa valeur : c'est le **plateau** qu'il établit, pas les
durées absolues, et le plateau se confirme au repos (voir plus bas).

**`-v` coûte ~0,4 s (0,6 %)** en sortie fichier (le « 19 s, 20 % » est démenti ;
voir § Après). Dans un terminal qui doit rendre 3656 lignes, le coût est
supérieur — cette dimension n'a pas été mesurée, l'A/B redirige vers un fichier.
Le coût en temps est **négligeable** ; le retrait a été fait pour l'hygiène de
sortie (tâche 1), risque nul.

**Le plateau xdist est plat de 4 à 12 workers** — 44 à 49 s, tout tient dans le
bruit. La valeur ne se choisit donc **pas** sur la vitesse. Le 2,6× annoncé par
l'issue mesurait un séquentiel gonflé par `-v` contre un parallèle qui ne l'était
pas ; le gain propre de xdist est de **77 → 47 s, soit 1,6×** — et c'est le seul
chiffre de cette section que la remesure au repos confirme sans le corriger :
57,9 → 35 s vaut **1,65×** (§ Après).

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

`tests/test_migrations.py` : **29 tests en 8,0 s** au repos (l'issue relevait
27,4 s, le sondage initial 18,2 s — tous deux pollués ; remesuré sous protocole
avant la tâche 3), soit **~14 %** de la suite séquentielle sans `-v` (8,0 / 57,9).
La tâche 3 a mutualisé la montée Alembic ; la valeur d'après est dans le § Après.
Sous `-n 4` il n'est plus le chemin critique.

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
  déjà `// @vitest-environment node`. Un `grep` restreint aux `.ts`/`.tsx` les
  manque — l'extension `.mjs` est invisible à ce filtre — et un jeu de globs
  bâti sur `**/*.test.ts` + `**/*.test.tsx` les laisserait **réclamés par aucun
  projet, donc jamais exécutés**. C'est la famille de panne de #300 — un vert qui
  ne dit pas ce qu'on croit — mais par **omission**, là où #300 était par excès
  (52 fichiers d'un worktree imbriqué, collectés en trop). Le `include` par
  défaut de vitest,
  `**/*.{test,spec}.?(c|m)[jt]s?(x)`, les couvre aujourd'hui — toute
  reconfiguration doit le couvrir aussi.

### `environmentMatchGlobs` est supprimé, pas déprécié

Vérifié dans les types de **vitest 4.1.10** installé : l'option a entièrement
disparu de `InlineConfig`. `test.projects` est la seule route.

## Verdicts par levier de l'issue

| levier | annoncé | mesuré | verdict |
| --- | --- | --- | --- |
| 5 — retirer `-v` | « marginal », à faire si budget | **~0,4 s (0,6 %)** en sortie fichier (voir § Après) | **fait** (tâche 1) |
| 3 — xdist | 2,6× | **1,6×** (77 → 47 s) | à faire, valeur **plafonnée** |
| 1 — env. node | 3,1× sur la tranche | **4× sur la tranche, 8 % sur la suite** | à faire, pour la boucle ciblée |
| 4 — tests de migration | 14 % du temps | **8,0 s** au repos (avant tâche 3) ; 13 montées mutualisables sur 29 | modeste sous xdist |
| 2 — flakiness | contention interne à vitest, diagnostiquer `maxWorkers` | **ne reproduit pas au repos** | **ne rien changer** à `maxWorkers` |

Le levier 2 n'est pas un changement de configuration : la cause est la
concurrence entre sessions sur la même machine, hors du dépôt. Plafonner
`maxWorkers` coûterait du temps mural au repos pour un bénéfice non mesuré.

## Après (mesuré le 20/08/2026, mêmes protocole et machine)

Convention : durée **rapportée par l'outil** (ligne `==== N passed in X.XXs ====`
pour pytest, ligne `Duration X.XXs` pour vitest), minimum sur les répétitions.
Les durées `SECONDS` (temps de mur) servent à la détection du rouge ; c'est la
durée outil qui est ici retenue. L'écart `SECONDS` − outil vaut ~3 s pour le
back (démarrage `uv run`) et ~1–3 s pour le front (démarrage `npx` + vitest) —
les 77 s d'origine (mesurées avec `SECONDS`) et les 74 s ci-dessous (durée
outil) sont donc comparables à ~2 s près.

| | avant, sondage initial (machine chargée) | avant, remesuré au repos | après |
| --- | --- | --- | --- |
| Suite back complète | 96 s | **58,2 s** (séquentiel avec `-v` : l'état d'alors) | **35 s** |
| Suite front complète | 77 s | non remesuré — l'état d'avant demandait de défaire la tâche 2 | **74 s** |
| `tests/test_migrations.py` seul, `-n 0` | 18,2 s | **8,0 s** | **5,6 s** |
| Flakiness front | 0 échec sur 2 | — | **0 échec sur 5**, au défaut de 5 s |

Le levier 2 est tranché par la ligne du bas : 5 exécutions consécutives au repos, toutes vertes — `maxWorkers` reste inchangé.

Le gain réel de la branche côté back est **1,66×** (58,2 → 35 s) : la colonne
« avant » du sondage initial était chargée.

### Le coût de `-v`, remesuré

Un premier A/B (tâche 4, bras **non entrelacés** : AA puis BB) donnait avec-v =
62,76 s et sans-v = 64,74 s — avec-v plus rapide, ce qui est causalement
impossible. La cause : `test_migrations.py` a une variance à queue lourde (voir
§ Protocole) ; avec 2 répétitions par bras et un écart total de 2 s, un tirage
de cette queue sur l'un des bras suffit à inverser l'ordre.

L'A/B a été rejoué en bras **entrelacés** (A B A B, retour au repos < 0,6 avant
chacun) :

| bras | rep 1 | rep 2 | min |
| --- | --- | --- | --- |
| avec `-v` | 58,23 s | 58,77 s | **58,23 s** |
| sans `-v` | 62,80 s | 57,86 s | **57,86 s** |
| **coût de `-v`** | | | **~0,4 s, soit 0,6 %** |

Le 62,80 s du bras sans-v est un tirage de la queue lourde. Le « 19 s, 20 % »
annoncé plus haut est **démenti** : le coût mesuré est de ~0,4 s sur 58 s,
sortie redirigée vers un fichier. La phrase du § Backend et la ligne du levier 5
dans le tableau « Verdicts » ont été corrigées en conséquence.

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
