# Phase 1 — Data Model

Aucune nouvelle table, aucune migration : cette feature ajoute des champs
**dérivés à la volée** à un schéma de sortie existant, à partir d'une colonne
(`Participation.status`) déjà en base et déjà lue par `stats_service`.

## `CourseSummary` (extension)

Synthèse d'une épreuve entière (`backend/app/schemas/course.py`), déjà
consommée par `/courses/{id}/summary` et rendue sur `/courses/[id]`.

| Champ | Type | Statut | Description |
|---|---|---|---|
| `total` | `int` | inchangé | Nombre total de participants de l'épreuve. |
| `finishers` | `int` | inchangé | Participants au statut « terminé ». |
| `non_finishers` | `int` | inchangé | Somme des trois statuts ci-dessous — **conservé tel quel**, aucun appelant ne doit perdre cette valeur (Principe IV). |
| `dnf` | `int` | **nouveau** | Participants au statut abandon (`DNF`). |
| `dns` | `int` | **nouveau** | Participants au statut non-partant (`DNS`) — jamais parti. |
| `dsq` | `int` | **nouveau** | Participants au statut disqualifié (`DSQ`). |
| `unknown` | `int` | inchangé | Statut vide ou non reconnu (ni finisher, ni DNF/DNS/DSQ). |

**Invariant** : `total == finishers + non_finishers + unknown` (déjà vrai
aujourd'hui) et, avec cette feature, `non_finishers == dnf + dns + dsq`.

**Validation rule** : les trois nouveaux champs sont des entiers `>= 0` ; une
épreuve sans aucun participant d'une catégorie porte `0` pour cette catégorie
(pas `null`) — c'est ce zéro que le front utilise pour décider de masquer la
pastille correspondante, comme il le fait déjà pour `unknown`.

## Pas d'entité nouvelle

Le statut d'un participant (`Participation.status`, valeurs `finisher` / `DNF`
/ `DNS` / `DSQ` / vide) existe déjà et n'est pas modifié par cette feature —
seule son agrégation en sortie de `stats_service.course_summary` change.
