# Boucle de tests

Quoi lancer, et quand, pour ne pas payer une suite complète à chaque édition.

## Pendant l'itération

Tests ciblés uniquement, depuis `backend/` ou `frontend/`.

```bash
# Backend
uv run pytest tests/<chemin> -n 0     # un fichier ou un dossier
uv run pytest tests/<chemin> -k <expr> -n 0
uv run pytest --lf -n 0               # rejoue les derniers échecs
uv run pytest --sw -n 0               # s'arrête au premier échec, reprend là

# Frontend
npx vitest run <fichier>
npx vitest related --run <fichiers source>
npx vitest --changed origin/main
```

## Une suite complète par branche

Avant `finishing-a-development-branch`, lancer la suite complète de
l'application touchée seulement (backend ou frontend, pas les deux par défaut).

Les deux suites sont lancées ensemble quand la branche change :

- le contrat API consommé par le front ;
- les dépendances ;
- la configuration de test ;
- les workflows CI ;
- `backend/alembic/` ou `backend/app/models/` : la suite backend se lance alors
  avec `--migrations` (voir ci-dessous).

Une suite complète n'est jamais relancée tant qu'aucun fichier n'a été modifié
depuis le dernier vert.

## Migrations

Les tests marqués `migrations` (`backend/tests/test_migrations.py`) sont
désélectionnés par défaut, quel que soit `-m`. Seul le test fumée
`test_upgrade_head_sur_base_vierge` (`test_migrations_smoke.py`) reste dans la
boucle. `--migrations` les réintègre :

```bash
uv run pytest -m "not integration" --migrations
uv run pytest tests/test_migrations.py --migrations -n 0
```

La CI passe toujours `--migrations`.

## testmon

`pytest-testmon` (groupe `dev`) est un opt-in local pour le backend : il rejoue
seulement les tests dont le code exécuté a changé. Jamais en CI, où la suite
complète tourne (`merge_group`).

```bash
uv run pytest --testmon --testmon-forceselect -m "not integration"
```

- `-m` seul coupe la sélection (testmon passe en `noselect` et rejoue tout) :
  `--testmon-forceselect` la garde avec `-m "not integration"`, et sans `-m`
  les tests réseau tourneraient.
- La première passe, ou toute passe après `rm .testmondata*`, rejoue tout et
  écrit `backend/.testmondata` (ignoré par le dépôt).
- Compatible avec `-n 4` (défaut), avec le schéma SQLite partagé par worker et
  avec le désélectionnement des migrations : aucun verrou rencontré.
- Limite connue : une fixture non Python (HTML, JSON d'un scraper) modifiée
  n'est pas suivie, aucun test n'est rejoué. Après un changement de fixture,
  lancer le fichier de test à la main.
- Le hook ci-dessous traite `--testmon` comme un test ciblé.

## Hooks

Un hook `PreToolUse` (`.claude/hooks/test_gate.py`, branché dans
`.claude/settings.json`) refuse dans Claude Code les suites complètes lancées
depuis un outil Bash : `pytest` ou `npm test` / `vitest run` sans fichier, sans
`-k`, `--lf`, `--sw`, `--testmon`, `related` ni `--changed`, avec ou sans préfixe `rtk`,
`uv run` ou `npx`. Un test ciblé passe sans bruit.

Pour une vraie suite complète (fin de branche), préfixer la commande par
`FULL_SUITE=1`. Le hook échoue ouvert : un JSON illisible ou une commande qu'il
ne sait pas découper ne bloque rien. Ses tests :
`python3 -m unittest discover -s .claude/hooks -p 'test_test_gate.py'`.

Un hook `Stop` (`.claude/hooks/targeted_tests.py`) lance des tests ciblés quand
un tour se termine avec du code modifié (diff par rapport à `HEAD` plus fichiers
non suivis, sources `backend/**/*.py` et `frontend/**/*.{ts,tsx,js,jsx}`
seulement). Commandes :

- backend : `uv run pytest --testmon --testmon-forceselect -m "not integration" -n 0 -q`
  (`testmon_retenu: oui`, cf. le sondage). Si testmon n'était pas retenu
  (`TESTMON_RETENU` dans le script), il lancerait les tests important
  directement les modules modifiés ;
- frontend : `npx vitest related --run <fichiers>`.

Budget total de 180 s partagé entre les étapes : au dépassement, les processus de
test sont tués (groupe entier), un avertissement sur stderr nomme l'étape
interrompue et celles sautées (le frontend l'est si le backend épuise le budget),
l'empreinte est enregistrée (pas de nouvel essai tant que le contenu ne change
pas) et rien ne bloque. Un test rouge bloque la fin du tour (sortie tronquée aux 40 dernières
lignes). Garde `stop_hook_active` : pas de second passage dans la foulée d'un
blocage. L'empreinte du contenu des fichiers modifiés est écrite après un passage
vert dans `<git-dir>/claude-targeted-tests.sha` ; une empreinte identique ne
relance rien. Le hook échoue ouvert. Ses tests :
`python3 -m unittest discover -s .claude/hooks -p 'test_targeted_tests.py'`.

## Répartition de la CI backend

Le job `backend` de la CI tourne en matrice de deux runners : `pytest-split`
répartit les tests (`--splits 2 --group N`) d'après `backend/.test_durations`,
fichier généré et versionné. Un fichier périmé reste correct (les tests inconnus
sont répartis au mieux), seul l'équilibre se dégrade. Rafraîchir quand la suite
change sensiblement (ajout ou retrait de nombreux tests, test devenu lent), depuis
`backend/` :

```bash
FULL_SUITE=1 uv run pytest -m "not integration" --migrations --store-durations
```

## Précédence

Cette règle du projet prime sur les consignes de suite complète des skills pour les étapes intermédiaires. `verification-before-completion` est satisfait par la commande ciblée pour une affirmation sur une tâche, et par la suite complète pour une affirmation sur la branche.

## La porte

La CI et la merge queue exécutent tout : suite complète backend et frontend,
`ci-ok` étant le seul check requis. La boucle locale allège l'itération, jamais
la porte.

## Mutation

Outillage de mesure, jamais dans la boucle ni en CI : il prouve qu'une
consolidation de tests n'abaisse pas la capacité à détecter une régression
(mutmut côté backend, StrykerJS côté frontend). Budget : 30 min de mutation par
lot, donc toujours restreindre à un chemin.

```bash
# Backend (depuis backend/) : motif de nom de mutant, glob fnmatch
uv run mutmut run "app.core.gender*"       # un module
uv run mutmut run "app.core.*"             # un paquet
uv run mutmut results --all true | grep "app.core.gender"

# Frontend (depuis frontend/)
npx stryker run --force --mutate "lib/rank.ts"
```

Score = tués / (tués + survivants), timeouts exclus.

- **mutmut** : `results` liste les mutants non tués de **tout** `app/` (les
  autres modules apparaissent « not checked »), donc filtrer par `grep` sur le
  préfixe du module. Pour compter : `mutmut results --all true | grep <préfixe>
  | awk -F': ' '{print $2}' | sort | uniq -c`. Le premier `run` d'une session
  exécute toute la suite unitaire en séquentiel (`-n 0`, 4 min à 5 min) pour
  cartographier quel test couvre quelle fonction, puis chaque mutant ne rejoue
  que ses tests ; modifier une fonction source invalide ses mutants (un test
  modifié, voir « Relancer » plus bas), un `run` suivant dure ~1 min sur
  `app.core.gender*` (36 mutants). Il ne lit pas `--migrations` et n'en a pas
  besoin.
- **Stryker** : le tableau affiche « total » qui compte les timeouts comme
  détectés ; recalculer avec la formule ci-dessus. `--force` est indispensable
  pour comparer avant et après une modification de **test** : le mode
  incrémental (`reports/stryker-incremental.json`) a réutilisé tel quel le
  verdict d'avant la suppression d'un test. Le runner est `vitest-gt`
  (`frontend/stryker/vitest-runner.mjs`) : le runner publié filtre les tests
  par un nom joint d'une espace, vitest 5 par un nom joint de « > », et tout
  test sous un `describe` était sauté, chaque mutant sortant « Survived » sans
  test exécuté (relevé au lot 3). Sur un composant React, comparer deux bras
  avec `--concurrency 3` : au défaut (7), la charge fait passer des centaines
  de mutants en timeout, et pas les mêmes d'un bras à l'autre (lot 3 : 325
  contre 0 timeouts, même fichier de test). Si les timeouts diffèrent encore
  entre les deux bras, relancer seulement leurs lignes, sur le bras où ils ont
  expiré et à la même concurrence : `--mutate <fichier>:<L>-<L> --timeoutMS
  60000`.
- **Où vivent les résultats** : backend dans `backend/mutants/` (copie de `app/`
  et `tests/`, base de résultats `mutmut-stats.json` et `*.meta`) ; frontend dans
  `frontend/reports/` (JSON et fichier incrémental) et `frontend/.stryker-tmp/`.
  Tous gitignorés.
- **Réinitialiser** : `rm -rf backend/mutants` (backend) ; `rm -rf
  frontend/reports frontend/.stryker-tmp` (frontend).
- **Pièges backend** : mutmut copie les sources sous `mutants/`, un niveau plus
  bas. Les tests qui lisent le dépôt hors de `backend/` via `parents[N]` (front,
  workflows, licence) y échouent et feraient avorter la cartographie : ils sont
  désélectionnés dans `[tool.mutmut] pytest_add_cli_args` (aucun ne couvre
  `app/`). Un nouveau test de ce genre doit y être ajouté. `scripts/`, `alembic/`
  et `alembic.ini` sont copiés via `also_copy`.
- **Mesures de référence** (machine chargée, load 3 à 10) : `app.core.gender*`
  34 tués, 2 survivants (94,4 %) ; `lib/rank.ts` 9 tués, 1 survivant (90 %),
  `components/tcn/ErrorScreen.tsx` 10 tués, 1 survivant (90,9 %), ces deux
  derniers à load 20 après le correctif du runner (avant : 7/10 et 0/11).
- **Relancer après une modification de test** : mutmut ne réinvalide que les
  fonctions **source** modifiées. Un `run` sans motif garderait le verdict
  d'avant pour un mutant dont seul le test a changé ; un `run` **avec** motif
  rejoue tous les mutants qu'il désigne et cartographie les nouveaux tests.
  Toujours passer le motif pour une comparaison.

## Consolider un lot

Procédure de `docs/superpowers/specs/2026-10-20-test-process-design.md` (K),
appliquée lot par lot. Les lots et leur statut :
`docs/superpowers/specs/2026-10-20-test-consolidation-inventaire.md`.

1. **Référence**, sur le code couvert par le lot, depuis `backend/` ou
   `frontend/` :
   - tests passés et nombre collecté ;
   - couverture de lignes du **seul** fichier du lot sur son code couvert, et la
     liste des lignes manquées :

     ```bash
     uv run --with pytest-cov pytest <tests> --cov=<module> --cov-report=term-missing -n 0
     npx vitest run <tests> --coverage --coverage.include=<source> --coverage.reporter=text
     ```

     Côté frontend, `--coverage` passe par `@vitest/coverage-v8` (dépendance
     de dev épinglée à la version de `vitest`) ; la couverture reste désactivée
     par défaut dans `vitest.config.ts`, et `frontend/coverage/` est gitignoré.

   - score de mutation (section « Mutation » ci-dessus), avec la liste des
     survivants pour vérifier ensuite que l'ensemble des mutants est le même.
     **Toujours passer le motif de mutant**, même pour un module entier
     (`uv run mutmut run "<module>*"`), et le même motif pour la mesure
     d'après : sans motif, mutmut garde les verdicts d'avant une modification
     qui ne touche que les tests. Noter durée murale et `uptime` au départ.
     Budget 30 min : au delà,
     restreindre aux fonctions dont des tests seront supprimés ou fusionnés
     (un motif de nom de mutant par fonction, `app.x.y.x_<fonction>__mutmut_*`),
     et garder **les mêmes motifs** pour la mesure d'après. Timeouts et mutants
     instables exclus des deux côtés.
2. **Consolider** :
   - `parametrize` / `it.each` pour les cas répétés ;
   - fusionner deux tests au même montage dont l'un prolonge l'autre ;
   - supprimer les tests d'interaction (vérification d'appels de mocks), de
     structure (constante, expression rationnelle privée) et ceux de haut
     niveau déjà couverts plus bas ;
   - mettre à jour les commentaires et docstrings qui nomment un test fusionné
     ou supprimé, ou qui en décrivent le rôle.

   Aucune assertion de comportement observable ne disparaît sans qu'un autre
   test la porte ; aucune assertion n'est affaiblie pour faire passer le lot. Un
   test d'interaction qui est le seul à tuer ses mutants (ex. :
   `follow_redirects=True` vérifié par espion) reste.
3. **Mesurer après**, mêmes commandes, mêmes motifs. Garder le lot seulement si
   le score de mutation est ≥ référence **et** la couverture ≥ référence (mêmes
   lignes manquées ou moins), sur le même ensemble de mutants. Sinon annuler le
   lot entier, tous ses fichiers (`git checkout -- <fichiers du lot>`), et
   consigner l'abandon dans l'inventaire.
4. **Un commit par lot** : `test(<zone>): consolidate <fichier> (#1707)`, corps
   `tests: A -> B, mutation: X/Y -> X'/Y', coverage: P% -> P'%` (X tués, Y
   tués + survivants ; A et B comptent les tests collectés, un cas de
   `parametrize` compte pour un).
5. **Mettre à jour la ligne de l'inventaire** (statut, chiffres, motifs
   restreints s'il y en a) dans le même commit, et ce qui a été envisagé puis
   écarté.

Un lot qui ne rapporte rien n'est pas forcé : une ligne « rien à consolider »
dans l'inventaire vaut mieux qu'une réécriture.
