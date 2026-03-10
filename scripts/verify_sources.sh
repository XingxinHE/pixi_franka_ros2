#!/usr/bin/env bash

set -euo pipefail

repos=(
  "src/franka_ros2 v2.2.0"
  "src/libfranka 0.19.0"
  "src/franka_description 1.3.0"
  "src/crisp_controllers v2.1.0"
)

fail_count=0

echo "Verifying pinned source versions"
echo "==============================="

for entry in "${repos[@]}"; do
  repo_path="${entry%% *}"
  expected_tag="${entry##* }"

  if [ ! -d "${repo_path}/.git" ]; then
    echo "[verify] ERROR ${repo_path} is missing or not a git repository"
    fail_count=$((fail_count + 1))
    continue
  fi

  actual_tag="$(git -C "${repo_path}" describe --tags --exact-match 2>/dev/null || true)"
  current_sha="$(git -C "${repo_path}" rev-parse HEAD)"

  if [ -z "${actual_tag}" ]; then
    echo "[verify] ERROR ${repo_path} is not at an exact tag (sha=${current_sha})"
    fail_count=$((fail_count + 1))
    continue
  fi

  if [ "${actual_tag}" != "${expected_tag}" ]; then
    echo "[verify] ERROR ${repo_path} expected tag ${expected_tag}, found ${actual_tag} (sha=${current_sha})"
    fail_count=$((fail_count + 1))
    continue
  fi

  echo "[verify] OK ${repo_path} tag=${actual_tag} sha=${current_sha}"
done

if [ "${fail_count}" -ne 0 ]; then
  echo "Verification failed with ${fail_count} mismatch(es)."
  exit 1
fi

echo "All source repositories match pinned tags."
