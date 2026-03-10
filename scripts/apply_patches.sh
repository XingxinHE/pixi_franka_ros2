#!/usr/bin/env bash

# Apply tracked patch files by copying them over existing upstream files.
# This script is strict on purpose: every patch file must map to an existing target file.

set -euo pipefail

PATCHES_DIR="patches"
SRC_DIR="src"

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

patch_count=0

for repo in "${PATCHES_DIR}"/*; do
  [ -d "${repo}" ] || continue

  repo_name="$(basename "${repo}")"
  target_dir="${SRC_DIR}/${repo_name}"

  if [ ! -d "${target_dir}" ]; then
    echo -e "${RED}Error: Target repository ${target_dir}/ not found${NC}"
    exit 1
  fi

  echo -e "${GREEN}Processing ${repo_name}...${NC}"

  while IFS= read -r -d '' file; do
    relative_path="${file#${repo}/}"
    target_file="${target_dir}/${relative_path}"

    if [ ! -f "${target_file}" ]; then
      echo -e "${RED}Error: Missing target file for patch: ${target_file}${NC}"
      exit 1
    fi

    cp "${file}" "${target_file}"
    patch_count=$((patch_count + 1))
    echo "  Copied: ${relative_path}"
  done < <(find "${repo}" -type f -print0 | sort -z)
done

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Patches applied successfully! Files copied: ${patch_count}${NC}"
