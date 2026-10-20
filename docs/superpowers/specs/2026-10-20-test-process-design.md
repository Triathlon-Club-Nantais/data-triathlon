# Design : lancer moins de tests par changement, sans affaiblir la porte (#1704)

Epic #1704, sous-issues #1705 (quick wins), #1706 (moyen terme), #1707 (à
envisager). Étude source : rapport « Optimiser le processus de test » du
20/10/2026 (constat chiffré repris dans le corps de #1704). Prédécesseur direct :
#508, `docs/superpowers/specs/2026-08-20-suites-de-tests-design.md` et son
sondage, dont ce design hérite le protocole de mesure et les pistes déjà
rejetées.

## Intention

Le développement ralentit parce que la suite complète tourne trop souvent en
local, pas parce que la CI est lente (médiane 151 s par PR). Quatre skills
Superpowers, la constitution et `.claude/workflows/195-fanout-scrapers.mjs`
demandent la suite entière ; rien ne prescrit les tests ciblés. Estimation non
mesurée : 5 à 10 suites complètes par feature, sur une machine que les sessions
parallèles saturent déjà.

Le principe directeur vient de Google (SWE at Google, ch. 23) et de Fowler :
**sélectionner en amont, tout vérifier en aval**. Tests ciblés pendant
l'itération ; suite complète une fois par branche ; suite complète toujours en
CI et en merge queue.

## Objectifs

1. Les agents et les humains itèrent sur les tests du code touché, et le savent
   par une règle écrite, puis par un hook qui l'applique.
2. Une PR qui ne touche qu'une application ne paie pas les jobs CI de l'autre.
3. La boucle locale ne paie plus les tests de migration ni la recréation du
   schéma à chaque test, si la mesure le justifie.
4. La suite est consolidée module par module, chaque lot prouvé par un score de
   mutation qui ne baisse pas.
5. Les 3 tests frontend rouges sous couverture sont expliqués et corrigés.

## Non-objectifs

- Réduire la durée de la CI en dessous de ce qu'elle est (déjà sous le seuil
  DORA de 10 min), hormis le découpage du job backend.
- Toucher aux skills Superpowers : ils vivent au niveau utilisateur, hors dépôt.
- La double exécution de `ci.yml` au merge, recommandée par le rapport : **déjà
  réglée** par #1572 (`deploy.yml` ne réagit plus au push sur `main`).
- Les tests `integration` (cron hebdomadaire, inchangé).

## Anti-objectifs (échec même si ça « marche »)

- Une PR fusionnée sans que la suite complète des deux applications ait tourné
  en merge queue.
- Un job CI sauté par erreur (filtre faux, job `changes` en échec) compté comme
  réussi par `ci-ok`.
- Un test supprimé sans preuve de mutation.
- Une mesure de gain prise sur une machine chargée et présentée comme un fait.
- Un hook qui rend les tours de conversation sans code lents.

## Contraintes

- `AGENTS.md` racine : 196 lignes sur un plafond de 200. La règle y tient en
  quelques lignes ; le détail va dans un document renvoyé (voir A).
- Actions GitHub épinglées par SHA avec la version en commentaire, comme le
  reste de `ci.yml`.
- `ci-ok` est le seul check requis du ruleset (#920) ; il ne compte aujourd'hui
  que `success`.
- Protocole de mesure du sondage d'août : seuil de charge, répétitions, minimum
  retenu. La machine a été relevée entre 12 et 34 de charge sur 8 cœurs le
  20/10 ; une mesure hors seuil n'est pas rapportée comme résultat.
- Pistes déjà rejetées par #508, à ne pas rouvrir sans fait nouveau :
  `isolate: false` sur jsdom (bloque la suite), `pool: "threads"` (3x plus
  lent), plafonner `maxWorkers`.
- Langue : Principe I de la constitution. Commits Conventional Commits.

## Décisions

### #1705, quick wins

**A. Règle de gradation.** Un court paragraphe dans `AGENTS.md` (sous
« Commandes ») et un document détaillé `docs/tests-boucle.md` ajouté au tableau
« Où lire quoi » (en libérant les lignes nécessaires ailleurs dans `AGENTS.md`,
sans perdre d'information). Contenu :

- Pendant l'itération : le fichier ou le dossier de test concerné
  (`uv run pytest tests/<chemin> -n 0`, `npx vitest run <fichier>`,
  `npx vitest related --run <fichiers source>`), et les raccourcis `--lf`,
  `--sw`, `vitest --changed origin/main`.
- Une suite complète **par branche**, avant `finishing-a-development-branch`, et
  seulement pour l'application touchée. Déclencheurs qui imposent les deux
  suites : changement de contrat API consommé par le front, de dépendances, de
  configuration de test, de workflows CI.
- Jamais de suite complète relancée « pour confirmer » sans fichier modifié
  depuis le dernier vert.
- Une phrase de précédence explicite : cette règle du projet prime sur les
  exigences de suite complète des skills pour les étapes intermédiaires ;
  `verification-before-completion` est satisfait par la commande ciblée pour une
  affirmation sur une tâche, et par la suite complète pour une affirmation sur
  la branche.
- `.claude/workflows/195-fanout-scrapers.mjs` : chaque sous-agent lance les
  tests de son fournisseur, plus le dossier de tests des scrapers ; pas la suite
  entière.
- La constitution n'est pas amendée : son exigence (suite verte pour toute PR)
  reste vraie, la CI et le passage par branche la satisfont. À vérifier par le
  builder en relisant ses lignes 165, 405 et 500.

**B. Filtre de chemins en CI.** Un job `changes` (`dorny/paths-filter`, épinglé
par SHA) produit `backend` et `frontend`. Les jobs backend (`backend`,
`backend-postgres`) et frontend (`frontend`, `frontend-test`) en dépendent avec
un `if:` sur leur sortie. Règles :

- Sur `merge_group`, les deux sorties sont forcées à vrai : la merge queue
  exécute toujours tout.
- Les workflows (`.github/**`) déclenchent les deux.
- `ci-ok` dépend aussi de `changes` et exige : `changes` en `success` ; sur
  `merge_group`, tous les jobs en `success` ; ailleurs, `success` ou `skipped`
  pour les jobs filtrés seulement. Un `changes` en échec rend donc `ci-ok`
  rouge.
- Le filtre vit dans les jobs, jamais dans `on.paths`.
- Correspondance des chemins : `backend/**` déclenche les jobs backend,
  `frontend/**` les jobs frontend, `.github/**` les deux. Le reste (`docs/`,
  `infra/`, `.specify/`, `render.yaml`, fichiers racine) n'en déclenche aucun.
  Un changement de contrat API côté backend ne déclenche pas le frontend en CI :
  les tests frontend simulent l'API et n'exécutent aucun code backend, donc ne
  peuvent pas rougir à cause de lui (la règle A, elle, demande au développeur de
  vérifier le front localement dans ce cas).
- `backend-audit` (hors `ci-ok`, `continue-on-error`) suit le filtre backend.
- `ci-ok` distingue la merge queue par `github.event_name == 'merge_group'`.

**C. Les 3 tests frontend rouges.** `AthleteDetachAction`, `TeammatesDialog`,
`CalendrierEntrainements`, rouges dans deux exécutions sous couverture et sous
charge. Méthode `systematic-debugging` : rejouer isolément, sans couverture,
puis sous couverture ; trancher entre test sensible au temps (horloge, délai,
date) et régression réelle ; corriger la cause. `CalendrierEntrainements` porte
une date (« vu le 10/10/2026 ») : piste d'horloge à vérifier en premier.

### #1706, moyen terme

**D. Hooks Claude Code projet** (dans `.claude/settings.json`, script versionné
sous `.claude/hooks/`) :

- `PreToolUse` sur Bash : refuse une suite complète (pytest sans chemin de test,
  `npm test`, `vitest run` sans fichier), avec un message qui rappelle la règle
  A. Passe-droit explicite : la commande préfixée par `FULL_SUITE=1`. La
  détection tolère le préfixe `rtk` ajouté par le hook RTK de l'utilisateur.
  Est une suite complète : `pytest` sans argument de chemin, ou avec
  `tests`/`tests/` seul ; `npm test` ou `vitest run` sans filtre de fichier.
  Restent permis : un sous-dossier ou un fichier, `::`, `-k`, `--lf`, `--sw`,
  `-m integration`, `vitest related`, `vitest --changed`. Les commandes
  chaînées (`cd backend && ...`, `;`, `&&`) sont analysées segment par segment.
- `Stop` : si des fichiers source ou de test ont changé depuis le dernier
  passage du hook (empreinte mise en cache), lance les tests ciblés de ces
  fichiers et bloque la fin du tour s'ils sont rouges ; sinon ne fait rien.
  Frontend : `vitest related --run`. Backend : `pytest --testmon` si E3 est
  retenu, sinon les fichiers de test modifiés plus ceux qui importent les
  modules modifiés. Délai maximal borné ; au-delà, le hook laisse passer avec un
  avertissement plutôt que de bloquer. La variante par import est volontairement
  superficielle (import direct seulement) : le hook est un filet de boucle
  interne, la CI reste la porte, et une recherche transitive coûterait plus que
  le gain. Cette variante ne bloque donc pas l'ordre des sous-issues.
- Ces hooks ne remplacent jamais la porte CI.

**E. Marqueur `migrations`.** `tests/test_migrations.py` reçoit le marqueur,
sauf `test_upgrade_head_sur_base_vierge`, qui reste la preuve locale de la
chaîne. Désélection par défaut **sans** passer par `addopts -m` : une option
`-m "not integration"` en ligne de commande l'écraserait. Opt-in par une option
explicite ; la ligne de commande du job CI `backend` peut changer pour
l'activer. `backend-postgres` n'exécute pas `test_migrations.py` aujourd'hui
(il rejoue `upgrade/check/downgrade/upgrade` et les tests de repositories) et
reste inchangé. La règle A ajoute : une branche qui
touche `backend/alembic/` ou les modèles lance la suite avec cette option.

**F. Fixtures DB transactionnelles, sous condition.** D'abord chronométrer le
coût de `create_all`/`drop_all` par test SQLite (protocole du sondage). Si ce
coût dépasse 10 % du temps cumulé de la suite unitaire backend, mesuré en
`-n 0` (la part ne dépend alors pas du parallélisme) : schéma créé une fois par
worker xdist, chaque test dans une transaction annulée (recette SQLAlchemy 2.0,
`join_transaction_mode="create_savepoint"`, avec le contournement pysqlite
documenté pour les SAVEPOINT). Sinon : la mesure est consignée dans le sondage
et la décision s'arrête là. Preuve : même nombre de tests passés, ordre
aléatoire de contrôle.

**G. Profilage vitest.** `vitest doctor` et la ventilation `Duration`. Essai
`isolate: false` sur le projet `node` seulement. Évaluation de happy-dom sur le
projet jsdom, adoptée seulement si plus rapide au repos à nombre de tests passés
égal. Toute conclusion, positive ou négative, va dans le sondage.

### #1707, à envisager

**H. pytest-testmon**, usage local en opt-in, dépendance de dev, fichier de
données ignoré par git, jamais en CI. Essai préalable avec `-n 4`. Limite
documentée dans `docs/tests-boucle.md` : les fixtures HTML des scrapers ne sont
pas suivies ; toucher une fixture impose de lancer le fichier de test du
fournisseur. Si l'essai xdist échoue ou si testmon rate des tests sur un cas
vérifié, il n'est pas adopté et D se rabat sur sa variante par import.

**I. Découpage du job backend en CI.** `pytest-split` en 2 shards, algorithme
`least_duration`, fichier de durées versionné. Contrôle : la somme des tests
collectés par shard égale la collecte complète. `ci-ok` dépend des shards.

**J. Outillage de mutation.** mutmut (backend) et StrykerJS avec le runner
vitest (frontend), en dépendances de dev, mode incrémental, lancés sur un
chemin donné. Hors CI.

**K. Consolidation de toute la suite.** Par lots, un lot par zone (un
fournisseur de scraper, un service, un dossier de routes, un dossier de
composants). Pour chaque lot :

1. Score de mutation de référence sur le code source couvert par le lot.
2. Consolidation : `parametrize` / `it.each` pour les cas répétés, suppression
   des tests d'interaction (mocks vérifiant des appels), des tests de structure
   et des tests de haut niveau déjà couverts plus bas.
3. Le lot est gardé seulement si le score de mutation ne baisse pas et si la
   couverture de lignes ne baisse pas ; sinon il est annulé.
4. Un commit par lot, avec dans le message : tests avant/après, score avant/après.

Priorité des lots : les plus gros fichiers d'abord (`test_raceresult.py`,
`test_import_service.py`, `RaceFinishers.test.tsx`, `AppNav.test.tsx`), puis
par taille décroissante. Le chantier s'arrête lot par lot : chaque lot fusionné
est un gain acquis.

Périmètre décidé par l'utilisateur : toute la suite. Le plan pose l'outillage,
la procédure, l'inventaire complet des lots, et détaille les quatre premiers ;
les suivants appliquent la même procédure. Budget de mutation par lot : si la
mesure sur le code couvert dépasse 30 minutes, elle se restreint aux fonctions
dont des tests sont supprimés ou fusionnés. Un mutant en timeout ou instable
n'entre pas dans la comparaison (même filtre avant et après).

## Ordre

#1705 d'abord (C en tête : un signal rouge faux fausse toutes les mesures
suivantes), puis #1706, puis #1707. Dans #1707, J avant K ; H avant la variante
backend du hook `Stop` si possible.

## Appels faits sans validation explicite (à relire)

- Commits directs sur `epic/1704-test-process`, revue sur la PR parapluie, comme
  pour les epics #1312 et #1360, plutôt qu'une PR par sous-issue. Dans ce
  worktree, `git` nu est bloqué par le hook ; les commits passent par
  `/usr/bin/git -C <worktree>`.
- Correspondance des chemins CI (B), règles de détection du hook (D), base
  `-n 0` pour F, budget de mutation de 30 minutes par lot (K).
- Variante par import du hook `Stop` volontairement superficielle.
- Point 4 du rapport (double exécution CI) retiré : déjà fait par #1572.
- Passe-droit `FULL_SUITE=1` pour le hook `PreToolUse`.
- Seuil de 10 % pour décider F.
- Le test fumée local des migrations : `test_upgrade_head_sur_base_vierge`.
- Consolidation : critère double (mutation et couverture ne baissent pas).

## Laissé au builder

- Le mécanisme exact de désélection du marqueur `migrations` (hook
  `pytest_collection_modifyitems` et option, ou autre), sous la contrainte
  ci-dessus.
- La forme du script de hook (shell ou Python) et l'emplacement du cache
  d'empreinte, hors du dépôt suivi.
- Le découpage précis des lots K au-delà des quatre premiers.
- Les versions exactes de `dorny/paths-filter`, pytest-testmon, pytest-split,
  mutmut et StrykerJS.

## Vérification

- Suites complètes backend et frontend vertes, `ruff`, `eslint`,
  `npm run build` verts, à la fin de chaque sous-issue.
- B : une PR de test ne touchant que `frontend/` montre les jobs backend
  `skipped` et `ci-ok` vert ; un run `merge_group` montre tout exécuté ; un
  `changes` forcé en échec rend `ci-ok` rouge.
- D : une session réelle où un agent tente `uv run pytest -m "not integration"`
  est refusée avec le message ; la même commande avec `FULL_SUITE=1` passe.
- E : `uv run pytest -m "not integration"` ne collecte plus les tests marqués ;
  le job CI les exécute (nombre de tests du job inchangé par rapport à `main`).
- Gains de temps remesurés sous le protocole du sondage, consignés dans un
  sondage daté de cette epic.
