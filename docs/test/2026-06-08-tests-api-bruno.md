# Plan de tests API — Bruno (backend-v2)

> **Date** : 2026-06-08
> **Cible** : `backend-v2/` (API versionnée sous `/api/v1`)
> **Outil** : [Bruno](https://www.usebruno.com/) (équivalent Postman)
> **Statut** : v2 codée, non encore déployée — tests à exécuter en local.

---

## Configuration de base

- **Base URL locale** : `http://localhost:8001/api/v1`
- **Lancement du serveur** (depuis `backend-v2/`, venv activé) :
  ```bash
  uvicorn app.main:app --reload --port 8001
  ```
- **Variable d'environnement Bruno** : `{{baseUrl}}` = `http://localhost:8001/api/v1`
- **Docs interactives en parallèle** : `http://localhost:8001/docs`

---

## 1. Health

| #  | Méthode | URL                    | Attendu                                  |
|----|---------|------------------------|------------------------------------------|
| 1  | GET     | `{{baseUrl}}/health`   | `200` — `{"status":"ok","database":true}` |

---

## 2. Scrape / Import (cœur du flux)

| #  | Méthode | URL                                                                                                  | Body / Notes                                  |
|----|---------|------------------------------------------------------------------------------------------------------|-----------------------------------------------|
| 2  | GET     | `{{baseUrl}}/scrape/detect?url=https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4` | → `{"provider":"klikego"}`              |
| 3  | GET     | `{{baseUrl}}/scrape/detect?url=https://site-inconnu.fr/x`                                             | → `{"provider":"playwright"}` (fallback)      |
| 4  | POST    | `{{baseUrl}}/scrape/event`                                                                            | import bloquant (body ci-dessous)             |
| 5  | POST    | `{{baseUrl}}/scrape/event`                                                                            | **2e appel même URL** → `"cached": true`      |
| 6  | POST    | `{{baseUrl}}/scrape/event/stream`                                                                     | flux SSE (`text/event-stream`), même body     |

**Body JSON (tests 4-6)** :
```json
{ "url": "https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4" }
```

**Réponse attendue (test 4)** : `{"imported": N, "skipped": M, "cached": false}`

**URLs réelles par provider** (validées en tests d'intégration, à varier sur le test 4) :

| Provider        | URL                                                                          |
|-----------------|------------------------------------------------------------------------------|
| Klikego         | `https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4` |
| Breizh Chrono   | `https://resultats.breizhchrono.com/resultats-courses/`                       |
| Wiclax          | `https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/` |
| TimePulse (live)| `https://www.timepulse.fr/epreuves/resultats/live/3232`                       |
| ProLiveSport    | `https://www.prolivesport.fr/result/1082/6`                                   |
| SportInnovation | `https://sportinnovation.fr/Evenements/Resultats/7031`                        |

> ⚠️ Vérifier que `scrape/event` conserve les non-finishers (DNF/DNS/DSQ) **sans temps ni rang** (cas ProLiveSport).

---

## 3. Courses & Épreuves

| #  | Méthode | URL                                                                            | Notes                                       |
|----|---------|--------------------------------------------------------------------------------|---------------------------------------------|
| 7  | GET     | `{{baseUrl}}/courses/events`                                                    | épreuves agrégées (compteurs participants + TCN) |
| 8  | GET     | `{{baseUrl}}/courses/events?event_type=Triathlon%20M&club=nantais`             | filtres                                     |
| 9  | GET     | `{{baseUrl}}/courses/events?date_from=2026-01-01&date_to=2026-12-31`           | plage de dates                             |
| 10 | GET     | `{{baseUrl}}/courses`                                                           | liste paginée                              |
| 11 | GET     | `{{baseUrl}}/courses?page=1&page_size=10&event_type=Triathlon%20S`             | pagination + filtre                        |
| 12 | GET     | `{{baseUrl}}/courses/1`                                                         | détail + participants (`id` issu du test 10) |
| 13 | GET     | `{{baseUrl}}/courses/999999`                                                    | → `404` "Course introuvable"               |

---

## 4. Participations

| #  | Méthode | URL                                                                                          | Notes                                      |
|----|---------|----------------------------------------------------------------------------------------------|--------------------------------------------|
| 14 | GET     | `{{baseUrl}}/participations`                                                                  | liste paginée (page_size 1–5000)           |
| 15 | GET     | `{{baseUrl}}/participations?name=dupont&club=nantais&event_type=Triathlon%20M`               | filtres combinés                           |
| 16 | GET     | `{{baseUrl}}/participations?date_from=2026-05-01&date_to=2026-06-30&page=2&page_size=20`      | dates + pagination                         |
| 17 | GET     | `{{baseUrl}}/participations/1`                                                                | détail (athlète + course imbriqués, `splits`, `status`) |
| 18 | GET     | `{{baseUrl}}/participations/999999`                                                           | → `404`                                    |
| 19 | POST    | `{{baseUrl}}/participations`                                                                  | création manuelle → `201` (body ci-dessous) |
| 20 | DELETE  | `{{baseUrl}}/participations/{id}`                                                             | → `204` (`id` créé au test 19)             |
| 21 | DELETE  | `{{baseUrl}}/participations/999999`                                                           | → `404`                                    |

**Body JSON (test 19)** :
```json
{
  "provider": "manuel",
  "athlete_name": "Test",
  "athlete_firstname": "Jean",
  "gender": "M",
  "club": "TCN",
  "event_name": "Triathlon de Test 2026",
  "event_date": "2026-06-08",
  "event_type": "Triathlon M",
  "bib_number": "42",
  "category": "SH",
  "rank_overall": 10,
  "total_time": "02:15:30",
  "swim_time": "00:30:00",
  "t1_time": "00:02:00",
  "bike_time": "01:05:00",
  "t2_time": "00:01:30",
  "run_time": "00:37:00"
}
```

> Vérifier ensuite (test 12/17) que les `splits` sont ré-étiquetés selon l'`event_type`.

---

## 5. Athletes

| #  | Méthode | URL                                                            | Notes                                   |
|----|---------|----------------------------------------------------------------|-----------------------------------------|
| 22 | GET     | `{{baseUrl}}/athletes`                                          | recherche paginée                       |
| 23 | GET     | `{{baseUrl}}/athletes?name=jean&club=nantais&page=1&page_size=50` | filtres                              |
| 24 | GET     | `{{baseUrl}}/athletes/1`                                        | fiche + toutes ses participations       |
| 25 | GET     | `{{baseUrl}}/athletes/999999`                                   | → `404` "Athlète introuvable"           |

---

## 6. Stats

| #  | Méthode | URL                                       | Notes                                       |
|----|---------|-------------------------------------------|---------------------------------------------|
| 26 | GET     | `{{baseUrl}}/stats`                        | agrégations globales                        |
| 27 | GET     | `{{baseUrl}}/stats?club=nantais`           | stats club TCN                              |
| 28 | GET     | `{{baseUrl}}/stats/events-geo`             | épreuves géocodées (lat/lon) pour la carte  |
| 29 | GET     | `{{baseUrl}}/stats/events-geo?club=nantais`| géo filtré club                             |

---

## 7. Admin (providers non supportés)

| #  | Méthode | URL                                              | Notes                                              |
|----|---------|--------------------------------------------------|----------------------------------------------------|
| 30 | POST    | `{{baseUrl}}/admin/pending-providers`            | → `201` — body `{"url":"https://chrono-inconnu.fr/resultats/123"}` |
| 31 | GET     | `{{baseUrl}}/admin/pending-providers`            | liste des non traités                              |
| 32 | DELETE  | `{{baseUrl}}/admin/pending-providers/{id}`       | → `204` (marque traité, `id` issu du test 30)     |

---

## Ordre d'exécution conseillé

1. **Smoke** : test 1 (health).
2. **Détection** : tests 2-3 (rapides, sans DB).
3. **Import** : test 4 (peuple la DB) → 5 (cache) → 6 (SSE).
4. **Lecture** : tests 7-18, 22-29 (s'appuient sur les données importées).
5. **CRUD manuel** : 19 (création) → 17/24 (relecture) → 20 (suppression).
6. **Admin** : 30 → 31 → 32.

### Bonnes pratiques Bruno

- Capturer l'`id` retourné aux tests 4/19/30 dans une variable (`bru.setVar`) et la réutiliser
  aux tests 12/17/20/32 plutôt que des `id` codés en dur.
- Ajouter des assertions sur le code HTTP **et** les champs clés
  (`res.status`, `res.body.imported`, `res.body.cached`).

---

## Suivi des exécutions

| Date       | Environnement | Résultat (OK/KO) | Notes |
|------------|---------------|------------------|-------|
| 2026-06-08 | local         |                  | Plan initial créé |
