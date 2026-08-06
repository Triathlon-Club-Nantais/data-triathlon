# Phase 1 — Modèle de données

**Aucune table, aucune migration.** C'est la propriété structurante de cette
feature : un lancement de batch n'a pas d'existence propre dans notre base. Son
état vit chez la plateforme d'exécution, son bilan est un artefact qu'elle
conserve, et son effet — les participations importées — passe par le chemin
d'import qui existe déjà.

Les entités ci-dessous sont donc des **DTO** (`app/schemas/batch_run.py`) et des
structures de service, pas des modèles SQLAlchemy.

---

## Entrée

### `RescrapeLaunch` — lancement d'une reprise filtrée

| Champ | Type | Règles |
| --- | --- | --- |
| `mode` | `Literal["rescrape"]` | Discriminant de l'union. |
| `provider` | `str \| None` | Doit appartenir au registre des scrapers, sinon 422. Même validation que `--provider` en CLI. |
| `older_than` | `int \| None` | Jours, `1..3650`. |
| `limit` | `int \| None` | Épreuves, `1..500`. |
| `dry_run` | `bool` | Défaut `false`. |

`provider` et `older_than` sont des **filtres cumulables** ; `limit` borne la
liste finale sans rien sélectionner (contrat de la CLI, `cli/AGENTS.md`).

### `FileLaunch` — lancement depuis un fichier téléversé

Transmis en `multipart/form-data`, non en JSON : il porte le fichier.

| Champ | Type | Règles |
| --- | --- | --- |
| `file` | fichier | Extension `.csv` ou `.xlsx`, ≤ 2 Mo (compté à la lecture, pas d'après `Content-Length`). |
| `url_column` | `int` | Index de colonne, `0..len(headers)-1`. Désigné par l'utilisateur, jamais déduit (FR-008). |
| `dry_run` | `bool` | Défaut `false`. |

**Ce que le service en tire** avant tout envoi, dans cet ordre : valeurs de la
colonne → celles qui sont des liens `http(s)` → `normalize_url` →
`dedupe_links` → partage entre `supported` (registre) et `ignored_by_host`. Le
lot envoyé est `supported`, et lui seul.

Refus explicites, chacun avec son motif nommé (FR-012) :

| Condition | Statut | Message |
| --- | --- | --- |
| Extension hors `.csv` / `.xlsx` | 422 | « Format non pris en charge : … » |
| Taille > 2 Mo | 413 | « Fichier trop volumineux (max 2 Mo). » |
| `url_column` hors bornes | 422 | « Colonne inconnue. » |
| 0 URL supportée dans la colonne | 422 | « Aucun lien exploitable dans cette colonne. » |
| > 500 URL après dédoublonnage | 422 | « Trop d'épreuves pour un seul lot (max 500). » |

Le dernier cas est le seul où l'on refuse un travail qu'on *pourrait* faire en
partie : c'est délibéré, une troncature silencieuse laisserait croire que tout a
été traité.

---

## Sortie

### `SheetColumns` — ce que l'utilisateur voit après le téléversement

| Champ | Type | Sens |
| --- | --- | --- |
| `row_count` | `int` | Lignes de données, en-tête exclu. |
| `columns` | `ColumnPreview[]` | Une entrée par colonne. |
| `suggested_index` | `int \| None` | Colonne portant le plus de liens ; `null` si aucune n'en porte. |

### `ColumnPreview`

| Champ | Type | Sens |
| --- | --- | --- |
| `index` | `int` | Position, seule référence stable — deux colonnes peuvent porter le même en-tête. |
| `header` | `str` | En-tête, ou `« Colonne N »` si la première ligne est vide à cet endroit. |
| `link_count` | `int` | Valeurs commençant par `http`. C'est ce compte qui rend visible une colonne d'hyperliens illisible (D8). |
| `samples` | `str[]` | Trois premières valeurs non vides, tronquées à 80 caractères. |

### `BatchRun` — un lancement, vu de l'interface

| Champ | Type | Sens |
| --- | --- | --- |
| `id` | `int` | Identifiant de l'exécution chez la plateforme. |
| `label` | `str` | Ce qui a été lancé, tiré du nom d'exécution (`run-name`). |
| `state` | `"pending" \| "running" \| "completed"` | Dérivé du statut de la plateforme. |
| `outcome` | `"success" \| "failure" \| "cancelled" \| null` | `null` tant que non terminé. |
| `started_at` | `datetime` | |
| `duration_s` | `int \| None` | |
| `triggered_by` | `"ui" \| "schedule" \| "manual"` | Dérivé de l'événement déclencheur. |
| `report_available` | `bool` | Un artefact de bilan est joignable. |
| `external_url` | `str` | Page de l'exécution, pour le détail complet. |

**Ces valeurs sont en anglais, et le français d'affichage appartient au front.**
Principe I : une valeur d'énumération sérialisée dans un JSON d'API est de la
couche technique invisible, ni un libellé montré ni un terme métier du triathlon
— la clause « pas d'exception de vocabulaire métier » s'y applique. « En cours »,
« Échec » et « Planifié » sont produits par les composants, jamais par l'API. Ne
pas les rebasculer côté serveur « pour la lisibilité » : ce serait une traduction
figée dans un contrat, et une seconde définition à tenir.

**`outcome = "failure"` ne veut pas dire « toutes les épreuves ont échoué ».** Il
recouvre trois causes que seul le bilan distingue : échec total du batch (code
`1`), erreur d'usage (code `2`), ou panne d'infrastructure avant même le
démarrage de la CLI. L'interface doit donc renvoyer au bilan plutôt que
d'affirmer une cause — et un échec sans bilan disponible est précisément le
signal d'une panne d'infrastructure.

### `BatchReport` — le bilan

C'est **la charge `--json` de la CLI, rendue telle quelle**. Ne pas la remodeler :
elle est déjà un contrat stable (Principe IV), et toute traduction de champs
créerait une seconde définition à tenir alignée.

Deux unités s'y côtoient, et l'interface doit les nommer comme le fait le
rapport texte :

- **en épreuves** : `unique_supported` (ciblées), `processed` (traitées),
  `errors` (en erreur) ;
- **en participants** : `imported`, `updated`, `skipped`.

Plus : `failures[]` (`url`, `label`, `message`) — le détail des épreuves en
erreur, borné aux seuls échecs ; `ignored_by_host` — les liens jamais soumis, qui
ne comptent ni en succès ni en échec ; `interrupted` ; et, pour une reprise, les
compteurs de réconciliation d'identité (#66).

---

## États et transitions

```text
        POST /admin/batches
                │
                ▼
           pending ───────────────► running ──────────► completed
        (dispatch accepté)      (runner alloué)   (success | failure | cancelled)
                │
                └─ refus 409 si une exécution est déjà pending ou running
```

Trois choses que ce diagramme rend explicites :

- **le dispatch ne rend pas l'identifiant de l'exécution** : la plateforme
  répond sans corps. L'interface retrouve l'exécution par le nom qu'elle a
  demandé (identifiant de corrélation), en interrogeant la liste — d'où un état
  `pending` qui dure quelques secondes et pendant lequel aucun identifiant
  n'existe encore. Cet identifiant est un `uuid4().hex[:8]` produit par l'API au
  moment du dispatch : huit caractères suffisent puisque le refus 409 interdit
  deux lancements concurrents, seul cas où une collision aurait un sens ;
- **il n'y a pas d'état « en file »** : un second lancement est refusé, pas mis
  en attente (FR-004) ;
- **rien n'est écrit chez nous à aucune de ces transitions**. Une panne de notre
  API pendant un batch n'a aucun effet sur lui.

---

## Ce qui touche la base, et par où

Le batch écrit dans `Athlete`, `Course` et `Participation` — mais **par le chemin
d'import existant** (`import_service` → repositories), depuis le runner, sans
passer par notre API. Cette feature n'ajoute aucun accès à la `Session` : c'est
ce qui la garde conforme au Principe II sans avoir à discuter de couches.
