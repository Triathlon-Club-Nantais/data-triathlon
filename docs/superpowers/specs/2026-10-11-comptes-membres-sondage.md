# Sondage des moyens de connexion des adhérents (#1321)

Mesuré le 11/10/2026 dans le code du dépôt et dans les documentations
officielles des fournisseurs (liens en fin de section). Epic : #1312.

## Ce que le code impose déjà

- **Aucune source ne connaît l'e-mail d'un adhérent.** `club_members` est
  alimentée par la page publique FFTri (`scrapers/fftri_club_members.py`,
  JSON-LD : nom, sexe, licence) ou par un fichier dont seules ces colonnes
  sont lues (`club_members_service.import_file`). Pas d'e-mail, par
  minimisation (`2026-10-01-base-legale-decision.md`).
- **Le numéro de licence n'est pas un secret** : la page FFTri le publie
  (`identifier`). Il ne prouve donc pas qu'un compte appartient à un
  licencié.
- La résolution d'un compte se fait par `(provider, subject)`, jamais par
  l'adresse ; une adresse **vérifiée** est exigée (`email_unverified`
  sinon), puis confrontée à `allowed_emails` (`provisioning.resolve_user`).
- Aucun envoi d'e-mail n'existe dans le dépôt. Le limiteur de débit maison
  (`api/deps.py`, fenêtre glissante par IP) suffit à protéger de nouvelles
  routes.
- Authlib 1.8 et joserfc 1.7 sont installés : la validation d'un `id_token`
  OIDC (JWKS) ne demande aucune dépendance nouvelle.

## Fournisseurs mesurés

| Option | Verdict | Raison mesurée |
| --- | --- | --- |
| AssoConnect | **Écarté comme moyen de connexion** | Aucun fournisseur SSO, OAuth ni OIDC. API CRM « sur demande » dans l'offre Expert (dès 109 € TTC/mois), contredite par la page de l'offre (« bientôt »). Zapier : déclencheurs sur les contacts seulement, aucune donnée d'adhésion. Seul l'export Excel des contacts (admin) est disponible. |
| Google (OIDC) | **Retenu** | Gratuit ; claim `email_verified` ; Google recommande `sub` comme identifiant, ce qui est notre invariant. Avec les seuls scopes `openid email profile`, pas d'écran d'avertissement ni de vérification d'application ; publication en production ouverte à tout compte Google. |
| Strava | Écarté | Aucun scope ne fournit l'e-mail. Application limitée à 1 athlète, puis 10 après mise à niveau, au delà revue obligatoire par Strava. |
| Apple | Écarté | Programme développeur payant (budget zéro) ; « masquer mon adresse » rend une adresse relais, inutilisable pour toute vérification. |
| Microsoft | Écarté | Le claim `email` « n'est pas garanti et ne doit jamais servir à une autorisation », pas d'`email_verified`. |
| Lien magique par e-mail | **Retenu** | Couvre l'adhérent sans compte Google. Prouve la possession de l'adresse, ce qui joue le rôle d'`email_verified`. Exige un service d'envoi (ci-dessous). |
| Mot de passe | Écarté | NIST SP 800-63B-4 : 15 caractères minimum, liste de mots de passe compromis, verrouillage, réinitialisation par e-mail. On paierait le service d'envoi **et** toute cette surface pour ce qu'un lien magique fait seul. `identities.secret_hash` reste vide. |

Sources : [AssoConnect tarifs](https://www.assoconnect.com/tarifs/),
[export contacts](https://help.assoconnect.com/hc/fr/articles/4695561557266),
[Zapier AssoConnect](https://zapier.com/apps/assoconnect/integrations),
[Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect),
[Google mode test](https://support.google.com/cloud/answer/15549945),
[Strava getting started](https://developers.strava.com/docs/getting-started/),
[Apple web](https://developer.apple.com/help/account/capabilities/configure-sign-in-with-apple-for-the-web),
[Microsoft claims](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference),
[NIST SP 800-63B](https://pages.nist.gov/800-63-4/sp800-63b.html).

## Envoi d'e-mails

**Render gratuit bloque les ports SMTP sortants (25, 465, 587) depuis le
26/09/2025** ([changelog](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports)) :
seule une API HTTP est possible, appelée par `core.http.guarded_transport()`.

| Service | Gratuit | Remarque |
| --- | --- | --- |
| Brevo | 300/jour | Société française, hébergement UE. |
| Mailjet | 200/jour, 6 000/mois | Groupe Sinch, hébergement UE non vérifié. |
| Resend | 100/jour, 3 000/mois | Résidence UE des données non confirmée. |
| Amazon SES | 3 000/mois, 12 mois seulement | Pas pérenne. |
| SendGrid | Plus d'offre gratuite depuis le 27/05/2025 | Écarté. |

**Recommandation : Brevo** (UE, quota largement au dessus de ~300
adhérents). Il devient sous-traitant : à ajouter à la politique de
confidentialité. Prérequis hors code : SPF et DKIM sur
`triathlon-club-nantais.com`, donc un accès au DNS du club **non vérifié à
ce jour**.

## Éligibilité : qui est adhérent ?

Faute d'e-mail côté adhérents, la liste d'autorisation ne peut pas servir de
règle d'éligibilité sans importer une donnée nouvelle. Deux voies :

1. **Importer les e-mails de l'export AssoConnect** dans une table dédiée.
   Écartée : nouvelle donnée personnelle de ~300 personnes, export manuel à
   refaire à chaque adhésion (donc liste toujours en retard), et un e-mail
   d'AssoConnect ne correspond pas forcément à celui du compte Google.
2. **Compte ouvert, adhésion prouvée par le rattachement à la fiche.**
   Retenue. Toute personne à l'adresse vérifiée peut ouvrir un compte, qui
   ne donne **aucun** droit. Elle demande à rattacher sa fiche athlète
   (#1325) ; la demande est validée en back-office, avec une suggestion
   automatique quand la fiche est liée à un `club_members` de la saison. Le
   statut « adhérent » d'un compte se **dérive** de ce rattachement validé,
   jamais saisi. Aucune donnée nouvelle, aucun export à tenir.

Conséquence sur le code d'accès partagé (#509) : une session ne peut en
dispenser **que** si le compte est adhérent au sens ci-dessus. Sinon, tout
compte Google ouvrirait le site.

Conséquence sur `allowed_emails` : elle reste la porte du back-office et
cesse de conditionner la simple ouverture d'un compte. Ouvrir un compte sans
droit est une écriture pilotée par un visiteur : le limiteur de débit
existant s'y applique.

## Conclusions pour les sous-issues de #1312

- **#1322** : la connexion n'exige plus `allowed_emails` ; un compte sans
  rôle ni rattachement n'a aucun droit ; la session dispense du code
  d'accès seulement pour un compte adhérent (rattachement validé à une
  fiche liée à `club_members` de la saison).
- **#1323** : le fournisseur est **Google (OIDC)**, validation de
  l'`id_token` par joserfc, résolution par `sub`.
- **#1324** : **lien magique** par Brevo (API HTTP), pas de mot de passe ;
  réponse identique que l'adresse soit connue ou non (FR-030) ; lien à usage
  unique, courte durée, empreinte en base comme les jetons de session.
- **#1325** : la validation en back-office devient le point où se décide
  l'adhésion ; suggestion automatique via `club_members`.
- **#1326** : inchangée.

## Non vérifié

- Colonnes exactes de l'export AssoConnect (pages d'aide en 403).
- Règles de vérification de marque Google pour afficher nom et logo sur
  l'écran de consentement.
- Accès au DNS de `triathlon-club-nantais.com` pour SPF et DKIM.
