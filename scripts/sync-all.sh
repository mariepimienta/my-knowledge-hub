#!/usr/bin/env bash
# Sync all Confluence pages across all projects.
#
# Usage: sync-all.sh [--force]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/confluence-sync.py" --all "$@"
