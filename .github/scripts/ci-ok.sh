#!/usr/bin/env bash
# Décision du check requis `ci-ok` (#1705).
#
# Entrées (environnement) :
#   EVENT_NAME       github.event_name
#   CHANGES_RESULT   résultat du job `changes`
#   RESULTS          paires `job=résultat` séparées par des espaces
#   FILTERED_JOBS    jobs pouvant être `skipped` par le filtre de chemins
#   BACKEND_CHANGED  sortie `backend` de `changes` (`true`/`false`)
#   FRONTEND_CHANGED sortie `frontend` de `changes` (`true`/`false`)
#
# `skipped` n'est toléré que sur `pull_request`, pour un job filtré dont
# l'application n'a pas changé. L'application se déduit du préfixe du nom du job
# (`backend*`, `frontend*`) : un job sauté alors que son application a changé
# (faute de frappe dans un `if:`) fait échouer le check.
# Tout autre événement (merge_group, workflow_dispatch, workflow_call de deploy.yml)
# exige `success` partout : la merge queue et les déploiements exécutent tout.
set -euo pipefail

: "${EVENT_NAME:?}" "${CHANGES_RESULT:?}" "${RESULTS:?}" "${BACKEND_CHANGED:?}" "${FRONTEND_CHANGED:?}"
echo "Événement : $EVENT_NAME, changes : $CHANGES_RESULT"
echo "Résultats : $RESULTS"

[ "$CHANGES_RESULT" = "success" ] || { echo "::error::changes n'a pas réussi"; exit 1; }

for pair in $RESULTS; do
  job=${pair%%=*}
  result=${pair#*=}
  [ "$result" = "success" ] && continue
  case $job in
    backend*) changed=$BACKEND_CHANGED ;;
    frontend*) changed=$FRONTEND_CHANGED ;;
    *) changed=true ;;
  esac
  if [ "$result" = "skipped" ] && [ "$EVENT_NAME" = "pull_request" ] && [ "$changed" = "false" ] \
    && [[ " ${FILTERED_JOBS:-} " == *" $job "* ]]; then
    continue
  fi
  echo "::error::$job : $result"
  exit 1
done
