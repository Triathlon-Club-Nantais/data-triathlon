#!/usr/bin/env bash
# Tests de ci-ok.sh : chaque cas fixe l'environnement et vérifie le code de sortie.
set -u
here=$(dirname "$0")
failures=0
ALL="backend=success backend-postgres=success frontend=success frontend-test=success"
FILTERED="backend backend-postgres frontend frontend-test"
ALL_SKIPPED="backend=skipped backend-postgres=skipped frontend=skipped frontend-test=skipped"

# BACKEND_CHANGED et FRONTEND_CHANGED valent `false` par défaut (PR sans changement de l'app).
check() { # nom code_attendu event changes results filtered
  EVENT_NAME=$3 CHANGES_RESULT=$4 RESULTS=$5 FILTERED_JOBS=$6 \
    BACKEND_CHANGED=${BACKEND_CHANGED:-false} FRONTEND_CHANGED=${FRONTEND_CHANGED:-false} bash "$here/ci-ok.sh" >/dev/null 2>&1
  code=$?
  if [ "$code" = "$2" ]; then echo "ok   $1"; else echo "FAIL $1 (attendu $2, obtenu $code)"; failures=$((failures + 1)); fi
}

BACKEND_CHANGED=true FRONTEND_CHANGED=true check pr_all_success_passes 0 pull_request success "$ALL" "$FILTERED"
FRONTEND_CHANGED=true check pr_filtered_skip_passes 0 pull_request success \
  "backend=skipped backend-postgres=skipped frontend=success frontend-test=success" "$FILTERED"
BACKEND_CHANGED=false FRONTEND_CHANGED=true check pr_unfiltered_skip_fails 1 pull_request success \
  "backend=success backend-postgres=skipped frontend=success frontend-test=success" "backend frontend frontend-test"
check changes_failure_fails 1 pull_request failure "$ALL_SKIPPED" "$FILTERED"
check changes_cancelled_fails 1 pull_request cancelled "$ALL_SKIPPED" "$FILTERED"
check merge_group_skip_fails 1 merge_group success \
  "backend=success backend-postgres=skipped frontend=success frontend-test=success" "$FILTERED"
check any_failure_fails 1 pull_request success \
  "backend=success backend-postgres=success frontend=success frontend-test=failure" "$FILTERED"
check workflow_dispatch_skip_fails 1 workflow_dispatch success \
  "backend=skipped backend-postgres=success frontend=success frontend-test=success" "$FILTERED"
BACKEND_CHANGED=true check pr_skip_with_changed_app_fails 1 pull_request success \
  "backend=skipped backend-postgres=success frontend=success frontend-test=success" "$FILTERED"
check empty_results_fails 1 pull_request success "" "$FILTERED"

exit $((failures > 0))
