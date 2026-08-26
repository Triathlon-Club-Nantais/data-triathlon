# Contrat — `/api/v1/admin/counter-scope`

Feature : [Portée des compteurs configurable](../spec.md) · Modèle : [data-model.md](../data-model.md)

Trois routes nouvelles. **Aucune route existante ne change** : le Principe IV n'est pas engagé.

Toutes exigent le pouvoir `counter_scope:manage` (`require_permission(P.COUNTER_SCOPE_MANAGE)`) et sont montées **derrière** `require_site_access` — rien ici ne participe à la pose du cookie de site, donc rien ne justifie une exemption (`api/v1/router.py`).

Le segment `{kind}` vaut `disciplines` ou `club-labels` — la forme URL des deux natures. La correspondance avec les valeurs stockées (`non_federal_discipline`, `tcn_club_label`) se fait dans le routeur, par une énumération : un `kind` inconnu rend `422`, jamais une liste vide.

---

## `GET /api/v1/admin/counter-scope`

Les deux listes d'un coup — l'écran les affiche ensemble, deux appels seraient deux allers-retours pour une page.

**200**

```json
{
  "disciplines": [
    {
      "id": 3,
      "value": "trail",
      "is_known": true,
      "created_at": "2026-08-26T10:12:00Z",
      "created_by": null
    }
  ],
  "club_labels": [
    {
      "id": 11,
      "value": "triathlon club nantais",
      "is_known": true,
      "created_at": "2026-08-26T10:12:00Z",
      "created_by": "Marie Dupont"
    }
  ]
}
```

| Champ | Sens |
| --- | --- |
| `value` | La chaîne sous sa forme comparable — c'est elle qui est comparée, donc c'est elle qu'on affiche |
| `is_known` | Pour une discipline : le slug appartient-il à `classify.CANONICAL_TYPES` ? Sert le badge d'avertissement de FR-011. Toujours `true` pour un libellé de club, qui n'a pas de nomenclature de référence |
| `created_by` | Nom d'affichage de l'auteur, ou `null` pour les entrées d'amorçage — l'écran rend `null` par « Configuration initiale » |

Les deux listes sont triées par `value` croissant : un ordre stable, et le seul qui aide à chercher une entrée à l'œil.

**403** si le pouvoir manque.

---

## `POST /api/v1/admin/counter-scope/{kind}`

**Corps**

```json
{ "value": "TRIATHLON  CLUB NANTAIS 44" }
```

**201** — l'entrée créée, même forme que dans la liste :

```json
{
  "id": 14,
  "value": "triathlon club nantais 44",
  "is_known": true,
  "created_at": "2026-08-26T14:02:11Z",
  "created_by": "Marie Dupont"
}
```

La valeur est normalisée avant écriture (`normalize_club` pour un libellé, minuscules et bords rognés pour une discipline). L'appelant reçoit la forme retenue, pas la sienne.

Une discipline hors nomenclature est **créée**, avec `is_known: false` — c'est le porteur de l'avertissement de FR-011, pas un refus (FR-004 : l'inconnu reste fédéral par défaut, et exclure une discipline pas encore importée est un geste légitime).

**Erreurs**

| Code | Cas | Message rendu (français, sérialisé dans `detail`) |
| --- | --- | --- |
| `422` | `kind` inconnu | forme standard FastAPI |
| `400` | Valeur vide une fois normalisée | « Le libellé ne peut pas être vide. » |
| `409` | Valeur déjà présente pour ce `kind` | « « triathlon club nantais » figure déjà dans la liste. » |

Le `409` s'appuie sur la contrainte `UNIQUE (kind, value)`, pas seulement sur une vérification préalable : deux écritures concurrentes ne peuvent pas créer un doublon.

Effets de bord, dans la même transaction : ligne dans `admin_action_log` (`counter_scope.entry_add`), puis **rechargement du registre après le commit**.

---

## `DELETE /api/v1/admin/counter-scope/{kind}/{entry_id}`

L'entrée est désignée par son `id`, jamais par sa valeur : un libellé porte des espaces, et le faire transiter par un segment d'URL est une source d'ennuis sans contrepartie.

**204** — pas de corps.

**Erreurs**

| Code | Cas | Message rendu |
| --- | --- | --- |
| `404` | `entry_id` inconnu, ou appartenant à l'autre `kind` | « Cette entrée n'existe pas. » |
| `409` | Retrait du **dernier** libellé de club (FR-010) | « Au moins un libellé de club doit rester : sans lui, aucun résultat ne serait compté comme résultat du club. » |

Le `409` ne vaut que pour `club-labels`. Vider la liste des disciplines exclues est légitime — tout devient fédéral, ce qui est cohérent, visible et réversible.

Effets de bord identiques au `POST` : journal (`counter_scope.entry_remove`), puis rechargement du registre après le commit.

---

## Effet observable, côté lecture

Aucun DTO existant ne change de forme. Ce qui change, c'est ce que ces DTO **valent** :

- `ParticipationOut.is_tcn` suit la liste des libellés — c'est le badge affiché.
- Tout endpoint portant `scope=club` ou `federal_only=true` suit les deux listes — ce sont les compteurs.

Les deux se prononcent depuis le même registre, donc restent d'accord pour toute configuration (FR-005). C'est ce qu'un test de contrat éprouve, sur une configuration **modifiée** et pas seulement sur celle livrée.

---

## Front — clés de requête

`lib/queries/admin.ts` gagne une clé de lecture et deux mutations. Chaque mutation invalide la clé de lecture, **et** les clés des écrans dont les compteurs dépendent de la configuration : après l'ajout d'un libellé, un tableau de bord déjà en cache afficherait encore les anciens compteurs. Le périmètre exact des clés à invalider se relève dans `lib/queries/keys.ts` au moment de l'implémentation.
