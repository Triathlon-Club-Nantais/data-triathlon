# Sondage — alertes « Code quality » CodeQL du dépôt

**Date** : 2026-08-04
**Objet** : établir ce que remonte l'onglet `/security/quality` de GitHub, trier vrais et faux
positifs sur pièces, corriger ce qui le mérite.
**Statut** : sondage. Il **prime** sur le design, la spec et le plan. Toute divergence se tranche
en re-sondant.

## Méthode

**Ces alertes ne sont exposées par aucune API.** Vérifié, dans l'ordre : `code-scanning/alerts`
répond `404 no analysis found` (y compris avec `analysis_kind=code-quality`, et sur
`refs/pull/<n>/head`) ; les routes `code-quality/alerts` et `code-quality/analyses` n'existent
pas ; le schéma GraphQL ne contient aucun type portant « Quality » ; les check-runs `Analyze
(python)` / `Analyze (javascript-typescript)` portent `annotations_count: 0` ; les logs de job
listent les requêtes interprétées mais aucun résultat. Le flux est réservé à l'UI dans cette
preview. Conséquence de méthode : **on ne lit pas la page, on reproduit l'analyse**.

Reproduction à l'identique du runner :

- CodeQL **2.26.2** (`codeql-bundle-v2.26.2`, la version du job) ;
- suites `python-code-quality.qls` et `javascript-code-quality.qls` — la default setup passe
  `queries: - uses: code-quality` avec `disable-default-queries: true`, et **aucun**
  `query-filters` ;
- deux langages, `python` et `javascript-typescript`, sur l'arbre entier du dépôt ;
- arbre mesuré : `origin/main` à `49b284b`.

```bash
codeql database create db-python --language=python --build-mode=none --source-root=src
codeql database analyze db-python .../python-code-quality.qls --format=sarif-latest
```

Deux obstacles d'environnement, notés pour qui rejouera la mesure sous le même sandbox :
l'extracteur Python ouvre un **socket local** (refusé → `PermissionError: [Errno 1]`), et CodeQL
écrit son répertoire de packaging dans `/tmp` (non inscriptible ; `TMPDIR` ne le redirige pas).
Les deux se contournent en lançant CodeQL **dans un conteneur** (`python:3.13-slim`, le bundle
embarquant son propre JRE). Le nom de suite abrégé `code-quality` ne se résout pas hors du HOME
habituel : passer le chemin absolu du `.qls`.

## 1. L'inventaire : 38 alertes

37 Python, 1 JavaScript.

| Sévérité | Nb | Règles |
| --- | --- | --- |
| `error` | 3 | `py/side-effect-in-assert` (2), `py/unused-exception-object` (1) |
| `warning` | 6 | `py/implicit-string-concatenation-in-list` (3), `py/regex/duplicate-in-character-class` (1), `py/unreachable-statement` (1), `js/malformed-html-id` (1) |
| `note` | 29 | `py/unused-global-variable` (11), `py/ineffectual-statement` (10), `py/empty-except` (4), `py/unused-import` (2), `py/import-and-import-from` (2) |

Répartition par zone : **20 des 38 sont hors code applicatif** — 9 dans `backend/tests/`, 8 dans
`backend/alembic/versions/`, 1 fixture HTML, 1 script, 1 `alembic/env.py`.

**Le classement de la page n'est pas l'ordre de priorité.** Les trois alertes `error` sont toutes
dans les tests et aucune ne décrit un défaut ; le seul défaut fonctionnel du lot est classé
`warning`.

## 2. Le seul défaut fonctionnel : `geocode_service.py`

`py/regex/duplicate-in-character-class`, `app/services/geocode_service.py:29`. La classe de
caractères s'écrivait `d['']` : **deux apostrophes ASCII identiques**, vérifié à l'octet
(`27 27`). L'intention était `d['’]` — droite **et** typographique.

Mesuré sur la fonction, avant correction :

```
'Triathlon d’Oléron'   -> 'd’Oléron'      ← préfixe non retiré
"Triathlon d'Oléron"   -> 'Oléron'        ← correct
'Duathlon d’Ancenis'   -> 'd’Ancenis'
```

`extract_city` rendait donc un libellé pollué, d'où un géocodage dégradé et une commune fausse
sur la carte. L'apostrophe U+2019 est le cas **courant** : c'est ce que produit l'autocorrection
d'un Google Sheet, et plusieurs chronométreurs la publient.

Impact **non quantifié en base** : la base de dev locale est vide (0 course) et la mesure n'a pas
été faite sur Supabase.

Corrigé, avec les deux graphies verrouillées dans `test_extraction_de_la_ville`. Périmètre tenu
au seul doublon signalé : **l'article élidé `l'` reste non retiré**, limite connue déjà verrouillée
par `test_extraction_de_la_ville_limites_connues` — la variante typographique `l’` y a été ajoutée
pour que la symétrie soit explicite, et non pour la traiter.

## 3. Le seul `except` muet qui posait un problème réel

`py/empty-except`, `app/scrapers/breizhchrono.py:240` : un `except Exception: pass` **large et
muet** autour d'un `client.get`. Le `except DomainError: raise` juste au-dessus montre qu'on avait
traité la remontée du garde SSRF (#101) — mais tout le reste (timeout, HTTP, parsing) laissait
`event_date = None` sans une ligne de journal.

Ce n'est pas cosmétique : `event_date` entre dans `UNIQUE(name, event_date, event_type)`. Sans
trace, **une épreuve importée sans date est indiscernable d'une épreuve qui n'en publie pas**.
Le module n'avait aucun logger ; il en a un, et le bloc journalise en `warning` avec l'URL et la
cause, sans changer la dégradation.

Les **trois autres** `py/empty-except` sont justifiés — `cli/reports.py:188` l'est même
longuement, dans sa docstring. La règle exige seulement le commentaire *à l'intérieur* du bloc :
trois lignes de commentaire, zéro changement de comportement.

## 4. Deux `assert` porteurs de l'effet de bord

`py/side-effect-in-assert` (`error`), `tests/test_api/test_participations_api.py:72` et
`tests/test_api/test_other_api.py:151` : le `DELETE` était *porté* par l'assertion, et
l'assertion suivante vérifiait son effet. Sous `python -O` la requête ne part pas et le test
suivant mesure autre chose. pytest ne tourne jamais en `-O` — impact pratique nul — mais c'est le
seul motif du lot où un effet de bord vit dans un `assert`. Extrait dans une variable.

## 5. Les 31 alertes restantes : trois motifs structurels, à ne pas « corriger »

| Motif | Nb | Verdict, sur pièces |
| --- | --- | --- |
| `...` des méthodes de `Protocol` (`services/progress.py`, `services/auth/idp/base.py`, `scrapers/registry.py`) | 10 | Idiome typé standard. Les remplacer par `pass` ferait taire la règle **au prix de l'idiome** |
| En-têtes Alembic (`revision`, `down_revision`, `branch_labels`, `depends_on`) | 8 | Lues par introspection d'Alembic. **Signal instable** : les 7 migrations ont la même forme, seules 2 alertent |
| Gardes d'idempotence (`logging._CONFIGURED`, `tracing._instrumented_engine` / `_instrumented_app`) | 3 | Faux positif intra-procédural : la remise à `None` est relue au *cycle suivant* (`shutdown` → `setup` → `shutdown`), que l'analyse ne modélise pas |

S'y ajoutent : `pytest.raises` mal compris par CodeQL — 1 `py/unreachable-statement` (le `raise`
final d'un bloc `pytest.raises`) et 1 `py/unused-exception-object` (`LoginError("code_invente")`,
qui valide bien à la construction) ; 3 `py/implicit-string-concatenation-in-list` qui ne sont que
des URLs de test coupées en deux ; 2 `py/unused-import` sur des `import app.models  # noqa: F401`
importés pour leur effet de bord (CodeQL ne lit pas les `noqa` de ruff) ; 2
`py/import-and-import-from` assumés dans `test_klikego.py` ; et le `<div id="">` d'une fixture
chronoweb qui **reproduit fidèlement** le HTML réel de la source, message d'erreur PHP compris.

## 6. Re-mesure après correction

Même bundle, mêmes suites, arbre de travail corrigé :

| | Avant | Après |
| --- | --- | --- |
| Total | 38 | **31** |
| `py/empty-except` | 4 | 0 |
| `py/side-effect-in-assert` | 2 | 0 |
| `py/regex/duplicate-in-character-class` | 1 | 0 |

Les 7 alertes visées sont refermées, **aucune nouvelle n'apparaît**. Suite backend :
2246 tests verts (`-m "not integration"`), `ruff check .` propre.

## 7. Réduire le bruit sans toucher au code : le mécanisme, sondé à mi-chemin

Filtrer le périmètre ne demande **pas** de basculer en advanced setup : la propriété de dépôt
`github-codeql-config-file` désigne un fichier de configuration CodeQL dont le contenu est
**fusionné** avec la configuration générée. Cibles retenues : `backend/alembic/versions/` et
`backend/tests/fixtures/`, portées par `.github/codeql/codeql-config.yml`.

Ce qui est **établi** :

- **L'analyse qui tourne n'est pas la default setup de code scanning.**
  `GET /repos/…/code-scanning/default-setup` répond `"state": "not-configured"` pendant que le
  workflow géré `dynamic/github-code-scanning/codeql` s'exécute avec
  `analysis-kinds: code-quality`. La rédaction initiale de ce §7 supposait l'inverse. Les deux
  pages de documentation consultées décrivent la propriété pour la default setup et **ne disent
  rien** de l'`analysis-kind` `code-quality` : c'est exactement le point qui reste à mesurer.
- **Le point d'injection existe, et il est observable.** L'action `init` reçoit un input `config:`
  porteur de YAML inline (`default-setup:` / `org:` / `model-packs: [ ]`), et le job publie le
  groupe `Augmented user configuration file contents` — aujourd'hui `disable-default-queries:
  true`, `queries: - uses: code-quality`, `query-filters: []`. Un `paths-ignore` fusionné y serait
  **lisible dans les logs**. La vérification de ce mécanisme ne passe donc **pas** par l'UI,
  contrairement à la lecture des alertes (§Méthode).
- **La propriété doit d'abord être déclarée dans l'organisation**, et la déclaration exige le scope
  `admin:org` (`gh auth refresh -h github.com -s admin:org`) : le schéma partait de `[]`.
- **Les propriétés personnalisées sont bien disponibles sur un plan d'organisation `free`.** Mesuré :
  `PUT /orgs/Triathlon-Club-Nantais/properties/schema/github-codeql-config-file` avec
  `value_type: string` est accepté. Déclarée **sans `default_value`**, la propriété laisse tous les
  dépôts de l'org à `value: null` — vérifié sur `/properties/values` — donc la déclaration seule ne
  change aucun run. C'est ce qui permet de la poser avant de décider où l'activer.
- **La propriété porte sur le dépôt, jamais sur la branche.** Un chemin local ne se résout donc que
  sur les refs qui contiennent le fichier. D'où la forme retenue,
  `remote=Triathlon-Club-Nantais/data-triathlon@main:.github/codeql/codeql-config.yml`, posée
  **après** l'arrivée du fichier sur `main` : elle se résout alors identiquement sur toutes les
  branches et n'ouvre aucune fenêtre pendant laquelle une PR en cours pointerait un fichier absent
  de sa ref (au moment du sondage, #161 ne l'avait pas).

Ce qui **reste à mesurer**, et ne doit pas être tenu pour acquis :

- **que l'`analysis-kind` `code-quality` honore la propriété** — la seule inconnue qui décide de tout
  le reste, et que rien dans la documentation ne tranche ;
- l'effet réel sur le décompte : **9 alertes de moins sur 31** attendues (8 en-têtes Alembic + le
  `js/malformed-html-id` de la fixture chronoweb).

Reste à faire, dans cet ordre : le fichier arrive sur `main` avec la PR de ce sondage, puis
`PATCH /repos/…/properties/values` pose la valeur
`remote=Triathlon-Club-Nantais/data-triathlon@main:.github/codeql/codeql-config.yml`, puis le groupe
`Augmented user configuration file contents` du run suivant tranche. Si la propriété s'avère ignorée
par l'`analysis-kind` `code-quality`, le fichier est à retirer — il ne faut pas le laisser en place
en laissant croire qu'il filtre quelque chose.

Deux règles portées par le fichier de configuration lui-même. Il ne porte **que** `paths-ignore` :
y ajouter `queries` ou `disable-default-queries` remplacerait la suite `code-quality` que la default
setup passe, donc le sens de la page. Et `backend/tests/` n'est **pas** filtré — les deux
`py/side-effect-in-assert` du §4 y étaient de vrais défauts, un filtre en bloc les aurait masqués.

Les **3 gardes d'idempotence** de `app/core/` (§5) ne sont pas filtrables par chemin. Elles restent
à fermer dans l'UI (« Won't fix »), comme les alertes de tests hors fixtures qu'on choisirait de ne
pas traiter.

## 8. Points restés ouverts

- **Pourquoi 2 migrations sur 7 alertent** alors que leurs en-têtes sont de forme identique.
  `UnusedModuleVariable.ql` porte une clause d'exclusion inter-scope
  (`defn.getBasicBlock().reachesExit() and u.getScope() != unused.getScope()`) et une notion
  d'export de module (`ModuleWithPointsTo.getAnExport()`) qu'on n'a pas réussi à rattacher à la
  différence observée. Conséquence pratique : **ne pas industrialiser de correction sur ce
  motif**, le signal n'étant pas stable.
- **L'impact de la regex n'est pas quantifié sur les données de production** (base de dev vide,
  pas d'accès Supabase depuis la mesure).
