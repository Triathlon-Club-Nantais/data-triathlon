# Liste des adresses d'adhérents (#1334)

Renvoyé depuis `backend/app/services/auth/AGENTS.md`. Epic #1312, spec :
`specs/20261011-155714-comptes-membres-socle/`. Le sondage
`docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md` prime.

La liste dit **qui est adhérent**, saison par saison, par l'adresse e-mail.
Elle est la source du statut adhérent de la connexion ouverte (#1322, plus
bas). Table `member_emails`, seul point de passage
`member_email_repository` ; logique dans `services/member_emails_service.py` ;
écran `/admin/adresses-adherents` ; commande `import-member-emails` ; pouvoir
`member_emails:manage`.

## Distincte de la liste d'autorisation

`allowed_emails` (`docs/auth/liste-autorisation.md`) reste la porte du
back-office et porte le rôle du premier jour. La liste d'adhérents a une autre
source (l'export AssoConnect), un autre cycle de vie (réimportée à chaque
saison) et une autre conservation. Les fondre ferait d'un contributeur externe
un adhérent, et d'un adhérent un candidat au back-office. Y figurer ne donne
**aucun** pouvoir.

## Règles d'import

- Fichier `.csv` ou `.xlsx` lu par `sheet_source.read_table`. La **première**
  colonne dont l'en-tête, normalisé par `sheet_source.header_key` (sans
  accents, ponctuation ni casse), vaut `email`, `mail`, `courriel`,
  `adressemail`, `adresseemail`, `emailaddress`, `adresseelectronique` ou
  `adressedecourriel` est lue ; **aucune autre** (minimisation). Les colonnes
  exactes de l'export AssoConnect n'ont pas été mesurées (pages d'aide en 403) :
  un en-tête inconnu se traite en ajoutant sa forme normalisée à
  `_EMAIL_HEADERS`.
- Adresse normalisée par `core.email.normalize_email` (`strip().lower()`, la forme partagée avec la liste d'autorisation et `users.email`), validée par
  `allowed_emails.validate_email` (la seule définition d'une adresse valide du
  dépôt). Doublons fusionnés. Une ligne entièrement vide est sautée ; une ligne
  sans adresse valide est comptée `ignored`.
- Sans colonne reconnue, ou sans aucune adresse valide (fichier à en-tête seul
  compris) : refus 422, **rien n'est écrit**. Un fichier vide ne vide donc
  jamais la liste d'une saison par erreur.
- L'import **remplace les entrées importées** de sa saison : une adresse
  `import` absente du fichier est retirée, une nouvelle est ajoutée. Les
  entrées `manual` ne sont jamais touchées ; une adresse présente des deux
  côtés reste manuelle. Compte rendu : `added`, `removed`, `unchanged`,
  `ignored`.
- Ajout manuel : une adresse déjà importée passe en `manual` (elle survit alors
  aux imports) ; déjà manuelle, 409. Retrait : quelle que soit l'origine.
- Seule une adresse **nue** passe : `validate_email` accepte la forme
  « Nom <adresse> », refusée ici (ligne `ignored`, ajout manuel en 422).
- Écritures sous point de reprise : un ajout simultané de la même adresse rend
  409 (ou promeut l'entrée importée), un ajout pendant un import fait échouer
  l'import en 409 (« La liste a été modifiée pendant l'import, réessayez. »).
- Chaque geste est journalisé (`member_emails.import` avec ses quatre compteurs,
  `.add`, `.remove`) sans l'adresse elle-même : le journal vit 12 mois, la
  liste moins longtemps.

## Saison qui compte

À la date `d`, la saison `season_of(d)` si elle a au moins une entrée
**importée**, sinon `season_of(d) - 1` (`member_email_repository.counting_season`).
Entre la rentrée du 1ᵉʳ septembre et le premier import, la liste de l'an passé
continue donc de compter. Une adresse ajoutée à la main ne fait pas basculer la
saison : sinon un seul ajout en septembre fermait tous les adhérents.

`counts(db, email, today)` cherche l'adresse dans la saison qui compte **et**
dans la saison en cours : avant le premier import, celle-ci ne porte que des
ajouts manuels, qui comptent en plus de la liste précédente. C'est le point
d'appui du statut adhérent de #1322.

## Statut adhérent (#1322)

Un compte est **adhérent** si son adresse retenue (`users.email`) compte
(`member_email_repository.counts`), **ou** s'il est rattaché à une fiche
(`users.athlete_id`, rattachement validé par le club, #1325) **licenciée au
club pour la saison en cours** (`club_member_repository.is_linked_licensee`,
statut `auto` ou `manual`, #1633). Le rattachement reste hors saison (il sert
l'espace personnel), il ne vaut simplement plus adhésion : un ancien adhérent
non relicencié perd la dispense du code au renouvellement, sans geste du club.
Le club peut aussi détacher un compte (« Comptes rattachés » de
`/admin/rattachements`, `athlete_claim.detach` au journal). La liste ne
valide jamais un rattachement d'office : elle ne porte que des adresses, sans
nom ; la file `/admin/rattachements` l'affiche comme indice. `services/membership.is_member(db, user,
today)` le dérive **à chaque requête** : jamais stocké sur `users` (invariant
de #115), donc retirer l'adresse de la liste prend effet à la requête
suivante, sans fermer de session. Ni un compte désactivé ni le compte système
des bénévoles (`SYSTEM_USER_EMAIL`) ne le sont jamais.

- **Ce qu'il donne** : la dispense du code d'accès au site
  (`require_site_access` le vérifie à défaut de cookie valide, y compris sans code configuré), sur l'API comme sur
  l'interface, où `serverFetch` relaie pour cela la session SSO. Et rien
  d'autre : aucun pouvoir, une route gardée par un pouvoir répond 403.
- **Adresse retenue** (FR-016, `membership.retained_email`) : parmi les
  adresses certifiées par le fournisseur, la première inscrite à la liste
  d'autorisation, sinon la première qui compte ici, sinon la principale.
  Rafraîchie à chaque connexion.
- **Exposé** par `GET /auth/me` (`is_member`). L'écran du code d'accès propose
  « Adhérent du club ? Se connecter » quand un moyen de connexion existe, et
  explique à un connecté non adhérent qu'il doit saisir le code ou faire
  ajouter son adresse.
- Un adhérent dont l'adresse AssoConnect diffère de celle de son compte n'est
  pas reconnu : l'administrateur ajoute l'adresse du compte à la main (en
  attendant le rattachement de fiche, #1325).

## Purge

`purge-retention` supprime les saisons `< season_of(today) - 1`
(`member_email_repository.purge_before`), même borne que les licenciés.
Avenant RGPD : `docs/superpowers/specs/2026-10-01-base-legale-decision.md`.
