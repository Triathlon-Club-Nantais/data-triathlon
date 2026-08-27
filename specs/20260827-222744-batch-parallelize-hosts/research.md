# Research: Parallélisation du batch d'import par hôte de chronométrage

Aucun `NEEDS CLARIFICATION` ne subsiste dans le Technical Context : la seule
ambiguïté matérielle (unité de regroupement) a été tranchée en
`/speckit-clarify` (voir `spec.md` § Clarifications). Ce document couvre les
décisions d'implémentation nécessaires pour honorer les exigences du spec.

## 1. Unité de regroupement : chronométreur, pas domaine réseau littéral

**Decision**: Regrouper les épreuves par chronométreur en réutilisant la
résolution déjà en place dans `app/scrapers/registry.py` (`_url_host` +
`_HOSTS` par provider), pas en parsant le seul netloc de l'URL.

**Rationale**: Deux providers existants (`WiclaxProvider` :
`wiclax-results.com` / `chronosmetron.com` / `chronowest.fr` ;
`RaceResultProvider`-famille : `raceresult.com` / `espace-competition.com` /
`chronoconsult.fr`) publient sur plusieurs domaines distincts. Grouper par
netloc littéral aurait laissé deux épreuves du même chronométreur partir en
parallèle sur deux de ses domaines — exactement ce que la Clarification de
`spec.md` exclut. Le registre expose déjà la résolution URL → provider ; la
réutiliser évite de dupliquer une deuxième notion de « host ».

**Alternatives considered**:
- Parser le netloc de chaque URL directement (`urlparse(url).hostname`) :
  rejeté — viole l'invariant de politesse pour les chronométreurs
  multi-domaines.
- Introduire une table ou un mapping de configuration séparé
  « domaine → groupe » : rejeté (YAGNI) — le mapping existe déjà dans le
  registre des scrapers, le dupliquer diverge à la première mise à jour de
  l'un des deux.

## 2. Modèle de concurrence : threads, pas asyncio ni multiprocessing

**Decision**: `concurrent.futures.ThreadPoolExecutor`, un thread par
chronométreur actif, borné par un plafond global configurable.

**Rationale**: Le goulot est le temps d'attente réseau (`httpx` bloquant) sur
14 fournisseurs tiers hétérogènes, pas le CPU. Les threads Python libèrent le
GIL pendant l'attente I/O — le gain attendu (SC-001) est donc atteignable sans
changer un seul scraper. `SessionLocal` (`app/core/database.py`) est déjà un
`sessionmaker` sur un pool dimensionné (`db_pool_size=15`,
`max_overflow=10`) : chaque thread peut ouvrir sa propre `Session`. En
implémentation, `run_batch` construit ce `sessionmaker` localement via
`sessionmaker(bind=db.get_bind())` plutôt que d'appeler `session_scope()`
(qui est câblé sur l'engine global) — ça réutilise l'engine de la `Session`
reçue en paramètre, quel qu'il soit, ce qui est aussi ce qui permet à un test
de fournir un engine isolé.

**Alternatives considered**:
- Réécriture asyncio (`httpx.AsyncClient`) : rejetée — toucherait les 14
  modules de `app/scrapers/`, un chantier sans commune mesure avec l'issue
  (Principe VI, simplicité/YAGNI), pour un gain identique sur un goulot déjà
  I/O-bound côté threads.
- `multiprocessing` : rejetée — aucun bénéfice CPU à chercher ; imposerait de
  sérialiser `Settings`/le résultat entre process et de dupliquer l'engine
  SQLAlchemy par process, complexité largement supérieure au gain.

## 3. Isolation de session : une `Session` par thread de groupe

**Decision**: Chaque thread de chronométreur ouvre et ferme sa propre
`Session` (`session_scope()`), scrape/persiste ses épreuves comme aujourd'hui,
puis la referme avant que le thread ne se termine. La `Session` reçue en
paramètre par l'appelant (`import_sheet.py` / `rescrape_db.py`) sert au
travail qui encadre le batch (résolution des cibles, nettoyage des orphelins
en fin de `rescrape-db`), pas au scrape lui-même.

**Rationale**: `Session` SQLAlchemy n'est pas thread-safe — la doc SQLAlchemy
l'interdit explicitement. Le pool existant absorbe sans réglage
supplémentaire un plafond de concurrence à un chiffre.

**Alternatives considered**: une Session unique protégée par un verrou
global : rejetée — ça déplacerait la sérialisation sur la DB au lieu du
réseau, sans rien simplifier, et re-sérialiserait de facto tout gain de
parallélisme.

## 4. Plafond de concurrence : nouvelle option CLI, défaut conservateur

**Decision**: Nouvelle option `--max-concurrent-hosts` (mirroir de `--delay`)
sur `import-sheet` et `rescrape-db`, avec une valeur par défaut de 4.

**Rationale**: FR-003 exige un plafond configurable — l'exposer en option CLI
suit le même patron que `--delay`, déjà consommé par le workflow GitHub
Actions (`.github/workflows/batch.yml`) sans changement de code à chaque
ajustement. La valeur 4 s'aligne sur le seul précédent chiffré du dépôt pour
« un degré de parallélisme sûr par défaut » (`pytest -n 4`, cf.
`backend/AGENTS.md`), et reste très en-deçà du pool DB disponible (15+10).

**Alternatives considered**: auto-détection depuis le nombre de CPU :
rejetée — le facteur limitant est le nombre de chronométreurs distincts et le
réseau, pas le CPU de la machine qui lance le batch. Une constante non
configurable : rejetée — l'issue demande explicitement d'éviter de saturer le
runner GitHub Actions, un réglage par environnement.

## 5. Progression concurrente : le Protocol `ProgressReporter` doit porter une identité de groupe

**Decision**: `item_start`/`item_progress`/`item_done` gagnent une identité de
groupe (le chronométreur) en paramètre. `PlainReporter` continue d'émettre une
ligne par évènement (déjà pensé pour un flux non-TTY) mais préfixe/qualifie
chaque ligne par ce groupe. `RichReporter` maintient une tâche Rich par
chronométreur actif au lieu d'un unique `_item_task` mutable.

**Rationale**: Les deux implémentations actuelles (`backend/app/cli/progress.py`)
gardent un état « épreuve courante » unique (`self._index`, `self._label`,
`self._item_task`) — sous appel concurrent, ce mutable partagé produirait des
lignes attribuées au mauvais chronométreur ou une barre Rich qui saute d'un
groupe à l'autre sans le dire. FR-006/SC de `spec.md` exigent de pouvoir
distinguer les épreuves en cours.

**Alternatives considered**: sérialiser tous les appels reporter derrière un
verrou en gardant le Protocol inchangé : rejetée — un verrou empêcherait la
corruption de l'état interne mais ne resout pas le vrai problème, qui est
qu'un seul « épreuve courante » ne peut pas représenter N épreuves
simultanées ; l'opérateur perdrait quand même la capacité de savoir laquelle
est laquelle (échec de FR-006).

## 6. Bilan agrégé thread-safe

**Decision**: L'accumulation dans `BatchTotals` (compteurs, `failures`,
`passive_sources`, `reassignments`) doit être protégée contre l'écriture
concurrente — soit par un verrou léger autour du seul bloc de comptabilité
(pas autour du scrape lui-même), soit en faisant remonter un résultat par
groupe fusionné après `as_completed`. Le choix précis entre ces deux formes
est un détail d'implémentation laissé à `/speckit-tasks` — les deux satisfont
FR-004/SC-003 à égalité.

**Rationale**: `BatchTotals` est une dataclass mutable ordinaire (pas conçue
pour l'écriture concurrente) ; sans protection, deux threads qui terminent une
épreuve au même instant peuvent perdre un incrément ou corrompre une liste
Python (non thread-safe pour les mutations composées comme `+=`).

## 7. Ctrl-C : d'une exception reçue à un signal coopératif

**Decision**: Le `KeyboardInterrupt` du Ctrl-C n'arrive que sur le thread
principal — chaque thread de groupe doit vérifier, entre deux épreuves de son
lot, un signal d'arrêt coopératif (ex. `threading.Event`) plutôt que
compter sur la propagation de l'exception. Sur interruption : les groupes
cessent de démarrer une nouvelle épreuve, l'épreuve en cours dans chacun va à
son terme (elle est déjà committée épreuve par épreuve), puis le bilan partiel
est assemblé comme aujourd'hui avant la sortie en code 130.

**Rationale**: FR-007/SC-004 exigent qu'aucune régression n'apparaisse sur ce
point précis — un contrat déjà verrouillé par `AGENTS.md` (cli/AGENTS.md,
« bilan partiel avant sortie 130 »). Tuer un thread de force n'est pas une
opération sûre en Python (risque de Session/transaction dans un état
incohérent) — le signal coopératif est la seule voie qui préserve la garantie
« rien n'est perdu de vue » avec des threads.

**Alternatives considered**: laisser chaque thread lever/propager sa propre
`KeyboardInterrupt` : rejetée — seul le thread principal reçoit le signal
OS ; les threads de groupe ne s'arrêteraient jamais d'eux-mêmes sans un signal
explicite.
