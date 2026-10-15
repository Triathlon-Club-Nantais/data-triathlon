# Licenciés en course sur /club (#1441)

## Brainstorming (tranché par l'agent, voie Superpowers)

- Saison : `core/season.current_season()` (bascule au 1er septembre). C'est
  celle que `/club` utilise déjà (KPI « Résultats », `currentSeason()` front)
  et celle de `ClubMember.season`. `services/fftri_category` (1er novembre)
  ne sert qu'aux catégories d'âge, il n'est pas concerné.
- `total` compte les lignes `ClubMember` de la saison, rattachées ou non.
- `raced` compte les lignes rattachées (`LINKED`) dont la fiche a un résultat
  validé (`validated_clause`) qui compte pour le club (`counts_for_tcn`), sur
  une épreuve datée dans les bornes de la saison (`season_bounds`), en titulaire
  ou en équipier de relais (`ParticipationTeammate`). Un résultat refusé reste
  `is_pending_validation`, donc exclu par la même clause.
- Une seule requête : deux agrégats sur `club_members`, `raced` par
  `SUM(CASE WHEN EXISTS ...)`. Aucun N+1, tenu par un test `measure_queries`.
- Champ additif `licensees: {season, total, raced} | null` sur
  `GET /club/summary` (Principe IV). `season` ajouté pour que la carte affiche
  la saison du serveur, sans recalcul côté front.
- Carte KPI « Licenciés en course », valeur X, indication « sur Y licenciés ·
  Saison Y — Y+1 » (« X / Y » à 68 px débordait la tuile, revue UI), masquée sous `null`. Grille 3 puis 5 colonnes en
  `lg` puis `xl` quand la carte est présente.

## Tâches (TDD)

1. Repository `club_member_repository.licensee_activity(db, season)` :
   tests rouges (rattaché couru, rattaché sans résultat, non rattaché, autre
   saison, en attente, refusé, équipier de relais, aucun licencié, une requête),
   puis implémentation.
2. Service et schéma : `ClubLicensees`, `ClubSummary.licensees`, calculé dans
   `club_service.get_club_summary`. Test API : `null` sans licencié, valeurs
   sous horloge figée.
3. Front : type `ClubSummary.licensees`, carte dans `ClubDashboard`. Vitest :
   affichée, masquée.
4. Doc : ligne `licensee_activity` dans `backend/app/api/AGENTS.md`.
