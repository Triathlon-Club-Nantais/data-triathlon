# Phase 0 — Recherche et décisions

**Feature** : actions d'administration sur la page d'un coureur (#439)
**Date** : 2026-08-20

Onze décisions. Chacune est adossée à un relevé fait dans le dépôt, cité par
fichier et ligne — pas à une préférence.

## Relevé de départ : ce qui existe déjà

| Geste de la spec | Ressource d'API | Pouvoir | État |
| --- | --- | --- | --- |
| Corriger l'identité (FR-001) | `PATCH /admin/athletes/{id}` | `athletes:write` | ✅ livrée (#117) |
| Corriger le club (FR-002) | idem | `athletes:write` | ❌ `AdminAthleteUpdate` ne porte pas `club` |
| Supprimer un résultat (FR-003) | `DELETE /participations/{id}` | `participations:delete` | ⚠️ livrée, **sans journal**, `db.delete()` dans la route |
| Réattribuer un résultat (FR-004) | `POST /admin/participations/{id}/reassign` | `participations:reassign` | ✅ livrée (#117) |

Côté front, `EditAthleteDialog` et `AthleteSearchPicker`
(`frontend/components/admin/`) portent déjà les deux formulaires, mais pour le
back-office ; la page publique `frontend/app/athletes/[id]/page.tsx` n'a aucune
action d'administration.

**Conséquence de cadrage** : l'essentiel du travail est frontend + deux écarts
backend à combler (le champ `club`, le journal de suppression), et **une** vraie
addition de schéma (D1).

---

## D1 — La correction manuelle du club se marque dans la donnée

**Décision** : une colonne booléenne `athletes.club_locked` (défaut `False`).
`admin_actions.update_athlete` la pose à `True` dès qu'une correction touche
`club` ; `athlete_repository.resolve` cesse d'écraser `club` quand elle est vraie.
Migration Alembic dédiée.

**Rationale** — trois relevés :

1. `athlete_repository.resolve` **ligne 96-97** est le **seul** écrivain de
   `Athlete.club` après la création de la fiche (`grep '\.club = '` sur
   `backend/app` : les seize autres occurrences écrivent `ScrapedResult.club`,
   c'est-à-dire le club **du résultat**, pas celui du coureur). Le garde a donc un
   point d'application unique, et aucun chemin d'import ne peut le contourner —
   `import_service` comme `rescrape_service` passent par `resolve`/`get_or_create`.
2. FR-019 exige que l'état vive dans la donnée. Un booléen est la forme minimale
   qui le fait.
3. Le drapeau se lit dans `resolve` comme un attribut déjà hydraté : **zéro
   requête supplémentaire** sur le chemin d'import, qui traite des centaines de
   lignes par épreuve.

**Alternatives rejetées** :

- **Déduire l'état du journal** (`admin_action_log` où `action="athlete.update"`
  et `payload` mentionne `club`) : le journal est une **trace**, pas un état
  (FR-019 le dit) — une purge du journal changerait le comportement d'import, et
  la lecture serait un scan JSON par coureur à chaque import.
- **Deux colonnes** (`club_imported` / `club_manual`, `club` dérivé) : trois
  colonnes pour porter un booléen, et cela casserait `AthleteBrief.club` (contrat
  public) comme l'index fonctionnel normalisé du club.
- **Un horodatage** `club_updated_at` comparé à la date d'import : les imports
  sont **rétroactifs** — une épreuve de 2023 se scrape aujourd'hui —, la
  comparaison serait fausse dans le sens le plus courant.

**Nommage** : `club_locked` et non `is_club_locked`. Le préfixe `is_` du dépôt
(`is_relay`, `is_pending_validation`, `is_rejected`, `is_active`) qualifie
**la ligne entière** ; ici le booléen qualifie **une colonne** de la ligne.

## D2 — Le drapeau ne s'expose pas dans l'API

**Décision** : `club_locked` reste interne. Ni `AthleteBrief` (public) ni
`AdminAthleteRead` (gardé) ne le rendent.

**Rationale** : aucun écran n'a besoin de le lire pour faire son travail — la
modale annonce en texte que la correction sera conservée, sans avoir à interroger
l'état. L'exposer serait un champ de contrat public ajouté « au cas où »
(Principe VI), et FR-018/FR-019 se vérifient au niveau où la règle vit : le
repository et le service.

**Alternative rejetée** : l'exposer pour afficher un badge « club figé ». Reporté
à un besoin constaté ; rien dans la spec ne le demande.

## D3 — Pas de dé-verrouillage dans cette feature

**Décision** : aucun geste pour rendre le club au suivi automatique.

**Rationale** : la spec ne le demande pas, et le contournement existe déjà —
corriger le club à la main vers le libellé voulu. Ajouter une bascule
« re-suivre l'import » serait une capacité spéculative (Principe VI).

## D4 — La suppression d'un résultat rejoint les autres gestes correctifs

**Décision** : `DELETE /participations/{id}` garde **son chemin, son 204 et sa
garde**, mais son corps délègue à un nouveau
`admin_actions.delete_participation(db, participation_id=…, user_id=…)`, qui
journalise `action="participation.delete"` puis supprime via un nouveau
`participation_repository.delete(db, participation)`. La route `commit`, comme
ses onze sœurs de `admin_data.py`.

**Rationale** — l'état actuel (`backend/app/api/v1/participations.py:137-153`)
est en écart sur deux plans, et FR-014 les rend tous deux bloquants :

- **aucune entrée au journal**, alors que les trois autres gestes de la feature
  en écrivent une ; un geste irréversible sans trace est précisément ce que le
  journal existe pour éviter ;
- **`db.delete(row)` dans la route**, seule couche interdite d'y toucher
  (Principe II ; la route n'est ni `cache.py` ni `reclassify.py`, les deux
  exemptions nommées).

Le chemin et le code de statut ne bougent pas : c'est une route `/api/v1`
publiée (Principe IV). Ce qui change est interne.

**Alternative rejetée** : ajouter une route `DELETE /admin/participations/{id}` et
laisser l'ancienne en place. Deux portes pour un geste, dont une sans journal —
la spec exige la trace pour **tous** les gestes, et « ne pas préserver la
compatibilité ascendante » (AGENTS.md) vise justement ce genre de doublon.

## D5 — Supprimer un résultat ne supprime pas le coureur

**Décision** : `delete_participation` **ne purge pas** la fiche devenue vide,
contrairement à `reassign_participation` (`admin_actions.py:621`,
`athlete_repository.delete_orphans_among`).

**Rationale** : l'asymétrie est voulue et les deux cas ne se ressemblent pas. Une
réattribution corrige une **fiche fantôme** née d'une mauvaise attribution : la
purger est la fin du geste. Ici, l'administrateur est **sur la fiche** d'une
personne réelle ; la détruire sous ses pieds rendrait 404 la page qu'il regarde
(FR-012 l'interdit), et supprimer une personne n'est pas la conséquence attendue
de « supprimer un résultat ».

## D6 — La réattribution exige deux pouvoirs, et le back-office s'aligne

**Décision** : l'action de réattribution n'est visible qu'avec
`participations:reassign` **et** `athletes:read` — sur cette page **et** dans le
back-office, dont on corrige au passage l'écart. Tranché avec le demandeur le
2026-08-20 ; consigné en FR-004, FR-020 et US4-AC3.

**Le fait mesuré, qui précède la décision** : la chaîne existante en production
couple déjà les deux pouvoirs *de fait*, mais n'en garde qu'un.

```text
CourseParticipationsDialog.tsx:46   visibilité ← participations:reassign  SEUL
        └─▶ ReassignParticipationDialog ─▶ AthleteSearchPicker
                └─▶ useAdminAthleteSearch ─▶ GET /admin/athletes?search=
                        └─▶ admin_data.py:69  require_permission(P.ATHLETES_READ)
```

Un porteur de `participations:reassign` sans `athletes:read` voit donc **déjà**
l'action, ouvre le sélecteur, et reçoit un `403` à la première frappe. Ce n'est
pas une exigence que #439 ajoute : c'est une incohérence préexistante, et #439
devait choisir un camp. Reconduire l'écart sur un second écran l'aurait doublé.

**Rationale** : choisir le coureur cible passe par la recherche gardée
`GET /admin/athletes?search=` (`athletes:read`), la seule qui rende la **date de
naissance** — seule façon de départager deux homonymes. Offrir le geste sans ce
pouvoir annonce un geste qui échoue, ce que FR-006 proscrit ; `useRolesAttribuables`
tient déjà le même raisonnement pour `roles:assign` (`frontend/lib/roles.ts:38`),
et le dépôt a son précédent de pouvoirs couplés :
`test_migrations.py::test_moderator_porte_ses_deux_codes_couples` — « instruire un
signalement sans pouvoir lire la liste n'a pas de sens ».

Le couplage ne dégrade aucune donnée et ne touche aucune garde : il ne change que
ce qui est **annoncé**. Aucun rôle système amorcé par les migrations ne porte l'un
de ces deux codes (vérifié sur `alembic/versions/`), donc aucun porteur existant
ne perd un accès.

**Alternative rejetée (1)** : brancher le sélecteur sur la recherche **publique**
`GET /athletes?name=` (#357), qui ne demande aucun pouvoir. Elle ne rend pas la
date de naissance : deux homonymes du même club y sont **indiscernables**, et le
geste censé corriger une confusion en fabriquerait une autre — le risque que
`athlete_repository.search_admin` documente nommément. C'est le compromis que
l'écran des bénévoles (#271) assume faute de SSO ; ici, rien ne l'impose.

**Alternative rejetée (2)** : ne garder le couplage que sur la nouvelle page et
laisser le back-office tel quel. Deux règles pour un même geste, dont une connue
fausse — la spec aurait consigné le bug au lieu de le corriger, pour une ligne
d'écart.

## D7 — `birth_date` : jamais affiché, jamais renvoyé sans `athletes:read`

**Décision** : la modale d'identité ne charge la fiche gardée
(`useAdminAthlete` → `GET /admin/athletes/{id}`) **que** si la session porte
`athletes:read`. Sans ce pouvoir, le champ date de naissance est **absent du
formulaire et absent du corps du `PATCH`**.

**Rationale** : `PATCH /admin/athletes/{id}` utilise `exclude_unset`
(`admin_data.py:225`) — un champ non envoyé n'est pas écrit. C'est donc l'absence
du champ, et non une valeur de repli, qui garantit qu'on n'efface pas une date
qu'on n'a jamais lue (US1-AC4). Le raisonnement inverse est déjà documenté sur
`useAdminAthlete` (`lib/queries/admin.ts:276-281`).

Nom, prénom **et club** sont, eux, prérenseignables sans aucun pouvoir de
lecture : `AthleteBrief` les porte déjà publiquement
(`backend/app/schemas/athlete.py`), et la page les a en main.

## D8 — Les composants prennent `tcn/`, et le partage se fait sur les hooks

**Décision** : nouveaux composants clients dans
`frontend/components/athletes/`, bâtis sur `tcn/Modal`, `tcn/Button`,
`tcn/Input`. `admin/EditAthleteDialog` **n'est pas** monté sur la page publique.
Ce qui est partagé, ce sont les mutations de `lib/queries/admin.ts`.

**Rationale** : `frontend/AGENTS.md` fixe la frontière — « tout nouvel écran
public prend `tcn/` » ; `ui/` porte la densité du back-office. Le précédent
exact existe et se lit en entier :
`frontend/components/courses/CourseSourcesPanel.tsx` pose des gestes gardés
(`courses:sources`) sur la page **publique** d'une épreuve, avec `tcn/Modal`
pour la confirmation, `useSession()` pour la visibilité et `toast` pour le
compte rendu. La feature suit ce patron plutôt que d'en inventer un second.

**Alternative rejetée** : réutiliser `EditAthleteDialog` tel quel. Elle
importerait la pile `@base-ui/react` du back-office dans le bundle de la page la
plus consultée du site, pour un formulaire de trois champs — et le rendu
détonnerait sur une page 100 % `tcn/`. L'audit de sur-ingénierie
(`docs/superpowers/specs/2026-08-06-frontend-surengineering-audit.md`) tranche
déjà que les primitives présentes des deux côtés ne sont pas un doublon à
résorber.

**Limite connue, assumée** : `tcn/Modal` gère `Escape` et `aria-modal` mais
**n'a pas de piège à focus** ni de restauration du focus à la fermeture, là où
`ui/dialog` (base-ui) en a un. C'est la limite des trois modales publiques
existantes (`CourseSourcesPanel`, `FeedbackButton`, `AthletePicker`) ; cette
feature ne l'aggrave pas et ne la corrige pas — à signaler à la revue UI/UX de
fin de branche, comme dette du composant partagé, pas de cette page.

## D9 — Les actions par résultat vivent **sous** la ligne, pas dedans

**Décision** : les boutons « Supprimer » et « Rattacher » se rendent dans une
sous-ligne sous la ligne du tableau, sœur de celle du lien « Voir la preuve ».
La ligne existante et sa grille de sept colonnes ne bougent pas.

**Rationale** : la ligne **entière** est un `<Link>`
(`app/athletes/[id]/page.tsx:127`). Un `<button>` à l'intérieur d'une ancre est
du HTML invalide, exactement la contrainte que le fichier documente déjà pour le
lien de preuve (lignes 174-179 : « un `<a>` imbriqué dans un autre serait
invalide en HTML »). La sous-ligne est la solution que la page a déjà retenue
pour le même problème.

**Alternatives rejetées** :

- **Une huitième colonne d'actions** : il faudrait sortir le `<Link>` de la
  grille et re-câbler la navigation cellule par cellule — restructuration de la
  ligne, de ses tokens de style et de ses tests, pour zéro gain.
- **Un « mode administration » qui remplace le corps du tableau** : deux rendus à
  maintenir pour le même tableau, et l'administrateur perd la vue publique qu'il
  est venu vérifier.

## D10 — Le rafraîchissement passe par `router.refresh()`

**Décision** : après chaque geste réussi, `router.refresh()`.

**Rationale** : les cinq indicateurs de la page (épreuves, meilleure place,
meilleur ratio, top 10, format favori) et le nom en tête sont calculés **dans le
composant serveur** (`page.tsx:46-63`). Une mise à jour d'état local ne les
recalculerait pas, et FR-015 les nomme. `router.refresh()` re-rend le RSC :
patron déjà en place dans `components/scrape/TcnScrapeForm.tsx:84`, testé
là-bas.

**Alternative rejetée** : mettre à jour un état local, comme
`CourseSourcesPanel.setSources`. Suffisant là-bas (les pills n'alimentent aucun
calcul), insuffisant ici.

## D11 — Le coût pour le visiteur anonyme reste nul

**Décision** : la page reste rendue côté serveur par `apiServer.getAthlete`
(`lib/api/server.ts:90`, bâti sur `serverFetch`, donc **sans cookies**) ; toute
lecture de session est **cliente**, par `useSession()`. Le jeton à ne pas
introduire dans `app/athletes/[id]/page.tsx` est `serverFetchAuthed`, sous
quelque forme que ce soit.

**Rationale** — deux relevés qui rendent SC-004 atteignable sans effort :

- `useSession` court-circuite la requête réseau quand le cookie témoin
  `tcn_logged_in` est absent (`lib/queries/auth.ts:12-17, 29`) : un visiteur
  anonyme ne déclenche **aucun** appel.
- Basculer la page sur `serverFetchAuthed` pour lire la session au rendu la
  rendrait **dynamique** ; `frontend/AGENTS.md` prévient que six pages publiques
  en rendu serveur dépendent de `serverFetch` restant inchangé.

C'est la contrainte porteuse de tout le design front : la visibilité est décidée
**dans le navigateur**, sur une session que le serveur n'a pas lue — et les
gardes d'API restent la seule autorité (FR-009).

---

## Ce qu'aucune décision ne change

- Aucun **nouveau pouvoir** : les quatre codes existent
  (`athletes:read`, `athletes:write`, `participations:delete`,
  `participations:reassign`) et sont déjà à l'inventaire de
  `core/permissions.py`.
- Aucun **nouveau chemin d'API** : une addition de champ (`club`) et un corps de
  route réécrit, rien de plus.
- Aucune **règle de club** touchée : `core/club.py` reste le seul juge de
  l'appartenance TCN, et le club porté par les résultats n'est jamais réécrit
  (FR-013).
