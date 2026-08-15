# Administration : révocation, gestes correctifs, doublons

Renvoyé depuis `backend/app/api/AGENTS.md`.

## Révocation d'urgence des sessions (#169)

`POST /admin/sessions/revoke` (`sessions:revoke`), corps facultatif, rend
`{"sessions": N, "accounts": M}` — deux chiffres qui ne comptent
que ce qui était **vivant** (non expiré, compte actif), alors que la suppression,
elle, emporte tout. L'écart est délibéré : supprimer une ligne morte est de
l'hygiène gratuite, l'annoncer comme « fermée » serait un mensonge, et faute
d'ordonnanceur une base réelle en est pleine. Trois points :

- **Une ressource, deux portées**, et la seconde n'est pas un doublon du
  retrait d'adresse. Corps absent → tout ; `{"email": …}` → les comptes portant
  cette adresse, **tous** (`users.email` n'est pas unique, FR-003 — en épargner
  un sous incident serait l'erreur coûteuse). Retirer une adresse (#170) ferme
  par la jointure mais **n'efface aucune ligne**, donc une réinscription dans la
  fenêtre de TTL ressuscite les jetons ; ici les lignes partent et le compte
  reste actif. Une adresse inconnue est un **succès sans effet** : l'écran ne
  propose que des adresses de sa propre liste, il n'y a pas de faute de frappe
  possible, là où la CLI la refuse.
- **Elle ferme la session de l'appelant**, et ce n'est pas un effet de bord à
  corriger : sous fuite, son jeton est suspect comme les autres. L'écran
  l'annonce avant le geste et renvoie vers `/login`.
- **Idempotente** : « 0 session fermée » est un succès. Distinguer un geste utile
  d'un geste dans le vide appartient au compte rendu, pas au code de statut.

Le jumeau hors ligne est `python -m app.cli revoke-sessions`, et la redondance
est le but — voir `app/cli/AGENTS.md`.

## Administration des données (#117)

`admin_data.py` porte dix ressources : six gestes correctifs et quatre lectures
réservées (onze routes — la recherche de coureurs et la fiche unique partagent
une ligne). Elles vivent sous `/admin/`, et **chacune porte sa garde** — jamais le
préfixe, pour la raison rappelée dans `backend/app/api/AGENTS.md` (§ Protéger une
ressource).

| Ressource | Pouvoir |
| --- | --- |
| `GET /admin/courses/{id}/deletion-impact` | `courses:delete` |
| `DELETE /admin/courses/{id}` | `courses:delete` |
| `PATCH /admin/courses/{id}` | `courses:write` |
| `GET /admin/courses/wipe-impact` | `courses:wipe_all` |
| `DELETE /admin/courses` | `courses:wipe_all` |
| `GET /admin/participations/wipe-impact` | `participations:wipe_all` |
| `DELETE /admin/participations` | `participations:wipe_all` |
| `GET /admin/athletes` (recherche) et `GET /admin/athletes/{id}` | `athletes:read` |
| `PATCH /admin/athletes/{id}` | `athletes:write` |
| `POST /admin/participations/{id}/reassign` | `participations:reassign` |

Quatre points à ne pas défaire :

- **L'ampleur annoncée est l'ampleur réelle.** Supprimer une épreuve emporte ses
  résultats *et* les fiches coureur qui n'ont couru qu'elle. `deletion-impact` et
  la purge appellent la **même** fonction (`athlete_repository.only_on_course`) :
  c'est ce qui rend l'égalité structurelle plutôt que surveillée. Un test la
  vérifie sur une même épreuve.
- **La cascade est ORM, pas DB.** `Course.participations` porte
  `cascade="all, delete-orphan"` ; aucun `ondelete` n'a été ajouté, et c'est
  délibéré — `database.py` n'émet pas `PRAGMA foreign_keys=ON`, la contrainte
  serait inerte en SQLite (dev et tests) et active en PostgreSQL.
- **`birth_date` ne sort que par `athletes:read`.** C'est la seule donnée
  personnelle fermée du site, et l'unique raison d'être de ce pouvoir. Ajouter le
  champ à `AthleteBrief` (lecture publique) le viderait de son objet ; un test de
  `test_athletes_api.py` l'interdit.
- **Le journal ne consigne que ce qui a changé.** Rattacher un résultat au
  coureur qui le porte déjà réussit sans écrire d'entrée : une demande sans effet
  n'est pas un geste. Un refus, lui, n'écrit rien **et** ne modifie rien — le
  service `flush`, la route `commit`.

Spec, plan et tâches : `specs/20260806-180938-admin-crud-actions/`.

## Doublons suspects (#288)

`admin_course_duplicates.py` — une seule ressource,
`GET /admin/courses/duplicates`, gardée par `courses:sources` : la liste est la
porte d'entrée de la fusion (#289) et de l'arbitrage entre chronométreurs
(#285), pas une correction d'identité. Ni pagination ni filtre.

Le router est mince à l'extrême ; **tout le jugement est dans
`services/course_duplicates.py`**, et c'est là qu'il faut lire avant de toucher
au réglage : les **deux seuils** y sont documentés côte à côte — celui de #277,
qui rapproche **automatiquement** à l'import, et celui d'ici, délibérément plus
large parce qu'un humain relit. Les motifs sont un ensemble **fermé** de trois,
chacun rattaché à un cas de terrain mesuré ; les élargir se tranche en
re-sondant, pas en ajoutant une tolérance
(`docs/superpowers/specs/2026-08-12-sources-multiples-epreuve-sondage.md`).
