#!/usr/bin/env bash
# Attend que le déploiement Render d'un commit soit en ligne (#921).
#
# Le deploy hook ne fait que mettre un déploiement en file : sans cette attente,
# un build ou un démarrage en échec passait inaperçu, et Vercel publiait le front
# devant un backend resté sur l'ancienne version.
#
# Entrées (environnement) :
#   DEPLOY_HOOK      hook du service, d'où l'on extrait l'ID `srv-…` (masqué)
#   RENDER_API_KEY   jeton de l'API Render
#   COMMIT_SHA       commit passé au hook par `&ref=`
#   EXPECTED_VERSION version que `/api/v1/version` doit rendre une fois en ligne
#   WAIT_SECONDS     délai maximal (défaut : 900)
#   POLL_SECONDS     intervalle d'interrogation (défaut : 15)
set -euo pipefail

: "${DEPLOY_HOOK:?}" "${RENDER_API_KEY:?}" "${COMMIT_SHA:?}" "${EXPECTED_VERSION:?}"
wait_seconds="${WAIT_SECONDS:-900}"
poll_seconds="${POLL_SECONDS:-15}"

service_id=$(printf '%s' "$DEPLOY_HOOK" | sed -n 's#.*/deploy/\(srv-[^/?]*\).*#\1#p')
[ -n "$service_id" ] || { echo "::error::ID de service introuvable dans le deploy hook"; exit 1; }
echo "::add-mask::$service_id"

render_api() {
  curl -sS --fail-with-body \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    --retry 3 --retry-connrefused --retry-delay 5 --max-time 60 "$@"
}

deadline=$(( $(date +%s) + wait_seconds ))
deploy_id=""
while :; do
  # Le déploiement de *ce* commit, pas le dernier de la liste : un autre peut
  # l'avoir précédé ou suivi dans la file.
  deploy=$(render_api "https://api.render.com/v1/services/$service_id/deploys?limit=20" \
    | jq -c --arg sha "$COMMIT_SHA" \
        '[.[].deploy | select(.commit.id == $sha)] | .[0] // empty')
  if [ -n "$deploy" ]; then
    deploy_id=$(jq -r '.id' <<<"$deploy")
    status=$(jq -r '.status' <<<"$deploy")
    echo "Déploiement Render : $status"
    case "$status" in
      live) break ;;
      build_failed | update_failed | pre_deploy_failed | canceled | deactivated)
        echo "::error::Le déploiement Render a échoué ($status) : le front n'est pas publié."
        exit 1
        ;;
    esac
  else
    echo "Déploiement Render du commit pas encore visible."
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "::error::Déploiement Render${deploy_id:+ $deploy_id} toujours pas en ligne après ${wait_seconds} s."
    exit 1
  fi
  sleep "$poll_seconds"
done

# `live` dit que Render a basculé, pas que c'est bien la version poussée qui
# répond : `APP_VERSION` est lue au démarrage (#162).
backend_url=$(render_api "https://api.render.com/v1/services/$service_id" | jq -r '.serviceDetails.url // empty')
[ -n "$backend_url" ] || { echo "::error::URL du service introuvable dans l'API Render"; exit 1; }
served=$(curl -sS --fail-with-body --retry 5 --retry-all-errors --retry-delay 10 --max-time 60 \
  "$backend_url/api/v1/version" | jq -r '.version // empty')
if [ "$served" != "$EXPECTED_VERSION" ]; then
  echo "::error::Le backend répond la version « $served », « $EXPECTED_VERSION » attendue."
  exit 1
fi
echo "Backend en ligne, version $served."
