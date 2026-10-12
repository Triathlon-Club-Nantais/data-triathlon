# Research: Comptes membres, socle

Complète le sondage `docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md` (qui prime) sur les points d'implémentation.

## R1. Infrastructure as code du tenant Entra External ID

- **Decision**: Bicep pour le tenant (`Microsoft.AzureActiveDirectory/ciamDirectories@2023-05-17-preview`, `location: 'Europe'`, `sku: { name: 'Base', tier: 'A0' }`, `createTenantProperties: { countryCode: 'FR', displayName }`), déployé par `az deployment group create` dans le groupe `TCN_Data_BDD`. Les objets **internes** au tenant (application, principal de service, consentement, secret, fournisseur Google, parcours d'inscription) sont créés par `infra/entra-external-id/configure-tenant.sh`, script bash idempotent (`az rest` sur Microsoft Graph v1.0, lecture avant écriture). Le client OAuth Google est une étape manuelle documentée (console Google Cloud, aucun outil gratuit).
- **Rationale**: le provider Graph de Bicep ne couvre ni `identityProviders` ni `authenticationEventsFlows`, et exige un déploiement au niveau du tenant externe avec élévation d'accès ; Terraform `azuread` ne les couvre pas non plus et `azurerm` n'a pas de ressource tenant (AzAPI seulement) ; Terraform imposerait en outre un état distant à héberger (coût et secret). Un script Graph couvre tout ce que Bicep ne couvre pas, en un seul langage déjà maîtrisé par `az`.
- **Alternatives considered**: Bicep + extension Graph (couverture partielle, preview, élévation) ; Terraform + AzAPI + `msgraph` (preview, état distant) ; portail seul (non reproductible, contraire à la demande).
- **Sources**: [ciamDirectories](https://learn.microsoft.com/en-us/azure/templates/microsoft.azureactivedirectory/ciamdirectories), [Graph Bicep](https://learn.microsoft.com/en-us/graph/templates/bicep/reference/overview?view=graph-bicep-1.0), [identityProviders](https://learn.microsoft.com/en-us/graph/api/identitycontainer-post-identityproviders?view=graph-rest-1.0), [authenticationEventsFlows](https://learn.microsoft.com/en-us/graph/api/identitycontainer-post-authenticationeventsflows?view=graph-rest-1.0), [includeApplications](https://learn.microsoft.com/en-us/graph/api/authenticationconditionsapplications-post-includeapplications?view=graph-rest-1.0).
- **Points de vigilance**: création jusqu'à 30 min ; rôle « Tenant Creator » requis ; une application n'appartient qu'à un parcours et doit avoir un principal de service ; identifiant du fournisseur de code e-mail `EmailOtpSignup-OAUTH` à confirmer par `GET /identity/identityProviders` (le script le lit plutôt que le supposer).

## R2. Validation de l'`id_token`

- **Decision**: découverte `https://{subdomain}.ciamlogin.com/{tenantId}/v2.0/.well-known/openid-configuration` lue dans `fetch_identity` (réseau autorisé à cette étape), mise en cache 1 h avec le JWKS. Décodage par `joserfc.jwt.decode(id_token, KeySet.import_key_set(jwks), algorithms=["RS256"])`, puis `authlib.oidc.core.CodeIDToken(claims, header, {"iss": {"essential": True, "value": discovery["issuer"]}, "aud": {"essential": True, "value": client_id}}, {"nonce": nonce, "client_id": client_id, "access_token": ...}).validate(leeway=120)`. Sur `kid` inconnu, un seul rafraîchissement du JWKS. Les points de terminaison d'autorisation et de jeton sont construits depuis le sous-domaine et l'identifiant du tenant, pour que `authorize()` reste sans réseau (contrat `IdentityProvider`).
- **Rationale**: `OpenIDMixin.parse_id_token` n'existe que dans les clients de framework, pas dans `httpx_client.OAuth2Client` ; `authlib.jose` est déprécié au profit de joserfc ; `aud` doit être passé explicitement, sinon il n'est pas vérifié ; l'émetteur se lit dans la découverte (fils Q&A sur des écarts d'hôte).
- **Alternatives considered**: `authlib.jose` (déprécié) ; émetteur codé en dur (fragile) ; découverte dans `authorize()` (casse le contrat « aucun réseau avant le retour »).

## R3. Adresse vérifiée côté Entra

- **Decision**: scopes `openid profile email` ; claims optionnels `email` et `xms_edov` sur l'`id_token` (déclarés par le script). `email_verified = bool(claims.get("email")) and claims.get("xms_edov") is True`. `verified_emails = (email,)` si vérifiée, sinon `()`. Identifiant : `oid`, exigé (absent → `provider_error`). `sub` est propre à chaque inscription d'application (pairwise) : recréer ou remplacer l'application rendrait orphelins tous les comptes, et l'appariement par adresse est interdit ; `oid` est stable dans tout le tenant (décision de revue de #1346).
- **Rationale**: Entra n'émet pas d'`email_verified` ; `xms_edov` vaut vrai pour une adresse venue de Google ou du code e-mail, faux pour les sources non vérifiées. Le constat sur jeton réel reste exigé avant production (FR-021) ; si `xms_edov` manque, la connexion est refusée en `email_unverified`, jamais acceptée par défaut.
- **Alternatives considered**: faire confiance à `email` seul (Microsoft le déclare non fiable pour l'autorisation) ; claim `idp` (non documenté pour le CIAM).

## R4. Dispense du code d'accès pour un adhérent

- **Decision**: `require_site_access` éprouve d'abord le cookie de site ; à défaut, il lit la session (`optional_user`, appelé directement et non en dépendance) et rend la main si `membership.is_member(db, user, today)`, y compris sans code configuré. Sinon 401. Côté frontend, `serverFetch` relaie, en plus de `tcn_site_session`, le cookie de session SSO (nom se terminant par `tcn_session`, préfixé `__Host-` en production). `checkSiteAccess` relaie déjà tout le pot de cookies.
- **Rationale**: même sécurité dans les deux ordres ; le cookie d'abord évite la lecture de session et les deux requêtes du statut adhérent pour tout visiteur qui a le code (revue de #1322, qui a inversé l'ordre initial calqué sur `require_benevole_access`). Le relais du cookie de session dans `serverFetch` ne dégrade pas le cache partagé : le cookie de site est déjà unique par visiteur (horodatage signé, cf. commentaire de `siteAccessCookieHeader`), donc aucun partage inter-visiteurs n'existe à perdre ; seuls ces deux cookies partent, pas le pot entier (#586).
- **Alternatives considered**: poser un cookie de site à la connexion d'un adhérent (deux sources de vérité, retrait de la liste sans effet avant expiration de 90 jours, contraire à SC-004).

## R5. Adresse retenue et statut adhérent

- **Decision**: `provisioning` retient, parmi les adresses vérifiées, la première inscrite à `allowed_emails`, sinon la première qui compte dans `member_emails`, sinon la principale (FR-016) ; elle alimente `users.email`, rafraîchie à chaque connexion. `membership.is_member(db, user, today)` : faux pour le compte système des bénévoles ou un compte inactif ; sinon `member_email_repository.counts(db, user.email, season_of(today))`.
- **Saison qui compte** : la saison en cours si elle a au moins une entrée importée, sinon la précédente ; les entrées manuelles de la saison en cours comptent aussi (une requête `EXISTS` sur les imports de la saison en cours, puis la recherche indexée sur `(email, season)` dans ces deux saisons au plus).
- **Rationale**: dérivé à chaque requête, donc un retrait prend effet immédiatement (SC-004) ; aucune colonne de rôle ni de statut sur `users` (invariant #115, discussion #209).
- **Alternatives considered**: colonne `is_member` sur `users` (figée, contraire à l'invariant) ; table de statut matérialisée (YAGNI à ce volume).

## R6. Import de la liste

- **Decision**: reprise de `club_members_service` : `sheet_source.read_table`, `_header_key`, `_column`, erreurs `DomainError` en français, `audit.record`. En-têtes acceptés (après normalisation alphanumérique) : `email`, `mail`, `courriel`, `adressemail`, `adresseemail`, `adressee-mail` normalisé, `emailaddress`, `adresseelectronique`, `adressedecourriel`. Une adresse valide correspond à `^[^@\s]+@[^@\s]+\.[^@\s]+$` après `core.email.normalize_email` (`strip().lower()`, revue de #1322).
- **Remplacement** : supprime les entrées `source="import"` de la saison absentes du fichier, ajoute les nouvelles, laisse les entrées `manual` ; une adresse présente en manuel et dans le fichier reste manuelle.
- **Rationale**: même geste que la liste des licenciés pour l'administrateur ; aucune autre colonne lue (minimisation).

## R7. Redirection après connexion

- **Decision**: le retour de parcours redirige vers `/admin` si l'utilisateur administre (`permissions.administers`), sinon vers `/`. Pas de paramètre `next` (FR-026 du socle, inchangé).
- **Rationale**: un adhérent sans rôle n'a rien à faire sur un écran `NoAdminAccess` (#1109).
