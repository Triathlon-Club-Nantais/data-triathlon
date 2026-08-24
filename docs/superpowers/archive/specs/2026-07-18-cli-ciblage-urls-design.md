# Cibler des épreuves précises en CLI (`--url` / `--urls-from`)

Issue : [#46](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/46)
Date : 2026-07-18

## Problème

Les batches sont tout-ou-rien. Un run d'`import-sheet` qui laisse 5 épreuves en
erreur sur 42 n'offre aucun moyen de rejouer ces 5-là : il faut relancer les 42.
Le bilan liste pourtant déjà les échecs (URL + cause), mais rien ne les consomme.

## Le contre-sens à éviter

L'issue propose de brancher `rescrape-db` sur les échecs d'`import-sheet` :

```bash
python -m app.cli import-sheet --json | jq -r '.failures[].url' > failures.txt
python -m app.cli rescrape-db --urls-from failures.txt
```

Cette boucle ne peut pas fonctionner si `--url` est un **filtre** sur la base :
une épreuve qui a échoué à l'import n'a rien persisté, elle est absente de la
table `course`, et `rescrape-db` ne sélectionne ses épreuves que via
`course_repository.iter_all()`. Le rejeu porterait sur zéro épreuve et sortirait
en code 0 — silence trompeur, exactement le défaut que `valider_provider` avait
déjà corrigé pour `--provider`.

**Décision : `--url` court-circuite la base.** Les URLs fournies sont soumises
telles quelles au batch, qu'elles soient connues en base ou non. `rescrape-db`
répond alors à deux besoins distincts mais tous deux légitimes : « re-scrape ce
que la base contient, filtré ainsi » et « re-scrape ces épreuves-là ».

Corollaire : `--url` / `--urls-from` sont **exclusifs** de `--provider` et
`--older-than`. Ce sont deux modes de sélection, pas des filtres à composer ; les
combiner silencieusement produirait un ET dont personne ne peut prédire le
résultat. La combinaison est une erreur d'usage (code 2).

Corollaire second : la question ouverte de l'issue — « `--url` inconnu en base :
code 2 ou ignoré avec mention ? » — devient sans objet. Une URL inconnue est le
**cas nominal** du rejeu d'un échec d'import, pas une anomalie. Elle est scrapée
normalement, sans avertissement.

## Périmètre

Dans le périmètre :

- `rescrape-db` : options `--url` (répétable) et `--urls-from <fichier|->`.
- `RescrapeOutcome` : détail des épreuves en échec, aligné sur `SheetOutcome`.
- Documentation : `AGENTS.md` (seul document vivant décrivant la CLI ; le
  `README.md` ne mentionne pas ces commandes, les plans de `docs/superpowers/`
  sont historiques et ne sont pas rétro-édités).

Hors périmètre, volontairement :

- Pas de `--url` sur `import-sheet` : le Google Sheet est sa source, une URL
  arbitraire n'y a pas sa place — c'est le rôle de `rescrape-db`.
- Pas de mémorisation des échecs entre deux runs (fichier d'état, table
  dédiée). Le pipe couvre le besoin ; un état persistant est une autre feature.

## Conception

### Nouveau module `cli/url_sources.py`

`validators.py` valide des saisies déjà en mémoire ; collecter les URLs suppose
en plus de la **lecture** (fichier, stdin). Assez pour justifier un module
distinct, minuscule et testable isolément.

```python
def charger_urls(urls: list[str], urls_from: str | None) -> list[str]:
```

Comportement :

- Concatène les `--url` répétés puis le contenu de `--urls-from`. Les deux
  options se cumulent (ajouter une URL à une liste est un besoin légitime).
  `--url` est répétable, `--urls-from` ne l'est pas : une seule source de liste,
  `cat a.txt b.txt | … --urls-from -` couvre le reste.
- `--urls-from -` lit **stdin**, ce qui supprime le fichier intermédiaire.
- Ignore les lignes vides et celles commençant par `#` : un opérateur qui
  construit sa liste à la main commente une URL plutôt que de la supprimer.
- Rejette toute ligne restante non-`http(s)` par `typer.BadParameter`, en citant
  le **numéro de ligne**. Corrigeable sans relire le fichier à l'œil.
- Fichier introuvable ou illisible → `typer.BadParameter` également.
- Dédoublonne via `sheet_source.dedupe_links` : ordre et forme d'origine
  conservés, clé de dédup `normalize_url` — la même que partout ailleurs.

```python
def valider_ciblage_exclusif(*, urls, provider, older_than) -> None:
```

Lève `typer.BadParameter` si un ciblage par URL est combiné à `--provider` ou
`--older-than`. Un callback Typer ne voit que sa propre option : cette
vérification croisée est appelée explicitement en tête de commande, **avant**
l'ouverture de la Session.

Échouer en couche CLI plutôt qu'en service donne gratuitement le bon contrat :
message et usage sur stderr, code de sortie 2 (convention Click), arrêt avant
tout travail. Même raisonnement que `valider_provider`.

`--limit` reste compatible avec `--url` : il ne sélectionne rien dans la base, il
borne la liste finale. Aucune raison de l'interdire.

### `rescrape_service.run_rescrape_db(..., urls: list[str] | None = None)`

Deux sources d'épreuves, un seul batch en aval :

- `urls=None` → comportement actuel : `iter_all(provider, older_than_days)`,
  filtrage des courses sans `source_url`, dédup par URL, `--limit`.
- `urls` fourni → **la base n'est pas interrogée pour sélectionner**. Chaque URL
  devient un `BatchItem`. Le libellé d'affichage est cherché via
  `course_repository.get_latest_by_source_url` ; épreuve inconnue → le libellé
  **retombe sur l'URL**. Aucune dégradation fonctionnelle : le libellé est
  cosmétique, il ne sert qu'à la ligne de progression.

Tout le reste est inchangé et le reste par construction, puisque les deux modes
convergent sur `run_batch` : `force=True` (bypass du cache TTL), `--delay`,
dry-run listant les URLs ciblées sans scraper, `echec_total`, Ctrl-C à 130. C'est
la raison de ne pas introduire une troisième commande : la boucle de batch, la
gestion d'interruption et le contrat de sortie existent déjà.

### Bilans alignés

`run_batch` collecte déjà un `BatchFailure(url, label, message)` par épreuve
fautive, pour les deux commandes — mais `RescrapeOutcome` le jette, seul
`SheetOutcome` le porte. Le compteur « Épreuves en erreur : 3 » de `rescrape-db`
dit donc *combien*, jamais *lesquelles*.

Avec le rejeu, ce trou devient bloquant : on rejoue 5 échecs, 2 échouent encore,
et une troisième tentative suppose de relire le terminal à la main. La boucle ne
se referme pas sur elle-même.

- `RescrapeOutcome` gagne `failures: list[BatchFailure]`, recopié depuis
  `BatchTotals`. `asdict()` l'embarque dans `--json` sans code supplémentaire.
- Dans `reports.py`, le bloc « Épreuves en erreur (détail) : » sort de
  `render_sheet_report` vers un helper `_lignes_echecs(outcome)` appelé par les
  deux rendus — deux fonctions qui divergeaient sans raison.

Le détail reste borné aux seuls échecs : léger, contrairement à une liste de
toutes les épreuves.

Le rejeu devient alors idempotent, sans fichier intermédiaire :

```bash
uv run python -m app.cli rescrape-db --json | jq -r '.failures[].url' \
  | uv run python -m app.cli rescrape-db --urls-from -
```

Liste d'échecs vide → zéro épreuve ciblée → code 0 (« rien à faire », déjà prévu
par la table des codes de sortie). On peut donc rejouer jusqu'à convergence.

### Codes de sortie

Inchangés, aucune sémantique nouvelle :

| Code | Cas |
| --- | --- |
| `0` | Succès, y compris partiel, y compris zéro épreuve ciblée. |
| `1` | Échec total : aucune des épreuves rejouées n'a abouti. |
| `2` | Saisie invalide : `--url` avec `--provider`/`--older-than`, ligne non-http, fichier illisible. |
| `130` | Ctrl-C, prioritaire sur `1`. |

## Tests

`tests/test_cli/` :

- `--url` répété, `--urls-from` fichier, `--urls-from -` (stdin).
- Lignes vides et commentaires `#` ignorés.
- Ligne non-http → code 2, message citant le numéro de ligne.
- Fichier introuvable → code 2.
- `--url` combiné à `--provider` → code 2 ; idem avec `--older-than`.
- Fichier vide → zéro épreuve ciblée, code 0.
- `failures` présent dans le rapport texte **et** dans la charge `--json` de
  `rescrape-db`.

`tests/test_services/` :

- Mode `urls` : `iter_all` n'est pas appelé.
- Libellé `provider · name` quand la course existe en base ; repli sur l'URL
  sinon.
- Deux formes de la même URL (casse d'hôte, slash final) → une seule épreuve.
- Dry-run en mode `urls` : `dry_run_urls` peuplé, aucun scrape.

Aucun test réseau : `run_batch` est déjà mocké dans les tests existants, le
marker `integration` n'est pas concerné.

## Documentation

- `AGENTS.md` : bloc des commandes CLI (ajout des deux options et de la boucle de
  rejeu) ; la phrase qui réserve le détail des échecs à `import-sheet` devient
  fausse et doit être corrigée.
- `README.md` : à mettre à jour si la CLI y est décrite.
