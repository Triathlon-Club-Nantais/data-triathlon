#!/usr/bin/env bash
# Configure le tenant externe Entra External ID du club (#1323) par Microsoft
# Graph v1.0 : application, principal de service, consentement, secret client,
# fournisseur Google, parcours d'inscription. Idempotent : chaque objet est lu
# avant d'être créé, et une relance ne crée rien de plus.
#
# Usage :
#   az login --tenant <tenantId> --allow-no-subscriptions
#   REDIRECT_URI="https://.../api/v1/auth/entra/callback [autre URI ...]" \
#   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... \
#   ./configure-tenant.sh <tenantId> [--rotate-secret]
#
# Le secret client est affiché une seule fois sur la sortie standard et n'est
# jamais écrit sur disque. Procédure complète : AGENTS.md du dossier.
set -euo pipefail

GRAPH="https://graph.microsoft.com/v1.0"
GRAPH_APP_ID="00000003-0000-0000-c000-000000000000"
APP_NAME="${APP_NAME:-data-triathlon}"
FLOW_NAME="${FLOW_NAME:-data-triathlon connexion}"
SCOPES="openid profile email offline_access"

usage() {
  echo "Usage : REDIRECT_URI=... $0 <tenantId> [--rotate-secret]" >&2
  exit 2
}

[[ $# -ge 1 ]] || usage
TENANT_ID="$1"
ROTATE_SECRET=false
if [[ $# -ge 2 ]]; then
  [[ "$2" == "--rotate-secret" ]] || usage
  ROTATE_SECRET=true
fi
: "${REDIRECT_URI:?REDIRECT_URI est requis (une ou plusieurs URI séparées par des espaces)}"

log() { echo "$*" >&2; }

graph() {
  # graph <méthode> <chemin> [arguments az rest supplémentaires]
  local method="$1" path="$2"
  shift 2
  az rest --method "$method" --url "${GRAPH}${path}" "$@"
}

# lookup <chemin> <requête JMESPath> [arguments az rest] : valeur, ou vide si absente.
lookup() {
  local path="$1" query="$2" value
  shift 2
  value="$(graph get "$path" --query "$query" -o tsv "$@")"
  [[ "$value" == "None" ]] && value=""
  echo "$value"
}

current_tenant="$(az account show --query tenantId -o tsv 2>/dev/null || true)"
if [[ "$current_tenant" != "$TENANT_ID" ]]; then
  log "Session az hors du tenant $TENANT_ID. Lancer d'abord :"
  log "  az login --tenant $TENANT_ID --allow-no-subscriptions"
  exit 1
fi

redirect_json=""
for uri in $REDIRECT_URI; do
  redirect_json+="${redirect_json:+,}\"${uri}\""
done

# Identifiants des permissions déléguées de Microsoft Graph, fixes pour tous les tenants.
app_body=$(cat <<JSON
{
  "displayName": "${APP_NAME}",
  "signInAudience": "AzureADMyOrg",
  "web": {"redirectUris": [${redirect_json}]},
  "optionalClaims": {"idToken": [
    {"name": "email", "essential": false},
    {"name": "xms_edov", "essential": false}
  ]},
  "requiredResourceAccess": [{
    "resourceAppId": "${GRAPH_APP_ID}",
    "resourceAccess": [
      {"id": "37f7f235-527c-4136-accd-4a02d197296e", "type": "Scope"},
      {"id": "14dad69e-099b-42c9-810b-d002981feec1", "type": "Scope"},
      {"id": "64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0", "type": "Scope"},
      {"id": "7427e0e9-2fba-42fe-b0c0-848c9e6a8182", "type": "Scope"}
    ]
  }]
}
JSON
)

# 1. Application
app_object_id="$(lookup /applications 'value[0].id' --url-parameters "\$filter=displayName eq '${APP_NAME}'")"
if [[ -z "$app_object_id" ]]; then
  app_object_id="$(graph post /applications --body "$app_body" --query id -o tsv)"
  log "Application créée : ${APP_NAME}"
else
  graph patch "/applications/${app_object_id}" --body "$app_body" >/dev/null
  log "Application existante mise à jour : ${APP_NAME}"
fi
app_id="$(graph get "/applications/${app_object_id}" --query appId -o tsv)"

# 2. Principal de service, sans lequel le parcours d'inscription refuse l'application
sp_id="$(lookup /servicePrincipals 'value[0].id' --url-parameters "\$filter=appId eq '${app_id}'")"
if [[ -z "$sp_id" ]]; then
  sp_id="$(graph post /servicePrincipals --body "{\"appId\": \"${app_id}\"}" --query id -o tsv)"
  log "Principal de service créé"
else
  log "Principal de service existant"
fi

# 3. Consentement administrateur aux permissions déléguées
graph_sp_id="$(lookup /servicePrincipals 'value[0].id' --url-parameters "\$filter=appId eq '${GRAPH_APP_ID}'")"
grant_id="$(lookup /oauth2PermissionGrants 'value[0].id' \
  --url-parameters "\$filter=clientId eq '${sp_id}' and resourceId eq '${graph_sp_id}' and consentType eq 'AllPrincipals'")"
if [[ -z "$grant_id" ]]; then
  graph post /oauth2PermissionGrants --body "{\"clientId\": \"${sp_id}\", \"consentType\": \"AllPrincipals\", \"resourceId\": \"${graph_sp_id}\", \"scope\": \"${SCOPES}\"}" >/dev/null
  log "Consentement administrateur accordé"
else
  graph patch "/oauth2PermissionGrants/${grant_id}" --body "{\"scope\": \"${SCOPES}\"}" >/dev/null
  log "Consentement administrateur existant"
fi

# 4. Secret client : créé s'il n'en existe aucun, ou sur demande explicite
secret_count="$(graph get "/applications/${app_object_id}" --query 'length(passwordCredentials)' -o tsv)"
if [[ "$secret_count" == "0" || "$ROTATE_SECRET" == true ]]; then
  secret="$(graph post "/applications/${app_object_id}/addPassword" \
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
  google_id="$(graph post "$providers_path" --body "{\"@odata.type\": \"microsoft.graph.socialIdentityProvider\", \"displayName\": \"Google\", \"identityProviderType\": \"Google\", \"clientId\": \"${GOOGLE_CLIENT_ID}\", \"clientSecret\": \"${GOOGLE_CLIENT_SECRET}\"}" --query id -o tsv)"
  log "Fournisseur Google créé"
else
  log "Fournisseur Google existant"
fi
# Lu plutôt que supposé : l'identifiant du code par e-mail n'est pas garanti stable.
email_otp_id="$(lookup "$providers_path" "value[?identityProviderType=='EmailOTP'].id | [0]")"
if [[ -z "$email_otp_id" ]]; then
  log "Fournisseur de code par e-mail introuvable dans le tenant"
  exit 1
fi

# 6. Parcours d'inscription et de connexion : code par e-mail et Google
flows_path="/identity/authenticationEventsFlows"
flow_id="$(lookup "$flows_path" "value[?displayName=='${FLOW_NAME}'].id | [0]")"
if [[ -z "$flow_id" ]]; then
  flow_id="$(graph post "$flows_path" --body "$(cat <<JSON
{
  "@odata.type": "#microsoft.graph.externalUsersSelfServiceSignUpEventsFlow",
  "displayName": "${FLOW_NAME}",
  "onInteractiveAuthFlowStart": {
    "@odata.type": "#microsoft.graph.onInteractiveAuthFlowStartExternalUsersSelfServiceSignUp",
    "isSignUpAllowed": true
  },
  "onAuthenticationMethodLoadStart": {
    "@odata.type": "#microsoft.graph.onAuthenticationMethodLoadStartExternalUsersSelfServiceSignUp",
    "identityProviders": [{"id": "${email_otp_id}"}, {"id": "${google_id}"}]
  }
}
JSON
)" --query id -o tsv)"
  log "Parcours d'inscription créé : ${FLOW_NAME}"
else
  log "Parcours d'inscription existant : ${FLOW_NAME}"
fi

# 7. Application rattachée au parcours (une application n'appartient qu'à un parcours)
apps_path="${flows_path}/${flow_id}/conditions/applications/includeApplications"
linked="$(lookup "$apps_path" "value[?appId=='${app_id}'].appId | [0]")"
if [[ -z "$linked" ]]; then
  graph post "$apps_path" --body "{\"@odata.type\": \"#microsoft.graph.authenticationConditionApplication\", \"appId\": \"${app_id}\"}" >/dev/null
  log "Application rattachée au parcours"
else
  log "Application déjà rattachée au parcours"
fi

log ""
log "Réglages Render :"
log "  AUTH_ENTRA_TENANT_ID=${TENANT_ID}"
log "  AUTH_ENTRA_CLIENT_ID=${app_id}"
log "  AUTH_ENTRA_SUBDOMAIN=<nom du tenant, sortie subdomain du déploiement Bicep>"
log "  AUTH_ENTRA_CLIENT_SECRET=<secret affiché ci-dessus, ou celui déjà posé>"
