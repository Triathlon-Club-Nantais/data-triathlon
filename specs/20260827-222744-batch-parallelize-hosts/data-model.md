# Data Model: Parallélisation du batch d'import par hôte de chronométrage

Aucune table ni migration : cette feature ne touche que des structures en
mémoire, internes à l'orchestration du batch (`app/services/batch.py`,
`app/services/progress.py`). Les entités ci-dessous étendent celles qui
existent déjà — rien n'est persisté.

## Épreuve à traiter (`BatchItem`, existant, inchangé)

`backend/app/services/batch.py::BatchItem` — `url: str`, `label: str`.
Aucun champ ajouté : le chronométreur d'une épreuve se dérive de son `url` à
la volée (voir Groupe de chronométreur), il n'a pas besoin d'être stocké sur
l'item lui-même.

## Groupe de chronométreur (nouveau, interne à `run_batch`)

Regroupement en mémoire des `BatchItem` d'un même lot, par chronométreur.
Représenté comme `list[tuple[str, list[BatchItem]]]` (le `host_key` voyage
avec ses items, pas une simple `list[list[BatchItem]]`) : `run_batch` et le
reporter en ont besoin directement, sans le re-dériver une seconde fois par
groupe.

| Champ | Type | Description |
|---|---|---|
| `host_key` | `str` | Identifiant stable du chronométreur (ex. le nom du provider résolu par `app/scrapers/registry.py`, ou son premier `_HOSTS` — un identifiant, pas nécessairement affiché) |
| `items` | `list[BatchItem]` | Les épreuves de ce groupe, **dans l'ordre du lot d'entrée** — l'ordre à l'intérieur d'un groupe ne change pas |

**Règle de dérivation** : `host_key` vient de `detect_provider(url)`
(`app/scrapers/registry.py`), pas d'un `urlparse(url).hostname` nu — voir
`research.md` § 1. Quand `detect_provider` rend une chaîne vide (URL non
reconnue par le registre, cas déjà possible aujourd'hui, hors scope de cette
feature), on retombe sur l'hôte réseau littéral de l'URL : deux URLs
inconnues de domaines différents restent dans des groupes distincts plutôt
que d'être fusionnées sous une même clé vide.

**Invariant** : à l'intérieur d'un groupe, le traitement reste strictement
séquentiel (même délai de politesse qu'aujourd'hui) ; entre groupes, le
traitement est concurrent, borné par le plafond de concurrence.

## Bilan de batch (`BatchTotals`, existant, sémantique renforcée)

`backend/app/services/batch.py::BatchTotals` — champs inchangés (`imported`,
`updated`, `skipped`, `errors`, `processed`, `interrupted`, `failures`,
`reconciled`, `reassignments`, `passive_sources`). Ce qui change n'est pas la
forme mais la **garantie de construction** : l'accumulation doit rester
correcte sous écriture concurrente par plusieurs groupes (voir `research.md`
§ 6) — le contenu final doit être équivalent à une exécution séquentielle
(FR-004/SC-003), l'ordre des listes (`failures`, `passive_sources`,
`reassignments`) n'étant plus garanti égal à l'ordre du lot d'entrée
(Assumptions de `spec.md`).

## Identité de progression (extension du Protocol `ProgressReporter`)

`backend/app/services/progress.py::ProgressReporter` — les méthodes
`item_start`, `item_progress`, `item_done` gagnent un paramètre d'identité de
groupe (le `host_key` ci-dessus, ou un libellé dérivé) pour permettre à
plusieurs épreuves d'être « en cours » en même temps sans ambiguïté :

| Méthode | Signature actuelle | Signature étendue |
|---|---|---|
| `item_start` | `(index: int, label: str)` | `(index: int, label: str, host: str)` |
| `item_progress` | `(done: int, total: int)` | `(done: int, total: int, host: str)` |
| `item_done` | `(imported: int, skipped: int, error: str \| None)` | `(imported: int, skipped: int, error: str \| None, host: str)` |

`batch_start`/`batch_end` restent inchangés (un seul batch, pas par groupe).
`NullReporter`, `PlainReporter`, `RichReporter` implémentent la nouvelle
signature (détail d'implémentation en `research.md` § 5 ; tests existants de
`test_batch.py` à mettre à jour en conséquence — hors scope de ce document,
couvert par `tasks.md`).

## Configuration (extension `Settings` / options CLI)

Aucune nouvelle colonne DB. Une nouvelle valeur de configuration, au même
niveau que `delay` aujourd'hui :

| Nom | Où | Défaut | Description |
|---|---|---|---|
| `max_concurrent_hosts` | Option Typer `--max-concurrent-hosts` sur `import-sheet` et `rescrape-db`, transmise à `run_batch` | `4` | Plafond du nombre de chronométreurs traités simultanément (FR-003) |
