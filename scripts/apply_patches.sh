#!/usr/bin/env bash

# Apply tracked patch files by copying them over pinned upstream files.
# Existing targets remain strict. A target may be created only when its full
# repository-relative path is explicitly listed in the tracked manifest.

set -euo pipefail

PATCHES_DIR="patches"
SRC_DIR="src"
NEW_FILES_MANIFEST="${PATCHES_DIR}/new-files.manifest"

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Applying patches from ${PATCHES_DIR}/ to ${SRC_DIR}/"
echo "================================================"

if [ ! -d "${PATCHES_DIR}" ]; then
  echo -e "${RED}Error: ${PATCHES_DIR}/ directory not found${NC}"
  exit 1
fi

if [ ! -d "${SRC_DIR}" ]; then
  echo -e "${RED}Error: ${SRC_DIR}/ directory not found${NC}"
  exit 1
fi

if [ ! -f "${NEW_FILES_MANIFEST}" ]; then
  echo -e "${RED}Error: New-file manifest not found: ${NEW_FILES_MANIFEST}${NC}"
  exit 1
fi

declare -A allowed_new_files=()
while IFS= read -r manifest_path || [ -n "${manifest_path}" ]; do
  [ -n "${manifest_path}" ] || continue

  if [[
    "${manifest_path}" == /* ||
    "${manifest_path}" == "." ||
    "${manifest_path}" == ".." ||
    "${manifest_path}" == ./* ||
    "${manifest_path}" == ../* ||
    "${manifest_path}" == *"/./"* ||
    "${manifest_path}" == *"/../"* ||
    "${manifest_path}" == *"/." ||
    "${manifest_path}" == *"/.."
  ]]; then
    echo -e "${RED}Error: Invalid new-file manifest path: ${manifest_path}${NC}"
    exit 1
  fi

  if [[ ! "${manifest_path}" =~ ^[A-Za-z0-9._+-]+(/[A-Za-z0-9._+-]+)+$ ]]; then
    echo -e "${RED}Error: Invalid new-file manifest path: ${manifest_path}${NC}"
    exit 1
  fi

  if [ -n "${allowed_new_files[${manifest_path}]+x}" ]; then
    echo -e "${RED}Error: Duplicate new-file manifest path: ${manifest_path}${NC}"
    exit 1
  fi

  patch_file="${PATCHES_DIR}/${manifest_path}"
  if [ ! -f "${patch_file}" ] || [ -L "${patch_file}" ]; then
    echo -e "${RED}Error: Manifested new file has no regular patch snapshot: ${patch_file}${NC}"
    exit 1
  fi

  allowed_new_files["${manifest_path}"]=1
done < "${NEW_FILES_MANIFEST}"

declare -a patch_sources=()
declare -a patch_targets=()
declare -a patch_relative_paths=()
declare -a patch_creates=()

for repo in "${PATCHES_DIR}"/*; do
  [ -d "${repo}" ] || continue

  repo_name="$(basename "${repo}")"
  target_dir="${SRC_DIR}/${repo_name}"

  if [ -L "${repo}" ]; then
    echo -e "${RED}Error: Patch repository may not be a symlink: ${repo}${NC}"
    exit 1
  fi

  if [ ! -d "${target_dir}" ] || [ -L "${target_dir}" ]; then
    echo -e "${RED}Error: Target repository ${target_dir}/ not found${NC}"
    exit 1
  fi

  while IFS= read -r -d '' file; do
    relative_path="${file#${repo}/}"
    target_file="${target_dir}/${relative_path}"
    manifest_path="${repo_name}/${relative_path}"
    target_parent="$(dirname "${target_file}")"

    current_dir="${target_dir}"
    relative_parent="$(dirname "${relative_path}")"
    if [ "${relative_parent}" != "." ]; then
      IFS='/' read -r -a parent_components <<< "${relative_parent}"
      for component in "${parent_components[@]}"; do
        current_dir="${current_dir}/${component}"
        if [ -L "${current_dir}" ]; then
          echo -e "${RED}Error: Patch target parent may not be a symlink: ${current_dir}${NC}"
          exit 1
        fi
      done
    fi

    if [ -e "${target_file}" ] || [ -L "${target_file}" ]; then
      if [ ! -f "${target_file}" ] || [ -L "${target_file}" ]; then
        echo -e "${RED}Error: Patch target is not a regular file: ${target_file}${NC}"
        exit 1
      fi
      creates_target=0
    else
      if [ -z "${allowed_new_files[${manifest_path}]+x}" ]; then
        echo -e "${RED}Error: Missing target file for unmanifested patch: ${target_file}${NC}"
        exit 1
      fi
      if [ ! -d "${target_parent}" ]; then
        echo -e "${RED}Error: Parent directory for manifested new file is missing: ${target_file}${NC}"
        exit 1
      fi
      creates_target=1
    fi

    patch_sources+=("${file}")
    patch_targets+=("${target_file}")
    patch_relative_paths+=("${repo_name}/${relative_path}")
    patch_creates+=("${creates_target}")
  done < <(find "${repo}" -type f -print0 | sort -z)
done

patch_count=${#patch_sources[@]}
created_count=0

for index in "${!patch_sources[@]}"; do
  cp -- "${patch_sources[${index}]}" "${patch_targets[${index}]}"
  created_count=$((created_count + patch_creates[index]))
  echo "  Copied: ${patch_relative_paths[${index}]}"
done

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Patches applied successfully! Files copied: ${patch_count}; created: ${created_count}${NC}"
