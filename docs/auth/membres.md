# Liste des adresses d'adhérents (#1334)

Renvoyé depuis `backend/app/services/auth/AGENTS.md`. Epic #1312, spec :
`specs/20261011-155714-comptes-membres-socle/`. Le sondage
`docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md` prime.

La liste dit **qui est adhérent**, saison par saison, par l'adresse e-mail.
Elle est la source sur laquelle s'appuiera la connexion ouverte aux adhérents
(#1322). Table `member_emails`, seul point de passage
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
- Adresse normalisée `strip().casefold()`, validée par
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
- Chaque geste est journalisé (`member_emails.import`, `.add`, `.remove`) sans
  l'adresse elle-même : le journal vit 12 mois, la liste moins longtemps.

## Saison qui compte

À la date `d`, la saison `season_of(d)` si elle a au moins une entrée, sinon
`season_of(d) - 1` (`member_email_repository.counting_season`). Entre la
rentrée du 1ᵉʳ septembre et le premier import, la liste de l'an passé
continue donc de compter. `counts(db, email, today)` répond pour une adresse ;
c'est le point d'appui du statut adhérent de #1322.

## Purge

`purge-retention` supprime les saisons `< season_of(today) - 1`
(`member_email_repository.purge_before`), même borne que les licenciés.
Avenant RGPD : `docs/superpowers/specs/2026-10-01-base-legale-decision.md`.
