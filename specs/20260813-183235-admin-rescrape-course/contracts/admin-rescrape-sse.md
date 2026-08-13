# Contrat : `POST /api/v1/admin/courses/{course_id}/rescrape`

Réponse `text/event-stream`, même famille que
`POST /api/v1/scrape/event/stream` (`app/api/v1/scrape.py`) : padding initial
de 2 Ko, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`,
`Content-Encoding: identity`. Chaque ligne `data: <json>\n\n`.

**Garde** : `Depends(require_permission(P.COURSES_SOURCES))` — 403 avant tout
octet du flux si le pouvoir manque, 401 avant le 403 si non authentifié (patron
`require_permission` standard).

**Concurrence** (FR-007) : si un re-scrape est déjà en cours sur la **même**
`course_id`, la route répond en `409` (corps JSON `{"detail": "..."}`,
patron `DomainError`) **avant** d'ouvrir le flux — pas un événement `phase:
error` dans un flux déjà commencé, pour que le front distingue un refus
immédiat d'un échec en cours de route.

## Phases (identiques en forme à `iter_import_event`, adaptées au ciblage par course)

### `scraping`

```json
{"phase": "scraping", "message": "Récupération des participants…"}
```

Sur un provider fan-out (Klikego...), des événements intermédiaires
supplémentaires suivent la forme déjà en place :

```json
{"phase": "scraping", "heat_slug": "...", "heat_label": "...", "heat_index": 2, "heats_total": 5}
```

### `saving`

```json
{"phase": "saving", "total": 214, "imported": 0, "updated": 40, "skipped": 0, "progress": 20}
```

Émis tous les 20 participants persistés (même cadence que l'import public), et
sur le dernier.

### `done` (succès)

```json
{
  "phase": "done",
  "imported": 3,
  "updated": 211,
  "skipped": 0,
  "reconciled": 1,
  "total": 214,
  "orphans_removed": 0
}
```

`orphans_removed` est **propre à cet endpoint** — absent de la phase `done` de
l'import public, ajouté ici parce que FR-006 l'exige explicitement sur ce
geste. Les autres clés reprennent le contrat déjà stable de `iter_import_event`.

### `error` (refus ou échec)

```json
{"phase": "error", "message": "Le chronométreur n'a publié aucun résultat à cette adresse. Les résultats affichés n'ont pas été touchés."}
```

Trois causes possibles, toutes en **français utilisateur** (messages
`DomainError`/`ScraperError`, Principe I) :

| `message` (forme) | Cause |
|---|---|
| « Le chronométreur n'a publié aucun résultat à cette adresse. … » | FR-009, zéro résultat — réutilise `admin_actions._require_same_event` |
| « Cette adresse publie une autre épreuve (« … »), pas « … ». … » | FR-009, identité divergente — idem |
| « Erreur lors de l'enregistrement des résultats. » | échec de persistance, transaction annulée (patron `iter_import_event`) |

Dans les trois cas, la course visée **n'est pas modifiée** (SC-004) : le refus
d'identité/zéro-résultat lève avant toute écriture, comme dans
`switch_course_source` ; l'échec de persistance déclenche un `rollback`.
