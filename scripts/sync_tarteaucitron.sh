#!/bin/bash
# Sync the vendored TarteAuCitron JS library (sites_conformes/static/lib/tarteaucitronjs/)
# from the npm-installed package (node_modules/tarteaucitronjs/), keeping the two in sync.
# Run `npm ci` first so node_modules matches package-lock.json.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$(dirname "${SCRIPT_DIR}")"

SRC="${REPO_ROOT}/node_modules/tarteaucitronjs/"
DEST="${REPO_ROOT}/sites_conformes/static/lib/tarteaucitronjs/"

if [ ! -d "${SRC}" ]; then
    echo "node_modules/tarteaucitronjs not found. Run 'npm ci' first." 1>&2
    exit 1
fi

extract_version() {
    grep -m1 '"version"' "$1" 2>/dev/null | sed -E 's/.*"version": *"([^"]+)".*/\1/'
}

OLD_VERSION="$(extract_version "${DEST}package.json")"
NEW_VERSION="$(extract_version "${SRC}package.json")"

rsync -a --delete "${SRC}" "${DEST}"

if [ "${OLD_VERSION}" = "${NEW_VERSION}" ]; then
    echo "✅ Vendored tarteaucitronjs already up to date (${NEW_VERSION})."
else
    echo "✅ Vendored tarteaucitronjs updated: ${OLD_VERSION:-absente} → ${NEW_VERSION}."
fi
