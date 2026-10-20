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
