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

**`DELETE /admin/courses` et `DELETE /admin/participations` rendent un corps
depuis #501** : `200` avec le décompte réel (`{courses_deleted, athletes_purged}`
et `{participations_deleted, athletes_purged, courses_reset}` respectivement),
plus `204` vide — la purge annonçait son ampleur avant le geste mais rendait un
succès muet, sans confirmer ce qu'elle avait détruit.

## Journal d'administration, en lecture (#501)

`GET /admin/action-log` (`admin_log:read`) rend les dernières entrées du
journal d'audit (`AdminActionLog`), paginées (`page`, `page_size`, défaut
20/max 100), la plus récente d'abord. Pouvoir dédié plutôt que réutilisation
de `courses:delete`/`participations:wipe_all` : le journal couvre des entités
que ces pouvoirs ne gardent pas. `payload` est redacté de `birth_date` quand
présent — voir `admin_action_log.py._redacted_payload`.

**Un geste correctif vit hors de ce tableau** : `DELETE /participations/{id}`,
gardée par `participations:delete`, est restée dans `participations.py` — chemin,
verbe et `204` sont publiés, et les déplacer sous `/admin/` serait la
« modification silencieuse de v1 » que le Principe IV proscrit. Depuis #439 elle
délègue au service et laisse une entrée `participation.delete` au journal : la
seule trace qui survive à ce qu'elle décrit. Le journal enregistre l'identité du
résultat effacé (épreuve, coureur, dossard, temps), pas seulement son
identifiant, qui ne désigne plus rien.

Sept points à ne pas défaire :

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
- **`PATCH /admin/athletes/{id}` porte le `club` actuel** en plus du triplet
  d'identité (#439). Il n'entre **pas** dans `uq_athlete_identity` : deux
  homonymes de clubs différents restent la même personne. « Sans club » s'écrit
  `null` ; la chaîne vide est refusée (422), sans quoi elle se rangerait comme un
  libellé de club à part entière.
- **La correction manuelle du club prime sur tout import ultérieur.** Le
  chronométreur d'une course d'il y a trois ans annonce le club de l'époque, et
  le laisser gagner ramènerait la correction à chaque réimport. D'où
  `athletes.club_locked`, posé par le service quand le club écrit **diffère** de
  celui en base — sur le geste, pas sur la présence du champ, sinon un
  enregistrement du formulaire prérempli gèlerait un libellé que personne n'a
  corrigé. `athlete_repository.resolve` le lit avant de suivre l'import. Le
  drapeau n'est **exposé par aucune réponse** : ni `AthleteOut`, ni
  `AdminAthleteOut`, ni `AthleteBrief` — c'est une mécanique interne, pas une
  donnée du coureur, et un test l'interdit.
- **Corriger le club actuel ne touche aucun club de résultat.**
  `participations.club` garde celui de l'époque de sa course : c'est ce qui rend
  l'historique lisible, et le recalculer effacerait la seule trace du club porté
  ce jour-là.
- **La réattribution exige `participations:reassign` *et* `athletes:read`**, à
  l'affichage comme au parcours (#439). Le sélecteur de coureur cible lit
  `GET /admin/athletes?search=`, gardée par `athletes:read` et seule à rendre la
  date de naissance qui départage deux homonymes du même club. Annoncée sur le
  seul pouvoir de réattribution, l'action s'ouvre sur une liste que rien ne peut
  remplir — un 403 muet. Le couplage vaut pour les **deux** écrans : la page
  publique du coureur et `CourseParticipationsDialog` du back-office, où il
  corrige un bug latent.

Spec, plan et tâches : `specs/20260806-180938-admin-crud-actions/`, puis
`specs/20260820-095442-page-athlete-actions-admin/` pour les gestes portés par la
page publique du coureur (#439).

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

## Portée des compteurs (#95)

Les deux ensembles qui décident de ce que l'application compte — les disciplines
exclues des compteurs et les libellés reconnus comme libellés du club — vivaient
en dur dans `core/discipline.py` et `core/club.py`. Ils sont en base, éditables
sous `counter_scope:manage`.

| Route | Effet |
| --- | --- |
| `GET /admin/counter-scope` | Les **deux** listes d'un coup — l'écran les affiche ensemble, deux appels seraient deux allers-retours pour une page. Triées par valeur. |
| `POST /admin/counter-scope/{kind}` | Déclare une entrée. `201` avec l'entrée créée. |
| `DELETE /admin/counter-scope/{kind}/{entry_id}` | Retire une entrée. `204`. |

`{kind}` vaut `disciplines` ou `club-labels` — la forme URL des deux natures,
distincte de ce qui est stocké (`non_federal_discipline`, `tcn_club_label`) :
l'URL est un contrat lu par des humains, la colonne un jeton technique. Une
nature inconnue rend `422`, jamais une liste vide.

**La valeur rendue est la forme retenue, pas la saisie.** Un libellé de club
passe par `normalize_club`, la **même** fonction que `is_tcn` et son miroir SQL
— une normalisation propre à l'écriture laisserait enregistrer un libellé que le
prédicat ne retrouverait jamais : déclaré, invisible, sans erreur. Une discipline
se contente des minuscules et des bords rognés.

**Deux refus, dissymétriques à dessein.**

- `409` sur le retrait du **dernier** libellé de club : sans aucun libellé, plus
  rien n'est compté comme résultat du club et tous les compteurs du club tombent
  à zéro — sans erreur, et en ressemblant à un tableau de bord légitimement vide.
- **Aucun refus** sur le vidage de la liste des disciplines : tout devient
  fédéral, ce qui est cohérent, visible et réversible.

`409` également sur un doublon, adossé à la contrainte `UNIQUE (kind, value)` et
pas seulement à une vérification préalable : deux administrateurs qui écrivent en
même temps ne peuvent pas créer de doublon. `400` sur une valeur vide une fois
normalisée.

**Une discipline hors nomenclature est acceptée**, avec `is_known: false` — pas
refusée. Exclure une discipline pas encore importée est un geste légitime, et le
principe posé en #76 tient : une discipline inconnue reste fédérale par défaut,
c'est la liste d'exclusion qui décide. `is_known` vaut toujours `true` pour un
libellé de club, qui n'a pas de nomenclature de référence.

**L'écriture prend effet sans redéploiement ni redémarrage** : le routeur
commite, journalise (`counter_scope.entry_add` / `counter_scope.entry_remove`),
puis recharge le registre en mémoire (`core/counter_scope.py`). Recharger
**après** le commit et pas avant : sinon la configuration exposée serait celle
d'une transaction que rien ne garantit d'aboutir.

Aucun DTO existant ne change de forme. Ce qui change, c'est ce que ces DTO
**valent** : `ParticipationOut.is_tcn` suit la liste des libellés, tout endpoint
portant `scope=club` ou `federal_only=true` suit les deux. Les deux se
prononcent depuis le même registre, donc restent d'accord pour n'importe quelle
configuration — ce que `tests/test_repositories/test_club_filter.py` éprouve sur
une configuration **modifiée**, pas seulement sur celle livrée.

Conception : `specs/20260826-154613-portee-compteurs-configurable/`.
