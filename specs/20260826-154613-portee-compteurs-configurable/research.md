# Phase 0 — Recherche et décisions

Feature : [Portée des compteurs configurable](./spec.md) · Issue [#95](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/95)

Aucun `NEEDS CLARIFICATION` n'était ouvert à l'entrée de cette phase. Ce document consigne les six décisions de conception et ce qui a été écarté, chacune adossée à un relevé fait sur le dépôt.

---

## 1. Où vit la configuration : une table, deux natures

**Décision** : une table `counter_scope_entries`, colonne `kind` discriminante (`non_federal_discipline` | `tcn_club_label`), unicité sur `(kind, value)`.

**Rationale** : les deux entrées ont la même forme — une chaîne appartenant à un ensemble, avec son auteur et sa date d'ajout. Aucune colonne ne distingue l'une de l'autre. Deux tables auraient produit deux modèles, deux repositories, deux jeux de schémas et deux routeurs pour la même forme.

**Alternatives écartées** :

- *Deux tables distinctes* — le doublon exact que le Principe VI écarte. Le jour où les deux natures divergeraient réellement (une discipline gagnant un attribut que le libellé n'a pas), séparer une table de douze lignes est un geste sans risque.
- *Une table de configuration générique clé/valeur* — à l'opposé du problème : elle perd l'unicité par nature, la validation par nature, et transforme deux listes lisibles en un sac de chaînes JSON.
- *Un fichier de configuration versionné plutôt que la base* — ne répond pas au besoin : l'objectif est précisément de retirer le déploiement du chemin.

---

## 2. Comment les prédicats lisent la configuration sans requêter la base

C'est la décision centrale de la feature.

**Contrainte relevée** : `ParticipationOut.is_tcn` (`backend/app/schemas/participation.py:45`) est un champ calculé de DTO. Il s'évalue au moment de la sérialisation, **sans Session** et sans personne pour lui en passer une. `app/scrapers/t2area.py:526` et `app/scrapers/breizhchrono.py:292` appellent `is_tcn` ligne par ligne à l'intérieur d'une boucle d'import. Au total, 29 sites d'appel des quatre prédicats dans `app/`.

**Décision** : un registre en mémoire de processus, `core/counter_scope.py`, sans Session ni import d'une couche supérieure. Il est **rempli depuis le dessus** : `services/counter_scope.py` lit la base via le repository et pousse les deux ensembles dans le registre. `core/club.py` et `core/discipline.py` le lisent.

**Rationale** : toutes les flèches de dépendance restent dirigées vers le bas. `core/` n'appelle rien au-dessus de lui, il est appelé. La règle d'identification club reste dans `app/core/club.py`, un seul endroit, comme l'exige le Principe II.

**Alternatives écartées** :

- *Passer la configuration en paramètre à `is_tcn` / `is_federal` / les clauses* — la forme la plus pure, et impraticable : 29 sites d'appel à modifier, et surtout le champ calculé de DTO n'a personne pour la lui fournir.
- *Placer le cache dans `services/` et le faire lire par `core/`* — `core/club.py` importerait `app/services/...`. Inversion frontale du sens du flux, interdite par le Principe II.
- *Laisser `core/` ouvrir sa propre Session (`SessionLocal()`) en lecture paresseuse* — une nouvelle occurrence de Session hors `repositories/`. Le Principe II en nomme exactement deux, exemptées à titre transitoire (`services/cache.py`, `services/reclassify.py`), et interdit toute nouvelle. Écarté sans hésitation.
- *Un cache TTL court plutôt qu'une invalidation explicite* — moins de câblage, mais une modification admin invisible pendant la durée du TTL, ce que FR-008 exclut. Et avec un seul processus, l'invalidation explicite est triviale.

---

## 3. Les valeurs d'aujourd'hui restent les défauts du registre

**Décision** : `core/counter_scope.py` porte `DEFAULT_NON_FEDERAL_DISCIPLINES` et `DEFAULT_TCN_CLUB_LABELS` — les valeurs exactes d'aujourd'hui. Le registre part de là ; le chargement depuis la base les remplace.

**Rationale** : le mode de défaillance d'un registre vide est le pire qui soit. Zéro libellé reconnu, c'est zéro résultat du club, tous les compteurs du club à zéro, aucune erreur, aucun avertissement — un tableau de bord vide qui ressemble à un tableau de bord. Le défaut fait qu'un remplissage oublié (un script, une commande nouvelle, un test) dégrade vers le comportement d'aujourd'hui, jamais vers le vide.

Bénéfice de bord : la suite existante (3 656 tests, base créée par `Base.metadata.create_all` dans `tests/conftest.py`, donc sans les lignes amorcées par la migration) reste verte sans qu'une assertion change. C'est précisément ce qui rend l'étape 2 du plan vérifiable.

**Le risque assumé** : deux sources pour la même valeur, les défauts du code et les lignes de la migration, qui peuvent diverger. Neutralisé par un test qui applique les migrations sur une base vierge et compare les lignes amorcées aux défauts du code.

**Alternative écartée** : *lever une exception à la première lecture d'un registre non rempli*. Franc, mais `is_tcn` est appelé depuis un champ calculé de DTO : l'exception casserait le rendu d'une page de résultats entière pour un défaut de câblage, et elle le ferait en production.

---

## 4. Les trois points de remplissage

**Décision** : le registre est rempli à trois endroits, et trois seulement.

| Point d'entrée | Où | Quand |
| --- | --- | --- |
| API web | `app/main.py`, dans le `lifespan` déjà en place | au démarrage du processus, après `alembic upgrade head` (cf. `startCommand` de `render.yaml`) |
| CLI de batch | `app/cli/__main__.py`, à côté de `configure_cli_logging()` | à chaque invocation |
| Écriture admin | `services/counter_scope.py`, après le `commit` | à chaque modification |

Les tests, eux, s'appuient sur les défauts ; une fixture `autouse` remet le registre à zéro entre deux tests, sur le patron de `_compteurs_de_debit_vierges` (`tests/conftest.py:27`) — un registre modifié par un test ne doit pas fuir dans le suivant.

**Rationale** : le remplissage est le rôle du **processus**, pas d'un module importé — la même doctrine que `configure_cli_logging`, dont la docstring dit exactement cela.

---

## 5. Pas de propagation entre processus

**Décision** : aucune. L'invalidation est locale au processus.

**Relevé** : `render.yaml:44` et `render.yaml:148` lancent `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Aucun `--workers`, aucun gunicorn, aucune réplique déclarée. Un seul processus serveur sert l'API.

**Rationale** : avec un processus, l'invalidation en mémoire est exhaustive par construction. Ajouter un Redis, un canal `LISTEN/NOTIFY` ou un TTL de rattrapage serait de la complexité pour un déploiement qui n'existe pas.

**Ce qui devra bouger le jour où l'API passera à plusieurs processus** : le point de remplissage nº 3 ne toucherait plus que le processus qui a servi l'écriture. Le remède le plus simple à ce moment-là — et ce n'est pas à construire maintenant — est un compteur de version en base relu à chaque requête, ou un TTL court. Consigné ici pour que ce ne soit pas redécouvert.

---

## 6. L'index fonctionnel sur les libellés normalisés ne bouge pas

**Décision** : aucune migration de reconstruction d'index. La feature ne touche pas à `_normalise_sql`.

**Relevé** : `CLUB_NORMALIZED_INDEX_EXPRESSION` (`backend/app/core/club.py`) compile `_normalise_sql` en littéral DDL, consommé à la fois par `Participation.__table_args__` et par la migration `e9cdbf3a4866` qui pose `ix_participations_club_normalized`. La docstring y est explicite : l'index fige le texte SQL **au moment où la migration a tourné**, dans le catalogue de la base ; modifier `_normalise_sql` sans migration de reconstruction périme l'index en silence, et les lectures retombent sur un balayage complet sans la moindre erreur.

**Rationale** : la feature rend configurable l'**ensemble** des libellés reconnus, pas la façon de les comparer. `tcn_clause` reste `_normalise_sql(column).in_(...)` — seule la liste passée à `in_()` change de source. L'expression indexée est identique, l'index reste servi.

**Frontière posée** : toute évolution future de la normalisation (accents, ponctuation, tirets) sort de cette feature et exige sa propre migration de reconstruction d'index. Écrit ici parce que c'est exactement la tentation que la feature va créer — « puisqu'on y est ».

---

## 7. Le pouvoir d'administration

**Décision** : un pouvoir nouveau, `counter_scope:manage`, sous une fonctionnalité nouvelle `FEATURE_COUNTER_SCOPE = "Portée des compteurs"`.

**Rationale** : le catalogue de `app/core/permissions.py` est la liste de référence, et son `AGENTS.md` pose la règle — « ajouter un pouvoir, c'est ajouter un membre à `P` et lui poser une garde », sans migration, le méta-test AST (`tests/test_permissions_catalogue.py`) rougissant tant que la garde manque. Le geste n'est ni un geste sur les rôles, ni un geste sur les épreuves : le ranger sous une fonctionnalité existante rendrait la grille de composition des rôles trompeuse.

**Alternative écartée** : *réutiliser un pouvoir existant* — `COURSES_WRITE` corrige une épreuve, pas la définition d'un compteur ; `ROLES_WRITE` ne parle pas de disciplines. Aucun des deux ne décrit l'acte.
