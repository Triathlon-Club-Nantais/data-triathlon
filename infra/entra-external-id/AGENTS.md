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
- Fournisseur de ressources `Microsoft.AzureActiveDirectory` inscrit sur la
  souscription, une fois : `az provider register --namespace Microsoft.AzureActiveDirectory`
  (vérifier par `az provider show -n Microsoft.AzureActiveDirectory --query registrationState`).
- `az` récent et `jq` (paquet courant, présent sur la plupart des postes qui
  ont `az`) : les corps de requête sont construits par `jq -n --arg`, jamais
  par interpolation. Ils passent par un fichier d'un dossier temporaire privé,
  supprimé en sortie, jamais par la ligne de commande : le secret Google
  n'apparaît pas dans la liste des processus.

## Ordre de déploiement

1. **Tenant** (jusqu'à 30 minutes). D'abord la simulation, puis le
   déploiement réel une fois le résultat relu :
   ```bash
   az deployment group what-if -g TCN_Data_BDD -f infra/entra-external-id/main.bicep -p infra/entra-external-id/main.bicepparam
   az deployment group create -g TCN_Data_BDD -f infra/entra-external-id/main.bicep -p infra/entra-external-id/main.bicepparam
   ```
   Noter les sorties `tenantId` et `subdomain`. Le nom du tenant (`tenantName`)
   ne prend que lettres et chiffres, 26 au plus (référence ARM citée dans
   `main.bicep`).
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
3. **Objets du tenant, une application par environnement** (comme les
   applications OAuth GitHub : un secret de preview qui fuit ne doit pas
   ouvrir la production). Deux lancements, preview puis production :
   ```bash
   az login --tenant <tid> --allow-no-subscriptions
   APP_NAME=data-triathlon-preview \
   REDIRECT_URI=https://data-triathlon-tcn-preview.vercel.app/api/v1/auth/entra/callback \
   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... \
   ./infra/entra-external-id/configure-tenant.sh <tid>

   APP_NAME=data-triathlon-prod \
   REDIRECT_URI=https://data.triathlon-club-nantais.com/api/v1/auth/entra/callback \
   ./infra/entra-external-id/configure-tenant.sh <tid>
   ```
   Le fournisseur Google et le parcours d'inscription sont communs au tenant :
   le premier lancement les crée, le second y rattache sa propre application.
   Le retour vise l'**interface**, jamais le backend (même règle que GitHub,
   `backend/app/services/auth/AGENTS.md`). Relancé, le script ne crée rien de
   plus ; il remet seulement l'application à jour (URI de retour, claims
   optionnels `email` et `xms_edov`, permissions `openid profile email`) et la
   portée du consentement. Il **ne rafraîchit pas** un parcours existant : ses
   moyens de connexion se modifient au portail. Le parcours est créé sans
   `onAttributeCollection`, facultatif selon la documentation Graph : au
   premier lancement, vérifier au portail qu'il ne demande que l'adresse. Le
   secret client n'est créé que s'il n'en existe aucun, ou avec
   `--rotate-secret` ; il s'affiche **une seule fois** sur la sortie standard
   et n'est écrit nulle part. Les anciens secrets restent valides après une
   rotation : les retirer au portail une fois Render à jour. Juste après une
   création, Graph peut répondre 404 ou 400 quelques secondes : le script
   réessaie six fois, à 5 s d'intervalle.

   **Ne jamais supprimer ni renommer une application à la légère.** Le
   backend résout les comptes par `oid`, stable dans le tenant, donc recréer
   une application ne les rend pas orphelins ; mais le script retrouve
   l'application par son nom (`APP_NAME`), et un renommage en créerait une
   seconde, avec un nouvel identifiant client à reporter sur Render.
4. **Réglages backend**, preview d'abord, chacun avec l'identifiant et le
   secret de **son** application : `AUTH_ENTRA_SUBDOMAIN`,
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

## Annuaire du tenant et suppression d'un compte

L'inscription en libre service crée, dans l'annuaire du tenant, un objet
utilisateur (adresse, nom affiché). Le site ne le supprime pas (#1326) : le
flux *client credentials* qui le permettrait est un module payant d'Entra
External ID. **Le club l'efface à la main après la suppression du compte**,
que celle-ci vienne du titulaire (« Supprimer mon compte ») ou de l'expiration
après 5 ans sans connexion (`purge-retention`).

Le compte supprimé emporte son identité, donc son `oid` : on ne retrouve pas
l'utilisateur Entra à partir du site après coup. On compare les deux listes,
une fois par mois et après chaque `purge-retention` qui annonce des comptes
supprimés :

1. `az login --tenant <tid> --allow-no-subscriptions` ;
2. les `oid` de l'annuaire :
   `az rest --method get --url 'https://graph.microsoft.com/v1.0/users?$select=id,mail,createdDateTime&$top=999'` ;
3. les `oid` connus du site : `SELECT subject FROM identities WHERE provider = 'entra'` ;
4. tout `oid` de l'annuaire absent du site, créé il y a plus d'une heure (un
   parcours en cours n'a pas encore son identité), est un compte supprimé :
   `az rest --method delete --url https://graph.microsoft.com/v1.0/users/<oid>`,
   ou depuis le portail du tenant (*Utilisateurs*).

Une demande d'effacement adressée au club pour un compte encore cité par une
donnée du club (refus 409 de la suppression en libre service) se traite de la
même façon une fois le compte supprimé par l'exploitant.

## Ce qui n'est pas automatisé

- le client OAuth Google (étape 2) ;
- la rotation du secret Google : le script ne remplace pas un fournisseur
  Google existant, la mettre à jour au portail du tenant ;
- le retrait des anciens secrets client après rotation ;
- les moyens de connexion d'un parcours déjà créé ;
- la suppression de l'utilisateur Entra après celle du compte (comparaison
  mensuelle ci-dessus) ;
- la validation de `main.bicep` (`az bicep build -f main.bicep`) et du script
  (`shellcheck configure-tenant.sh`) avant le premier lancement : ni le Bicep
  CLI ni shellcheck n'étaient installés à l'écriture, seul `bash -n` a tourné.
