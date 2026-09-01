# Research: Ouvrir le formulaire de crédit d'un athlète au mot de passe du site (#809)

## D1 — Mécanisme d'accès : `optional_user`, pas `current_user`

**Décision** : `POST /api/v1/volunteer-actions` (`backend/app/api/v1/
volunteer_actions.py`) passe de `Depends(current_user)` à
`Depends(optional_user)` — dépendance déjà existante dans `app/api/deps.py`,
utilisée telle quelle par `POST /feedback` (#267), le mécanisme désigné
explicitement par l'utilisateur comme patron à suivre.

**Rationale** : `optional_user` résout la session si un cookie SSO valide
est présent, et rend `None` sinon, sans jamais lever 401 — c'est exactement
la sémantique voulue (« la connexion SSO ne sert que pour valider les
déclarations », direction produit explicite). `require_site_access`, posé en
amont sur tout le routeur dans `v1/router.py`, reste inchangé et continue de
fermer la route à quiconque n'a pas le mot de passe partagé — rien à modifier
côté routage.

## D2 — `declared_by_user_id` devient nullable, pas un compte système

**Décision** : `VolunteerAction.declared_by_user_id` passe de
`Mapped[int]` à `Mapped[int | None]` (colonne `NOT NULL` → nullable),
migration Alembic à l'appui. `VolunteerActionSelfOut.declared_by_user_id` et
`AdminVolunteerActionOut.declared_by_user_id` (`schemas/volunteer_action.py`)
passent de `int` à `int | None`.

**Rationale** : l'utilisateur a explicitement rejeté l'option « compte
système dédié » soumise en clarification, au profit du patron déjà en place
pour `UserFeedback.user_id` (`Mapped[int | None]`, sans `ondelete`, cf.
`backend/app/models/user_feedback.py`) — une déclaration sans auteur
individuel est un état légitime, pas une anomalie à masquer derrière une
identité de façade. Cohérent avec le reste du dépôt : aucune autre table du
domaine bénévolat n'a de compte système (contrairement à `benevoles.py`,
dont le mot de passe partagé est un mécanisme distinct, `require_
benevole_access`, hors périmètre ici).

## D3 — Aucune limite de débit dédiée

**Décision** : pas de honeypot ni de comptage par IP, contrairement à
`POST /feedback`.

**Rationale** : `POST /feedback` est **totalement** anonyme — exempté de
`require_site_access` (`_EXEMPTES_DE_LA_GARDE_SITE`, `v1/router.py`) — d'où
son honeypot et son plafond par IP compté en base
(`feedback_service.submit`). `POST /volunteer-actions` reste, lui, derrière
le mot de passe partagé du site : la surface d'abus est déjà bornée à qui
connaît ce mot de passe, un public restreint et de confiance (adhérents et
bénévoles), sans commune mesure avec l'exposition d'un bouton de feedback
visible de tout Internet. Reproduire ce dispositif serait une protection
sans menace identifiée en face (Principe VI, YAGNI).

## D4 — Frontend : la section se rend hors de la garde de session

**Décision** : `app/(public_restricted)/benevolat/page.tsx` sort la section
« Créditer un athlète pour le quota de saison » (`VolunteerActionForm`) du
bloc conditionné par `useSession()`. Le formulaire d'auto-déclaration
existant (#751, `VolunteerDeclarationForm`/`VolunteerDeclarationList`) reste
dans ce bloc, inchangé.

**Rationale** : c'est la section #751 qui a besoin d'une identité (la
déclaration est nominative, liée à l'auteur), pas la section #778/#809 — le
recadrage ne concerne que la seconde (spec.md Assumptions). La page affiche
donc désormais, sans condition de session, la recherche d'athlète et le
formulaire de crédit ; la section #751 continue d'afficher l'invite
« Se connecter » pour un visiteur sans session SSO.

## D5 — Aucun affichage admin à adapter

**Décision** : ni la file d'attente admin (#779, `AdminVolunteerActionOut`)
ni la liste des actions validées sur la fiche athlète (#781,
`VolunteerActionsList.tsx`) n'affichent aujourd'hui `declared_by_user_id` —
grep vérifié sur `frontend/`. Aucun repli d'affichage à ajouter dans cette
sous-issue.

**Rationale** : `VolunteerActionsList.tsx` (#781) n'expose que `title`/
`description` ; le seul consommateur qui référence `declared_by_user_id` côté
backend est `AdminVolunteerActionOut`, mais **aucune route frontend
n'existe encore pour la file d'attente #779** (gap constaté séparément,
issue à part — hors périmètre de #809). Rendre la colonne nullable ne casse
donc aucun affichage existant ; le jour où un écran de validation admin sera
construit, il devra prévoir un repli (« —» ou « Anonyme ») pour ce champ, à
sa propre charge.

## D6 — Test d'ouverture de route : bascule de fermée à ouverte

**Décision** : `POST /api/v1/volunteer-actions` sort de
`ROUTES_VOLUNTEER_ACTIONS_FERMEES` dans
`tests/test_auth/test_public_routes_still_open.py` — l'ensemble devient vide
et est retiré (avec son commentaire, devenu faux : une déclaration ne porte
plus toujours l'identité de son auteur).

**Rationale** : ce fichier dérive son inventaire de l'application (pas de
liste tenue à la main pour "quelles routes sont fermées") — une route retirée
de `ROUTES_FERMEES` est automatiquement éprouvée comme ouverte par le reste
du test. C'est le comportement voulu : la route ne doit plus jamais rendre
401 pour absence de session individuelle.
