# Contrat CLI : `reconcile-athletes` (#906, #907, #908, #900)

Commande de reprise des données, sur le modèle de `purge-timepulse-duplicates` (`backend/app/cli/AGENTS.md`). Logique dans `app/services/athlete_reconciliation.py` ; la commande ne fait qu'analyser les options, ouvrir la session et rendre le rapport.

## Invocation

```bash
uv run python -m app.cli reconcile-athletes                               # simulation, rien n'est écrit
uv run python -m app.cli reconcile-athletes --json                        # simulation, bilan JSON sur stdout
uv run python -m app.cli reconcile-athletes --yes --by-email admin@…      # application
```

| Option | Effet |
| --- | --- |
| *(aucune)* | simulation : calcule tout, n'écrit rien, rapport complet |
| `--yes` | applique ; exige `--by-email` |
| `--by-email` | compte admin sous lequel chaque fusion est journalisée ; inconnu → code 2 |
| `--json` | stdout ne porte que la ligne JSON ; rapport texte sur stderr |
| `--no-progress` | pas de progression sur stderr |

## Sortie JSON

```json
{
  "applied": false,
  "families": {
    "comma_names":   {"renamed": 3430, "merged": 2951, "review": 0},
    "same_key":      {"merged": 1930, "review": 8},
    "swapped":       {"merged": 1100, "review": 196},
    "concatenated":  {"merged": 3200, "review": 363}
  },
  "operations": [
    {"family": "same_key", "action": "merge", "kept_id": 96493, "absorbed_id": 34479},
    {"family": "comma_names", "action": "rename", "athlete_id": 126328, "nom": "HOFMANN", "prenom": "Patrick"}
  ],
  "review": [
    {"family": "same_key", "athlete_ids": [126900, 126901], "reason": "same_course_bibs"}
  ],
  "errors": []
}
```

Les chiffres ci-dessus sont illustratifs. Les clés `families`, `operations`, `review` et `errors` sont stables ; une simulation et une application sur les mêmes données donnent les mêmes `operations` (SC-009).

## Codes de sortie

| Code | Cas |
| --- | --- |
| 0 | succès, y compris simulation, « rien à faire » et application partielle (`errors` non vide) |
| 1 | échec total (aucune opération appliquée alors qu'il y en avait) |
| 2 | usage : `--yes` sans `--by-email`, compte inconnu |
| 130 | Ctrl-C ; le rapport partiel est émis, les fusions déjà commitées restent |

## Garanties

- Une transaction par opération : une interruption ne laisse aucune fusion à moitié faite.
- Idempotente : relancée après application, `operations` est vide.
- N'agit jamais sur les fiches factices (clé vide, `?DOSSARD`, `Anonyme`, identités masquées, noms d'équipe).
