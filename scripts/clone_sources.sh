#!/usr/bin/env bash

set -euo pipefail

clone_or_checkout_tag() {
  local repo_path="$1"
  local repo_url="$2"
  local repo_tag="$3"
  local recurse_submodules="${4:-false}"

  if [ -d "${repo_path}/.git" ]; then
    if git -C "${repo_path}" rev-parse -q --verify "refs/tags/${repo_tag}" >/dev/null; then
      echo "[clone] ${repo_path} exists, required tag ${repo_tag} already available locally"
    else
      echo "[clone] ${repo_path} exists, fetching missing tag ${repo_tag}"
      git -C "${repo_path}" fetch --tags --force origin
    fi
    git -C "${repo_path}" checkout --detach "${repo_tag}"
  elif [ -e "${repo_path}" ]; then
    echo "[clone] Error: ${repo_path} exists but is not a git repository"
    exit 1
  else
    echo "[clone] Cloning ${repo_url} at ${repo_tag} into ${repo_path}"
    if [ "${recurse_submodules}" = "true" ]; then
      git clone --branch "${repo_tag}" --recurse-submodules "${repo_url}" "${repo_path}"
    else
      git clone --branch "${repo_tag}" "${repo_url}" "${repo_path}"
    fi
  fi

  echo "[clone] ${repo_path} -> tag=$(git -C "${repo_path}" describe --tags --exact-match) sha=$(git -C "${repo_path}" rev-parse HEAD)"
}

clone_or_checkout_tag "src/franka_ros2" "https://github.com/frankarobotics/franka_ros2.git" "v2.2.0"
clone_or_checkout_tag "src/franka_description" "https://github.com/frankarobotics/franka_description.git" "1.3.0"
clone_or_checkout_tag "src/libfranka" "https://github.com/frankarobotics/libfranka.git" "0.19.0" "true"
clone_or_checkout_tag "src/crisp_controllers" "https://github.com/utiasdsl/crisp_controllers.git" "v2.1.0"
