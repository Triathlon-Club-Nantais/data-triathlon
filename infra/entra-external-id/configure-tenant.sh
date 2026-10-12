#!/usr/bin/env bash
# Configure le tenant externe Entra External ID du club (#1323) par Microsoft
# Graph v1.0 : application, principal de service, consentement, secret client,
# fournisseur Google, parcours d'inscription. Idempotent : chaque objet est lu
# avant d'être créé, et une relance ne crée rien de plus.
#
# Une application par environnement : lancer le script une fois par
# environnement, avec son propre APP_NAME et sa propre URI de retour.
#
# Usage :
#   az login --tenant <tenantId> --allow-no-subscriptions
#   APP_NAME=data-triathlon-preview \
#   REDIRECT_URI=https://.../api/v1/auth/entra/callback \
#   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... \
#   ./configure-tenant.sh <tenantId> [--rotate-secret]
#
# Le secret client est affiché une seule fois sur la sortie standard et n'est
# jamais écrit sur disque. Prérequis : az et jq. Procédure : AGENTS.md du dossier.
set -euo pipefail

GRAPH="https://graph.microsoft.com/v1.0"
GRAPH_APP_ID="00000003-0000-0000-c000-000000000000"
FLOW_NAME="${FLOW_NAME:-data-triathlon connexion}"
SCOPES="openid profile email"

usage() {
  echo "Usage : APP_NAME=... REDIRECT_URI=... $0 <tenantId> [--rotate-secret]" >&2
  exit 2
}

[[ $# -ge 1 ]] || usage
TENANT_ID="$1"
ROTATE_SECRET=false
if [[ $# -ge 2 ]]; then
  [[ "$2" == "--rotate-secret" ]] || usage
  ROTATE_SECRET=true
fi
: "${APP_NAME:?APP_NAME est requis (une application par environnement)}"
: "${REDIRECT_URI:?REDIRECT_URI est requis (URI de retour de cet environnement)}"
command -v jq >/dev/null || { echo "jq est requis" >&2; exit 1; }

log() { echo "$*" >&2; }

# Les corps de requête passent par un fichier de ce dossier privé, jamais par la
# ligne de commande : le secret Google n'apparaît pas dans la liste des processus.
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
umask 077

graph() {
  # graph <méthode> <chemin> [arguments az rest supplémentaires]
  local method="$1" path="$2"
  shift 2
  az rest --method "$method" --url "${GRAPH}${path}" "$@"
}

# send <méthode> <chemin> <json> [arguments] : écriture, corps lu depuis un fichier.
send() {
  local method="$1" path="$2" body="$3"
  shift 3
  printf '%s' "$body" > "$WORKDIR/body.json"
  graph "$method" "$path" --body "@$WORKDIR/body.json" "$@"
}

# lookup <chemin> <requête JMESPath> [arguments] : valeur, ou vide si absente.
lookup() {
  local path="$1" query="$2" value
  shift 2
  value="$(graph get "$path" --query "$query" -o tsv "$@")" || return 1
  [[ "$value" == "None" ]] && value=""
  echo "$value"
}

# retry <commande...> : Graph est à cohérence différée, un objet tout juste créé
# peut répondre 404 ou 400 quelques secondes.
retry() {
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if "$@"; then return 0; fi
    log "Graph pas encore cohérent, nouvel essai dans 5 s ($attempt/6)"
    sleep 5
  done
  "$@"
}

current_tenant="$(az account show --query tenantId -o tsv 2>/dev/null || true)"
if [[ "$current_tenant" != "$TENANT_ID" ]]; then
  log "Session az hors du tenant $TENANT_ID. Lancer d'abord :"
  log "  az login --tenant $TENANT_ID --allow-no-subscriptions"
  exit 1
fi

# Identifiants des permissions déléguées openid, profile, email de Microsoft
# Graph, fixes pour tous les tenants.
app_body="$(jq -n --arg name "$APP_NAME" --arg uri "$REDIRECT_URI" --arg graph "$GRAPH_APP_ID" '{
  displayName: $name,
  signInAudience: "AzureADMyOrg",
  web: {redirectUris: [$uri]},
  optionalClaims: {idToken: [
    {name: "email", essential: false},
    {name: "xms_edov", essential: false}
  ]},
  requiredResourceAccess: [{
    resourceAppId: $graph,
    resourceAccess: [
      {id: "37f7f235-527c-4136-accd-4a02d197296e", type: "Scope"},
      {id: "14dad69e-099b-42c9-810b-d002981feec1", type: "Scope"},
      {id: "64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0", type: "Scope"}
    ]
  }]
}')"

# 1. Application
app_object_id="$(lookup /applications 'value[0].id' --url-parameters "\$filter=displayName eq '${APP_NAME}'")"
if [[ -z "$app_object_id" ]]; then
  created="$(send post /applications "$app_body")"
  app_object_id="$(jq -r .id <<<"$created")"
  app_id="$(jq -r .appId <<<"$created")"
  log "Application créée : ${APP_NAME}"
else
  send patch "/applications/${app_object_id}" "$app_body" >/dev/null
  app_id="$(graph get "/applications/${app_object_id}" --query appId -o tsv)"
  log "Application existante mise à jour : ${APP_NAME}"
fi

# 2. Principal de service, sans lequel le parcours d'inscription refuse l'application
sp_id="$(lookup /servicePrincipals 'value[0].id' --url-parameters "\$filter=appId eq '${app_id}'")"
if [[ -z "$sp_id" ]]; then
  sp_id="$(retry send post /servicePrincipals "$(jq -n --arg app "$app_id" '{appId: $app}')" --query id -o tsv)"
  log "Principal de service créé"
else
  log "Principal de service existant"
fi

# 3. Consentement administrateur aux permissions déléguées
graph_sp_id="$(lookup /servicePrincipals 'value[0].id' --url-parameters "\$filter=appId eq '${GRAPH_APP_ID}'")"
grant_id="$(lookup /oauth2PermissionGrants 'value[0].id' \
  --url-parameters "\$filter=clientId eq '${sp_id}' and resourceId eq '${graph_sp_id}' and consentType eq 'AllPrincipals'")"
if [[ -z "$grant_id" ]]; then
  retry send post /oauth2PermissionGrants "$(jq -n --arg sp "$sp_id" --arg res "$graph_sp_id" --arg scope "$SCOPES" \
    '{clientId: $sp, consentType: "AllPrincipals", resourceId: $res, scope: $scope}')" >/dev/null
  log "Consentement administrateur accordé"
else
  send patch "/oauth2PermissionGrants/${grant_id}" "$(jq -n --arg scope "$SCOPES" '{scope: $scope}')" >/dev/null
  log "Consentement administrateur existant, portée remise à : ${SCOPES}"
fi

# 4. Secret client : créé s'il n'en existe aucun, ou sur demande explicite.
# La réponse est lue en mémoire, jamais écrite dans un fichier.
secret_count="$(retry graph get "/applications/${app_object_id}" --query 'length(passwordCredentials)' -o tsv)"
if [[ "$secret_count" == "0" || "$ROTATE_SECRET" == true ]]; then
  secret="$(retry graph post "/applications/${app_object_id}/addPassword" \
    --body '{"passwordCredential": {"displayName": "render"}}' --query secretText -o tsv)"
  log "Secret client créé. À poser dans AUTH_ENTRA_CLIENT_SECRET, il ne sera plus affiché :"
  echo "$secret"
else
  log "Secret client existant conservé (--rotate-secret pour en créer un nouveau)"
fi

# 5. Fournisseur Google (client OAuth créé à la main dans la console Google Cloud)
providers_path="/identity/identityProviders"
google_id="$(lookup "$providers_path" "value[?identityProviderType=='Google'].id | [0]")"
if [[ -z "$google_id" ]]; then
  : "${GOOGLE_CLIENT_ID:?GOOGLE_CLIENT_ID est requis pour créer le fournisseur Google}"
  : "${GOOGLE_CLIENT_SECRET:?GOOGLE_CLIENT_SECRET est requis pour créer le fournisseur Google}"
  google_id="$(send post "$providers_path" "$(jq -n --arg id "$GOOGLE_CLIENT_ID" --arg secret "$GOOGLE_CLIENT_SECRET" '{
    "@odata.type": "microsoft.graph.socialIdentityProvider",
    displayName: "Google",
    identityProviderType: "Google",
    clientId: $id,
    clientSecret: $secret
  }')" --query id -o tsv)"
  rm -f "$WORKDIR/body.json"
  log "Fournisseur Google créé"
else
  log "Fournisseur Google existant (non modifié)"
fi
# Lu plutôt que supposé : l'identifiant du code par e-mail n'est pas garanti stable.
email_otp_id="$(lookup "$providers_path" "value[?identityProviderType=='EmailOTP'].id | [0]")"
if [[ -z "$email_otp_id" ]]; then
  log "Fournisseur de code par e-mail introuvable dans le tenant"
  exit 1
fi

# 6. Parcours d'inscription et de connexion, commun aux applications du tenant.
# `onAttributeCollection` est facultatif selon la documentation Graph : omis, le
# parcours ne demande rien de plus que l'adresse (à confirmer au premier lancement).
flows_path="/identity/authenticationEventsFlows"
flow_id="$(lookup "$flows_path" "value[?displayName=='${FLOW_NAME}'].id | [0]")"
if [[ -z "$flow_id" ]]; then
  flow_id="$(retry send post "$flows_path" "$(jq -n --arg name "$FLOW_NAME" --arg otp "$email_otp_id" --arg google "$google_id" '{
    "@odata.type": "#microsoft.graph.externalUsersSelfServiceSignUpEventsFlow",
    displayName: $name,
    onInteractiveAuthFlowStart: {
      "@odata.type": "#microsoft.graph.onInteractiveAuthFlowStartExternalUsersSelfServiceSignUp",
      isSignUpAllowed: true
    },
    onAuthenticationMethodLoadStart: {
      "@odata.type": "#microsoft.graph.onAuthenticationMethodLoadStartExternalUsersSelfServiceSignUp",
      identityProviders: [{id: $otp}, {id: $google}]
    }
  }')" --query id -o tsv)"
  log "Parcours d'inscription créé : ${FLOW_NAME}"
else
  log "Parcours d'inscription existant, moyens de connexion non modifiés : ${FLOW_NAME}"
fi

# 7. Application rattachée au parcours (une application n'appartient qu'à un parcours)
apps_path="${flows_path}/${flow_id}/conditions/applications/includeApplications"
linked="$(retry lookup "$apps_path" "value[?appId=='${app_id}'].appId | [0]")"
if [[ -z "$linked" ]]; then
  retry send post "$apps_path" "$(jq -n --arg app "$app_id" \
    '{"@odata.type": "#microsoft.graph.authenticationConditionApplication", appId: $app}')" >/dev/null
  log "Application rattachée au parcours"
else
  log "Application déjà rattachée au parcours"
fi

log ""
log "Réglages Render de cet environnement :"
log "  AUTH_ENTRA_TENANT_ID=${TENANT_ID}"
log "  AUTH_ENTRA_CLIENT_ID=${app_id}"
log "  AUTH_ENTRA_SUBDOMAIN=<nom du tenant, sortie subdomain du déploiement Bicep>"
log "  AUTH_ENTRA_CLIENT_SECRET=<secret affiché ci-dessus, ou celui déjà posé>"
