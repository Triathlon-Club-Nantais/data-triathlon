# Inventaire : consolidation des tests (#1707)

Lots de la décision K de `2026-10-20-test-process-design.md`. Chaque lot suit
la procédure « Consolider un lot » de `docs/tests-boucle.md` ; sa ligne est mise
à jour dans le commit du lot.

## Règle de découpage

Un lot par zone, attribuée par fichier de test :

- **Lots 1 à 4** : les quatre fichiers que la spec nomme (tâches 12 à 15), sortis
  de leur zone.
- **Backend, racine de `tests/`** : `test_<p>*.py` où `<p>` est un module de
  `app/scrapers/` (hors `base`, `classify`, `registry`, `utils`) donne la zone
  « fournisseur `<p>` » ; `test_<s>.py` où `<s>` est un module de
  `app/services/` donne « service `<s>` » ; le reste forme « backend tests/
  (racine, transverse) ».
- **Backend, `tests/test_services/`** : un lot par fichier, « service `<s>` »
  quand `app/services/<s>.py` existe, « service (`<nom>`) » sinon (test
  transverse à plusieurs services, à rattacher à la lecture).
- **Backend, autres dossiers** (`test_api/`, `test_auth/`, `test_cli/`,
  `test_core/`, `test_repositories/`, `test_scripts/`) : un lot par dossier. Ce
  sont les plus gros : le budget de 30 min de mutation y impose presque
  toujours la restriction aux fonctions touchées, et un lot peut s'y traiter en
  plusieurs commits, un par sous-ensemble cohérent.
- **Frontend, `app/`** : un lot par premier segment de route, groupes `(…)`
  ignorés (`app/(public_restricted)/athletes/[id]/` → « routes app/athletes ») ;
  les tests posés directement sous `app/` ou sous un groupe forment
  « routes app/ (racine) ».
- **Frontend, `components/`** : un lot par dossier de composants (dossier
  parent direct du fichier).
- **Frontend, ailleurs** (`lib/…`, `hooks/`, `test/`, `scripts/`, racine) : un
  lot par dossier.

Ordre : lots 1 à 4, puis lignes décroissantes. « Tests » compte les tests
collectés (un cas de `parametrize` ou de `it.each` compte pour un), y compris
les tests `integration` et `migrations`.

État au 21/10/2026, après le lot 4 : 614 fichiers, 135 676 lignes, 10 412 tests,
153 lots.

## Lots

| Lot | Zone | Fichiers de test | Code couvert | Lignes | Tests | Statut |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | test_raceresult.py | `test_raceresult.py` (sous `backend/tests/`) | `backend/app/scrapers/raceresult.py` | 4132 | 377 | gardé (tâche 12) : tests 381 → 377, mutation 1613/2074 → 1613/2074, couverture 95,6 % → 95,6 % |
| 2 | test_import_service.py | `test_import_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/import_service.py` | 2962 | 162 | gardé (tâche 13) : tests 169 → 162, mutation 225/389 → 225/389, couverture 96,2 % → 96,2 % |
| 3 | RaceFinishers.test.tsx | `RaceFinishers.test.tsx` (sous `frontend/components/results/`) | `frontend/components/results/RaceFinishers.tsx` | 1589 | 113 | gardé (tâche 14) : tests 134 → 113, mutation 451/749 → 451/749, couverture 98,5 % → 98,5 % |
| 4 | AppNav.test.tsx | `AppNav.test.tsx` (sous `frontend/components/layout/`) | `frontend/components/layout/AppNav.tsx` | 1750 | 125 | gardé (tâche 15) : tests 146 → 125, mutation 391/783 → 391/783, couverture 96,7 % → 96,7 % |
| 5 | backend test_api/ | 48 fichiers (sous `backend/tests/test_api/`) | `backend/app/api/` | 11936 | 888 | à faire (tâche 16) |
| 6 | backend test_auth/ | 56 fichiers (sous `backend/tests/test_auth/`) | `backend/app/services/auth/` | 11209 | 1075 | à faire (tâche 16) |
| 7 | composants admin | 48 fichiers (sous `frontend/components/admin/`) | `frontend/components/admin/` | 10707 | 551 | à faire (tâche 16) |
| 8 | backend test_repositories/ | 39 fichiers (sous `backend/tests/test_repositories/`) | `backend/app/repositories/` | 10077 | 655 | à faire (tâche 16) |
| 9 | backend tests/ (racine, transverse) | 29 fichiers (sous `backend/tests/`) | `backend/app/` | 6057 | 997 | à faire (tâche 16) |
| 10 | backend test_cli/ | 23 fichiers (sous `backend/tests/test_cli/`) | `backend/app/cli/` | 3365 | 214 | à faire (tâche 16) |
| 11 | service admin_actions | `test_admin_actions.py` (sous `backend/tests/test_services/`) | `backend/app/services/admin_actions.py` | 2690 | 148 | à faire (tâche 16) |
| 12 | fournisseur klikego | `test_klikego.py` (sous `backend/tests/`) | `backend/app/scrapers/klikego.py` | 2632 | 155 | à faire (tâche 16) |
| 13 | composants athletes | 10 fichiers (sous `frontend/components/athletes/`) | `frontend/components/athletes/` | 2160 | 111 | à faire (tâche 16) |
| 14 | frontend lib/utils | 23 fichiers (sous `frontend/lib/utils/`) | `frontend/lib/utils/` | 2071 | 220 | à faire (tâche 16) |
| 15 | composants scrape | 5 fichiers (sous `frontend/components/scrape/`) | `frontend/components/scrape/` | 1927 | 108 | à faire (tâche 16) |
| 16 | routes app/athletes | 6 fichiers (sous `frontend/app/(public_restricted)/athletes/[id]/`) | `frontend/app/(public_restricted)/athletes/` | 1821 | 116 | à faire (tâche 16) |
| 17 | composants admin/jeunes | 10 fichiers (sous `frontend/components/admin/jeunes/`) | `frontend/components/admin/jeunes/` | 1778 | 84 | à faire (tâche 16) |
| 18 | backend test_core/ | 19 fichiers (sous `backend/tests/test_core/`) | `backend/app/core/` | 1756 | 460 | à faire (tâche 16) |
| 19 | composants results | 6 fichiers (sous `frontend/components/results/`) | `frontend/components/results/` | 1729 | 98 | à faire (tâche 16) |
| 20 | routes app/ (racine) | 13 fichiers (sous `frontend/app/`) | `frontend/app/` | 1569 | 109 | à faire (tâche 16) |
| 21 | fournisseur wiclax | `test_wiclax.py` (sous `backend/tests/`) | `backend/app/scrapers/wiclax.py` | 1527 | 84 | à faire (tâche 16) |
| 22 | composants benevoles | 7 fichiers (sous `frontend/components/benevoles/`) | `frontend/components/benevoles/` | 1492 | 89 | à faire (tâche 16) |
| 23 | composants club | 9 fichiers (sous `frontend/components/club/`) | `frontend/components/club/` | 1456 | 98 | à faire (tâche 16) |
| 24 | fournisseur oktime | `test_oktime.py` (sous `backend/tests/`) | `backend/app/scrapers/oktime.py` | 1368 | 129 | à faire (tâche 16) |
| 25 | fournisseur sporthive | `test_sporthive.py` (sous `backend/tests/`) | `backend/app/scrapers/sporthive.py` | 1355 | 98 | à faire (tâche 16) |
| 26 | composants layout | 10 fichiers (sous `frontend/components/layout/`) | `frontend/components/layout/` | 1276 | 102 | à faire (tâche 16) |
| 27 | fournisseur breizhchrono | `test_breizhchrono.py` (sous `backend/tests/`) | `backend/app/scrapers/breizhchrono.py` | 1269 | 56 | à faire (tâche 16) |
| 28 | composants tcn/participation-detail | 5 fichiers (sous `frontend/components/tcn/participation-detail/`) | `frontend/components/tcn/participation-detail/` | 1239 | 102 | à faire (tâche 16) |
| 29 | fournisseur chronoplace | `test_chronoplace.py` (sous `backend/tests/`) | `backend/app/scrapers/chronoplace.py` | 1176 | 108 | à faire (tâche 16) |
| 30 | service stats_service | `test_stats_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/stats_service.py` | 1145 | 57 | à faire (tâche 16) |
| 31 | composants dashboard | 7 fichiers (sous `frontend/components/dashboard/`) | `frontend/components/dashboard/` | 1114 | 76 | à faire (tâche 16) |
| 32 | frontend lib | 15 fichiers (sous `frontend/lib/`) | `frontend/lib/` | 1107 | 100 | à faire (tâche 16) |
| 33 | fournisseur prolivesport | `test_prolivesport.py` (sous `backend/tests/`) | `backend/app/scrapers/prolivesport.py` | 1092 | 78 | à faire (tâche 16) |
| 34 | composants tcn | 17 fichiers (sous `frontend/components/tcn/`) | `frontend/components/tcn/` | 1091 | 89 | à faire (tâche 16) |
| 35 | composants charts | 9 fichiers (sous `frontend/components/charts/`) | `frontend/components/charts/` | 1076 | 78 | à faire (tâche 16) |
| 36 | fournisseur sportinnovation | `test_sportinnovation.py` (sous `backend/tests/`) | `backend/app/scrapers/sportinnovation.py` | 1006 | 86 | à faire (tâche 16) |
| 37 | service course_duplicates | `test_course_duplicates.py` (sous `backend/tests/test_services/`) | `backend/app/services/course_duplicates.py` | 1005 | 29 | à faire (tâche 16) |
| 38 | fournisseur chronoweb | `test_chronoweb.py` (sous `backend/tests/`) | `backend/app/scrapers/chronoweb.py` | 970 | 87 | à faire (tâche 16) |
| 39 | composants courses | 4 fichiers (sous `frontend/components/courses/`) | `frontend/components/courses/` | 934 | 52 | à faire (tâche 16) |
| 40 | routes app/courses | 4 fichiers (sous `frontend/app/(public_restricted)/courses/[id]/`) | `frontend/app/(public_restricted)/courses/` | 918 | 66 | à faire (tâche 16) |
| 41 | service batch | `test_batch.py` (sous `backend/tests/test_services/`) | `backend/app/services/batch.py` | 906 | 39 | à faire (tâche 16) |
| 42 | fournisseur timepulse | `test_timepulse.py` (sous `backend/tests/`) | `backend/app/scrapers/timepulse.py` | 848 | 53 | à faire (tâche 16) |
| 43 | routes app/benevoles | `layout.test.tsx`, `page.test.tsx` (sous `frontend/app/benevoles/`) | `frontend/app/benevoles/` | 809 | 38 | à faire (tâche 16) |
| 44 | routes app/admin | 10 fichiers (sous `frontend/app/admin/`) | `frontend/app/admin/` | 670 | 28 | à faire (tâche 16) |
| 45 | fournisseur runnerbreizh | `test_runnerbreizh.py` (sous `backend/tests/`) | `backend/app/scrapers/runnerbreizh.py` | 665 | 47 | à faire (tâche 16) |
| 46 | frontend lib/queries | 4 fichiers (sous `frontend/lib/queries/`) | `frontend/lib/queries/` | 658 | 34 | à faire (tâche 16) |
| 47 | fournisseur t2area | `test_t2area.py` (sous `backend/tests/`) | `backend/app/scrapers/t2area.py` | 633 | 76 | à faire (tâche 16) |
| 48 | frontend lib/api | 4 fichiers (sous `frontend/lib/api/`) | `frontend/lib/api/` | 578 | 39 | à faire (tâche 16) |
| 49 | frontend (racine) | 4 fichiers (sous `frontend/`) | `frontend/` | 567 | 42 | à faire (tâche 16) |
| 50 | service participation_stats_service | `test_participation_stats_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/participation_stats_service.py` | 550 | 43 | à faire (tâche 16) |
| 51 | composants benevolat | `AdminVolunteerActionsTable.test.tsx`, `VolunteerActionForm.test.tsx` (sous `frontend/components/benevolat/`) | `frontend/components/benevolat/` | 546 | 31 | à faire (tâche 16) |
| 52 | service geocode_service | `test_geocode_service.py` (sous `backend/tests/`) | `backend/app/services/geocode_service.py` | 526 | 52 | à faire (tâche 16) |
| 53 | fournisseur competitor | `test_competitor.py` (sous `backend/tests/`) | `backend/app/scrapers/competitor.py` | 526 | 46 | à faire (tâche 16) |
| 54 | service athlete_identity_review | `test_athlete_identity_review.py` (sous `backend/tests/test_services/`) | `backend/app/services/athlete_identity_review.py` | 486 | 40 | à faire (tâche 16) |
| 55 | service rescrape_service | `test_rescrape_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/rescrape_service.py` | 486 | 22 | à faire (tâche 16) |
| 56 | service batch_runs | `test_batch_runs.py` (sous `backend/tests/test_services/`) | `backend/app/services/batch_runs.py` | 482 | 48 | à faire (tâche 16) |
| 57 | frontend hooks | 4 fichiers (sous `frontend/hooks/`) | `frontend/hooks/` | 466 | 21 | à faire (tâche 16) |
| 58 | composants auth | `UserMenu.test.tsx` (sous `frontend/components/auth/`) | `frontend/components/auth/` | 450 | 34 | à faire (tâche 16) |
| 59 | service athlete_reconciliation | `test_athlete_reconciliation.py` (sous `backend/tests/test_services/`) | `backend/app/services/athlete_reconciliation.py` | 417 | 23 | à faire (tâche 16) |
| 60 | routes app/club | `athletes/page.test.tsx`, `page.test.tsx` (sous `frontend/app/(public_restricted)/club/`) | `frontend/app/(public_restricted)/club/` | 401 | 24 | à faire (tâche 16) |
| 61 | routes app/encadrement | 6 fichiers (sous `frontend/app/encadrement/`) | `frontend/app/encadrement/` | 387 | 18 | à faire (tâche 16) |
| 62 | service (passive_source_on_import) | `test_passive_source_on_import.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 384 | 15 | à faire (tâche 16) |
| 63 | service opposition_service | `test_opposition_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/opposition_service.py` | 378 | 35 | à faire (tâche 16) |
| 64 | service mapping | `test_mapping.py` (sous `backend/tests/test_services/`) | `backend/app/services/mapping.py` | 354 | 48 | à faire (tâche 16) |
| 65 | service training_session_service | `test_training_session_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/training_session_service.py` | 347 | 24 | à faire (tâche 16) |
| 66 | routes app/mon-espace | `loading.test.tsx`, `page.test.tsx` (sous `frontend/app/(public_restricted)/mon-espace/`) | `frontend/app/(public_restricted)/mon-espace/` | 342 | 22 | à faire (tâche 16) |
| 67 | composants site-access | `ForgetSiteAccessButton.test.tsx`, `SiteAccessGate.test.tsx`, `SiteAccessLink.test.tsx` (sous `frontend/components/site-access/`) | `frontend/components/site-access/` | 339 | 21 | à faire (tâche 16) |
| 68 | service athlete_merge | `test_athlete_merge.py` (sous `backend/tests/test_services/`) | `backend/app/services/athlete_merge.py` | 338 | 24 | à faire (tâche 16) |
| 69 | composants legal/content | 4 fichiers (sous `frontend/components/legal/content/`) | `frontend/components/legal/content/` | 333 | 33 | à faire (tâche 16) |
| 70 | service (authorization) | `test_authorization.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 325 | 15 | à faire (tâche 16) |
| 71 | service retention_service | `test_retention_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/retention_service.py` | 321 | 25 | à faire (tâche 16) |
| 72 | service club_members_service | `test_club_members_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/club_members_service.py` | 318 | 21 | à faire (tâche 16) |
| 73 | service split_gap | `test_split_gap.py` (sous `backend/tests/test_services/`) | `backend/app/services/split_gap.py` | 317 | 38 | à faire (tâche 16) |
| 74 | frontend test | 6 fichiers (sous `frontend/test/`) | `frontend/test/` | 311 | 14 | à faire (tâche 16) |
| 75 | composants home | `BandeauDirect.test.tsx`, `ChiffreAnime.test.tsx`, `TuilesEspaces.test.tsx` (sous `frontend/components/home/`) | `frontend/components/home/` | 305 | 29 | à faire (tâche 16) |
| 76 | service (duplicate_rank_renumbering) | `test_duplicate_rank_renumbering.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 291 | 11 | à faire (tâche 16) |
| 77 | service training_recurrence_service | `test_training_recurrence_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/training_recurrence_service.py` | 279 | 17 | à faire (tâche 16) |
| 78 | service (counts_for_tcn_triggers) | `test_counts_for_tcn_triggers.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 273 | 12 | à faire (tâche 16) |
| 79 | service bulk_import_service | `test_bulk_import_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/bulk_import_service.py` | 267 | 12 | à faire (tâche 16) |
| 80 | service (relay_split_rank_renumbering) | `test_relay_split_rank_renumbering.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 267 | 6 | à faire (tâche 16) |
| 81 | service club_service | `test_club_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/club_service.py` | 259 | 14 | à faire (tâche 16) |
| 82 | service (import_identity) | `test_import_identity.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 258 | 18 | à faire (tâche 16) |
| 83 | frontend scripts | `backend-url.test.mjs`, `exit-code.test.mjs` (sous `frontend/scripts/`) | `frontend/scripts/` | 257 | 23 | à faire (tâche 16) |
| 84 | backend test_scripts/ | `test_dev_server.py`, `test_repair_courses.py` (sous `backend/tests/test_scripts/`) | `backend/scripts/` | 249 | 19 | à faire (tâche 16) |
| 85 | composants guide | 4 fichiers (sous `frontend/components/guide/`) | `frontend/components/guide/` | 249 | 24 | à faire (tâche 16) |
| 86 | frontend lib/__tests__ | 4 fichiers (sous `frontend/lib/__tests__/`) | `frontend/lib/__tests__/` | 244 | 28 | à faire (tâche 16) |
| 87 | service (rescrape_active_source) | `test_rescrape_active_source.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 234 | 10 | à faire (tâche 16) |
| 88 | service (platform_event_reconciliation) | `test_platform_event_reconciliation.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 224 | 9 | à faire (tâche 16) |
| 89 | service result_claims | `test_result_claims.py` (sous `backend/tests/test_services/`) | `backend/app/services/result_claims.py` | 212 | 18 | à faire (tâche 16) |
| 90 | service volunteer_action_service | `test_volunteer_action_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/volunteer_action_service.py` | 208 | 18 | à faire (tâche 16) |
| 91 | routes app/ajouter | `loading.test.tsx`, `page.test.tsx` (sous `frontend/app/(public_restricted)/ajouter/`) | `frontend/app/(public_restricted)/ajouter/` | 204 | 12 | à faire (tâche 16) |
| 92 | composants ui | 4 fichiers (sous `frontend/components/ui/`) | `frontend/components/ui/` | 204 | 9 | à faire (tâche 16) |
| 93 | service (admin_corrections_survive) | `test_admin_corrections_survive.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 200 | 11 | à faire (tâche 16) |
| 94 | service athlete_claims | `test_athlete_claims.py` (sous `backend/tests/test_services/`) | `backend/app/services/athlete_claims.py` | 199 | 15 | à faire (tâche 16) |
| 95 | service (sheet_source_upload) | `test_sheet_source_upload.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 197 | 18 | à faire (tâche 16) |
| 96 | composants map | `ListeEpreuves.test.tsx`, `MapView.test.tsx` (sous `frontend/components/map/`) | `frontend/components/map/` | 195 | 14 | à faire (tâche 16) |
| 97 | service (merge_absorbed_identity) | `test_merge_absorbed_identity.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 194 | 7 | à faire (tâche 16) |
| 98 | service member_emails_service | `test_member_emails_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/member_emails_service.py` | 193 | 25 | à faire (tâche 16) |
| 99 | service challenge_service | `test_challenge_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/challenge_service.py` | 189 | 14 | à faire (tâche 16) |
| 100 | routes app/login | `page.test.tsx` (sous `frontend/app/login/`) | `frontend/app/login/` | 189 | 12 | à faire (tâche 16) |
| 101 | frontend lib/benevoles | `brouillon.test.ts`, `file.test.ts` (sous `frontend/lib/benevoles/`) | `frontend/lib/benevoles/` | 179 | 20 | à faire (tâche 16) |
| 102 | service (import_club_homonyms) | `test_import_club_homonyms.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 178 | 10 | à faire (tâche 16) |
| 103 | composants participations | `ResultCardDownload.test.tsx`, `ResultClaimAction.test.tsx` (sous `frontend/components/participations/`) | `frontend/components/participations/` | 173 | 6 | à faire (tâche 16) |
| 104 | fournisseur nextrun | `test_nextrun.py` (sous `backend/tests/`) | `backend/app/scrapers/nextrun.py` | 171 | 10 | à faire (tâche 16) |
| 105 | service (athlete_purge_references) | `test_athlete_purge_references.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 170 | 18 | à faire (tâche 16) |
| 106 | service course_review | `test_course_review.py` (sous `backend/tests/test_services/`) | `backend/app/services/course_review.py` | 169 | 10 | à faire (tâche 16) |
| 107 | service (reclassification_on_import) | `test_reclassification_on_import.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 165 | 4 | à faire (tâche 16) |
| 108 | service course_reconciliation | `test_course_reconciliation.py` (sous `backend/tests/test_services/`) | `backend/app/services/course_reconciliation.py` | 165 | 21 | à faire (tâche 16) |
| 109 | service quality | `test_quality.py` (sous `backend/tests/test_services/`) | `backend/app/services/quality.py` | 162 | 21 | à faire (tâche 16) |
| 110 | service (import_homonyms) | `test_import_homonyms.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 161 | 13 | à faire (tâche 16) |
| 111 | service weather_service | `test_weather_service.py` (sous `backend/tests/`) | `backend/app/services/weather_service.py` | 148 | 11 | à faire (tâche 16) |
| 112 | service (club_best_times) | `test_club_best_times.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 145 | 9 | à faire (tâche 16) |
| 113 | service season_goals | `test_season_goals.py` (sous `backend/tests/test_services/`) | `backend/app/services/season_goals.py` | 144 | 13 | à faire (tâche 16) |
| 114 | service (reidentification_on_import) | `test_reidentification_on_import.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 137 | 6 | à faire (tâche 16) |
| 115 | service (opposition_on_import) | `test_opposition_on_import.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 136 | 11 | à faire (tâche 16) |
| 116 | service membership | `test_membership.py` (sous `backend/tests/test_services/`) | `backend/app/services/membership.py` | 135 | 15 | à faire (tâche 16) |
| 117 | service (challenge_on_import) | `test_challenge_on_import.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 133 | 8 | à faire (tâche 16) |
| 118 | routes app/resultats | `loading.test.tsx`, `page.test.tsx` (sous `frontend/app/(public_restricted)/resultats/`) | `frontend/app/(public_restricted)/resultats/` | 133 | 8 | à faire (tâche 16) |
| 119 | service training_group_service | `test_training_group_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/training_group_service.py` | 121 | 10 | à faire (tâche 16) |
| 120 | routes app/api | `route.test.ts` (sous `frontend/app/api/cron/keep-warm/`) | `frontend/app/api/` | 119 | 8 | à faire (tâche 16) |
| 121 | service (concurrent_imports_postgres) | `test_concurrent_imports_postgres.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 118 | 1 | à faire (tâche 16) |
| 122 | service course_merge | `test_course_merge.py` (sous `backend/tests/test_services/`) | `backend/app/services/course_merge.py` | 116 | 2 | à faire (tâche 16) |
| 123 | service volunteer_access | `test_volunteer_access.py` (sous `backend/tests/test_services/`) | `backend/app/services/volunteer_access.py` | 112 | 8 | à faire (tâche 16) |
| 124 | service (allowed_emails) | `test_allowed_emails.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 107 | 7 | à faire (tâche 16) |
| 125 | composants legal | `LegalLinks.test.tsx`, `LegalPage.test.tsx`, `blocks.test.tsx` (sous `frontend/components/legal/`) | `frontend/components/legal/` | 102 | 9 | à faire (tâche 16) |
| 126 | service (nameless_identity) | `test_nameless_identity.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 100 | 7 | à faire (tâche 16) |
| 127 | service athlete_detach | `test_athlete_detach.py` (sous `backend/tests/test_services/`) | `backend/app/services/athlete_detach.py` | 100 | 3 | à faire (tâche 16) |
| 128 | service shared_password | `test_shared_password.py` (sous `backend/tests/test_services/`) | `backend/app/services/shared_password.py` | 97 | 14 | à faire (tâche 16) |
| 129 | routes app/benevolat | `layout.test.tsx`, `page.test.tsx` (sous `frontend/app/(public_restricted)/benevolat/`) | `frontend/app/(public_restricted)/benevolat/` | 97 | 6 | à faire (tâche 16) |
| 130 | service (last_outing) | `test_last_outing.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 95 | 8 | à faire (tâche 16) |
| 131 | service relay_twin_cleanup | `test_relay_twin_cleanup.py` (sous `backend/tests/test_services/`) | `backend/app/services/relay_twin_cleanup.py` | 92 | 5 | à faire (tâche 16) |
| 132 | service (import_module_layout) | `test_import_module_layout.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 90 | 5 | à faire (tâche 16) |
| 133 | service timepulse_cleanup | `test_timepulse_cleanup.py` (sous `backend/tests/test_services/`) | `backend/app/services/timepulse_cleanup.py` | 88 | 4 | à faire (tâche 16) |
| 134 | service cache | `test_cache.py` (sous `backend/tests/test_services/`) | `backend/app/services/cache.py` | 87 | 12 | à faire (tâche 16) |
| 135 | service counter_scope | `test_counter_scope.py` (sous `backend/tests/test_services/`) | `backend/app/services/counter_scope.py` | 81 | 12 | à faire (tâche 16) |
| 136 | service (challenge_athlete_links) | `test_challenge_athlete_links.py` (sous `backend/tests/test_services/`) | `backend/app/services/` | 79 | 5 | à faire (tâche 16) |
| 137 | service challenge_requalification | `test_challenge_requalification.py` (sous `backend/tests/test_services/`) | `backend/app/services/challenge_requalification.py` | 78 | 4 | à faire (tâche 16) |
| 138 | service reclassify | `test_reclassify.py` (sous `backend/tests/test_services/`) | `backend/app/services/reclassify.py` | 77 | 6 | à faire (tâche 16) |
| 139 | fournisseur fftri_club_members | `test_fftri_club_members.py` (sous `backend/tests/`) | `backend/app/scrapers/fftri_club_members.py` | 75 | 11 | à faire (tâche 16) |
| 140 | composants analytics | `AnalyticsConsent.test.tsx` (sous `frontend/components/analytics/`) | `frontend/components/analytics/` | 75 | 6 | à faire (tâche 16) |
| 141 | service validation_queue_service | `test_validation_queue_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/validation_queue_service.py` | 74 | 6 | à faire (tâche 16) |
| 142 | service club_alias | `test_club_alias.py` (sous `backend/tests/test_services/`) | `backend/app/services/club_alias.py` | 72 | 8 | à faire (tâche 16) |
| 143 | routes app/challenges | `loading.test.tsx`, `page.test.tsx` (sous `frontend/app/(public_restricted)/challenges/[id]/`) | `frontend/app/(public_restricted)/challenges/` | 69 | 3 | à faire (tâche 16) |
| 144 | service feedback_service | `test_feedback_service.py` (sous `backend/tests/test_services/`) | `backend/app/services/feedback_service.py` | 67 | 6 | à faire (tâche 16) |
| 145 | service not_found | `test_not_found.py` (sous `backend/tests/test_services/`) | `backend/app/services/not_found.py` | 61 | 8 | à faire (tâche 16) |
| 146 | service site_access | `test_site_access.py` (sous `backend/tests/test_services/`) | `backend/app/services/site_access.py` | 57 | 3 | à faire (tâche 16) |
| 147 | composants challenges | `AthleteChallenges.test.tsx`, `CourseChallengesNote.test.tsx` (sous `frontend/components/challenges/`) | `frontend/components/challenges/` | 57 | 6 | à faire (tâche 16) |
| 148 | routes app/guide | `page.test.tsx` (sous `frontend/app/(public_restricted)/guide/`) | `frontend/app/(public_restricted)/guide/` | 56 | 4 | à faire (tâche 16) |
| 149 | service sheet_source | `test_sheet_source.py` (sous `backend/tests/test_services/`) | `backend/app/services/sheet_source.py` | 53 | 6 | à faire (tâche 16) |
| 150 | service gender_backfill | `test_gender_backfill.py` (sous `backend/tests/test_services/`) | `backend/app/services/gender_backfill.py` | 48 | 3 | à faire (tâche 16) |
| 151 | service fftri_category | `test_fftri_category.py` (sous `backend/tests/test_services/`) | `backend/app/services/fftri_category.py` | 45 | 19 | à faire (tâche 16) |
| 152 | routes app/carte | `page.test.tsx` (sous `frontend/app/(public_restricted)/carte/`) | `frontend/app/(public_restricted)/carte/` | 38 | 2 | à faire (tâche 16) |
| 153 | service progress | `test_progress.py` (sous `backend/tests/test_services/`) | `backend/app/services/progress.py` | 32 | 3 | à faire (tâche 16) |

## Lot 1 : `test_raceresult.py`

Gardé. Code couvert : `app/scrapers/raceresult.py` (703 instructions, 2074
mutants `app.scrapers.raceresult*`, module entier : pas de restriction).

| Mesure | Avant | Après |
| --- | --- | --- |
| Tests collectés | 381 | 377 |
| Fonctions de test | 196 | 184 |
| Lignes | 4315 | 4132 |
| Mutation (tués / tués + survivants) | 1613/2074 (77,8 %) | 1613/2074 (77,8 %) |
| Timeouts | 0 | 0 |
| Couverture de lignes (fichier seul) | 672/703 (95,6 %) | 672/703 (95,6 %) |

Même ensemble de 2074 mutants, verdict identique mutant par mutant ; mêmes 31
lignes manquées. Durée murale de mutmut : 336 s avant (load 4,95 → 17,94,
cartographie reprise de la tâche 11), 145 s après (load 2,72 → 10,92,
cartographie incrémentale des seuls nouveaux tests).

Fait :

- `_API_BASE` : le test de structure sur la constante est supprimé, l'hôte
  passe en assertion de comportement dans
  `test_fetch_config_interroge_la_route_canonique` (URL appelée commençant par
  `https://my.raceresult.com/393893/results/config`).
- `_RE_RRPUBLISH` : le test direct de l'expression rationnelle est supprimé ;
  ses deux syntaxes sont portées par les tests de façade sur captures réelles
  (chronoconsult entre guillemets, espace-competition nu).
- Gardes `TabConfig.Lists` de `_iter_list_specs` et `_iter_hidden_list_specs`,
  `_fetch_list` qui rend `None` (404, payload sans `data`), `_identities_conflict`
  (4 fonctions, 5 cas) : `parametrize`.
- `test_build_result_dnf_depuis_le_groupe` et `..._dns_depuis_le_groupe` :
  absorbés par `test_build_result_purge_temps_et_rangs_dun_non_finisher`,
  paramétré sur « Abandons » et « Non Partants » (statut, temps vide, rangs
  `None` sur une ligne qui porte vraiment temps et rangs, plus fort que sur une
  ligne d'abandon déjà vide).
- `?contest=0` vaut l'épreuve entière : devient un cas du `parametrize` de
  `test_scrape_event_all_interroge_exactement_les_listes_annoncees` (même
  montage, mêmes assertions).
- Fan-out : montage à trois contests factorisé (`_monte_trois_contests`, via le
  paramètre `contests` de `_monte_pipeline` au lieu de cinq surcharges de
  `_fetch_config`) ; `test_scrape_event_fanout_nominal_returns_trace` fusionné
  dans `test_provider_raceresult_expose_fanout_par_defaut` (le fournisseur
  délègue sans transformation, toutes les assertions de trace gardées) ;
  `test_scrape_event_fanout_on_heat_start_notifie_par_heat_non_cache` fusionné
  dans `test_scrape_event_fanout_cache_probe_skips_heats` (même sonde, mêmes
  assertions sur slug, index et total).

Envisagé, écarté :

- `test_scrape_event_all_ouvre_le_client_avec_follow_redirects` (espion sur
  `httpx.Client`) : test d'interaction, mais le seul à tuer le mutant
  `follow_redirects=False`, dont dépendent les façades redirigées.
- Les tests `_enrich` (scalaires vides, renseignés, identité, splits) : un
  `parametrize` mêlerait des invariants distincts que les noms séparent
  lisiblement.
- Les tests de pipeline des sections #977, #984, #897 et 312695 : montages
  différents (fixtures réelles, payloads propres à chaque épreuve), aucun
  doublon d'assertion trouvé ; les fusionner serait une réécriture, hors du
  périmètre « modeste et sûr » du premier lot.
- Les tests de façade et de `_fetch_meta` : chacun tient une forme réelle
  distincte, déjà minimal.

## Lot 2 : `test_import_service.py`

Gardé. Code couvert : `app/services/import_service.py` (105 instructions, 389
mutants `app.services.import_service*`, module entier : pas de restriction).

| Mesure | Avant | Après |
| --- | --- | --- |
| Tests collectés | 169 | 162 |
| Fonctions de test | 145 | 126 |
| Lignes | 3094 | 2962 |
| Mutation (tués / tués + survivants) | 225/389 (57,8 %) | 225/389 (57,8 %) |
| Timeouts | 0 | 0 |
| Couverture de lignes (fichier seul) | 101/105 (96,2 %) | 101/105 (96,2 %) |

Même ensemble de 389 mutants, verdict identique mutant par mutant ; mêmes 4
lignes manquées (55, 67-68, 95). Le fichier exerce aussi `import_persistence` et
`import_dispatch`, hors du code couvert du lot : la couverture de tout `app/`
par ce seul fichier a été comparée en plus, lignes manquées identiques module
par module. Durée murale de mutmut : 505 s avant (load 3,31 → 21,67), 281 s
après (load 11,22 → 10,11).

Fait :

- Montages qui se prolongent, fusionnés : `test_import_creates_entities` et
  `test_cached_return_porte_updated_zero` dans
  `test_import_creates_entities_then_a_reimport_is_cached` ;
  `test_reimport_after_cache_dedups_by_bib` dans
  `test_reimport_apres_cache_ne_compte_pas_les_dossards_deja_en_base` (mêmes
  compteurs, plus la fiabilité) ; `test_cached_return_porte_les_courses` dans
  `test_import_event_expose_les_courses_touchees` ;
  `test_reconciliation_ne_vide_jamais_le_prenom` et
  `test_reconciliation_refusee_ne_cree_pas_d_orphelin` en un test ;
  `test_import_sans_dossard_cree_les_participations` dans le test d'idempotence
  du réimport ; `test_import_sans_dossard_conserve_les_homonymes` dans le
  réimport des homonymes.
- `parametrize` : les deux tests de réimport d'homonymes sans dossard (même
  nombre, une occurrence de plus) ; les deux tests jeunes de #1221 ; les deux
  trames d'erreur du fan-out streamé ; les quatre tests de `cache_probe` sous
  `force` (`import_event` et `iter_import_event`, avec et sans `force`) ; les
  paires `import_event` / `iter_import_event` de `persist=False`, du rejeu de
  deadlock et de la transaction de lecture relâchée avant le scrape ; les
  tests de `validate_url` qui rendent une URL (acceptée, non réécrite, double
  encodage). Sur ces paires, chaque cas porte désormais l'union des assertions
  (course absente après une erreur de fan-out, épreuve en base après le rejeu,
  aucune course après un dry-run streamé).
- `test_scrape_all_streaming_use_cache_probe_false_desarme_la_sonde_par_heat`
  supprimé : `iter_import_event(force=True)` passe par le même
  `scrape_all_streaming(use_cache_probe=False)` et le cas `force` du test
  paramétré en porte les deux assertions (dispatcher invoqué, sonde `None`).

Envisagé, écarté :

- `test_is_empty_…` et `test_merge_fields_…` (fonctions privées
  d'`import_persistence`) : hors du code couvert du lot, aucune mesure de
  mutation pour prouver qu'un autre test les porte.
- Les deux tests de fusion et de renommage à la réconciliation (#66) : montages
  différents (cible préexistante ou non), un `parametrize` y mêlerait des
  assertions conditionnelles.
- `test_force_bypasse_le_cache_ttl` et sa version générateur : assertions de
  phase propres au flux, la fusion demanderait des branches dans le test.
- Les tests de relais (#894, #895, #1001) et de redatation (#972, #1263) :
  chacun tient un montage et un invariant distincts.
- Les tests de requêtes par lot (#706, #1503) : déjà paramétrés ou de
  montages distincts.

## Lot 3 : `RaceFinishers.test.tsx`

Gardé. Code couvert : `components/results/RaceFinishers.tsx` (162
instructions, 754 mutants, fichier entier : pas de restriction).

| Mesure | Avant | Après |
| --- | --- | --- |
| Tests collectés | 134 | 113 |
| Appels `it` et `it.each` | 134 | 103 |
| Lignes | 1758 | 1589 |
| Mutation, concurrence 3, même ensemble (tués / tués + survivants) | 451/749 (60,2 %) | 451/749 (60,2 %) |
| Timeouts de l'exécution complète | 0 | 19 |
| Couverture de lignes (fichier seul) | 135/137 (98,5 %) | 135/137 (98,5 %) |

Comparaison à ensemble égal, les 749 mutants tranchés avant. L'exécution
complète de l'après en tranche 730, verdict identique mutant par mutant (447
tués). Des 19 timeouts de l'après, 4 étaient tués avant, tous sur la ligne 735 :
la relance ciblée de cette ligne sur le fichier consolidé, `npx stryker run --force --concurrency 3 --timeoutMS 60000 --mutate "components/results/RaceFinishers.tsx:735-735"`,
en tue 8 sur 8 (dont ces 4, 17 s). Les 15 autres survivaient avant et sont
comptés survivants après ; les compter tués ne ferait que monter le score.
Aucun mutant tué avant n'est perdu. Couverture identique sur les quatre mesures (instructions
160/162, branches 253/262, fonctions 51/53), mêmes lignes manquées (550-557).
La mesure a d'abord exigé de corriger le runner Stryker (tout test sous un
`describe` était sauté, cf. `docs/tests-boucle.md`, « Mutation »).

Fait :

- `it.each` : la ventilation du pied de tableau (4 cas, texte exact y compris
  pour 1811 participants, au lieu d'une expression rationnelle partielle) ; le
  saut de page hors bornes et vers la première page ; le choix de taille de
  page (2) ; « Aller à ma ligne » sur page indifférente et sans le périmètre
  club (les deux vérifient l'URL exacte `/courses/1?q=Thomas+DNFGUY`) ; « ne
  figure pas » avec et sans périmètre club ; les quatre cas négatifs du
  marqueur d'écart. Aucun `if` dans un corps paramétré.
- Montages qui se prolongent, fusionnés (toutes les assertions gardées) :
  liens de pagination et `aria-describedby` ; recherche sans résultat dans le
  test #M3 ; filtre club seul (message, puis sortie) ; tri par segment (ordre
  du backend, `BUTTON`, croissant, décroissant) ; tri par temps total
  croissant puis décroissant ; lien de ligne et liens de chaque ligne ; arrêt
  de tabulation, préchargement, repère d'attente et sa position en une boucle
  par ligne (la position est désormais vérifiée sur chaque ligne, plus
  seulement la première) ; périmètre du tri dans le statut et dans
  l'`aria-label` ; cadre de sélection et pied de carte ; pas d'athlète
  mémorisé (ni « Vous », ni saut) ; « Vous » en grille et en cartes ; fond et
  classe de ma ligne, sur ma seule ligne ; filtre carte avec recherche
  (message, puis effacement) ; bascule grille/cartes et contenu des cartes ;
  ligne en attente en grille et en cartes.
- « annonce une épreuve sans aucun participant (ETAT-3) » supprimé : son
  assertion vit dans « garde son en-tête sur une épreuve vide… », renommé
  pour porter ETAT-3.

Envisagé, écarté :

- « donne au repère de catégorie son libellé complet » : un premier brouillon
  le fusionnait, et perdait la branche `if (club)` fausse de
  `titreAbsenceFiltre` (filtre catégorie seul, sélection vide), que ce test
  est seul à atteindre. Gardé tel quel.

## Lot 4 : `AppNav.test.tsx`

Gardé. Code couvert : `components/layout/AppNav.tsx` (151 instructions, 794
mutants au rapport, fichier entier : pas de restriction).

| Mesure | Avant | Après |
| --- | --- | --- |
| Tests collectés | 146 | 125 |
| Appels `it` et `it.each` | 137 | 111 |
| Lignes | 1925 | 1750 |
| Mutation, concurrence 3, même ensemble (tués / tués + survivants) | 391/783 (49,9 %) | 391/783 (49,9 %) |
| Timeouts de l'exécution complète | 29 | 0 |
| Couverture de lignes (fichier seul) | 116/120 (96,7 %) | 116/120 (96,7 %) |

La ligne du tableau annonçait 137 tests : c'est le compte de `vitest list`,
qui ne déplie pas les cas d'`it.each` (111 sur le fichier consolidé) ; vitest
en collecte 146. La ligne porte désormais le compte collecté (125), et l'état
global en tête suit cette ligne. Les 29 timeouts de l'avant (lignes 488 à
547) sont tranchés par la relance ciblée sur le fichier d'origine, `npx stryker run --force --concurrency 3 --timeoutMS 60000 --mutate "components/layout/AppNav.tsx:488-547"` :
6 tués, 23 survivants, le même verdict que l'après pour chacun. À ensemble
égal, 783 mutants tranchés des deux côtés (11 sans couverture exclus), verdict
identique mutant par mutant, comparés par leur étendue complète (une clé sur
le seul début confond 20 mutants et en perdait 10). Couverture identique sur les quatre mesures
(instructions 146/151, branches 244/253, fonctions 69/74), mêmes lignes
manquées (204, 241, 457, 542). L'exécution complète de l'avant a duré 2016 s,
au delà du budget de 30 min ; la restriction aux lignes touchées aurait couvert
presque tout le fichier, d'où l'exécution complète des deux côtés.

Fait (toutes les assertions gardées) :

- `it.each` : largeur du rail replié et déplié dès le premier rendu (NAV-3 ;
  le cas replié vérifie désormais lui aussi que `localStorage` n'est pas lu) ;
  alignement de l'en-tête replié et déplié (#620) ; infobulles des trois
  éléments repliés trouvés au premier rendu (« Ajouter une épreuve »,
  « Rechercher un athlète », « Accueil ») ; ni sélecteur ni entrée Back-office
  pour un membre sans pouvoir et pour un anonyme (le cas anonyme vérifie
  désormais aussi l'absence de Back-office). Aucun `if` dans un corps
  paramétré.
- Montages qui se prolongent, fusionnés : logo du rail déplié sans prefetch
  et non doublé du monogramme (#428, NAV-2) ; palette ⌘K titrée recherche, avec
  son invite, sans la promesse du tableau de bord (#952, absorbe « ouvre le
  picker au ⌘K ») ; palette de sélection ouverte par `OPEN_PICKER_EVENT`, puis
  gardée sous Ctrl+K (absorbe « ouvre le picker sur OPEN_PICKER_EVENT ») ; la
  croix de la tuile (#442) : titre, pas de « suivre », `.tcn-icon-btn`, 44 px,
  puis désélection qui laisse la recherche (cinq tests en un) ; « Mes
  résultats » (lien et absence de prefetch) ; 503 : relance à la place de « Se
  connecter », anneau orange, région de statut, retour du compte (trois tests
  en un) ; session en attente : ni « Se connecter » ni contenu dans le repère
  occupé ; état du déclencheur du tiroir puis fermeture (#1077, #1116) ; entrée
  courante marquée et en orange 4,5:1 (#1078) ; « Droits des rôles » et
  filtrage par pouvoir ; état connecté puis tiroir (#114) ; tuile « Mon
  athlète » nommée (#502), puis son infobulle ; onglet « Validation »
  raccourci et nommé par son texte visible (#890, #1012) ; « Plus » éteint
  (avant et après la session) puis ouvrant le tiroir (#1620) ; pied du tiroir
  qui ne se ferme ni sur l'adresse ni sur « Se déconnecter » ; sélecteur
  d'espace sur le rail et en tête du tiroir.

Envisagé, écarté :

- Fusionner « moves focus to the account trigger once the rail retry
  succeeds » dans le test du 503 : un premier brouillon le faisait, et
  l'exécution complète de l'après montrait 23 mutants « Survived » devenus
  « Killed » (lignes 116 à 379, dont des littéraux de style). Faux gain : ce
  test échoue lancé seul sur le code intact (il ne passe qu'après une relance
  antérieure du même fichier, déjà vrai du test d'origine), et Stryker ne
  rejoue que les tests qui couvrent un mutant. Remis à sa place, après le test
  du 503, avec un commentaire ; l'après a été remesuré. La cause de cette
  dépendance d'ordre (code ou test) reste à chercher, hors de ce lot.
- `readAthlete` (stock corrompu, forme `{ id, name }`) : code
  d'`AthletePicker`, hors du code couvert du lot, aucune mesure pour prouver
  qu'un autre test les porte.
- « asks every count in a single call » et les tests qui comptent les appels
  de `getSession` : tests d'interaction, gardés faute de preuve qu'un autre
  test tue leurs mutants.
- Les mêmes montages répartis entre plusieurs `describe` (tiroir anonyme,
  catégorie « Administration » à deux pouvoirs, athlète retenu sur le rail
  replié) : les fusionner mêlerait des issues distinctes ; et les sections
  publiques du tiroir, anonyme ou connecté (#621), ne se paramètrent pas sans
  `if` (le cas connecté attend le compte, le cas anonyme ne le peut pas).
- « ouvre le picker au clavier même avec un athlète retenu » : le paramétrer
  avec le cas sans athlète demanderait un `if` autour de l'écriture du stock.

## Régénérer le tableau

Depuis la racine du dépôt (le script vit ici, il n'est pas versionné ailleurs) :

```bash
(cd backend && uv run pytest tests --collect-only -q --migrations -n 0 -p no:cacheprovider) > /tmp/collect.txt
(cd frontend && npx vitest list --json=/tmp/vitest.json)
python3 inventaire.py /tmp/collect.txt /tmp/vitest.json
```

Le script rend « à faire » sur chaque ligne : reporter les statuts des lots
déjà traités. Il signale sur stderr tout test collecté hors de l'inventaire.

<details>
<summary><code>inventaire.py</code></summary>

```python
"""Inventaire des lots de consolidation. Usage (racine du dépôt) :
python3 inventaire.py <pytest --collect-only -q> <vitest list --json>
"""
import collections
import os
import json
import pathlib
import sys

ROOT = pathlib.Path.cwd()
PINNED = {  # lots 1 à 4, fixés par la spec (tâches 12 à 15)
    "backend/tests/test_raceresult.py": "backend/app/scrapers/raceresult.py",
    "backend/tests/test_services/test_import_service.py": "backend/app/services/import_service.py",
    "frontend/components/results/RaceFinishers.test.tsx": "frontend/components/results/RaceFinishers.tsx",
    "frontend/components/layout/AppNav.test.tsx": "frontend/components/layout/AppNav.tsx",
}
SCRAPERS = sorted(
    (p.stem for p in (ROOT / "backend/app/scrapers").glob("*.py")
     if p.stem not in {"__init__", "base", "classify", "registry", "utils"}),
    key=len, reverse=True,
)
SERVICES = {p.stem for p in (ROOT / "backend/app/services").glob("*.py")}
BACKEND_DIRS = {
    "test_api": "backend/app/api/", "test_auth": "backend/app/services/auth/",
    "test_cli": "backend/app/cli/", "test_core": "backend/app/core/",
    "test_repositories": "backend/app/repositories/", "test_scripts": "backend/scripts/",
}

counts = collections.Counter()
for line in open(sys.argv[1]):
    if "::" in line:
        counts["backend/" + line.split("::")[0]] += 1
for test in json.load(open(sys.argv[2])):
    counts[str(pathlib.Path(test["file"]).relative_to(ROOT))] += 1

files = [str(p.relative_to(ROOT)) for p in (ROOT / "backend/tests").rglob("test_*.py")]
files += [
    str(p.relative_to(ROOT)) for p in (ROOT / "frontend").rglob("*.test.*")
    if p.suffix in {".ts", ".tsx", ".mjs"}
    and not {"node_modules", ".claude"} & set(p.relative_to(ROOT).parts)
]


def zone(path: str) -> tuple[str, str]:
    p = pathlib.PurePosixPath(path)
    if path in PINNED:
        return path, PINNED[path]
    stem = p.stem.removeprefix("test_")
    if p.parts[0] == "backend":
        sub = p.parts[2] if len(p.parts) > 3 else ""
        if not sub:
            for s in SCRAPERS:
                if stem == s or stem.startswith(s + "_"):
                    return f"fournisseur {s}", f"backend/app/scrapers/{s}.py"
        if stem in SERVICES and sub in ("", "test_services"):
            return f"service {stem}", f"backend/app/services/{stem}.py"
        if sub == "test_services":
            return f"service ({stem})", "backend/app/services/"
        if sub:
            return f"backend {sub}/", BACKEND_DIRS[sub]
        return "backend tests/ (racine, transverse)", "backend/app/"
    rel = p.parts[1:-1]
    if rel and rel[0] == "app":
        i = next((i for i, s in enumerate(rel) if i and not s.startswith("(")), None)
        if i is None:
            return "routes app/ (racine)", "frontend/app/"
        return f"routes app/{rel[i]}", "frontend/" + "/".join(rel[:i + 1]) + "/"
    if rel and rel[0] == "components":
        return f"composants {'/'.join(rel[1:])}", "frontend/" + "/".join(rel) + "/"
    d = "/".join(rel) or "(racine)"
    return f"frontend {d}", "frontend/" + "/".join(rel) + ("/" if rel else "")


lots: dict = {}
for f in files:
    z, src = zone(f)
    lot = lots.setdefault(z, {"src": src, "files": [], "lines": 0, "tests": 0})
    lot["files"].append(f)
    lot["lines"] += sum(1 for _ in open(ROOT / f, encoding="utf-8"))
    lot["tests"] += counts[f]

order = list(PINNED) + sorted((z for z in lots if z not in PINNED), key=lambda z: -lots[z]["lines"])
print("| Lot | Zone | Fichiers de test | Code couvert | Lignes | Tests | Statut |")
print("| --- | --- | --- | --- | --- | --- | --- |")
for i, z in enumerate(order, 1):
    lot = lots[z]
    fs = sorted(lot["files"])
    common = os.path.commonpath(fs) if len(fs) > 1 else os.path.dirname(fs[0])
    shown = ", ".join(f"`{os.path.relpath(f, common)}`" for f in fs) if len(fs) <= 3 \
        else f"{len(fs)} fichiers"
    shown += f" (sous `{common}/`)"
    name = pathlib.PurePosixPath(z).name if z in PINNED else z
    status = f"à faire (tâche {11 + i})" if i <= 4 else "à faire (tâche 16)"
    print(f"| {i} | {name} | {shown} | `{lot['src']}` | {lot['lines']} | {lot['tests']} | {status} |")
print(f"\n{len(files)} fichiers, {sum(l['lines'] for l in lots.values())} lignes, "
      f"{sum(l['tests'] for l in lots.values())} tests, {len(lots)} lots.", file=sys.stderr)
missing = set(counts) - set(files)
if missing:
    print("tests hors inventaire :", sorted(missing), file=sys.stderr)
```

</details>
