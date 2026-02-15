#!/usr/bin/env bash
# List all projects in the knowledge hub with status summary.
#
# Usage: list-projects.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECTS_DIR="$REPO_ROOT/projects"

# Check if projects directory has any entries
shopt -s nullglob
projects=("$PROJECTS_DIR"/*/)
shopt -u nullglob

if [ ${#projects[@]} -eq 0 ]; then
    echo "No projects found."
    echo "Run: bash scripts/init-project.sh <project-name>"
    exit 0
fi

echo "Projects in knowledge hub:"
echo "=========================="
echo ""

for project_path in "${projects[@]}"; do
    name="$(basename "$project_path")"

    # --- Page count and access from sources.yaml ---
    page_count=0
    access="n/a"
    if [ -f "$project_path/sources.yaml" ]; then
        # Use inline Python to parse YAML properly
        eval "$(python3 -c "
import yaml, sys
with open('$project_path/sources.yaml') as f:
    data = yaml.safe_load(f) or {}
pages = data.get('pages', [])
print(f'page_count={len(pages)}')
if pages:
    modes = set(p.get('access', 'read-only') for p in pages)
    print(f'access={\"mixed\" if len(modes) > 1 else modes.pop()}')
else:
    print('access=n/a')
" 2>/dev/null)" || {
            page_count=$(grep -c 'page_id:' "$project_path/sources.yaml" 2>/dev/null || echo "0")
            access="unknown"
        }
    fi

    # --- Last sync time from .sync-metadata.json ---
    last_sync="never"
    if [ -f "$project_path/.sync-metadata.json" ]; then
        latest="$(python3 -c "
import json, sys
with open('$project_path/.sync-metadata.json') as f:
    data = json.load(f)
if data:
    times = [v.get('synced_at', '') for v in data.values() if isinstance(v, dict)]
    times = [t for t in times if t]
    if times:
        print(max(times))
    else:
        print('never')
else:
    print('never')
" 2>/dev/null)" || latest="unknown"
        if [ -n "$latest" ]; then
            last_sync="$latest"
        fi
    fi

    # --- File counts ---
    confluence_files=0
    notes_files=0
    email_files=0

    if [ -d "$project_path/confluence" ]; then
        confluence_files=$(find "$project_path/confluence" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    fi
    if [ -d "$project_path/notes" ]; then
        notes_files=$(find "$project_path/notes" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    fi
    if [ -d "$project_path/emails" ]; then
        email_files=$(find "$project_path/emails" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    fi

    # --- Output ---
    echo "  $name"
    echo "    Pages: $page_count ($access)"
    echo "    Last sync: $last_sync"
    echo "    Files: $confluence_files confluence, $notes_files notes, $email_files emails"
    echo ""
done
