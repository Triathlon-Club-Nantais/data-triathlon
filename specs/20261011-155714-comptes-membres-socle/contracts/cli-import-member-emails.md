# Contrat : `python -m app.cli import-member-emails` (#1334)

```bash
uv run python -m app.cli import-member-emails --season 2026 --file export-assoconnect.xlsx [--json]
```

- `--season` (obligatoire, borné), `--file` (chemin CSV ou XLSX).
- Sortie texte (stdout) : saison, ajoutées, retirées, inchangées, ignorées.
- `--json` : stdout ne porte que `{"season", "added", "removed", "unchanged", "ignored"}`, le texte part sur stderr (`emit_report`).
- Codes de sortie : 0 succès ; 1 échec (`DomainError` : message français sur stderr, aucune écriture) ; 2 usage (Typer, fichier introuvable) ; 130 interruption.
- Journal : `member_emails.import`, `user_id` nul (pas d'acteur).
