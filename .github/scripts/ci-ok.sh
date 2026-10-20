#!/usr/bin/env bash
# Décision du check requis `ci-ok` (#1705).
#
# Entrées (environnement) :
#   EVENT_NAME       github.event_name
#   CHANGES_RESULT   résultat du job `changes`
#   RESULTS          paires `job=résultat` séparées par des espaces
#   FILTERED_JOBS    jobs pouvant être `skipped` par le filtre de chemins
#
# `skipped` n'est toléré que sur `pull_request`, et seulement pour les jobs filtrés.
# Tout autre événement (merge_group, workflow_dispatch, workflow_call de deploy.yml)
# exige `success` partout : la merge queue et les déploiements exécutent tout.
set -euo pipefail

: "${EVENT_NAME:?}" "${CHANGES_RESULT:?}"
echo "Événement : $EVENT_NAME, changes : $CHANGES_RESULT"
echo "Résultats : ${RESULTS:-}"

[ "$CHANGES_RESULT" = "success" ] || { echo "::error::changes n'a pas réussi"; exit 1; }

for pair in ${RESULTS:-}; do
  job=${pair%%=*}
  result=${pair#*=}
  [ "$result" = "success" ] && continue
  if [ "$result" = "skipped" ] && [ "$EVENT_NAME" = "pull_request" ] \
    && [[ " ${FILTERED_JOBS:-} " == *" $job "* ]]; then
    continue
  fi
  echo "::error::$job : $result"
  exit 1
done
