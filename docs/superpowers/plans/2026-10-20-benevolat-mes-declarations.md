# Bénévolat : fiche présélectionnée et « Mes déclarations » (#1672)

**Objectif.** Sur `/benevolat`, un membre connecté et rattaché trouve sa fiche
déjà choisie (modifiable), et revoit ses déclarations avec leur statut.

**Arbitrage de contrat.** L'issue nomme `GET /auth/me/volunteer-actions`, mais
cette route existe déjà (#1696) et rend les actions **validées de la fiche
rattachée**, consommée par Mon espace. Principe IV : on n'en change pas le
contrat. Ajout d'une route sœur `GET /auth/me/volunteer-declarations`, filtrée
sur `declared_by_user_id`, tous statuts, toutes fiches (on peut déclarer pour
un autre). Pas de migration.

## Backend

- `repositories/volunteer_action_repository.py` : `list_declared_by(db, *, user_id)`,
  `selectinload(athlete)`, plus récentes d'abord.
- `services/volunteer_action_service.py` : passe-plat.
- `schemas/volunteer_action.py` : `MyVolunteerDeclarationOut` = id, athlete_id,
  athlete_nom, athlete_prenom, season, title, description, status, created_at.
- `api/v1/auth.py` : la route, `current_user` (401 anonyme).
- Tests `tests/test_api/test_my_volunteer_declarations_api.py` : seules mes
  déclarations, tous statuts, fiche d'un autre incluse, champs exacts, 401.

## Frontend

- `lib/types.ts`, `lib/api/client.ts`, `lib/queries/keys.ts`,
  `lib/queries/auth.ts` (`useMyVolunteerDeclarations(enabled)`).
- `lib/queries/volunteer-actions.ts` : la création invalide la liste.
- `components/benevolat/VolunteerActionForm.tsx` : fiche par défaut =
  `session.athlete` ; « Changer d'athlète » la retire ; après envoi, retour à
  la fiche par défaut.
- `components/benevolat/MesDeclarations.tsx` : rendu nul sans session ;
  chargement, erreur, vide, liste (titre, athlète, date, saison, pastille de
  statut).
- `app/(public_restricted)/benevolat/page.tsx` : monte la liste sous le formulaire.
- Tests composant : présélection, changement, liste et états.

Hors périmètre : Mon espace (autre session), modification d'une déclaration.
