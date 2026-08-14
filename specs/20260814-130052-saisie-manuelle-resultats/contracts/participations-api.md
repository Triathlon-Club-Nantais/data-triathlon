# Contrat d'API — saisie manuelle des résultats (#270)

**Feature** : `20260814-130052-saisie-manuelle-resultats` · **Date** : 2026-08-14

Aucune route nouvelle, aucune route retirée. Deux schémas gagnent des champs, et
cinq chemins de lecture changent de **contenu** sans changer de forme.

Le Principe IV est respecté : aucun champ retiré, aucune sémantique de paramètre
inversée, aucun code de retour modifié. Justification détaillée en
[research.md](../research.md) D9.

---

## 1. `POST /api/v1/participations` — entrée

**Garde retirée, corrigé le 2026-08-14.** La route était protégée par
`participations:write`, fermée depuis #115. Vérification manuelle par le
mainteneur : ce contrôle d'accès bloquait le cas d'usage central du
formulaire — un membre sans compte ne pouvait plus rien saisir. La route
redevient **publique** ; `participations:write` est retiré du catalogue
(`app/core/permissions.py`) puisqu'il ne gardait plus rien. `DELETE
/participations/{id}` (`participations:delete`), destructif, reste gardé,
inchangé. FR-026.

### Champs ajoutés à `ParticipationCreate`

| Champ | Type | Défaut | Exigence |
| --- | --- | --- | --- |
| `status` | `str` | `""` | FR-023 — `finisher`, `DNF` ou `DNS` |
| `team_name` | `str` | `""` | FR-013 |
| `evidence_url` | `str` | `""` | FR-014 |
| `format_label` | `str` | `""` | FR-008 — précision du format « Autre » |
| `distance_km` | `float \| None` | `None` | FR-009 — distance totale des disciplines sans format normalisé. **Gap découvert à l'implémentation** : absent du contrat initial, alors que `Course.distance_km` existe déjà et que `ScrapedResult.distance_km` était déjà présent côté scrapers — seul le pont `ParticipationCreate → ScrapedResult` manquait. |

`format_label` sort aussi sur `CourseBrief` (sortie), ajouté au même titre —
propriété de l'épreuve, pas de la participation.

`status` vide conserve le comportement actuel : `mapping.derive_status` retombe
sur son heuristique (`finisher` si temps total, sinon `DNF`). Un statut transmis
prime — c'est déjà ce que fait la fonction, elle n'est pas modifiée.

### Champs **délibérément absents** de l'entrée

| Champ | Pourquoi |
| --- | --- |
| `is_pending_validation` | Forcé à `True` par la route. L'exposer laisserait tout porteur de `participations:write` publier un résultat comme déjà vérifié, ce qui viderait FR-016 de son sens. |

### Champs conservés mais que le formulaire cesse d'envoyer

`gender`, `club`, `category` restent dans le schéma — les scrapers les
renseignent (FR-003) et les retirer serait le « champ retiré » que le Principe IV
proscrit. Seul le **formulaire** cesse de les proposer.

`source_url` reste dans le schéma pour la même raison, mais le formulaire manuel
ne l'envoie plus : le lien saisi part désormais dans `evidence_url`
(research.md D5). Une épreuve créée à la main n'a donc aucune `CourseSource`,
comportement déjà documenté et mesuré à 0 épreuve concernée sur 95.

### Réponse

`201` avec un `ParticipationOut` portant `is_pending_validation: true`.
Codes d'erreur inchangés — notamment le `DuplicateError` sur dossard déjà pris.

---

## 2. `ParticipationOut` — sortie

Trois champs ajoutés, servis par **toutes** les routes qui rendent ce schéma
(`GET /participations`, `GET /participations/{id}`, `GET /courses/{id}`,
`GET /athletes/{id}`).

| Champ | Type | Défaut | Exigence |
| --- | --- | --- | --- |
| `is_pending_validation` | `bool` | `false` | FR-020 |
| `team_name` | `str \| None` | `null` | FR-013 |
| `evidence_url` | `str \| None` | `null` | FR-014 |

`format_label` sort sur `CourseBrief`, pas ici : c'est une propriété de
l'épreuve.

**`is_pending_validation` est le champ que #271 consommera.** Il est exposé dès
maintenant pour que la file de validation n'exige aucun second changement de
contrat.

---

## 3. Chemins de lecture dont le contenu change

Ces cinq chemins **excluent** désormais les résultats en attente de validation
(FR-021). Leur forme de réponse est strictement inchangée.

| Route | Ce qu'elle sert | Fonction filtrée |
| --- | --- | --- |
| `GET /participations` | page `/resultats` | `_apply_filters` |
| `GET /events` | page épreuves, carte | `_apply_filters` (via `_grouped_events_query`) |
| `GET /stats` | tableau de bord, page club, **podiums** | `for_stats` |
| `GET /courses/{id}` | classement paginé d'une épreuve | `list_page_for_course` |
| `GET /courses/{id}/summary` | synthèse d'épreuve | `summary_rows_for_course` |

**Pas de paramètre `include_pending`.** L'exclusion est un invariant, pas une
préférence d'affichage : la rendre optionnelle permettrait à n'importe quel
appelant public de réinjecter des données non vérifiées dans les agrégats. Cf. la
justification du Principe V dans le Complexity Tracking du plan.

### Chemin de lecture **non** filtré

| Route | Pourquoi |
| --- | --- |
| `GET /athletes/{id}` | La fiche athlète **est** la surface d'affichage voulue (FR-019). Les participations y sortent avec `is_pending_validation: true`, à charge du front de les marquer. |

`course_finishers`, porté par `AthleteParticipationOut` sur cette même route, est
en revanche calculé par `finishers_count_by_group`, qui **filtre** : la taille du
classement annoncée reste celle du classement publié.

---

## 4. Contrat interne — la clause d'exclusion

Pas une API HTTP, mais un contrat que le reste du code doit respecter, au même
titre que `core/club.tcn_clause` et `core/discipline.federal_clause`.

```python
# app/core/validation.py

def is_pending(participation) -> bool: ...
def validated_clause(column): ...   # clause SQLAlchemy : la ligne est vérifiée
```

**Règle** : toute nouvelle requête qui alimente un affichage public agrégé
applique `validated_clause`. Les onze fonctions de
`participation_repository.py` concernées — cinq qui filtrent, six qui ne filtrent
pas — sont énumérées et justifiées en research.md D2, et un test verrouille la
répartition.

---

## 5. Front — contrat de types

`frontend/lib/types.ts` suit la sortie :

```ts
// Participation
is_pending_validation: boolean;
team_name: string | null;
evidence_url: string | null;
```

Aucun type n'est retiré. `gender`, `club` et `category` restent typés : les
résultats importés les portent toujours.
