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

`admin_data.py` porte quatorze ressources : neuf gestes correctifs et cinq
lectures réservées (quinze routes — la recherche de coureurs et la fiche unique
partagent une ligne). Elles vivent sous `/admin/`, et **chacune porte sa garde** — jamais le
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
| `PUT /admin/participations/{id}/teammates` (#894) | `participations:reassign` |
| `GET /admin/athletes/{id}/season-quota` (#709) | `athletes:season_validate` |
| `POST /admin/athletes/{id}/season-validations` (#709) | `athletes:season_validate` |
| `DELETE /admin/athletes/{id}/season-validations/{season}` (#709) | `athletes:season_validate` |

**Les trois routes de saison portent la validation de saison** (#709) : le quota
indicatif (trois épreuves validées, un bénévolat accepté, saison déjà validée ou
non), la validation et la dévalidation. La saison est bornée à 2000-2100 (#1054).
Contrat détaillé : `specs/20260828-134141-club-season-counters/contracts/api.md`.

**`PUT .../teammates` attribue un relais à ses équipiers** (#894) : le corps est
la composition voulue, 2 à 8 entrées `{athlete_id}` ou `{athlete_name,
athlete_firstname}` (un nom inconnu crée la fiche, un nom connu la réutilise).
Tout ou rien, rejouable sans effet ni journal ; 409 si un équipier est déjà
classé sur l'épreuve, 400 si le résultat n'est pas un relais, 422 sur un corps
invalide. La réponse `ParticipationOut` gagne `teammates` (liste vide hors
relais attribué), et `reassign` sur un relais attribué **vide** la composition.
Même couple de pouvoirs que la réattribution côté écran. Spec :
`specs/20260924-171341-relay-multi-athletes/`.

**`DELETE /admin/courses` et `DELETE /admin/participations` rendent un corps
depuis #501** : `200` avec le décompte réel (`{courses_deleted, athletes_purged}`
et `{participations_deleted, athletes_purged, courses_reset}` respectivement),
plus `204` vide — la purge annonçait son ampleur avant le geste mais rendait un
succès muet, sans confirmer ce qu'elle avait détruit.

## Fusion de deux fiches d'athlète (#908)

| Route | Pouvoir | Effet |
| --- | --- | --- |
| `GET /admin/athletes/{id}/merge-impact?absorbed_id=` | `athletes:write` **et** `athletes:read` | Aperçu, sans écriture : les deux fiches avec leur date de naissance (d'où le second pouvoir, FR-025 de #117), ce qui serait déplacé (`moves`), `alias_added`, et `blocking_reason` / `blocking_label` si la fusion serait refusée. |
| `POST /admin/athletes/{id}/merge` `{absorbed_id}` | `athletes:write` | Absorbe `absorbed_id` dans `{id}` ; rend la fiche conservée. 404 fiche inconnue, 409 refus (`code` = la raison) ou fiche en cours d'import. |

- **Tout passe sur la fiche conservée** : résultats, liens d'équipier de relais,
  actions bénévoles, validations de saison (une saison validée des deux côtés
  n'en garde qu'une), comptes membres, variantes de graphie et paires écartées
  depuis la revue (le jugement « deux personnes » suit la personne ; la paire
  des deux fiches fusionnées tombe). Elle prend aussi ce qu'elle n'a pas :
  club (un club verrouillé par un admin prime), genre, date de naissance.
- **Refus**, avec le même prédicat dans l'aperçu et l'acte : `same_athlete`,
  `distinct_users` (deux comptes membres), `same_course_bibs` (un résultat
  chacune sur une même épreuve individuelle), `same_participation` (un même
  relais), `distinct_birth_dates`, `team_and_person` (une fiche d'équipe,
  libellé à `&`, `/`, `+` ou « et », face à une fiche de personne, #1192).
  `same_course_bibs` vaut aussi pour deux
  résultats sans dossard sur une même épreuve individuelle : on ne court pas
  deux fois la même course.
- **Seule une fiche principale lègue sa graphie** : un homonyme distingué
  absorbé n'ajoute pas de variante, sa clé appartenant à une autre personne.
- **La graphie absorbée devient une variante** de la fiche conservée
  (`athlete_aliases`) : l'import la résout désormais comme elle, équipiers de
  relais compris, et le rescrape de l'épreuve d'origine ne recrée pas la faute.
  Une variante suit la même garde qu'un repli : deux dossards d'une épreuve
  individuelle, l'un sous la graphie conservée et l'autre sous la variante, restent
  deux personnes.
- **Concurrence** : la fusion verrouille les deux fiches (`FOR UPDATE`) après
  tout import qui les a résolues, au plus 5 s, puis répond 409 « fiche en cours
  d'import ».
- **Journal** : `athlete.merge` sur la fiche conservée, avec l'identité de
  l'absorbée (sans date de naissance) et le décompte des éléments déplacés.
- **Renommage en conflit** : le 409 de `PATCH /admin/athletes/{id}` porte en plus
  `conflicting_athlete_id`, pour proposer la fusion. Une variante compte comme
  l'identité de sa fiche.

## Variantes d'identité d'une fiche (#1242)

| Route | Pouvoir | Effet |
| --- | --- | --- |
| `GET /admin/athletes/{id}/aliases` | `athletes:write` | `{aliases: [{id, last_name_key, first_name_key, created_at}]}`, les graphies que l'import rattache à la fiche. 404 fiche inconnue. |
| `DELETE /admin/athletes/{id}/aliases/{alias_id}` | `athletes:write` | Retire la variante (204) : l'import ne range plus cette graphie sur la fiche, les résultats déjà rattachés restent. 404 variante inconnue ou d'une autre fiche. Journal `athlete.alias_remove`, avec les deux clés. |

La fiche athlète les liste sous l'ancre `#variantes` (rien n'est rendu sans
variante) ; la carte `alias_collision` de `/admin/identites` y renvoie.

## Séparer une fiche (#1209)

`POST /admin/athletes/{id}/detach` (`athletes:write` et `participations:reassign`),
corps `{"participation_ids": [...]}`. Les résultats choisis partent sur une
nouvelle fiche d'homonyme (même nom, rang suivant), chacun par le rattachement
admin (verrouillé contre les imports). La paire est enregistrée comme distincte,
pour que `reconcile-athletes` ne la refusionne pas. Rend la nouvelle fiche (201).
Refus : liste vide, résultat d'une autre fiche, fiche qui serait vidée (400),
fiche ou résultat inconnu (404), corps mal formé, `participation_ids` absent ou
non entier (422), deux résultats d'une même épreuve (409). Journal : `athlete.detach`.

## Revue d'identité des athlètes (#908)

| Route | Pouvoir | Effet |
| --- | --- | --- |
| `GET /admin/identity-review` | `athletes:write` | Les cas à trancher, sans pagination, dans un ordre stable (motif, puis plus petit id). |
| `GET /admin/identity-review/count` | `athletes:write` | `{total}`. Prévu pour une pastille de la nav, que le front n'affiche pas encore : son coût est à mesurer en production d'abord (#1146). |
| `POST /admin/identity-review/ignore` `{athlete_id_a, athlete_id_b}` | `athletes:write` | Écarte une paire jugée distincte (201) ; 400 même fiche, 404 fiche inconnue, 409 déjà écartée. Journal `athlete_identity.ignore`. |
| `POST /admin/identity-review/confirm-club` `{athlete_id, club_key}` | `athletes:write` | Confirme un club pour une fiche (201, `{athlete_id, club_key, confirmed_at}`) : elle n'est plus signalée pour lui et l'import y rattache les résultats publiés sous ce club. 400 clé vide ou club que la fiche ne porte pas, 404 fiche inconnue, 409 déjà confirmé. Journal `athlete_identity.confirm_club`. |
| `GET /admin/identity-review/ignored` | `athletes:write` | `{pairs: [{id, ignored_at, automatic, athletes: [{id, nom, prenom}×2]}]}`, la plus récente d'abord (#1243). `automatic` : paire posée par l'import, sans auteur. Une paire posée par la séparation porte l'admin qui l'a faite et ne s'en distingue pas. |
| `DELETE /admin/identity-review/ignored/{id}` | `athletes:write` | Annule une mise à l'écart (204). 404 inconnue. Journal `athlete_identity.unignore`. **Ce n'est pas un simple retour en revue** : deux fiches de même clé d'identité, ou que la reprise fusionnerait d'elle-même (`recovery_would_merge`), seront fusionnées par la prochaine reprise (`reconcile-athletes`), sans retour possible, et n'apparaissent pas dans la revue entre-temps. Les autres reviennent dans la revue si un motif les retient. L'écran demande une confirmation qui le dit. |
| `GET /admin/identity-review/confirmed-clubs` | `athletes:write` | `{clubs: [{id, athlete_id, nom, prenom, club_key, confirmed_at}]}`, le plus récent d'abord (#1243). |
| `DELETE /admin/identity-review/confirmed-clubs/{id}` | `athletes:write` | Annule une confirmation (204) : la fiche est de nouveau signalée pour ce club. Les résultats déjà rattachés par l'import sous ce club restent sur la fiche. 404 inconnue. Journal `athlete_identity.unconfirm_club`. |

`/admin/identity-review` et non `/admin/athletes/identity-review` : la route
`/admin/athletes/{athlete_id}` capterait le segment et rendrait 422.

Six motifs, calculés à la volée depuis les données (aucune table de cas) :

- `same_course_bibs` : une fiche portant deux dossards distincts sur une même
  épreuve individuelle, quand la fiche ou l'un de ces résultats relève du club
  (deux lignes sans dossard ne prouvent pas deux coureurs). Ne s'écarte pas : il
  se règle par réattribution.
- `club_homonym` : une **paire** d'homonymes distingués dont l'un relève du club
  (hors club, la mention `homonyms_created` du rapport d'import suffit) ; trois
  homonymes du club donnent un cas par paire, chacun écartable.
- `swapped`, `concatenated` : nom et prénom inversés, ou nom complet face à une
  fiche découpée, **seulement** quand la reprise ne les fusionnerait pas d'elle-même
  (`recovery_would_merge` : même club ou même genre, renseigné des deux côtés,
  jamais une même épreuve, porteur ou équipier, et aucun refus de la fusion :
  deux comptes membres, un même résultat, deux dates de naissance). Une clé qui
  porte un chiffre (équipe numérotée, `?DOSSARD #n`, `Anonyme …`) n'est pas une
  personne et n'y figure pas.
- `alias_collision` : une fiche principale recréée sur une graphie qu'une fusion
  avait rattachée à une autre.
- `multi_club` : une fiche de membre TCN dont les résultats individuels validés
  portent un club significatif (ni vide, ni ville, ni libellé de la portée) non
  confirmé, à côté d'un autre club. Le champ `clubs` (`club`, `club_key`,
  `results`) liste les clubs à vérifier ; chacun se confirme par la route
  ci-dessus, ou se sépare par `POST /admin/athletes/{id}/detach`.

Une paire n'est listée qu'une fois, sous le premier motif qui la retient.
Chaque cas porte les fiches (identité, club, genre, catégories, nombre de
résultats, rang d'homonyme) et les épreuves en conflit avec leurs lignes. Le
compte (`/count`) ne charge pas ce détail : quatre requêtes de faits par paire
pour toutes les paires, sans les résultats complets.

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
  d'identité (#439). Le doublon se vérifie sur la clé normalisée du nom et du
  prénom (#907), la date de naissance n'y entre plus (#900) ; une fiche renommée
  vers une clé neuve en devient la fiche principale. Le club n'entre **pas** dans `uq_athlete_identity` : deux
  homonymes de clubs différents restent la même personne. « Sans club » s'écrit
  `null` ; la chaîne vide est refusée (422), sans quoi elle se rangerait comme un
  libellé de club à part entière.
- **Le rapport d'import signale les identités ambiguës** (#908) : la clé
  `ambiguous_identities` (`[{course_id, athlete_id, candidate_ids}]`, présente sur
  tous les chemins de `done`, vide par défaut) liste les lignes dont le repli
  d'identité (nom et prénom inversés, nom complet face à une fiche découpée) a
  trouvé plusieurs fiches : une fiche neuve est créée, rien n'est deviné, et
  `candidate_ids` donne les fiches entre lesquelles l'admin tranche.
- **Deux dossards d'un même nom sur une épreuve individuelle sont deux personnes**
  (#967). Le second reçoit une fiche d'homonyme distinguée (`homonym_rank` ≥ 1),
  et le rapport d'import le liste dans `homonyms_created`
  (`[{course_id, bib, athlete_id, homonym_of}]`, présent sur tous les chemins de
  `done`). Vaut pour un dossard neuf comme pour une correction de nom de la
  source. Seul compte un autre dossard que ce scrape publie encore sous le même
  nom : un dossard périmé ou passé à un autre coureur ne fait pas d'homonyme.
  Un relais n'est pas concerné. L'import ne vise ensuite plus jamais la fiche
  d'homonyme par l'identité : un nouveau résultat sans conflit va à la fiche
  principale, et seul un geste admin en donne à l'homonyme. Limites connues :
  le premier dossard rencontré garde la fiche principale, quel que soit le
  coureur ; un homonyme dont la source corrige ensuite le nom peut rester vide
  jusqu'à la purge des orphelins ; `rescrape-db` et `import-sheet` ne reprennent
  pas encore `homonyms_created` dans leur rapport.
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

## Droit d'opposition (#334)

`admin_oppositions.py` : trois routes gardées par `oppositions:manage`.
`GET /admin/oppositions` liste les oppositions (dates de demande et
d'application, délai, `overdue` au-delà de 30 jours, auteur, nombre de
résultats anonymisés), **sans aucun nom** : la base n'en garde pas.
`POST /admin/oppositions/preview` chiffre ce qu'une application toucherait,
homonymes compris, sans rien écrire. `POST /admin/oppositions` applique
(`201`, ou `200` sur une identité déjà opposée, réappliquée sur la même ligne).
L'identité est une fiche (`athlete_id`) **ou** un nom et un prénom, jamais les
deux (`422`). Contrat : `specs/20261001-181344-athlete-opposition/contracts/`.

Ce que l'application fait, et où : `services/opposition_service.py`. Le filtre
des imports vit dans `import_persistence._Persister` ; la saisie manuelle et la
composition d'équipe refusent l'identité (`OpposedIdentityError`, `422`).

## Doublons suspects (#288)

`admin_course_duplicates.py` — cinq routes, toutes gardées par
`courses:sources` : `GET /admin/courses/duplicates` (la liste, ni pagination
ni filtre), `GET .../count` (#726, la pastille de nav),
`POST .../ignore` (#754, écarte une paire — un faux positif vérifié une fois
par un humain ne doit plus revenir), et pour revenir sur une erreur (#1243)
`GET .../ignored` (`{pairs: [{id, ignored_at, courses: [{id, name, event_date}×2]}]}`)
et `DELETE .../ignored/{id}` (204, journal `course_duplicate.unignore`). La liste est la porte d'entrée de la
fusion (#289) et de l'arbitrage entre chronométreurs (#285), pas une
correction d'identité — `courses:sources` et non `courses:write` pour les
trois. `ignore` n'exige **pas** `courses:delete` comme la fusion : le geste ne
supprime rien, il persiste un arbitrage (table `ignored_course_duplicates`,
filtrée dans `find_candidates` avant de rendre la liste).

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
| `PATCH /admin/counter-scope/club-labels/{entry_id}` | `{ambiguous}` : marque un libellé du club comme ambigu, ou le rétablit (#1206). Un libellé ambigu (« tcn », aussi le Triathlon Club Narbonne) ne compte que si l'athlète est rattaché au club par un autre résultat validé ou une licence ; le verdict de chaque résultat se recalcule dans la transaction. `200` avec l'entrée ; `400` sur une discipline ; `404` sur une entrée inconnue ; `409` si le libellé est le dernier non ambigu. |

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

`409` également sur un doublon, par **vérification préalable** — la valeur est
normalisée, puis cherchée avant d'écrire. La contrainte `UNIQUE (kind, value)`
reste le filet de la base et empêche le doublon d'exister, mais elle n'est pas
le chemin de l'erreur HTTP : sur deux écritures rigoureusement concurrentes, la
seconde rendrait `500` et non `409`. Assumé à cette échelle — quelques écritures
par an, une poignée d'administrateurs —, et le doublon n'est pas créé pour
autant. `400` sur une valeur vide une fois normalisée.

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
**valent** : `ParticipationOut.is_tcn` lit le verdict stocké
`Participation.counts_for_tcn` (#1206), recalculé à chaque écriture de la
liste des libellés ; tout endpoint portant `scope=club` lit la même colonne, et
`federal_only=true` suit la liste des disciplines. Ils restent donc d'accord
pour n'importe quelle configuration — ce que `tests/test_repositories/test_club_filter.py` éprouve sur
une configuration **modifiée**, pas seulement sur celle livrée.

Conception : `specs/20260826-154613-portee-compteurs-configurable/`.

## Licenciés du club (#1202)

Cinq routes sous `/admin/club-members`, toutes gardées par la permission
`club_members:manage`. Le routeur (`api/v1/admin_club_members.py`) valide, délègue
à `services/club_members_service.py` et commite ; le service recalcule
`counts_for_tcn` à chaque écriture.

| Route | Rôle | Réponse |
| --- | --- | --- |
| `GET /admin/club-members?season=` | Licenciés d'une saison (début de saison, 2000 à 2100), avec les saisons connues | `ClubMembersSeasonOut` : `season`, `seasons`, compteurs (`total`, `linked`, `unlinked`, `ambiguous`), `members` |
| `POST /admin/club-members/sync` | Relit la liste publiée par la FFTri et remplace la saison qu'elle couvre, en gardant les rattachements manuels | `MembersSyncReportOut` |
| `POST /admin/club-members/import` | Multipart `season` + `file` (CSV ou XLSX, colonnes « Nom » et « Prénom » requises) : remplace une saison passée | `MembersSyncReportOut` |
| `POST /admin/club-members/{member_id}/link` | Corps `{"athlete_id": int}` : rattache à la main un licencié à une fiche | `ClubMemberOut` (`link_status: "manual"`) |
| `DELETE /admin/club-members/{member_id}/link` | Annule un rattachement manuel (#1243) : le licencié reprend le rattachement automatique, comme à la relecture suivante, sinon revient « à rattacher ». `400` s'il n'est pas rattaché à la main. Journal `club_member.unlink` | `ClubMemberOut` |

Erreurs propres à ces routes : `502` si la page FFTri est illisible ou
injoignable, `413` au-delà de 2 Mo (lecture bornée par morceaux dans
`api/uploads.py`, partagée avec `/admin/batches`), `422` si les colonnes
« Nom » et « Prénom » manquent ou si la saison sort de la plage, `404` si le
licencié ou la fiche n'existe pas. `401` sans session, `403` sans la permission.
