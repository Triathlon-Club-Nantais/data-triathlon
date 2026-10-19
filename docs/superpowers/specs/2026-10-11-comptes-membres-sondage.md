# Sondage des moyens de connexion des adhérents (#1321)

Mesuré le 11/10/2026 dans le code du dépôt, les discussions GitHub et les
documentations officielles des fournisseurs (liens en fin de section).
Epic : #1312.

## Ce que l'historique a déjà tranché

- **Discussion #209** (ouvrir la connexion aux adhérents via AssoConnect) :
  AssoConnect est un **référentiel d'appartenance, pas un fournisseur
  d'identité** ; proposition Google + lien magique ; l'export AssoConnect
  importé en CSV par un admin alimente une liste d'e-mails d'adhérents ;
  « membre » est un statut dérivé, jamais un rôle sur `users` ; un départ du
  club désactive le compte sans le supprimer.
- **Discussion #372 / #271** : éviter autant que possible e-mail + mot de
  passe (gestion des données, CNIL).
- Aucune discussion ni issue ne mentionne un service d'identité Azure. Le
  seul usage d'Entra est l'app registration de la CI, au tier gratuit
  (`docs/infra-azure.md`).

## Ce que le code impose déjà

- **Aucune source en base ne connaît l'e-mail d'un adhérent.**
  `club_members` vient de la page publique FFTri (nom, sexe, licence) ou d'un
  fichier dont seules ces colonnes sont lues, par minimisation
  (`2026-10-01-base-legale-decision.md`).
- **Le numéro de licence n'est pas un secret** : la page FFTri le publie. Il
  ne prouve pas qu'un compte appartient à un licencié.
- Un compte se résout par `(provider, subject)`, jamais par l'adresse ; une
  adresse **vérifiée** est exigée (`email_unverified` sinon), puis confrontée
  à `allowed_emails` (`provisioning.resolve_user`).
- Aucun envoi d'e-mail n'existe. Le limiteur de débit maison
  (`api/deps.py`) suffit à protéger de nouvelles routes.
- Authlib 1.8 et joserfc 1.7 sont installés : valider un `id_token` OIDC ne
  demande aucune dépendance nouvelle.

## Fournisseurs mesurés

| Option | Verdict | Raison mesurée |
| --- | --- | --- |
| AssoConnect | Écarté comme moyen de connexion | Aucun SSO, OAuth ni OIDC. API CRM « sur demande » dans l'offre Expert (dès 109 € TTC/mois), contredite par la page de l'offre (« bientôt »). Zapier : contacts seulement. Reste l'**export Excel des contacts**, utilisé pour l'éligibilité (plus bas). |
| **Entra External ID** | **Retenu, sous réserve d'un test** | Voir section dédiée : Google et code par e-mail derrière un seul fournisseur OIDC, 0 € jusqu'à 50 000 utilisateurs actifs par mois. |
| Google en direct (OIDC) | Repli | Gratuit, claim `email_verified`, `sub` comme identifiant. Pas de vérification d'application avec `openid email profile`. Couvre seulement les détenteurs d'un compte Google. |
| Strava | Écarté | Aucun scope ne fournit l'e-mail ; application limitée à 10 athlètes avant revue par Strava. |
| Apple | Écarté | Programme développeur payant ; adresse relais inutilisable pour l'éligibilité. |
| Microsoft (comptes perso) | Écarté | Claim `email` « non garanti », pas d'`email_verified`. |
| Mot de passe | Écarté | Contraire à #271 ; NIST SP 800-63B-4 impose 15 caractères, liste de mots de passe compromis, réinitialisation par e-mail. `identities.secret_hash` reste vide. |
| Azure AD B2C | Écarté | Fermé aux nouveaux clients depuis le 01/05/2025. |
| App Service Easy Auth, Static Web Apps | Hors sujet | Ne protègent que des applications hébergées chez Azure ; ni Render ni Vercel. |

Sources : [AssoConnect tarifs](https://www.assoconnect.com/tarifs/),
[export contacts](https://help.assoconnect.com/hc/fr/articles/4695561557266),
[Zapier AssoConnect](https://zapier.com/apps/assoconnect/integrations),
[Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect),
[Google mode test](https://support.google.com/cloud/answer/15549945),
[Strava](https://developers.strava.com/docs/getting-started/),
[Apple web](https://developer.apple.com/help/account/capabilities/configure-sign-in-with-apple-for-the-web),
[Microsoft claims](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference),
[NIST SP 800-63B](https://pages.nist.gov/800-63-4/sp800-63b.html),
[B2C FAQ](https://learn.microsoft.com/en-us/azure/active-directory-b2c/faq).

## Entra External ID : le courtier SSO Azure

Un tenant externe (CIAM) lié à la souscription Azure du club, que
l'application voit comme **un seul fournisseur OIDC** de plus dans
`services/auth/idp/`.

- **Coût** : « gratuit pour les 50 000 premiers MAU », cumulés sur les
  tenants de la souscription. Facturés seulement : SMS, client credentials,
  Go-Local, add-ons premium. Aucun n'est nécessaire.
  ([tarifs](https://azure.microsoft.com/en-us/pricing/details/microsoft-entra-external-id/),
  [modèle](https://learn.microsoft.com/en-us/entra/external-id/external-identities-pricing))
- **Moyens de connexion inclus** : Google, **code à usage unique par
  e-mail**, Facebook, Apple, passkey, OIDC personnalisé
  ([fonctionnalités](https://learn.microsoft.com/en-us/entra/external-id/customers/concept-supported-features-customers)).
  **Microsoft envoie lui-même les codes** : pas de service d'envoi, pas de
  SPF/DKIM, pas d'accès DNS à obtenir. C'est un code, pas un lien magique.
- **Intégration** : OIDC standard, code d'autorisation + PKCE, autorité
  `https://<tenant>.ciamlogin.com/<tenantId>/v2.0`. Authlib l'utilise comme
  n'importe quel fournisseur OIDC ; GitHub reste à côté pour le back-office.
- **À accepter pour rester à 0 €** : l'URL `<tenant>.ciamlogin.com` (un
  domaine personnalisé passe par Azure Front Door, facturé à part, environ
  35 $/mois, non vérifié) ; des e-mails de code à l'expéditeur Microsoft.
- **Extensions personnalisées** (`OnAttributeCollectionSubmit`, en preview) :
  appelées **à l'inscription seulement**, délai de ~2 s, incompatible avec un
  Render gratuit qui démarre à froid. **Non retenues** : l'éligibilité se
  vérifie dans notre API, à chaque connexion.
- **Risque ouvert, à lever par un test** : le claim `email` doit être ajouté
  explicitement au jeton, et un fil Microsoft Q&A le signale absent pour les
  comptes Google tant qu'il n'est pas remappé
  ([claims](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-add-attributes-to-token),
  [Q&A](https://learn.microsoft.com/en-us/answers/questions/5892412/microsoft-entra-external-id-email-claim-not-includ)).
  L'émission d'un `email_verified` n'est pas documentée : une adresse
  passée par le code e-mail est prouvée, une adresse Google l'est par Google,
  mais il faut le **constater** sur un jeton réel avant d'en faire une règle.
- **Sortie** : les comptes vivent dans l'annuaire Entra ; en partir oblige à
  relier les comptes par e-mail. Coût faible tant qu'il n'y a pas de mot de
  passe, ce qui est le cas.

**Repli si le test échoue** : Google en direct + code ou lien par e-mail
envoyé par nos soins. Render gratuit bloque le SMTP sortant depuis le
26/09/2025
([changelog](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports)),
donc une API HTTP : Azure Communication Services Email (0,00025 $ par e-mail,
~0,50 $/mois à 1 000 utilisateurs, mais domaine personnalisé obligatoire, le
domaine Azure étant plafonné à 10 e-mails par heure), ou Brevo (300/jour
gratuits, société française). Les deux exigent SPF et DKIM sur
`triathlon-club-nantais.com`.

| Coût mensuel | 300 MAU | 1 000 MAU |
| --- | --- | --- |
| Entra External ID (Google + code e-mail, domaine par défaut) | 0 € | 0 € |
| Repli : Google direct + ACS Email | ~0,15 $ | ~0,50 $ |

## Éligibilité : qui est adhérent ?

Deux voies cumulées, la première automatique, la seconde manuelle :

1. **Liste d'e-mails d'adhérents.** Une liste importée par un admin depuis
   l'**export AssoConnect** (patron de l'import `club_members`), ou complétée
   à la main, fait foi. Un compte dont une adresse **vérifiée** y figure est
   adhérent : sa demande de rattachement à une fiche athlète est **validée
   d'office**.
2. **Demande de rattachement validée.** Sinon, la demande part dans une file
   du back-office, avec une suggestion quand la fiche est liée à un
   `club_members` de la saison. Validée, elle rend le compte adhérent.

Le statut « adhérent » se **dérive** de l'une ou l'autre voie, jamais saisi
sur `users` (#209, invariant de #115).

**Cette liste est distincte d'`allowed_emails`.** `allowed_emails` reste la
porte du back-office (et le rôle du premier jour) ; la liste d'adhérents a
une autre source (export AssoConnect), un autre cycle de vie (réimportée à
chaque saison, une adresse absente du dernier import cesse de compter) et une
autre conservation (alignée sur `club_members`). Les fondre ferait d'un
contributeur externe un adhérent, et d'un adhérent un candidat au
back-office.

**Coût RGPD** : ~300 adresses e-mail deviennent une donnée nouvelle. Il faut
un avenant à `2026-10-01-base-legale-decision.md` (finalité : reconnaître un
adhérent à la connexion ; conservation : saison en cours et précédente) et la
mise à jour de la politique de confidentialité, y compris Microsoft comme
sous-traitant si Entra est retenu.

**Code d'accès partagé (#509)** : une session ne peut en dispenser **que**
pour un compte adhérent. Sinon tout compte Google ouvrirait le site.

## Conclusions pour les sous-issues de #1312

- **#1322** : la connexion n'exige plus `allowed_emails` ; un compte sans
  rôle ni statut adhérent n'a aucun droit ; la session dispense du code
  d'accès seulement pour un compte adhérent.
- **#1323** : fournisseur **Entra External ID** (Google + code par e-mail),
  premier critère : constater sur un jeton réel la présence d'un e-mail
  vérifié pour les deux moyens. Échec : repli sur Google en direct.
- **#1324** : sans objet si Entra est retenu (le code par e-mail est
  inclus). Ne se réouvre qu'en repli.
- **Nouvelle sous-issue** : importer la liste d'e-mails d'adhérents depuis
  l'export AssoConnect (table dédiée, purge alignée sur `club_members`,
  avenant RGPD).
- **#1325** : validation d'office si une adresse vérifiée du compte est dans
  la liste d'adhérents, sinon file de validation du back-office.
- **#1326** : inchangée.

## Non vérifié

- Présence d'un e-mail vérifié dans le jeton Entra pour Google et pour le
  code e-mail (test bloquant de #1323).
- Prise en charge des comptes Google Workspace à domaine personnalisé par
  la fédération Google d'Entra.
- Colonnes exactes de l'export AssoConnect (pages d'aide en 403).
- Prix d'Azure Front Door (seulement utile pour un domaine de connexion
  personnalisé, non retenu).

## Résultat du test sur tenant

**À faire par l'exploitant avant production** (FR-021 de
`specs/20261011-155714-comptes-membres-socle/`). Le code de #1323 est livré et
testé sans réseau, contre un fournisseur simulé ; aucun tenant réel n'a encore
été interrogé. Procédure : `infra/entra-external-id/AGENTS.md`, § « Constat
FR-021 et repli ».

| Moyen | `email` présent | `xms_edov` | `idp` | Date | Constaté par |
|---|---|---|---|---|---|
| Google (adresse gmail.com) | oui | `false` | présent, valeur à confirmer (`google.com` attendu) | 19/10/2026 | mainteneur, preview |
| Code par e-mail | à constater | à constater | à constater | | |

Claims reçus pour Google : `aud, email, exp, iat, idp, iss, name, nbf, nonce,
oid, preferred_username, rh, sid, sub, tid, uti, ver, xms_edov`. `xms_edov`
parle du propriétaire du **domaine** de l'adresse, pas de l'adresse : il vaut
`false` pour toute adresse gmail.com, et la règle d'origine refusait donc tout
compte Google. Règle retenue (#1664) : adresse certifiée si `xms_edov` vaut
`true`, **ou** si `idp` vaut exactement `google.com`, Google ne délivrant
qu'une adresse vérifiée. Le journal `Entra identity without a certified
address` donne les noms des claims, `xms_edov` et `idp`, jamais l'adresse.

Si l'un des deux ne porte pas `email` avec `xms_edov: true`, la connexion par
ce moyen est refusée (`email_unverified`) : ne pas activer `AUTH_ENTRA_*` en
production, et rouvrir #1324 (Google en direct).
