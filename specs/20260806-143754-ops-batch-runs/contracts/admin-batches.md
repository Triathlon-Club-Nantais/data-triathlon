# Contrat HTTP — lancement et suivi des batches

Cinq routes sous `/api/v1`, chacune exigeant son pouvoir (FR-005) et gardée
**route par route**, jamais par préfixe : `/admin/` porte déjà le signalement
anonyme `POST /admin/pending-providers`, qu'une garde de router supprimerait sans
que rien ne le nomme.

*(La règle « route par route » vient du socle de pouvoirs livré par #115 — elle y
porte un numéro d'exigence qui n'a rien à voir avec la numérotation de cette
feature, d'où l'absence de renvoi chiffré ici.)*

| Route | Pouvoir | Rôle |
| --- | --- | --- |
| `POST /admin/sheets/columns` | `batch:run` | Lire les colonnes d'un fichier téléversé |
| `POST /admin/batches` | `batch:run` | Lancer une reprise filtrée |
| `POST /admin/batches/from-file` | `batch:run` | Lancer depuis un fichier et une colonne |
| `GET /admin/batches` | `batch:read` | Les derniers lancements |
| `GET /admin/batches/{run_id}/report` | `batch:read` | Le bilan d'un lancement |

La lecture des colonnes exige `batch:run` et non `batch:read` : ce n'est pas une
consultation, c'est la première moitié d'un lancement.

---

## `POST /admin/sheets/columns`

**Requête** — `multipart/form-data` : `file` (`.csv` ou `.xlsx`, ≤ 2 Mo).

**200**

```json
{
  "row_count": 128,
  "suggested_index": 9,
  "columns": [
    { "index": 0, "header": "Nom", "link_count": 0, "samples": ["Dupont", "Martin"] },
    { "index": 9, "header": "Donne-nous un lien pour accéder aux résultats.",
      "link_count": 117,
      "samples": ["https://www.klikego.com/resultats/...", "https://…"] }
  ]
}
```

**Erreurs** : `413` fichier trop volumineux · `422` format non pris en charge ou
fichier illisible · `401` sans session · `403` sans `batch:run`.

`suggested_index` vaut `null` si aucune colonne ne contient de lien — cas
nominal d'un classeur dont les liens sont des hyperliens sans texte (D8).
L'interface le dit alors explicitement plutôt que de présélectionner au hasard.

---

## `POST /admin/batches`

**Requête** — `application/json` :

```json
{ "mode": "rescrape", "provider": "klikego", "older_than": 30, "limit": 50, "dry_run": true }
```

Tous les champs sauf `mode` sont facultatifs. **La base visée n'est pas dans le corps** : elle vient du réglage `GITHUB_BATCH_TARGET` de l'instance (cf. `contracts/workflow.md`). L'accepter du client permettrait à l'administration de la preview d'écrire en production. `provider` est validé contre le
registre des scrapers ; `older_than` ∈ `1..3650` ; `limit` ∈ `1..500`.

**202**

```json
{ "correlation_id": "b7c1f2e4", "state": "pending" }
```

Le corps ne porte **pas** d'identifiant d'exécution : la plateforme n'en rend pas
au dispatch. L'interface interroge ensuite `GET /admin/batches` et retrouve son
lancement par `correlation_id`, présent dans le libellé de l'exécution.

**Erreurs** :

| Statut | Cas |
| --- | --- |
| `409` | Une exécution est déjà `pending` ou `running`. Le message la nomme. |
| `422` | Option hors catalogue : fournisseur inconnu, borne dépassée, mode inconnu. |
| `503` | Lancement non configuré (jeton absent) ou refusé par la plateforme (jeton expiré). Le message distingue les deux. |
| `401` / `403` | Sans session / sans `batch:run`. |

---

## `POST /admin/batches/from-file`

**Requête** — `multipart/form-data` : `file`, `url_column` (entier), `dry_run`.

**202** — même corps que `POST /admin/batches`, augmenté de ce qui a été retenu,
pour que l'utilisateur voie ce qu'il vient de lancer :

```json
{
  "correlation_id": "9ade31c0",
  "state": "pending",
  "epreuves": 117,
  "ignored_by_host": { "example-chrono.fr": 4 }
}
```

**Erreurs** : celles de `POST /admin/batches`, plus `422` pour colonne inconnue,
colonne sans lien exploitable, ou plus de 500 URL après dédoublonnage — chacune
avec son message propre, jamais un refus générique.

---

## `GET /admin/batches`

**Requête** — `?limit=` (défaut 20, max 50).

**200** — un tableau de `BatchRun` (cf. `data-model.md`), le plus récent d'abord.

```json
[
  {
    "id": 1284,
    "label": "rescrape · klikego · 50 épreuves",
    "state": "running",
    "outcome": null,
    "started_at": "2026-08-06T14:37:54Z",
    "duration_s": null,
    "triggered_by": "ui",
    "report_available": false,
    "external_url": "https://github.com/…/actions/runs/1284"
  }
]
```

**Dégradation assumée** : si la plateforme est injoignable, la route rend `503`
avec un message qui le dit — jamais un tableau vide, qui se lirait « aucun
lancement » alors que l'information est simplement indisponible.

---

## `GET /admin/batches/{run_id}/report`

**200** — la charge `--json` de la CLI, **telle quelle** :

```json
{
  "unique_supported": 117, "processed": 117, "errors": 3,
  "imported": 2841, "updated": 96, "skipped": 15230,
  "rows_without_link": 11,
  "ignored_by_host": { "example-chrono.fr": 4 },
  "interrupted": false,
  "failures": [
    { "url": "https://…", "label": "klikego · https://…", "message": "HTTP 503" }
  ]
}
```

**404** — l'exécution n'a pas d'artefact de bilan : elle n'est pas terminée, ou
elle a échoué avant que la CLI ne s'exécute. Le message distingue les deux, parce
que la seconde est le signal d'une panne d'infrastructure (D6, `data-model.md`).

**410** — l'artefact a expiré (rétention de la plateforme). L'exécution reste
consultable sur sa page ; le bilan structuré, non.

---

## Ce que ces routes ne font pas

- **Aucune ne s'exécute longuement.** La plus lente télécharge un artefact de
  quelques kilo-octets. Le service web ne porte jamais le batch (FR-013).
- **Aucune n'écrit en base.** Pas de repository, pas de `Session` — hors du
  `Depends(get_db)` qu'exige la garde de pouvoir pour lire les rôles.
- **Aucune n'accepte de commande.** Le corps est une union discriminée d'options
  typées ; il n'existe aucun chemin par lequel une chaîne fournie par
  l'utilisateur devienne un argument de ligne de commande (FR-003, D11).
