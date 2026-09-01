# Research: Liste des actions de bénévolat validées sur la fiche athlète (#781)

## D1 — Endpoint dédié `GET .../volunteer-actions/validated`, pas un `GET` nu sur le chemin de création

**Décision** : `GET /api/v1/admin/athletes/{athlete_id}/volunteer-actions/validated`,
un nouveau suffixe — pas `GET /admin/athletes/{athlete_id}/volunteer-actions`
(le chemin déjà pris par `POST .../volunteer-actions`, #709, création admin,
`admin_data.py`).

**Rationale** : le même chemin porté par deux routers différents (`admin_data.py`
pour le `POST`, un nouveau fichier pour le `GET`) fonctionnerait
techniquement (FastAPI route par méthode+chemin), mais romprait « le
chemin dit qui peut appeler » — un lecteur de `admin_data.py` n'y verrait
que `athletes:volunteer_manage` (création) sans savoir qu'un `GET` sur le
même chemin, ailleurs, exige un pouvoir différent
(`athletes:volunteer_validate`). Un suffixe explicite lève l'ambiguïté à
la lecture, sans coût.

## D2 — Vit dans `admin_volunteer_actions.py` (#779), pas `admin_data.py`

**Décision** : le nouveau `GET` rejoint le router déjà gardé par
`athletes:volunteer_validate` (#779 — `pending`, `accept`, `reject`).

**Rationale** : même pouvoir, même router — cohérent avec « le chemin dit
qui peut appeler ». `admin_data.py` reste le chemin de création
(`athletes:volunteer_manage`), jamais touché par #781.

## D3 — Réutilise `AdminVolunteerActionOut` (#779), aucun nouveau schéma

**Décision** : la réponse de la liste est `list[AdminVolunteerActionOut]`,
le schéma déjà posé par #779 (`title`/`description` optionnels).

**Rationale** : mêmes champs exacts, même origine (`VolunteerAction`) — un
nouveau schéma dupliquerait sans raison. Les valeurs `None` (ligne créée
par le chemin admin #709, jamais titrée) restent possibles même parmi les
validées ; l'edge case de spec.md (repli d'affichage « — ») est un
problème d'affichage frontend, pas de contrat backend.

## D4 — Repository : nouvelle fonction, pas une extension de `list_for_athlete_season`

**Décision** : `list_validated_for_athlete(db, *, athlete_id)` — nouvelle
fonction, sans paramètre de saison.

**Rationale** : `list_for_athlete_season` (existante) est scopée à une
saison précise (utilisée par le quota) ; FR-004 exclut explicitement tout
filtre de saison ici. Réutiliser `list_for_athlete_season` en bouclant sur
toutes les saisons aurait été plus coûteux (N requêtes) qu'une requête
unique filtrée sur `athlete_id` + `status == "validee"`.

## D5 — Frontend : composant dédié, patron `.tcn-table` simplifié

**Décision** : nouveau composant `VolunteerActionsList.tsx` sous
`components/athletes/`, monté sur la page profil après `EventsTable`
(pas dans le slot `actions` du `PageHeader`, trop compact pour un
tableau) — garde de visibilité identique à `SeasonValidationPanel.tsx`
(`session.data?.permissions.includes("athletes:volunteer_validate")`,
rendu nul sinon, #439).

**Rationale** : deux colonnes de texte (titre, description) ne débordent
jamais un écran à 360px comme le font les six colonnes d'`EventsTable`
(Date/Épreuve/Type/Format/Temps/Place) — reproduire son seuil de bascule
grille/cartes (#461) ajouterait de la complexité sans bénéfice mesurable
(Principe VI). Le patron réutilisé est `.tcn-table` + rôles ARIA
(table/rowgroup/row/columnheader/cell), pas la duplication complète.

## D6 — Pas de nouvelle permission

**Décision** : réutilise `athletes:volunteer_validate` (#779) tel quel.

**Rationale** : l'issue #781 elle-même le demande (« la permission de
lecture ajoutée par #779 ») — #779 avait déjà tranché pour un pouvoir
unique couvrant consultation et décision (research.md D2 de #779), donc
aucune permission `_read` séparée à ajouter ici.
