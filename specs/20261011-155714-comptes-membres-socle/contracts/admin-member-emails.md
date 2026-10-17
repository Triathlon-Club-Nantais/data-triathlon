# Contrat : `/api/v1/admin/member-emails` (#1334)

Toutes les routes : garde du code d'accès au site (inclusion dans le tuple gardé de `api/v1/router.py`) **et** `require_permission(P.MEMBER_EMAILS_MANAGE)` posé route par route. Sans session : 401 ; sans le pouvoir : 403.

## `GET /admin/member-emails?season=<int>`

`season` optionnel (défaut : saison en cours), borné `SEASON_MIN..SEASON_MAX` (422 sinon).

```json
{
  "season": 2026,
  "counting_season": 2025,
  "seasons": [2026, 2025],
  "entries": [
    {"id": 12, "email": "jeanne@exemple.fr", "season": 2026, "source": "import", "created_at": "2026-10-11T14:00:00Z"}
  ]
}
```

`counting_season` : saison qui compte aujourd'hui, la saison en cours dès qu'elle a une entrée importée, sinon la précédente (règle de `data-model.md`). Entrées triées par adresse.

## `POST /admin/member-emails/import`

`multipart/form-data` : `season` (int, borné), `file` (CSV ou XLSX, taille bornée par `read_bounded_upload`).

200 :
```json
{"season": 2026, "added": 280, "removed": 4, "unchanged": 12, "ignored": 3}
```

422 (`DomainError`, message français) : format non pris en charge, fichier illisible, aucune colonne d'e-mail reconnue (`MissingEmailColumnError`), aucune adresse valide (`NoValidEmailError`), saison hors bornes. Aucune écriture dans ces cas. 409 si la liste change pendant l'import (`ConcurrentImportError`). Journal : `member_emails.import`, avec les quatre compteurs (aucune adresse).

## `POST /admin/member-emails`

```json
{"email": "jeanne@exemple.fr", "season": 2026}
```

201 → l'entrée (même forme que `entries[]`, `source: "manual"`). 422 adresse invalide ; 409 déjà présente en manuel pour la saison. Journal : `member_emails.add`.

## `DELETE /admin/member-emails/{id}`

204 ; 404 inconnue. Journal : `member_emails.remove`.
