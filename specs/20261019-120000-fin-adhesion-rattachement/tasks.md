# Tasks: Fin du statut adhérent par rattachement, détachement par le club

- [x] T001 Tests `membership.is_member` : licencié rattaché de la saison, licence passée seule, licence non rattachée, adresse sur la liste
- [x] T002 `club_member_repository.is_linked_licensee`, `membership.is_member`
- [x] T003 Tests service `list_links` et `admin_detach` (journal, 404 sans fiche)
- [x] T004 `user_repository.list_linked`, service `athlete_claims`
- [x] T005 Tests API `GET /admin/athlete-links`, `DELETE /admin/athlete-links/{user_id}` (401, 403, 200, 204, 404)
- [x] T006 Schémas et routes
- [x] T007 Tests front : section « Comptes rattachés », détachement confirmé
- [x] T008 Types, client, hooks, composant `AthleteLinksTable`, pose sur `/admin/rattachements`, libellé du journal
- [x] T009 Politique de confidentialité, `docs/auth/membres.md`, guide admin
- [x] T010 Suites complètes
