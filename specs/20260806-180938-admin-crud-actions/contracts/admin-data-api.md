# Contrat — API d'administration des données

**Base** : `/api/v1/admin` — Principe IV (versionné, additif).
**Module** : `backend/app/api/v1/admin_data.py`.

Sept routes — quatre gestes et trois lectures réservées — **sept gardes
individuelles**. Aucune garde de préfixe : le même préfixe `/admin` porte
`POST /admin/pending-providers`, qui est le signalement **anonyme** du site
public.

Toutes les erreurs sortent au format du dépôt : `{"detail": "<message
français>"}`, produit par `register_exception_handlers`.

Codes communs à toutes les routes :

| Code | Cas |
| --- | --- |
| `401` | pas de session — « Vous devez être connecté pour accéder à cette ressource. » |
| `403` | session valide, pouvoir absent — « Vous n'avez pas les droits nécessaires pour cette action. » Le message ne nomme pas le pouvoir exigé (FR-019 de #115). |
| `404` | entité inexistante |
| `422` | corps invalide : aucun champ, chaîne vide ou blanche, `null` sur un champ obligatoire, `event_type` hors nomenclature |

---

## 0.a Chiffrer l'impact d'une suppression *(lecture)*

```http
GET /api/v1/admin/courses/{course_id}/deletion-impact
```

**Pouvoir** : `courses:delete` — qui peut détruire peut mesurer.
**Succès** : `200`.

```json
{ "course_id": 12, "name": "Triathlon de Nantes", "participations": 412, "athletes": 37 }
```

`athletes` = les coureurs dont **toutes** les participations sont sur cette
épreuve, donc ceux qui disparaîtront par ricochet (FR-022). C'est ce que la
modale de confirmation annonce (FR-017, FR-026).

| Code | Cas |
| --- | --- |
| `200` | chiffré — **rien n'est modifié** |
| `404` | « Épreuve introuvable. » |

## 0.a-bis Lire une fiche coureur *(lecture)*

```http
GET /api/v1/admin/athletes/{athlete_id}
```

**Pouvoir** : `athletes:read` · **Succès** : `200`, un `AdminAthleteRead`.

Ajoutée en cours d'implémentation, et pas par confort : l'écran d'édition
atteint depuis un résultat ne dispose que de l'`AthleteBrief` de la
participation — **sans `birth_date`**. Ouvrir l'édition avec cette fiche
tronquée puis enregistrer effacerait une date que l'écran n'a jamais lue.

| Code | Cas |
| --- | --- |
| `200` | fiche complète |
| `404` | « Coureur introuvable. » |

## 0.b Rechercher un coureur *(lecture)*

```http
GET /api/v1/admin/athletes?search=<terme>&page=1&page_size=20
```

**Pouvoir** : `athletes:read` · **Succès** : `200`, liste d'`AdminAthleteRead`
enrichie du compte de résultats.

```json
[ { "id": 57, "nom": "Dupont", "prenom": "Jean", "birth_date": "1988-03-02",
    "gender": "M", "club": "Triathlon Club Nantais", "participations": 14 } ]
```

`search` filtre sur nom **et** prénom, comme la recherche publique. C'est la
seule route de la feature qui rend `birth_date` : la lecture publique
`GET /athletes` ne l'expose pas et **ne doit pas** l'exposer (FR-025).

| Code | Cas |
| --- | --- |
| `200` | y compris liste vide — une recherche sans résultat n'est pas une erreur |
| `422` | `page_size` hors bornes |

## 1. Supprimer une épreuve

```http
DELETE /api/v1/admin/courses/{course_id}
```

**Pouvoir** : `courses:delete` · **Succès** : `204`, sans corps.

Effets, dans une transaction unique :

1. suppression de l'épreuve et, par cascade ORM, de **toutes** ses
   participations (FR-002) ;
2. purge des fiches coureur qui perdent leur dernier résultat (FR-022) ;
3. écriture d'une entrée `course.delete` au journal (FR-012).

| Code | Cas |
| --- | --- |
| `204` | supprimée |
| `404` | « Épreuve introuvable. » |

> Une épreuve supprimée **revient** si son URL de chronométrage est réimportée.
> C'est le comportement de la chaîne d'import ; l'écran de confirmation ne doit
> pas laisser croire à un bannissement de l'URL.

---

## 2. Corriger une épreuve

```http
PATCH /api/v1/admin/courses/{course_id}
Content-Type: application/json
```

**Pouvoir** : `courses:write` · **Succès** : `200`, corps `CourseBrief`
(schéma existant, inchangé).

Requête — `AdminCourseUpdate`, tous les champs facultatifs :

```json
{
  "name": "Triathlon de Nantes",
  "event_date": "2026-05-17",
  "event_type": "triathlon-s",
  "is_relay": false
}
```

Sémantique **PATCH stricte** : seuls les champs **présents** sont écrits
(`model_dump(exclude_unset=True)`). `null` explicite sur `event_date` est une
mise à `NULL` valide et se distingue de l'absence du champ — mais `null` sur
`name`, `event_type` ou `is_relay` est un **422** : ces colonnes sont `NOT NULL`,
et leur `None` de schéma signifie « champ absent », pas « valeur nulle ».

`event_type` n'accepte que les slugs de `classify.CANONICAL_TYPES` : il pilote le
partage fédéral (`core/discipline.py`), les statistiques et le gabarit de splits,
et un `triathlon_m` fautif retirerait l'épreuve des filtres sans rien signaler.

| Code | Cas |
| --- | --- |
| `200` | corrigée |
| `404` | « Épreuve introuvable. » |
| `409` | l'identité visée est déjà prise — « Une épreuve porte déjà ce nom à cette date (#<id>). » |
| `422` | corps vide, `name` blanc ou `null`, `event_type` hors nomenclature, date invalide |

Aucun résultat n'est touché (FR-023).

---

## 3. Corriger un coureur

```http
PATCH /api/v1/admin/athletes/{athlete_id}
Content-Type: application/json
```

**Pouvoir** : `athletes:write` · **Succès** : `200`, corps `AdminAthleteRead`.

Requête — `AdminAthleteUpdate` :

```json
{ "nom": "Dupont", "prenom": "Jean", "birth_date": "1988-03-02" }
```

Réponse — `AdminAthleteRead` (nouveau DTO : `AthleteBrief` n'expose pas
`birth_date`, qui est pourtant le tiers de l'identité éditée) :

```json
{ "id": 42, "nom": "Dupont", "prenom": "Jean", "birth_date": "1988-03-02",
  "gender": "M", "club": "Triathlon Club Nantais" }
```

| Code | Cas |
| --- | --- |
| `200` | corrigé |
| `404` | « Coureur introuvable. » |
| `409` | « Un coureur porte déjà cette identité (#<id>). » |
| `422` | corps vide, `nom` ou `prenom` blanc ou `null`, date invalide |

`nom` et `prenom` restent en français : gelés par contrat public (Principe I).

---

## 4. Rattacher un résultat à un autre coureur

```http
POST /api/v1/admin/participations/{participation_id}/reassign
Content-Type: application/json
```

**Pouvoir** : `participations:reassign` · **Succès** : `200`, corps
`ParticipationOut` (schéma existant, inchangé).

Requête :

```json
{ "athlete_id": 42 }
```

Effets, dans une transaction unique : `athlete_id` réécrit, purge du coureur
d'origine s'il perd son dernier résultat (FR-022), entrée
`participation.reassign` au journal.

| Code | Cas |
| --- | --- |
| `200` | rattaché — y compris si le résultat était **déjà** sur ce coureur (sans effet, sans entrée de journal) |
| `404` | « Résultat introuvable. » ou « Coureur introuvable. » |
| `409` | « Ce coureur a déjà un résultat sur cette épreuve. » |

`POST` et non `PATCH` : ce n'est pas l'édition d'un champ du résultat, c'est un
geste nommé qui déplace un rattachement et peut détruire une fiche coureur au
passage.

---

## Inventaire des pouvoirs — impact sur `GET /admin/permissions`

Additif (Principe IV). La route rend deux groupes de plus et un pouvoir de plus
dans un groupe existant :

```json
[
  { "feature": "Épreuves", "permissions": [
      { "code": "courses:write",  "label": "Corriger une épreuve",  "description": "…" },
      { "code": "courses:delete", "label": "Supprimer une épreuve", "description": "…" } ] },
  { "feature": "Coureurs", "permissions": [
      { "code": "athletes:read",  "label": "Consulter les fiches coureur", "description": "…" },
      { "code": "athletes:write", "label": "Corriger un coureur", "description": "…" } ] },
  { "feature": "Résultats", "permissions": [
      { "code": "participations:write", "…": "…" },
      { "code": "participations:delete", "…": "…" },
      { "code": "participations:reassign", "label": "Rattacher un résultat", "description": "…" } ] }
]
```

Aucun rôle existant ne gagne ces pouvoirs automatiquement : un administrateur
les attribue via `PATCH /admin/roles/{id}` (#115). Un rôle `is_superuser` les
porte de fait.

## Ce que le contrat **n'**ajoute **pas**

- Aucune route de lecture du journal d'audit — hors périmètre (spec §Hors
  périmètre).
- Aucune liste d'épreuves : l'écran consomme `GET /courses`, inchangé.
- **Aucune modification de route existante.** En particulier `GET /athletes` et
  `GET /athletes/{id}` ne gagnent pas `birth_date` : c'est le point de FR-025,
  et l'y ajouter viderait `athletes:read` de son objet.
