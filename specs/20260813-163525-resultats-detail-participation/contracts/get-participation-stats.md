# Contract: `GET /api/v1/participations/{participation_id}` (extension)

Endpoint **existant**, `backend/app/api/v1/participations.py` — pas de
nouvelle route, pas de v2. Le contrat actuel (`ParticipationOut`) est étendu
par un champ optionnel `stats`, additif au sens du Principe IV.

## Requête

Inchangée : `GET /api/v1/participations/{participation_id}`, aucun nouveau
paramètre de requête. Pas d'authentification (cohérent avec l'existant —
FR-004 : pas de restriction club sur la lecture).

## Réponse — 200

`ParticipationOut`, avec l'ajout suivant :

```jsonc
{
  "id": 4821,
  "athlete": { "...": "AthleteBrief, inchangé" },
  "course": { "...": "CourseBrief, inchangé" },
  "club": "Triathlon Club Nantais",
  "category": "V1",
  "bib_number": "56",
  "rank_overall": 56,
  "rank_category": 4,
  "rank_gender": 41,
  "total_time": "02:02:31",
  "status": "finisher",
  "is_relay": false,
  "splits": {
    "swim": "00:22:52",
    "t1": "00:02:55",
    "bike": "01:01:07",
    "t2": "00:01:54",
    "run": "00:33:45"
  },
  "created_at": "2026-05-03T09:12:00Z",
  "is_tcn": true,

  // NOUVEAU — null si la course n'est pas éligible (FR-003/FR-005) ou si la
  // participation est un relais (FR-012). Absent de la réponse pour aucun
  // consommateur existant : ce champ n'existait pas avant cette feature.
  "stats": {
    // Segments publiés par l'épreuve, dans l'ordre d'affichage (FR-013).
    // Les trois blocs ci-dessous s'y réfèrent ; eux omettent les valeurs
    // manquantes, lui non — c'est ce qui distingue « segment non publié par
    // l'épreuve » de « split absent chez cet athlète ».
    "segments": ["swim", "t1", "bike", "t2", "run"],
    "ranking_evolution": [
      { "segment": "swim", "scratch_position": 91, "segment_position": 88 },
      { "segment": "t1",   "scratch_position": 91, "segment_position": 112 },
      { "segment": "bike", "scratch_position": 74, "segment_position": 68 },
      { "segment": "t2",   "scratch_position": 63, "segment_position": 60 },
      { "segment": "run",  "scratch_position": 56, "segment_position": 63 }
    ],
    "comparison": [
      { "position_label": "1er",  "rank": 1,   "percentages": { "swim": 141.6, "t1": 137.8, "bike": 124.9, "t2": 139.0, "run": 124.0, "total": 128.0 } },
      { "position_label": "10e",  "rank": 10,  "percentages": { "swim": 112.8, "t1": 130.6, "bike": 112.4, "t2": 115.2, "run": 109.0, "total": 112.0 } },
      { "position_label": "25e",  "rank": 25,  "percentages": { "swim": 105.9, "t1": 140.0, "bike": 104.4, "t2": 95.0,  "run": 106.6, "total": 105.8 } },
      { "position_label": "50e",  "rank": 50,  "percentages": { "swim": 95.7,  "t1": 119.0, "bike": 99.6,  "t2": 85.7,  "run": 111.1, "total": 101.9 } }
      // "100e" omise ici : moins de 100 finishers sur cette course (FR-014).
    ],
    "improvement": [
      { "segment": "swim", "gains": { "0.5": 1, "1": 2, "2": 4,  "5": 10, "10": 18, "25": 39 } },
      { "segment": "t1",   "gains": { "0.5": 1, "1": 1, "2": 1,  "5": 1,  "10": 2,  "25": 5  } },
      { "segment": "bike", "gains": { "0.5": 2, "1": 5, "2": 11, "5": 26, "10": 40, "25": 62 } },
      { "segment": "t2",   "gains": { "0.5": 1, "1": 1, "2": 1,  "5": 1,  "10": 2,  "25": 4  } },
      { "segment": "run",  "gains": { "0.5": 2, "1": 2, "2": 5,  "5": 13, "10": 27, "25": 48 } }
    ]
  }
}
```

## Réponse — course non éligible ou participation relais

Même route, même 200, `"stats": null`. Le front rend l'état "statistiques
indisponibles" (FR-005) sur la seule base de ce `null` — pas de champ booléen
séparé à vérifier en plus.

## Réponse — 404

Inchangée : `participation_id` inconnu → `NotFoundError`, comme aujourd'hui.
Cas supplémentaire côté front (pas un nouveau code HTTP) : si `course_id` de
l'URL front (`/courses/[id]/participations/[participationId]`) ne correspond
pas à `participation.course.id` renvoyé, le front traite comme "introuvable"
(`notFound()`), même si l'API a répondu 200 sur l'ID de participation seul.

## Rétrocompatibilité (Principe IV)

- Aucun champ existant n'est retiré, renommé, ni de sémantique modifiée.
- `GET /courses/{id}` (liste paginée des finishers) et `GET /participations`
  **ne déclenchent aucun calcul** : `stats` n'est calculé que pour la lecture
  d'**une** participation, jamais pour une page de finishers entière (coût :
  un classement complet par participation demandée, pas par ligne de tableau —
  cf. research.md §2 sur le choix de `list_for_course`).
- Le **champ**, lui, apparaît partout où `ParticipationOut` est sérialisé —
  liste paginée des finishers, `AthleteParticipationOut` de la fiche athlète —
  toujours à `null`. Ajout purement additif (Principe IV), mais à connaître
  pour les charges `page_size=all` : un `"stats": null` par ligne.
