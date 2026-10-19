# Entra External ID (#1323)

Le tenant externe qui porte la connexion des adhérents par **Google** ou par
**code reçu par e-mail**. Le backend le consomme comme second fournisseur
d'identité (`backend/app/services/auth/idp/entra.py`, slug `entra`), à côté de
GitHub. Spec : `specs/20261011-155714-comptes-membres-socle/` (US3,
FR-018 à FR-024) ; choix d'outillage : `research.md` R1.

Trois gestes, parce qu'aucun outil ne couvre tout : **Bicep** crée le tenant
(`main.bicep`, ressource `ciamDirectories`), le **script Graph**
`configure-tenant.sh` crée les applications (application, principal de service,
consentement, secret), et le **portail** porte le fournisseur Google et le
parcours d'inscription. Le provider Graph de Bicep ne couvre ni les fournisseurs
d'identité ni les parcours, Terraform imposerait un état distant à héberger, et
Azure CLI ne peut pas les créer : Graph refuse à cette application Microsoft
les permissions `IdentityProvider.*` et `EventListener.*` (`AADSTS65002`, mesuré
au premier déploiement le 2026-10-15), consentement ou pas.

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
  supprimé en sortie, jamais par la ligne de commande.

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
   ./infra/entra-external-id/configure-tenant.sh <tid>

   APP_NAME=data-triathlon-prod \
   REDIRECT_URI=https://data.triathlon-club-nantais.com/api/v1/auth/entra/callback \
   ./infra/entra-external-id/configure-tenant.sh <tid>
   ```
   Le retour vise l'**interface**, jamais le backend (même règle que GitHub,
   `backend/app/services/auth/AGENTS.md`). Relancé, le script ne crée rien de
   plus ; il remet seulement l'application à jour (URI de retour, claims
   optionnels `email` et `xms_edov`, permissions `openid profile email`) et la
   portée du consentement. Le secret client n'est créé que s'il n'en existe
   aucun, ou avec `--rotate-secret` ; il sort **une seule fois**, seul, sur la
   sortie standard (les journaux vont sur la sortie d'erreur) : la rediriger
   vers un fichier `chmod 600` hors du dépôt (`> ~/.tcn-entra-preview.secret`)
   le temps de le poser sur Render. Les anciens secrets restent valides après une
   rotation : les retirer au portail une fois Render à jour. Juste après une
   création, Graph peut répondre 404 ou 400 quelques secondes : le script
   réessaie six fois, à 5 s d'intervalle.

   **Ne jamais supprimer ni renommer une application à la légère.** Le
   backend résout les comptes par `oid`, stable dans le tenant, donc recréer
   une application ne les rend pas orphelins ; mais le script retrouve
   l'application par son nom (`APP_NAME`), et un renommage en créerait une
   seconde, avec un nouvel identifiant client à reporter sur Render.
4. **Au portail** (https://entra.microsoft.com, intitulés anglais), après
   bascule sur le tenant externe (**Settings**, **Directories +
   subscriptions**, **Switch**) :
   - **Entra ID**, **External Identities**, **All identity providers**, onglet
     **Built-in**, **Google**, **Configure** : identifiant et secret du client
     OAuth de l'étape 2 ;
   - **External Identities**, **User flows**, **New user flow** : nom
     `tcn-signup-signin`, fournisseurs **Email one-time passcode** et
     **Google** (jamais e-mail avec mot de passe), attribut **Email Address**
     seul (plus **Display Name** au besoin), aucun téléphone ;
   - dans le parcours, **Applications**, **Add application** : les deux
     applications de l'étape 3.
5. **Réglages backend**, preview d'abord, chacun avec l'identifiant et le
   secret de **son** application : `AUTH_ENTRA_SUBDOMAIN`,
   `AUTH_ENTRA_TENANT_ID`, `AUTH_ENTRA_CLIENT_ID`, `AUTH_ENTRA_CLIENT_SECRET`
   (`docs/ci-cd.md`). Les quatre ou aucun : le bouton n'apparaît qu'avec les
   quatre.
6. **Constat FR-021**, avant toute mise en production (ci-dessous).

## Constat FR-021 et repli

Le backend ne tient une adresse pour vérifiée que si l'`id_token` porte `email`
**et** soit `xms_edov: true`, soit `idp: google.com` ; sinon la connexion est
refusée en `email_unverified`, avec un WARNING qui donne les noms des claims,
`xms_edov` et `idp` (jamais l'adresse). Constaté le 19/10/2026 pour Google :
`xms_edov` vaut `false` pour une adresse gmail.com, d'où la règle sur `idp`.
Reste à constater le code par e-mail. Sur la
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
dans le mois qui suit, que celle-ci vienne du titulaire (« Supprimer mon
compte ») ou de l'expiration après 5 ans sans connexion (`purge-retention`).

Le compte supprimé emporte son identité, mais la ligne `account.delete` du
journal d'administration garde ses `oid` Entra (`payload.entra_oids`), 12 mois
et à cette seule fin. **Ne jamais comparer l'annuaire à une base** : le tenant
sert à la préproduction comme à la production, et une comparaison contre la
mauvaise base supprimerait des comptes vivants.

**Rappel** (#1635) : la reprise planifiée du lundi (`batch.yml`) compte les
identifiants à effacer de la semaine et, s'il y en a, ouvre ou complète l'issue
`ops` « Entra directory deletions to finish » (le nombre seul : le dépôt est
public). Une reprise du lundi manquée ne rappelle pas sa semaine : le relevé
mensuel, sur 35 jours par défaut, la rattrape. Au plus tard à ce rappel, et au moins une fois par mois, sur la base de
**production** (nommée explicitement ; même geste à part sur celle de
préproduction si on le souhaite, jamais les deux mêlées) :

1. relever les identifiants depuis le dernier nettoyage, dont la date est notée
   à la fin de l'étape 3 :
   `uv run python -m app.cli entra-deletions --since <date du dernier nettoyage>`
   (depuis `backend/`, `DATABASE_URL` de production). Elle lit le journal
   `account.delete` et rend chaque `oid` avec sa commande `az rest` ; une
   suppression sans `oid` (connexion GitHub seule) n'y figure pas ;
2. `az login --tenant <tid> --allow-no-subscriptions`, puis **à blanc** pour
   chaque `oid` : `az rest --method get --url https://graph.microsoft.com/v1.0/users/<oid>`.
   Un 404 veut dire déjà supprimé ; relire la liste avant d'aller plus loin ;
3. supprimer chacun (les commandes rendues à l'étape 1) :
   `az rest --method delete --url https://graph.microsoft.com/v1.0/users/<oid>`,
   puis noter la date du nettoyage.

Une demande d'effacement adressée au club pour un compte encore cité par une
donnée du club (refus 409 de la suppression en libre service) se traite de la
même façon, une fois le compte supprimé par l'exploitant :
`python -m app.cli delete-account --user-id <id>` (passe à blanc), puis avec
`--yes` (#1634). Les données du club qui le citent passent au compte système.

## Ce qui n'est pas automatisé

- le client OAuth Google (étape 2) ;
- le fournisseur Google, le parcours et le rattachement des applications
  (étape 4), et la rotation du secret Google, au portail du tenant ;
- le retrait des anciens secrets client après rotation ;
- la suppression de l'utilisateur Entra après celle du compte (relevé par
  `entra-deletions`, rappelé chaque lundi par une issue `ops`, #1635) ;
- la validation avant modification : `az bicep build`, `what-if`, et
  `uvx --from shellcheck-py shellcheck configure-tenant.sh`. Le premier
  déploiement (2026-10-15) a révélé deux valeurs que la référence ARM donnait
  fausses, corrigées dans `main.bicep` : SKU `Base`, nom suffixé
  `.onmicrosoft.com`.
