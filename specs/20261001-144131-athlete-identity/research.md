# Research : une identité stable par athlète réel (#1146)

Relevé du code au 2026-10-01 (base `main` 6e26028a). Chemins relatifs à `backend/` sauf mention.

## État des lieux

- **Résolution à l'import** : `_Persister` (`app/services/import_service.py:580`). `_identity_key` (:522) → `_pair_key` (:529) = `strip().lower()` du nom et du prénom, sans retrait d'accent ni de ponctuation. `_resolve_pending` (:878) appelle `athlete_repository.get_by_identities_batch` (:114), qui filtre `tuple_(lower(nom), lower(prenom)).in_(…)` **et `birth_date IS NULL`**, puis crée les absents par `create_batch` (:142, `add_all` + `flush`).
- **Contraintes** : `uq_athlete_identity(nom, prenom, birth_date)` (`app/models/athlete.py:14`) est sensible à la casse et inopérante (`birth_date` toujours NULL, NULL distincts). `ix_athletes_identity(lower(nom), lower(prenom))` n'est pas unique.
- **Appariement d'une ligne** : par `(course, dossard)` (`_by_bib`), sinon par athlète résolu (`_without_bib[athlete_id]`, multiset avec crédits). `_reconcile_resolved` (:1116) déplace la participation dès que l'athlète résolu diffère.
- **Protections existantes** : `teammate_links` non vide (#894, la ligne n'est que mise à jour, l'identité n'est pas résolue) ; `_reconcile_blocked` (:1105, prénom neuf vide) ; `Athlete.club_locked` (#439). **Aucun drapeau sur une participation réattribuée.**
- **Purge des orphelins** : `delete_orphans_among` (`athlete_repository.py:411`) épargne les équipiers et `referenced_outside_results` (bénévolat, validations, comptes). Le rescrape purge une fois par lot (`rescrape_service.py:302`).
- **Concurrence** : verrous consultatifs par URL (`lock_import_url`) et par épreuve (`lock_course`, `course_locks.lock_courses_or_409`). `deadlock_retries` (`app/services/deadlock.py:64`). **Aucun traitement d'`IntegrityError`.**
- **Admin** : `update_athlete` (`app/services/admin_actions.py:964`) lève `DuplicateError` (409) si l'identité visée existe ; `reassign_participation` (:723) ne déplace qu'une participation ; aucun service de fusion d'athlètes. Précédent de fusion : `app/services/course_merge.py` (`merge_impact` :99, `merge_courses` :130). Précédent de revue : `app/services/course_duplicates.py` + table `ignored_course_duplicate` + page `frontend/app/admin/doublons`.
- **Références à `athletes.id`** : `participations.athlete_id`, `participation_teammates.athlete_id` (RESTRICT), `season_validations` (unique `athlete_id, season`), `volunteer_actions`, `users.athlete_id` (plusieurs comptes possibles).
- **Club** : `Participation.club` (club le jour de la course) et `Athlete.club` (club courant), comparés par `core/club.tcn_clause` / `is_tcn`.
- **Découpage « NOM, Prénom »** : `split_athlete_name` (`app/scrapers/utils.py:232`) coupe déjà sur la première virgule (#906, code livré). Klikego garde son découpage propre (`klikego_platform.py:210`), sans virgule.
- **Tests PostgreSQL** : `TEST_POSTGRES_URL` bascule `db_session` sur PostgreSQL (`tests/conftest.py:92-110`). Le job CI `backend-postgres` lance `alembic upgrade/check/downgrade/upgrade` puis `pytest tests/test_repositories -n 0` sur postgres:16. Seul précédent à deux sessions : `tests/test_repositories/test_lock_repository.py` (fixture `autre_session`).
- **Déploiement** : Render exécute `alembic upgrade head` avant le démarrage (`render.yaml:44,149`) ; une migration qui échoue bloque le déploiement.
- **Tête Alembic** : `d49e03833de6`.

## R1. Forme et stockage de la clé normalisée

- **Decision** : deux colonnes `athletes.last_name_key` et `athletes.first_name_key`, calculées en Python par une fonction unique `identity_key(text)` (nouveau module `app/core/athlete_identity.py`) : NFKD, retrait des marques combinantes, `casefold`, ligatures et lettres que NFKD ne décompose pas, `œ→oe`, `æ→ae`, `ø→o`, `ł→l`, `đ→d` (le `ß→ss` vient de `casefold`), puis seuls les caractères alphanumériques Unicode conservés (`str.isalnum`). Un nom non latin (« Иванов ») garde donc une clé stable ; seule la ponctuation pure donne une clé vide. Les colonnes sont écrites à chaque création ou renommage, par le repository.
- **Rationale** : `unaccent` n'est pas `IMMUTABLE` en PostgreSQL et ne peut entrer ni dans un index d'expression ni dans une contrainte ; une colonne stockée donne la même valeur en SQLite et en PostgreSQL, sans dépendre de l'extension. Deux colonnes séparées (et non une clé concaténée) sont nécessaires pour l'inversion et le nom concaténé (R4). `core/text.deaccent` ne gère pas les ligatures : on ne l'étend pas (il sert à la parité de la recherche, hors périmètre).
- **Prénom seul** : un nom vide et un prénom renseigné (Klikego rend `("", "Jean Dupont")` quand le premier mot n'est pas en majuscules) donnent la clé `(clé du prénom, "")`, celle d'un nom complet sans prénom ; le repli de concaténation (R4) retrouve alors la fiche découpée.
- **Clé vide** : si le nom et le prénom n'ont aucune clé, les deux colonnes valent NULL. Une fiche sans identité exploitable n'est jamais rapprochée d'une autre et ne heurte pas l'unicité (NULL distincts, sur les deux moteurs). À l'import, une ligne à clé vide **sans dossard** est écartée et comptée, comme les noms masqués de #897 (rien de stable pour l'apparier au rescrape) ; **avec dossard**, elle reçoit l'identité « Anonyme <épreuve>-<dossard> » des noms masqués (#897, `anonymous_identity`), stable d'un rescrape à l'autre. Les chiffres sont gardés : « CIC 7 » ≠ « CIC 9 », « ?DOSSARD #12 » ≠ « ?DOSSARD #13 ».
- **Alternatives** : index d'expression `regexp_replace(unaccent(lower(…)))` (impossible, non immuable ; et divergent de SQLite) ; colonne générée (même obstacle) ; normalisation au seul moment de la lecture (pas de contrainte possible).

## R2. Unicité garantie par la base, homonymes distingués

- **Decision** : colonne `athletes.homonym_rank` (entier, NOT NULL, défaut 0) et contrainte unique `uq_athlete_identity(last_name_key, first_name_key, homonym_rank)`, qui remplace `uq_athlete_identity(nom, prenom, birth_date)`. Rang 0 = fiche principale, la seule que l'import vise ; rang ≥ 1 = homonyme distingué. `ix_athletes_identity(lower(nom), lower(prenom))` est supprimé (plus aucun lecteur).
- **Rationale** : la contrainte n'a aucune colonne nullable dès que la clé existe : elle tient sur les deux moteurs, sans index partiel. `birth_date` sort de l'identité : c'est exactement #900 (FR-005).
- **Migration sans blocage** : la migration calcule les clés de toutes les fiches (≈108 000, règle figée dans la migration comme `ccda2de245af`) et attribue les rangs par `id` croissant dans chaque groupe de même clé. Les ~1 900 groupes de doublons existants deviennent provisoirement « homonymes distingués » : la contrainte se pose sans échec et le déploiement passe ; la reprise (R9) les fusionne ensuite. L'import vise le rang 0, donc la plus ancienne fiche, comme aujourd'hui de fait.
- **Alternatives** : index unique partiel `WHERE birth_date IS NULL` (laisse #900 entier, et casse sous la première date posée) ; `NULLS NOT DISTINCT` (PostgreSQL 15+ seulement, absent de SQLite) ; échouer la migration tant que des doublons existent (bloquerait le déploiement Render jusqu'à la reprise, qui dépend elle-même du code déployé).

## R3. Création idempotente sous concurrence (#981)

- **Decision** : `athlete_repository.create_batch` passe à `INSERT … ON CONFLICT (last_name_key, first_name_key, homonym_rank) DO NOTHING RETURNING id`, puis relit par clé les identités non retournées (créées par la transaction concurrente). Les deux dialectes de SQLAlchemy exposent `on_conflict_do_nothing` (`sqlalchemy.dialects.postgresql.insert`, `sqlalchemy.dialects.sqlite.insert`) ; un seul code, choisi selon `bind.dialect.name` dans le repository, comme `lock_repository._on_postgres`.
- **Visibilité** : en READ COMMITTED, un INSERT en conflit avec une ligne non commitée attend la fin de l'autre transaction ; après son commit, la relecture la voit. Si l'autre transaction échoue, l'INSERT réussit. Aucun cas ne laisse de trou.
- **Homonymes** : la création d'un rang ≥ 1 (R5) prend `max(rank)+1` et retente sur conflit (cas rare, borné à quelques essais).
- **Test** : `tests/test_repositories/test_athlete_identity_concurrency.py`, deux sessions sur le même bind PostgreSQL (modèle `test_lock_repository.py`), sauté hors PostgreSQL ; exécuté par le job CI `backend-postgres`.
- **Alternatives** : `pg_advisory_xact_lock` par identité (milliers de verrous par import, sans équivalent SQLite) ; capter `IntegrityError` et rejouer l'import (coûteux, et la règle du dépôt préfère la lecture préalable pour les erreurs nommées, ici inapplicable sous concurrence).

## R4. Résolution à l'import : ordre et repli

- **Decision** : pour chaque ligne non appariée par dossard verrouillé (R6), dans l'ordre :
  1. fiche principale de même clé ;
  2. variante mémorisée par une fusion (R7) ;
  3. repli, **seulement si 1 et 2 échouent** : clé inversée `(prénom, nom)` ; si la ligne a un prénom vide, une fiche dont `last_name_key || first_name_key` ou `first_name_key || last_name_key` vaut la clé du nom ; si une fiche a un prénom vide, celle dont la clé du nom vaut la concaténation des clés de la ligne, dans un sens ou dans l'autre. Le repli ne rattache que si **une seule** fiche principale répond ; sinon création et mention au rapport. Si la fiche trouvée par repli porte déjà un autre dossard sur l'épreuve individuelle (R5), le repli est ignoré et la ligne crée la fiche principale de sa clé directe (elle n'en a pas, sinon l'étape 1 l'aurait trouvée).
- **Rationale** : la concaténation de colonnes remplace « tenter chaque découpage » (FR-004) par une égalité, plus simple et plus rapide ; elle couvre tous les découpages d'un coup. Le repli après l'identité directe protège les vrais « MARTIN Thomas » / « THOMAS Martin » déjà distincts.
- **Coût** : deux requêtes par lot (directe + variantes), puis une requête de repli limitée aux clés non résolues. Index d'expression sur les deux concaténations, déclarés dans le modèle et la migration pour les deux moteurs.
- **Alternatives** : repli flou (distance d'édition), hors périmètre de la spec.

## R5. Deux dossards sur une même épreuve individuelle (#967, Q1)

- **Decision** : `_Persister` tient, par épreuve non relais, la table `athlete_id → dossards` (participations existantes de `_index_course` + lignes déjà attribuées dans ce scrape). Une ligne à **dossard neuf** dont la fiche résolue porte déjà un autre dossard sur l'épreuve reçoit une fiche d'homonyme distinguée (rang suivant, R3). Le rapport d'import gagne `homonyms_created` (liste `{course_id, bib, athlete_id, homonym_of}`).
- **Réconciliation** : une participation existante appariée par dossard n'est déplacée **que si** la clé scrapée diffère de la clé de sa fiche actuelle et n'est pas une variante de celle-ci. Sans cette règle, la fiche d'homonyme créée serait vidée au rescrape suivant (sa ligne se résoudrait vers la fiche principale). La même règle protège une fiche datée par un admin (#900) et une fiche fusionnée.
- **Revue limitée au club** : la revue (R8) calcule à la volée les groupes de fiches de même clé dont l'une relève du club (`tcn_clause` sur `Athlete.club` ou sur `Participation.club` de leurs participations) ; hors club, seule la mention au rapport subsiste.
- **Alternatives** : stocker un « cas » en table au moment de l'import (une table d'état de plus, alors que le cas se recalcule depuis les données) ; départager par catégorie d'âge ou genre (spec : discriminants secondaires non retenus, trop bruités).

## R6. Correction admin protégée au rescrape (#896)

- **Decision** :
  - `participations.athlete_locked` (booléen, défaut faux), posé par `reassign_participation`. Une ligne appariée par dossard à une participation verrouillée n'est que mise à jour (valeurs), sans résolution d'identité : même branche que `teammate_links` (#894).
  - `participations.source_identity_key` (texte, nullable) : clé normalisée `"<last_name_key>|<first_name_key>"` de la ligne source, écrite à chaque création ou mise à jour par l'import. L'appariement **sans dossard** se fait par cette clé et non plus par athlète : il remonte dans `add()`, avant toute résolution, sur un multiset `source_identity_key → lignes`. Une ligne réattribuée est donc retrouvée sans recréer la fiche d'origine.
  - Rétro-remplissage par la migration : clé de la fiche actuelle (juste pour toute ligne jamais réattribuée ; une ligne déjà réattribuée est hors périmètre, cf. spec).
- **Rationale** : avec dossard, un drapeau suffit ; sans dossard il faut une clé d'appariement indépendante de la fiche (commentaire du 2026-09-29 sur #896). La fusion n'a pas besoin du drapeau : la clé scrapée de la fiche absorbée devient une variante de la fiche conservée (R5, règle de réconciliation).
- **Orphelins** : si une fiche est malgré tout recréée vide, la purge existante (`delete_orphans_among`) s'en charge (FR-013).
- **Alternatives** : comparer à `raw_data` (forme propre à chaque fournisseur, illisible de façon générique) ; verrouiller la fiche entière (bloquerait la correction légitime d'un chronométreur sur les autres résultats).

## R7. Fusion admin et variantes (#908, Q2)

- **Decision** : nouveau service `app/services/athlete_merge.py`, calqué sur `course_merge.py` : `merge_impact(kept_id, absorbed_id)` (aperçu en lecture) et `merge_athletes(kept_id, absorbed_id, user_id)`.
  - Verrous, dans cet ordre : `SELECT … FOR UPDATE` sur les deux lignes `athletes` (ordre d'id), puis `lock_courses_or_409` sur toutes les épreuves des deux fiches (essai sans attente, 409 si occupé : pas d'interblocage avec un import), puis seulement la lecture des références à déplacer. L'attente du `FOR UPDATE` est bornée (`SET LOCAL lock_timeout = '5s'` sur PostgreSQL) : au-delà, 409 « fiche en cours d'import, réessayez » plutôt qu'une requête HTTP suspendue pendant un rescrape en lot.
  - Côté import (PostgreSQL), la résolution prend `FOR KEY SHARE` sur les fiches trouvées (`get_by_identity_keys_batch`, variantes et repli). Une fusion attend donc la fin d'un import qui a résolu la fiche absorbée, puis déplace aussi ses nouvelles participations ; un import qui résout après le commit de la fusion trouve la variante. Sans ce verrou, l'import d'une épreuve neuve insérerait une participation vers une fiche supprimée (clé étrangère violée). `FOR KEY SHARE` ne bloque pas les mises à jour de club et de genre (`apply_updates`), seulement la suppression.
  - Refus (`DomainError` 409, message français) : même fiche ; fiches liées à deux comptes différents ; dossards distincts sur une même épreuve individuelle ; présence des deux fiches sur une même participation (porteur et équipier) ; deux dates de naissance différentes.
  - Déplacements : participations, lignes `participation_teammates`, `volunteer_actions`, `season_validations` (une saison validée des deux côtés : la ligne de la fiche conservée reste, l'autre est supprimée), `users.athlete_id`. Club verrouillé, genre et date de naissance repris de la fiche absorbée quand la conservée ne les a pas.
  - Variantes : table `athlete_aliases(last_name_key, first_name_key, athlete_id)`, unique sur la clé, `athlete_id` en ON DELETE CASCADE. La fusion y inscrit la clé de la fiche absorbée (si elle diffère de celle de la conservée) et repointe les variantes de l'absorbée. Si la conservée est un homonyme distingué de même clé que l'absorbée principale, elle reprend le rang 0.
  - Journal : `audit.record`, `action="athlete.merge"`, `entity_id=kept_id`, payload `{absorbed: {id, nom, prenom, club}, moved: {participations, teammates, volunteer_actions, season_validations, users}, alias_added}` ; `birth_date` n'y figure jamais (la rédaction de `admin_action_log.py` ne masque que `before`/`after`).
- **Renommage en conflit (FR-020)** : `update_athlete` lève toujours 409, avec en plus l'id de la fiche en conflit dans le corps (`conflicting_athlete_id`, champ additif) ; le front propose alors la fusion. L'unicité vérifiée devient celle de la clé normalisée (et des variantes).
- **Course résiduelle** : une variante est inscrite au commit de la fusion ; un import concurrent qui aurait lu avant peut recréer une fiche principale de cette clé. La revue (R8) liste « fiche principale dont la clé est une variante d'une autre fiche » ; aucun verrou supplémentaire.
- **Alternatives** : variantes stockées dans `athletes` (ligne fantôme, casse l'unicité) ; pas de variantes (refusé par Q2).

## R8. Revue d'identité

- **Decision** : calquée sur la revue des épreuves en doublon : service `app/services/athlete_identity_review.py` qui calcule les candidats à la volée, table `ignored_athlete_pairs(athlete_id_low, athlete_id_high, ignored_by_user_id, ignored_at)` (FK en ON DELETE CASCADE), routes `GET /api/v1/admin/athletes/identity-review`, `GET …/count`, `POST …/ignore`, page front `/admin/identites` avec badge de navigation.
- **Motifs** : `same_course_bibs` (fiche du club portant deux dossards sur une épreuve individuelle) ; `club_homonym` (homonymes distingués dont l'un relève du club) ; `swapped` et `concatenated` (paires laissées par la reprise) ; `alias_collision` (R7). Chaque candidat porte identités, clubs, genres, catégories, et les épreuves communes ou en conflit.
- **Permission** : `athletes:write` (lecture et écart), la fusion exigeant la même.
- **Alternatives** : table de cas persistés avec statut (état dupliqué des données, à tenir synchrone).

## R9. Reprise des données (#906, #907, #908, #900, Q3)

- **Decision** : commande CLI `reconcile-athletes` (`app/cli/commands/reconcile_athletes.py`, logique dans `app/services/athlete_reconciliation.py`), sur le modèle de `purge-timepulse-duplicates` : sans `--yes`, simulation (aucune écriture, rapport complet) ; `--yes --by-email <admin>` applique, chaque fusion étant journalisée sous ce compte ; `--json` ; codes 0/1/2/130.
- **Familles, dans l'ordre** :
  0. « même club » : `Athlete.club` renseigné des deux côtés et égal après normalisation (`core/club`) ; « même genre » : renseigné des deux côtés et égal. Deux valeurs vides ne sont pas un signal.
  1. renormalisation « NOM, Prénom » (prénom vide et virgule dans le nom ; nom finissant par une virgule ; prénom finissant par une virgule, nom et prénom inversés) : coupe sur la première virgule, comme `split_athlete_name`. Si l'identité cible existe, fusion dans la fiche existante ; sinon renommage. `source_identity_key` des participations concernées recalculée sur l'identité renormalisée (sinon un rescrape sans dossard ne les retrouverait plus) ;
  2. groupes de même clé (rangs ≥ 1 issus de la migration) : fusion dans la fiche de rang 0, sauf garde de refus de R7 → revue ;
  3. paires inversées et concaténées : fusion automatique si même club (`Athlete.club` normalisé) ou même genre, et jamais sur une même épreuve ; sinon revue (Q3) ;
  4. fiches datées par un admin ayant un homonyme non daté : couvertes par la famille 2 (la date ne compte plus dans la clé).
- **Exclusions** : fiches factices (clé vide, `?DOSSARD`, `Anonyme`, `xxx`, noms contenant `&` ou chiffres de numérotation d'équipe), comme dans les requêtes des sous-issues.
- **Reprise sur interruption** : une transaction et un commit par fusion ; les candidats se recalculent à chaque lancement, donc relancer ne refait rien de fait (FR-029).
- **Exécution en production** : en local depuis `backend/`, `DATABASE_URL` sur la base cible et règle de pare-feu temporaire, procédure de `purge-timepulse-duplicates` (`docs/ci-cd.md:585-599`). Pas de nouveau mode dans `batch.yml` (geste ponctuel, catalogue fermé).
- **Alternatives** : script SQL brut (pas de mode simulation partagé avec le code de fusion, journal à refaire) ; nouveau mode de workflow (geste unique, coût de contrat disproportionné).

## R10. Découpage en PR (workflow d'epic)

Branche d'intégration `epic/1146-athlete-identity` ; une PR par sous-issue, `Refs #1146`, dans cet ordre (chaque étape laisse un produit qui marche) :

| PR | Sous-issues | Contenu |
| --- | --- | --- |
| 1 | #907, #908 (résolution) | `identity_key`, colonnes et rangs, migration de rétro-remplissage, contrainte, résolution par clé sans `birth_date`, repli inversion et concaténation |
| 2 | #900, #896 | `athlete_locked`, `source_identity_key`, appariement sans dossard par clé, règle de réconciliation, `update_athlete` sur la clé |
| 3 | #981 | `create_batch` en `ON CONFLICT DO NOTHING`, test à deux sessions PostgreSQL |
| 4 | #967 | homonymes distingués à l'import, rapport `homonyms_created` |
| 5 | #908, #907, #967 (revue) | fusion admin, variantes, API et UI ; revue d'identité |
| 6 | #906 | commande `reconcile-athletes`, procédure de production |

Source de vérité du découpage : `tasks.md`, tableau « PR ».

La PR 5 peut se scinder en deux (résolution, puis fusion et revue) si sa taille le demande.
