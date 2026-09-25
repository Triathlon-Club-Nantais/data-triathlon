# Research: Rattacher un résultat de relais à plusieurs athlètes

Relevé du code fait le 2026-09-24 (deux passes : écriture et lecture). Les
chemins sont relatifs à `backend/` sauf mention contraire.

## R1. Modèle : table de liaison, pas une participation par équipier

**Decision** : table de liaison `participation_teammates (participation_id,
athlete_id)`. Le résultat reste **une** ligne `participations`.
`Participation.athlete_id` reste renseigné et pointe sur le premier équipier
(l'« équipier porteur »).

**Rationale** :

- `UniqueConstraint("course_id", "bib_number")` (`app/models/participation.py:32`) :
  les équipiers d'un relais partagent un dossard. Une ligne par équipier
  exigerait de lever cette contrainte ou d'inventer des dossards.
- Les lectures qui comptent des **lignes** restent justes sans modification :
  classement d'épreuve (`list_page_for_course` :660, son `total` :680,
  `summary_rows_for_course` :720), compteurs de participants et de finishers
  (`set_counts`, `import_service.py:853`), anomalies de rang
  (`quality._rank_anomalies`, `services/quality.py:56-79`, qui marquerait
  chaque duo en `duplicate_rank` avec des copies), podiums du club
  (`club_podiums`, `participation_repository.py:898-938`, compté une seule
  fois sans dédoublonnage).
- Contrat `/api/v1` (Principe IV) : `ParticipationOut.athlete` reste un athlète
  unique et valide. Les équipiers arrivent dans un champ **ajouté**
  (`teammates`). Avec des copies, `/participations`, `/courses/{id}` et
  `/club/summary` rendraient le même relais N fois sans qu'aucun champ ne
  change : un changement de sens silencieux.
- `athlete_id` renseigné garde valides toutes les lectures qui supposent un
  athlète par résultat (DTO, journal, bénévoles).

**Alternatives considered** :

- *Une participation par équipier (patron runnerbreizh)* : rejetée. Conflit
  avec la contrainte de dossard, une dizaine de requêtes d'agrégat à
  dédoublonner, qualité de rang faussée, changement de sens silencieux de l'API.
  Runnerbreizh s'en sort seulement parce que la source ne publie aucun dossard
  (`runnerbreizh.py:253-293`, `mapping.py:226`).
- *`athlete_id` rendu nullable, les équipiers uniquement dans la liaison* :
  rejetée. `ParticipationOut.athlete` est requis et le front le dit « toujours
  servi » (`frontend/lib/types.ts:104-118`). Le rendre optionnel changerait le
  contrat.

## R2. Qui figure dans la liaison

**Decision** : la liaison contient **tous** les équipiers, le porteur compris.
Un résultat est « attribué à une équipe » si et seulement s'il a des lignes de
liaison. Invariant : si la liaison est non vide, `athlete_id` en fait partie.

**Rationale** : une seule question pour les lectures par athlète :
« `athlete_id = X` ou X dans la liaison ». La composition se lit d'un seul
endroit.

## R3. Protéger l'attribution contre le rescrape

**Constat** : rien ne protège aujourd'hui une réattribution d'administrateur
(pas de drapeau sur `participations` ; seul `Athlete.club_locked` existe,
`app/models/athlete.py:27`).

- Avec dossard, `_Persister` retrouve la ligne par `(course, bib)`
  (`import_service.py:650`) et `_reconcile_resolved` (:790-812) **remet**
  l'athlète scrapé, donc l'athlète fictif de l'équipe.
- Sans dossard, l'appariement se fait par athlète (`_match_without_bib`,
  :814-826). L'athlète fictif n'ayant plus de ligne, une **nouvelle** ligne
  serait créée en doublon.

**Decision** :

1. `_reconcile_resolved` ne touche pas à l'athlète d'une participation qui a
   des équipiers.
2. À l'attribution, le nom de la fiche d'origine est copié dans `team_name`
   quand celui-ci est vide (FR-009 le veut de toute façon visible). Sans
   dossard, le persister apparie d'abord une ligne scrapée de relais à une
   participation attribuée de la même épreuve dont le `team_name` égale le nom
   scrapé, avant l'appariement par athlète. Définition :
   - `team_name`, s'il était vide, reçoit
     `" ".join(filter(None, [fiche.nom, fiche.prenom]))` de la fiche d'origine.
     Un `team_name` déjà renseigné (saisie manuelle) n'est jamais écrasé.
   - Le rescrape compare `normalize(team_name)` à
     `normalize(" ".join(filter(None, [athlete_name, athlete_firstname])))`,
     uniquement pour les lignes de relais de la même épreuve. `normalize` :
     minuscules, sans accents, espaces réduits.
   - Cette composition absorbe les variantes de fournisseur : prénom vide
     (oktime, raceresult, chronoweb) et nom découpé en nom et prénom
     (timepulse).
3. La fiche fictive recréée au passage est purgée par le nettoyage d'orphelins
   qui suit déjà tout rescrape (`admin_actions.py:707`,
   `rescrape_service.py:291`), à condition que ce nettoyage tienne compte de la
   liaison (R5).

**Alternatives considered** : un drapeau `manually_assigned` sur
`participations`. Rejeté : l'existence de lignes de liaison porte déjà
l'information, un drapeau ferait deux sources de vérité.

**Hors périmètre, relevé** : la réattribution simple existante est défaite par
le rescrape de la même façon. C'est un défaut antérieur, à ouvrir en issue
séparée plutôt qu'à corriger ici.

## R4. Règle de décompte (Q1 de la spec, option B)

**Decision** :

- Compteurs individuels : `Participation.is_relay = false` ajouté aux
  requêtes par athlète. Côté serveur, `stats_rank_rows` (participation_repository.py:868)
  lorsqu'elle sert un athlète, et les sommes de podiums du roster
  (`athlete_repository.py:483-489`). Côté front, les deux calculs locaux :
  `app/(public_restricted)/athletes/[id]/page.tsx:46-48` et
  `lib/utils/ma-saison.ts:30-33`.
- Compteurs du club : inchangés. Le relais est une seule ligne, il compte une
  fois.
- Le drapeau lu est celui de la **participation** : TimePulse mêle solos et
  relais dans une même course (`Participation.is_relay`).

## R5. Lectures par athlète qui doivent apprendre la liaison

- `list_for_athlete` (participation_repository.py:420-438) : fiche athlète.
- `exists_for_athlete_on_course` (:59) : refus d'un équipier qui a déjà un
  résultat sur l'épreuve.
- `only_on_course` et `delete_orphans_among` (athlete_repository.py:251, :278) :
  un équipier présent seulement dans la liaison n'est **pas** orphelin.
- Roster, rang et composition du club (athlete_repository.py:478-538) :
  créditer chaque équipier.
- `count_for_athlete` (fiche d'administration).

Lectures qui **ne changent pas** : classement d'épreuve, listes,
tableau de bord du club, podiums du club, qualité.

## R6. Création d'un équipier par son nom

**Decision** : réutiliser `mapping.get_or_create_athlete` / `athlete_repository.resolve`
(`services/mapping.py:197`, `repositories/athlete_repository.py:132`), déjà
employés par `POST /participations` (`api/v1/participations.py:67`). Une
saisie identique à une fiche existante (nom, prénom, sans date de naissance)
la réutilise (FR-003). Aucun nouvel endpoint de création d'athlète.

## R7. Front

- Base du sélecteur multiple : `components/admin/AthleteSearchPicker.tsx:19`
  (mono-sélection `selectedId`/`onSelect`) et la requête
  `useAdminAthleteSearch` (`lib/queries/admin.ts:311`).
- Point d'entrée : `components/athletes/ParticipationAdminActions.tsx`, qui
  porte déjà la réattribution (garde `participations:reassign`, :88).
- Affichage : le libellé du résultat de relais montre `team_name` et les noms
  des équipiers là où il montre aujourd'hui l'athlète.
