# Demande d'adhésion au club : design

Date : 21/10/2026. Milestone v0.9.0 (gel jeudi 22/10 au soir, tag vendredi 23/10).
Voie Superpowers. Lu sur `origin/main` fba80e0c.

## Intention

Depuis #1322, toute adresse vérifiée ouvre une session, mais un compte hors
liste d'adhérents n'a aucun droit et l'écran du code d'accès lui dit seulement
« demandez l'ajout de votre adresse à un administrateur du club ». Cette demande
se fait aujourd'hui hors de l'application. On la fait entrer dans l'application :
la personne demande à rejoindre le club, un administrateur la valide ou la
refuse, et la validation la rend adhérente.

Les adresses déjà connues ne demandent rien : l'import de l'extrait AssoConnect
(`/admin/adresses-adherents`, #1334, `member_emails`) les rend adhérentes dès la
connexion. C'est la pré-autorisation voulue ; elle existe, on n'y touche pas.

## Objectifs

1. Un compte connecté non adhérent peut envoyer une demande d'adhésion au TCN,
   avec de quoi l'identifier ou le recontacter.
2. Un administrateur voit les demandes en attente (badge de navigation), les
   valide ou les refuse.
3. Valider ajoute l'adresse du compte à la liste d'adhérents de la saison
   courante : la personne devient adhérente, sans autre geste.
4. Le rattachement à une fiche athlète devient réservé aux adhérents.
5. Le modèle ne bloque pas l'epic multi-club #1677.

## Non-objectifs

- Toucher à l'import AssoConnect ou à la règle `is_member` (#1334).
- Retirer le code d'accès partagé (#509). Décision du 21/10 : pour v0.9.0 il
  reste une entrée distincte vers l'espace club ; un adhérent sans compte doit
  pouvoir continuer à y accéder le jour du lancement. Son retrait est une issue
  de suivi, liée à #1683 (un code par club).
- Envoyer un e-mail (aucune infrastructure d'envoi dans le backend).
- Le multi-club lui-même : routage `/c/<slug>`, sélecteur de club, file par club
  (#1682, #1685, #1687).

## Anti-objectifs (échec même si « ça marche »)

- Une adresse déjà sur la liste d'adhérents est obligée de faire une demande.
- Un adhérent sans compte perd l'accès à l'espace club le jour du lancement.
- Une seconde porte d'entrée cachée vers le statut d'adhérent (le rattachement
  validé sur un licencié FFTri rend aujourd'hui adhérent ; c'est la raison du
  point 4).
- Des données personnelles de demande gardées sans durée annoncée.

## Décisions de l'utilisateur

- La file suit le patron de la file de rattachement (#1325) et vit au même
  endroit (`/admin/rattachements` ou à côté), avec un badge.
- Valider = ajout de l'adresse à `member_emails` de la saison courante, par le
  mécanisme d'ajout manuel existant (`source = manual`), donc préservé par les
  imports suivants.
- Le code d'accès partagé reste pour v0.9.0 ; le blocage du non-adhérent porte
  sur le rattachement et donc sur « Mon espace ».
- Un non-adhérent ne peut plus demander un rattachement ; la proposition
  « rattachement ouvert à tous, instruit par la plateforme » est écartée pour
  v0.9.0 (elle n'a de sens qu'avec plusieurs clubs).
- La demande porte : **prénom, nom, et date de naissance ou numéro de
  téléphone**, pour vérifier la légitimité ou recontacter la personne.

## Comportement

### Côté demandeur

- Où apparaît « Demander à rejoindre le TCN » : à la place de l'invitation au
  rattachement dans « Mon espace » (`MonEspace.tsx`, branche `athlete === null`)
  quand le compte n'est pas adhérent, sur `/mon-compte` à côté de « Non
  adhérent », et en lien depuis l'écran du code d'accès (message actuel de
  `connexionAdherent()` dans `frontend/lib/site-access-login.ts`).
- Formulaire : prénom et nom obligatoires ; date de naissance et téléphone
  facultatifs individuellement, **au moins l'un des deux** requis. L'adresse
  e-mail est celle du compte, non saisie.
- États visibles : aucune demande, en attente (avec possibilité d'annuler),
  refusée.
- Une demande par compte et par club. Une demande refusée peut être renvoyée
  après 30 jours (**choix de l'agent**) : le renvoi met à jour la même ligne
  (retour à `pending`, nouveaux champs, nouvelle date) ; si la purge l'a déjà
  supprimée, c'est une création.
- Un compte qui perd le statut d'adhérent (saison expirée) redevient
  demandeur possible, même s'il a déjà une fiche rattachée.
- Un adhérent (statut `is_member`) ne voit jamais le bouton, et l'API refuse sa
  demande.
- `GET /auth/me` expose la demande en cours, comme il expose déjà
  `athlete_claim`.

### Côté administrateur

- Liste des demandes en attente : prénom, nom, date de naissance ou téléphone,
  adresse du compte, date de la demande.
- Valider : ajoute l'adresse à `member_emails` via `member_emails_service.add`
  (celui de `POST /admin/member-emails`, adresse seule, `season =
  core.season.current_season()`), puis supprime la demande (même patron que l'approbation d'un rattachement, qui
  supprime la ligne). Si l'adresse est déjà sur la liste entre-temps, la
  validation réussit quand même et supprime la demande (le 409 « déjà manuel »
  de `add` est absorbé). Tant que `member_emails` n'a pas d'organisation
  (#1684), l'ajout est global : accepté (**choix de l'agent**).
- Refuser : statut `rejected`, horodaté.
- La file ne liste que les demandes en attente ; le badge les compte
  (**choix de l'agent**).
- Chaque geste va au journal d'administration (`admin_action_log`).
- Badge de navigation alimenté par `GET /admin/badge-counts`, comme `claims`.
- Permission nouvelle `member_requests:review`, ajoutée au même paquet de rôles
  que `member_emails:manage` et `athlete_claims:review`
  (`core/permissions.py`). Les rôles existants la reçoivent par une migration
  de données, comme `2901789fc3c8_club_roles.py` l'a fait pour
  `athlete_claims:review` : tout rôle qui porte `member_emails:manage` reçoit
  `member_requests:review`.

### Rattachement réservé aux adhérents

- `POST /auth/me/athlete-claim` exige le statut adhérent (et non plus le seul
  code d'accès). Réponse d'erreur explicite, en français côté message affiché.
- Les demandes de rattachement déjà en attente ne sont pas touchées et restent
  validables par l'administrateur, même si le demandeur n'est pas adhérent ; la
  garde ne porte que sur la création (**choix de l'agent**).
- Les autres routes de « Mon espace » ouvertes à tout compte connecté
  (objectifs, bénévolat, export, opposition RGPD) ne changent pas.

## Données

- Nouvelle table, une ligne par demande : compte (`user_id`), organisation
  (`organisation_id` **non nul**, TCN par défaut via l'organisation par défaut),
  prénom, nom, date de naissance (nullable), téléphone (nullable), statut
  (`pending`, `rejected`), dates de création et de décision, auteur de la
  décision. Unicité `(user_id, organisation_id)`. Contrainte « date de naissance
  ou téléphone » au niveau du schéma Pydantic, et si simple, en CHECK.
- L'`organisation_id` dès maintenant permet à #1684 (adhérents par club), #1685
  (plusieurs clubs par compte) et #1687 (file instruite par le club de contexte)
  de s'appuyer dessus sans migration de données.
- Une migration Alembic : rebase sur `origin/main` d'abord, une seule tête,
  `down_revision` dans la description de PR.

## RGPD

- Les données de la demande sont supprimées à la validation (ligne supprimée)
  et à l'annulation par la personne.
- Une demande refusée est conservée 30 jours (le délai de renvoi), puis purgée
  par `purge-retention` (#1158, `services/retention_service.py`).
- Une demande en attente restée sans décision est purgée au bout de 6 mois
  (**choix de l'agent**, chiffre repris dans la politique de confidentialité).
- La politique de confidentialité (`frontend/components/legal/content/confidentialite.tsx`)
  mentionne ce traitement, sa finalité et sa durée.
- La suppression du compte supprime ses demandes (cascade).

## Contraintes

- TDD (Principe III). Tests unitaires sans réseau.
- Couches `api → services → repositories → DB`.
- Langue : UI et messages en français, identifiants et tests en anglais.
- Aucune modification silencieuse des endpoints `/api/v1` publiés : on ajoute.
- Front : passe `ui-ux-review` en fin de branche.

## Laissé au constructeur

- Noms exacts de la table, du modèle, des routes (suivre `athlete_claims` et
  `result_claims`) ; `/auth/me/member-request` et `/admin/member-requests` sont
  les noms attendus par défaut.
- Emplacement exact de la file dans le back-office (même page que les
  rattachements ou page voisine), tant que le badge y mène.
- Validation du format du téléphone (souple, pas de bibliothèque nouvelle).
- Découpage en tâches et parallélisation.

## Suivis à ouvrir (hors v0.9.0)

- Retrait ou restriction du code d'accès partagé une fois les adhérents passés
  aux comptes (lié à #1683).
- File instruite par club (#1687) et demande vers un club choisi (#1685).
