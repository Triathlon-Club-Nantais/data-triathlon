# Entra External ID (#1323)

Le tenant externe qui porte la connexion des adhérents par **Google** ou par
**code reçu par e-mail**. Le backend le consomme comme second fournisseur
d'identité (`backend/app/services/auth/idp/entra.py`, slug `entra`), à côté de
GitHub. Spec : `specs/20261011-155714-comptes-membres-socle/` (US3,
FR-018 à FR-024) ; choix d'outillage : `research.md` R1.

Deux outils, parce qu'aucun ne couvre tout : **Bicep** crée le tenant
(`main.bicep`, ressource `ciamDirectories`), le **script Graph**
`configure-tenant.sh` crée ce qui vit dans le tenant (application, principal de
service, consentement, secret, fournisseur Google, parcours d'inscription). Le
provider Graph de Bicep ne couvre ni les fournisseurs d'identité ni les
parcours, et Terraform imposerait un état distant à héberger.

## FinOps

- **0 €** jusqu'à 50 000 utilisateurs actifs par mois, très au delà du club.
- **Interdits**, tous payants : domaine personnalisé (Front Door), MFA ou code
  par **SMS**, et le flux *client credentials* (jetons machine facturés). Ni
  `main.bicep` ni le script n'en déclarent ; ne pas les activer au portail.

## Prérequis

- Rôle **Tenant Creator** (ou Contributor) sur le groupe de ressources
  `TCN_Data_BDD` de la souscription du club.
- `az` récent ; le script lit les réponses par `--query`, sans `jq`.
- Le lancer depuis son propre poste : le secret Google passe en argument de
  `az rest`, donc visible dans la liste des processus le temps de l'appel.

## Ordre de déploiement

1. **Tenant** (jusqu'à 30 minutes) :
   `az deployment group create -g TCN_Data_BDD -f infra/entra-external-id/main.bicep -p infra/entra-external-id/main.bicepparam`.
   Noter les sorties `tenantId` et `subdomain`.
2. **Client OAuth Google**, à la main (aucun outil gratuit) : console Google
   Cloud, *API et services → Identifiants → ID client OAuth*, type
   « Application Web ». Domaines autorisés de l'écran de consentement :
   `ciamlogin.com` et `microsoftonline.com`. URI de redirection autorisées
   (`<tid>` = identifiant du tenant, `<sub>` = sous-domaine) :
   - `https://login.microsoftonline.com`
   - `https://login.microsoftonline.com/te/<tid>/oauth2/authresp`
   - `https://login.microsoftonline.com/te/<sub>.onmicrosoft.com/oauth2/authresp`
   - `https://<tid>.ciamlogin.com/<tid>/federation/oidc/accounts.google.com`
   - `https://<tid>.ciamlogin.com/<sub>.onmicrosoft.com/federation/oidc/accounts.google.com`
   - `https://<sub>.ciamlogin.com/<tid>/federation/oauth2`
   - `https://<sub>.ciamlogin.com/<sub>.onmicrosoft.com/federation/oauth2`

   **Publier** l'écran de consentement en production : en mode test, seuls les
   comptes testeurs déclarés passent.
3. **Objets du tenant** :
   ```bash
   az login --tenant <tid> --allow-no-subscriptions
   REDIRECT_URI="https://data.triathlon-club-nantais.com/api/v1/auth/entra/callback https://data-triathlon-tcn-preview.vercel.app/api/v1/auth/entra/callback" \
   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... \
   ./infra/entra-external-id/configure-tenant.sh <tid>
   ```
   Le retour vise l'**interface**, jamais le backend (même règle que GitHub,
   `backend/app/services/auth/AGENTS.md`). Relancé, le script ne crée rien de
   plus ; il remet seulement l'application à jour (URI de retour, claims
   optionnels `email` et `xms_edov`, permissions `openid profile email
   offline_access`). Le secret client n'est créé que s'il n'en existe aucun, ou
   avec `--rotate-secret` ; il s'affiche **une seule fois** sur la sortie
   standard et n'est écrit nulle part. Les anciens secrets restent valides
   après une rotation : les retirer au portail une fois Render à jour.
4. **Réglages backend**, preview d'abord : `AUTH_ENTRA_SUBDOMAIN`,
   `AUTH_ENTRA_TENANT_ID`, `AUTH_ENTRA_CLIENT_ID`, `AUTH_ENTRA_CLIENT_SECRET`
   (`docs/ci-cd.md`). Les quatre ou aucun : le bouton n'apparaît qu'avec les
   quatre.
5. **Constat FR-021**, avant toute mise en production (ci-dessous).

## Constat FR-021 et repli

Le backend ne tient une adresse pour vérifiée que si l'`id_token` porte `email`
**et** `xms_edov: true` ; sinon la connexion est refusée en `email_unverified`.
Que le tenant réel émette bien ces deux claims n'a pas été constaté. Sur la
preview, se connecter une fois par Google et une fois par code e-mail, décoder
l'`id_token` reçu (journal de débogage local, jamais en production), et
consigner le résultat dans la section « Résultat du test sur tenant » de
`docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md`.

En cas d'échec, ne pas poser `AUTH_ENTRA_*` en production : le **repli** est
Google en direct (#1324), sans changer les règles de connexion.

## Ce qui n'est pas automatisé

- le client OAuth Google (étape 2) ;
- la rotation du secret Google : le script ne remplace pas un fournisseur
  Google existant, la mettre à jour au portail du tenant ;
- le retrait des anciens secrets client après rotation ;
- la validation de `main.bicep` : `az bicep build -f main.bicep` avant le
  premier déploiement (le Bicep CLI n'était pas installé à l'écriture).
