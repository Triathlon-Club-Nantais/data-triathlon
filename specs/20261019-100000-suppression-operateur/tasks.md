# Tasks: Suppression d'un compte par l'exploitant

- [x] T001 Tests repository : `required_reference_counts` (par colonne, zéro omis), `reassign_required_references`
- [x] T002 `backend/app/repositories/user_repository.py`
- [x] T003 Tests service `force_delete_account` : passe à blanc sans effet, application (références au compte système, compte supprimé, journal `operator`), dernier administrateur refusé, compte système refusé
- [x] T004 `backend/app/services/auth/accounts.py`
- [x] T005 Tests CLI `delete-account` : cible requise et exclusive, inconnu en code 2, passe à blanc, `--yes`
- [x] T006 `backend/app/cli/commands/delete_account.py`, enregistrement
- [x] T007 Docs `backend/app/cli/AGENTS.md`, `infra/entra-external-id/AGENTS.md`
- [x] T008 Suite backend et ruff
