# Phase 0 — Recherche : saisie manuelle des résultats (#270)

**Feature** : `20260814-130052-saisie-manuelle-resultats` · **Date** : 2026-08-14

Tout ce qui suit est relevé **dans le code du dépôt**, pas supposé. Chaque
décision nomme les fichiers qu'elle engage.

---

## D1 — Où vit l'état « en attente de validation »

**Décision** : une colonne booléenne `is_pending_validation` sur
`Participation`, `NOT NULL`, `server_default="false"`, sur le patron exact de
`is_relay` (`models/participation.py:47`).

**Rationale** : l'arbitrage Q2 du 2026-08-14 (FR-023/FR-024) rend l'abandon
déclarable, donc l'état de validation ne peut pas être une valeur de plus dans
`Participation.status` — un `DNF` en attente serait irreprésentable, et la
validation écraserait le statut sportif. Le `server_default` évite tout backfill :
les **20 318** participations existantes (relevé du 2026-08-14 sur
`backend/triathlon.db`) deviennent non-pendantes sans migration de données, ce
qui est exactement ce que la spec demande (« les saisies antérieures ne sont pas
rétroactivement marquées »).

**Alternatives écartées** :

- *Surcharger `status`* — c'était l'option A de la question Q2, écartée par le
  mainteneur. Elle économisait la colonne mais fermait la déclaration d'abandon.
- *Colonne `validation_state` en chaîne* (`pending` / `validated` / `rejected`) —
  le troisième état n'est demandé nulle part : #271 décrit une file et une
  validation, pas un rejet. Principe VI, pas d'abstraction spéculative. Le jour
  où le rejet existe, un booléen se remplace par une chaîne en une migration.
- *Table `participation_validations` séparée* — une jointure sur chaque chemin de
  lecture pour porter un booléen.

**Nommage** : `is_pending_validation` et non `is_validated`, pour que le défaut
`false` soit l'état ordinaire. Une colonne `is_validated` aurait exigé
`server_default="true"`, c'est-à-dire d'affirmer que 20 318 lignes ont été
vérifiées par quelqu'un.

---

## D2 — Le point unique d'exclusion des agrégats

**Décision** : un module `app/core/validation.py` portant le prédicat Python et
la clause SQL, sur le patron **littéral** de `core/discipline.py`
(`is_federal` / `federal_clause`) et de `core/club.py` (`is_tcn` / `tcn_clause`) ;
appliqué à **cinq** sites de `participation_repository.py`, et délibérément
**pas** aux six autres.

**Rationale** : FR-021 exige une exclusion totale. Le dépôt a déjà payé le prix
d'une règle transverse réimplémentée à trois endroits — c'est l'issue #76,
citée par le Principe II de la constitution comme sa justification. Une règle de
plus dispersée dans huit `filter()` finirait de la même façon.

**Les cinq sites qui filtrent** (relevé exhaustif dans
`repositories/participation_repository.py`) :

| Site | Ligne | Ce qu'il alimente |
| --- | --- | --- |
| `_apply_filters` | 275 | `list_participations` (page `/resultats`) **et** `_grouped_events_query` → `events_with_counts` / `events_page` (page épreuves, carte) |
| `for_stats` | 492 | `stats_service.get_stats` → tableau de bord **et** page club, podiums compris |
| `list_page_for_course` | 423 | classement paginé d'une épreuve (#163) |
| `summary_rows_for_course` | 460 | synthèse d'épreuve (décomptes, histogramme, `split_keys`) |
| `finishers_count_by_group` | 207 | `course_finishers` de la fiche athlète (taille du classement) |

`_apply_filters` couvre à lui seul trois surfaces publiques, dont les **podiums** :
ceux-ci sont calculés côté front dans `components/club/ClubDashboard.tsx` à partir
des participations servies par l'API — aucun agrégat de podium n'existe côté
backend (`grep -rn podium backend/app` → zéro résultat). Filtrer la source suffit
donc, et c'est plus sûr que de traiter le front.

**Les six sites qui ne filtrent pas, et pourquoi** — c'est la moitié qui se perd
à la relecture :

| Site | Raison |
| --- | --- |
| `list_for_athlete` | **La** surface d'affichage voulue par FR-019. La filtrer viderait la feature de son objet. |
| `list_for_course` | Chemin d'**import** (`import_service`, `quality.analyze`), pas d'affichage — déjà documenté comme tel dans `api/AGENTS.md`. |
| `count_for_athlete` | Purge des fiches coureur orphelines (#117). Ignorer une participation pendante supprimerait la fiche d'un athlète qui en a une. |
| `count_for_course` / `delete_for_course` | Gestes d'administration : ils portent sur ce qui existe, pas sur ce qui est publié. |
| `count_bibs_absent_from` | Aperçu d'impact de fusion (#286) : il mesure ce qui **serait perdu**, or une pendante se perdrait tout autant. |
| `existing_bibs_for_course` | Dédoublonnage d'import. En omettre une laisserait un doublon entrer. |

**Verrou** : un test qui énumère ces onze fonctions et vérifie l'appartenance de
chacune au bon groupe. Précédent dans le dépôt :
`tests/test_permissions_catalogue.py` tient le même genre d'invariant par AST.

**Alternative écartée** : un paramètre de requête `include_pending`. Voir la
justification du Principe V en Complexity Tracking du plan — il rendrait
l'exclusion contournable par n'importe quel appelant public, c'est-à-dire
exactement ce que FR-021 interdit.

**Conséquence pour #271** : la file de validation ne lira **pas** l'API publique.
Elle aura sa propre fonction de repository (`list_pending`) derrière une route
`/admin/` gardée, sur le patron d'`admin_feedback.py`. Rien à prévoir ici — c'est
une note de cadrage pour le ticket suivant, pas du code à écrire maintenant.

---

## D3 — Les disciplines à créer et les quatre endroits qui les déclarent

**Décision** : ajouter les slugs manquants dans les quatre déclarations, dans cet
ordre.

**Relevé de l'existant** (`scrapers/classify.py:24` et
`frontend/lib/constants.ts:1`) :

| Demandé par Vincent | État |
| --- | --- |
| Triathlon | présent, formats XS→XL complets |
| Duathlon | présent, **XL manquant** (XS→L seulement) |
| Swim & Run | présent sous `swimrun` (« SwimRun ») |
| Run & Bike | présent sous `bike-run` (« Bike & Run ») — **même discipline, confirmé le 2026-08-14** |
| Aquathlon | présent **sans aucun format** |
| Raid Multisport | **absent** |
| Cross Triathlon | **absent** |
| Swim Bike | **absent** |

**Slugs à créer** : `duathlon-xl`, `aquathlon-{xs,s,m,l,xl}`,
`swim-bike` + `swim-bike-{xs,s,m,l,xl}`, `cross-triathlon`, `raid-multisport`.

**Les quatre endroits** :

1. `scrapers/classify.py` — `CANONICAL_TYPES`. Sans cette entrée,
   `normalize_event_type` n'est plus idempotent sur le slug, et
   `services/reclassify.py:46` peut le réécrire silencieusement.
2. `services/mapping.py` — `_MULTI_WORD_BASES` (ligne 50). **Le piège central de
   cette décision** : `mapping._sport_base` coupe au premier tiret, donc
   `swim-bike-m` donne la base `swim`, `cross-triathlon` donne `cross` et
   `raid-multisport` donne `raid`. Les trois nouvelles disciplines sont
   multi-mots, les trois doivent y être déclarées.

   **Attention à l'homonymie** : `classify.py` porte lui aussi un `_sport_base`
   (ligne 130), mais c'est une **autre** fonction — texte libre → sport nommé,
   là où celle de `mapping.py` fait slug → base. `_MULTI_WORD_BASES` n'existe
   que dans `mapping.py` (vérifié par grep sur `backend/app/`), et `classify.py`
   n'a rien d'équivalent à modifier : ses nouvelles disciplines n'ont pas à être
   reconnaissables depuis un nom d'épreuve libre, le formulaire envoyant le slug
   directement. `CANONICAL_TYPES` suffit à protéger ces slugs du re-classement,
   `normalize_event_type` court-circuitant dessus (ligne 192).
3. `services/mapping.py` — `_SPLIT_KEYS_BY_SPORT`. `swim-bike` a besoin de son
   gabarit (`swim` / `t1` / `bike`, **pas** de course à pied) ; `cross-triathlon`
   retombe correctement sur le gabarit par défaut (natation / T1 / vélo / T2 /
   course), et `raid-multisport` n'a pas de découpage prévisible — gabarit
   positionnel ou aucun.
4. `frontend/lib/constants.ts` — `EVENT_TYPE_LABELS`, d'où `EVENT_TYPE_OPTIONS`
   se déduit automatiquement (ligne 31).

**`core/discipline.py` n'est pas touché**, et c'est délibéré : la liste y est une
**liste d'exclusion**, documentée comme telle en tête de module. Les trois
nouvelles disciplines sont fédérales et le deviennent par défaut, sans une ligne
de code.

---

## D4 — La précision du format « Autre »

**Décision** : une colonne `format_label` (chaîne, nullable) sur `Course`.

**Rationale** : le format est aujourd'hui encodé **dans** `event_type`
(`triathlon-m`), et cette taxonomie est fermée — `CANONICAL_TYPES` la verrouille
pour garantir l'idempotence du re-classement. Fabriquer un slug par texte libre
saisi ferait entrer des valeurs arbitraires dans un ensemble que `classify` et
`reclassify` supposent clos, et `is_federal` les jugerait fédérales sans que
personne ne l'ait décidé.

La précision est une propriété de l'**épreuve**, pas du résultat : deux membres
de la même épreuve « Autre » doivent lire la même précision.

**Alternatives écartées** :

- *La ranger dans `distance_km`* — la colonne est un `Float`
  (`models/course.py:55`). « 750 m / 20 km / 5 km » n'y entre pas.
- *La ranger dans `Participation.raw_data`* (JSON, déjà présent) — invisible de
  toute lecture, non requêtable, et rangée sur la mauvaise entité.

**Le champ « distance totale »** des disciplines sans format, lui, n'ajoute
**rien** : il alimente `Course.distance_km`, qui existe et que
`disciplineLabel()` affiche déjà (`frontend/lib/constants.ts:71`).

---

## D5 — Le lien vers les résultats n'est pas une source

**Décision** : une colonne `evidence_url` (chaîne, nullable) sur `Participation`.
Le formulaire manuel **cesse d'envoyer `source_url`**.

**Rationale — et c'est la décision la plus lourde de conséquences du plan.**
Faire du lien saisi le `source_url` de l'épreuve le transformerait en
`CourseSource`. Or `services/mapping.py:169` appelle `course_source_repository.attach`,
et `attach` (#283) pose la source **active** quand l'épreuve n'en a aucune — ce
qui est exactement le cas d'une épreuve créée à la main. Le lien deviendrait donc
la source active d'une épreuve déclarée, avec trois effets en chaîne :

1. `rescrape-db` (#282) scraperait cette URL au prochain passage, avec
   `provider="manuel"`, c'est-à-dire aucun scraper capable de la lire ;
2. elle entrerait dans le cache TTL (`is_fresh`), qui indexe sur `source_url` ;
3. `GET /courses/{id}/sources` (#284) l'annoncerait publiquement comme le
   chronométreur de l'épreuve.

Une pièce justificative destinée à un relecteur humain ne doit produire aucun de
ces trois effets.

**Conséquence assumée** : une épreuve créée par saisie manuelle n'aura aucune
source, donc un `provider` vide. Ce n'est pas nouveau et c'est déjà documenté
comme le comportement attendu — `backend/app/models/AGENTS.md` : « `POST
/participations` sans `source_url` donne donc une épreuve à provider vide »,
portée mesurée le 12/08/2026 à **0 épreuve sur 95**. Le code le prévoit déjà
explicitement (`mapping.py:165`, branche « Saisie manuelle : pas d'URL »).

**Changement de comportement à signaler** : aujourd'hui, `TcnScrapeForm` passe
l'URL collée non reconnue en `defaultUrl` au formulaire manuel
(`TcnScrapeForm.tsx:187`), qui l'envoie en `source_url`. Après cette feature, la
même URL atterrira dans `evidence_url`. C'est le comportement voulu, mais il
modifie ce que fait le formulaire d'une URL collée.

---

## D6 — « Collectif » réutilise `is_relay`, et cela crée une épreuve distincte

**Décision** : le choix collectif écrit `is_relay=True`, et le nom d'équipe va
dans une colonne `team_name` (chaîne, nullable) sur `Participation`.

**Conséquence à connaître avant de la découvrir en test** : `is_relay` traverse
`_to_scraped` (`api/v1/participations.py:44`) et alimente **à la fois** la
participation et l'identité de la `Course` — `uq_course_identity` porte sur
`(name, event_date, event_type, is_relay)`. Une saisie « collectif » ne rejoint
donc pas l'épreuve solo du même nom : elle crée une seconde ligne `Course`. Ce
n'est pas un défaut à corriger ici, c'est le modèle en vigueur, documenté dans
`models/AGENTS.md` (« le relais est un heat distinct du solo, sans quoi les deux
fusionnaient dans la même ligne »).

`team_name` va sur `Participation` et non sur `Course` : deux équipes courent la
même épreuve.

---

## D7 — Le statut sportif à la saisie

**Décision** : `ParticipationCreate` gagne un champ `status`, et
`mapping.derive_status` reste inchangé.

**Rationale** : `derive_status` (`mapping.py:96`) respecte déjà un statut
explicite et ne retombe sur l'heuristique « temps total présent → finisher, sinon
DNF » qu'à défaut. Un champ transmis suffit donc, sans toucher à la fonction —
et c'est important : l'heuristique seule transformerait tout abandon déclaré sans
temps en DNF par accident plutôt que par déclaration, et surtout tout **forfait**
(DNS) déclaré sans temps en DNF, ce qui est faux.

Les valeurs restent celles de `scrapers/base.py` (`STATUS_FINISHER`, `STATUS_DNF`,
et `DNS`), pas un nouveau vocabulaire.

---

## D8 — Validation du formulaire côté front

**Décision** : rester sur `react-hook-form` + `zod` + `@hookform/resolvers/zod`,
déjà en place (`ManualResultForm.tsx:1-11`), et exprimer les règles
conditionnelles par un `superRefine` sur le schéma plutôt que par des états React.

**Rationale** : FR-004 exige des messages par champ qui bloquent la soumission —
c'est le comportement natif du resolver, déjà démontré par les quatre `min(1, …)`
du schéma actuel. Les trois règles conditionnelles (format « Autre » → précision
obligatoire ; collectif → nom d'équipe obligatoire ; discipline → champs de temps
affichés) sont des dépendances entre champs, ce que `superRefine` exprime en
restant la **seule** source de vérité de la validation.

**Piège documenté sur place à ne pas rouvrir** : le commentaire ligne 39-40
explique que le générique explicite de `useForm` a été retiré à cause du
désaccord Input/Output introduit par les `.default("")`. Les nouveaux champs
doivent suivre la même convention, sinon le build TypeScript strict casse.

**Bibliothèque de composants** : `ManualResultForm` est nommément listé dans
`frontend/AGENTS.md` parmi les sept écrans publics qui tirent encore
`ui/{card,button,badge,input}` — dette assumée, explicitement pas « une exception
à arbitrer au cas par cas ». On reste donc sur `ui/`, et les nouveaux sélecteurs
prennent `ui/select` (bâti sur `@base-ui/react`) plutôt que le `<select>` nu
d'aujourd'hui, qui n'a ni gestion clavier ni style cohérent.

---

## D9 — Contrat d'API : additif, donc pas de v2

**Décision** : `ParticipationCreate` et `ParticipationOut` gagnent des champs ;
aucun n'est retiré ni resémantisé. Pas de `/api/v2`.

**Rationale** : le Principe IV vise « champ retiré, sémantique inversée d'un
paramètre, code de retour modifié ». Ajouter des champs optionnels à une entrée
et des champs à une sortie n'est aucun des trois.

**Le point qui mérite d'être posé explicitement** : FR-021 change le contenu de
`GET /participations` et de `GET /courses/{id}`, qui excluront désormais des
lignes. Ce n'est pas une régression de contrat parce que **les lignes exclues
n'existaient pas avant cette feature** : aucun appelant ne perd une donnée qu'il
recevait hier. Le jour où un appelant a besoin des pendantes, il passe par la
route d'administration de #271.

---

## Synthèse des changements de schéma

Une seule migration Alembic, quatre colonnes, aucun backfill.

| Table | Colonne | Type | Défaut | Décision |
| --- | --- | --- | --- | --- |
| `participations` | `is_pending_validation` | `Boolean NOT NULL` | `false` | D1 |
| `participations` | `team_name` | `String NULL` | — | D6 |
| `participations` | `evidence_url` | `String NULL` | — | D5 |
| `courses` | `format_label` | `String NULL` | — | D4 |

Aucun index : les quatre colonnes sont lues avec la ligne, jamais cherchées.
`is_pending_validation` entre dans des `WHERE` mais sur des sélections déjà
restreintes par `course_id`, saison ou portée club — et sa cardinalité (deux
valeurs, dont une ultra-majoritaire) en fait un mauvais candidat à l'index isolé.
À revoir si la file de #271 devient lente, pas avant.

---

## Question tranchée

**« Run & Bike » = `bike-run` — confirmé le 2026-08-14.** Une seule et même
discipline. D3 ne gagne donc **aucun** slug de ce fait : l'entrée `bike-run`
existante couvre le besoin, et son libellé « Bike & Run » reste tel quel — c'est
la forme officielle de la fédération, et le renommer toucherait l'affichage de
toutes les épreuves déjà importées sous cette discipline pour un gain nul. Si le
porteur produit préfère malgré tout sa formulation à l'écran, c'est une valeur à
changer dans `frontend/lib/constants.ts`, sans effet sur les données.

Aucune question ouverte ne subsiste sur cette feature.
