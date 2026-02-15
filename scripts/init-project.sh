#!/usr/bin/env bash
# Initialize a new project in the knowledge hub.
#
# Usage: init-project.sh <project-name>
#
# Creates the project directory structure, templates, and updates PROJECT-INDEX.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECTS_DIR="$REPO_ROOT/projects"

# --- Helpers ---

die() {
    echo "ERROR: $1" >&2
    exit 1
}

usage() {
    echo "Usage: $(basename "$0") <project-name>"
    echo ""
    echo "Creates a new project with the standard directory structure."
    echo "Project name must be kebab-case (lowercase letters, numbers, hyphens)."
    exit 1
}

# --- Validation ---

if [ $# -ne 1 ]; then
    usage
fi

PROJECT_NAME="$1"

# Validate kebab-case
if ! echo "$PROJECT_NAME" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
    die "Project name must be kebab-case: lowercase letters, numbers, and hyphens (e.g., 'my-project')."
fi

PROJECT_DIR="$PROJECTS_DIR/$PROJECT_NAME"

if [ -d "$PROJECT_DIR" ]; then
    die "Project '$PROJECT_NAME' already exists at $PROJECT_DIR"
fi

# --- Create structure ---

echo "Creating project: $PROJECT_NAME"

mkdir -p "$PROJECT_DIR/confluence/assets"
mkdir -p "$PROJECT_DIR/notes"
mkdir -p "$PROJECT_DIR/emails"

# --- Write PROJECT.md ---

cat > "$PROJECT_DIR/PROJECT.md" << EOF
# $PROJECT_NAME

## Overview

<!-- Brief description of this project -->

## Key Contacts

<!-- List key people and their roles -->

## Quick Links

<!-- Links to relevant repos, dashboards, etc. -->
EOF

# --- Write sources.yaml ---

cat > "$PROJECT_DIR/sources.yaml" << 'YAMLEOF'
# Confluence pages to sync for this project.
#
# Each page entry has:
#   name:        Friendly name used with --page flag
#   page_id:     Confluence page ID (from the URL)
#   local_path:  Where to store the synced markdown (relative to project dir)
#   access:      "read-only" (default) or "read-write"
#   sync_children: true (default) or false
#   sync_attachments: true (default) or false
#
# Example:
#   pages:
#     - name: architecture
#       page_id: "12345678"
#       local_path: confluence/architecture.md
#       access: read-only
#       sync_children: true

pages: []
YAMLEOF

# --- Write empty sync metadata ---

echo '{}' > "$PROJECT_DIR/.sync-metadata.json"

# --- Regenerate PROJECT-INDEX.md ---

regenerate_index() {
    local index_file="$REPO_ROOT/PROJECT-INDEX.md"
    local has_projects=false

    cat > "$index_file" << 'HEADER'
# Project Index

HEADER

    # Use nullglob to handle empty directories safely
    shopt -s nullglob

    for project_path in "$PROJECTS_DIR"/*/; do
        has_projects=true
        local name
        name="$(basename "$project_path")"

        # Read first non-empty, non-heading line from PROJECT.md as description
        local description="No description"
        if [ -f "$project_path/PROJECT.md" ]; then
            local line
            while IFS= read -r line; do
                # Skip empty lines and headings
                if [ -n "$line" ] && ! echo "$line" | grep -qE '^\s*#'; then
                    # Strip HTML comments
                    line="$(echo "$line" | sed 's/<!--.*-->//')"
                    if [ -n "$(echo "$line" | tr -d '[:space:]')" ]; then
                        description="$line"
                        break
                    fi
                fi
            done < "$project_path/PROJECT.md"
        fi

        # Count pages in sources.yaml
        local page_count=0
        if [ -f "$project_path/sources.yaml" ]; then
            page_count=$(grep -c '^[[:space:]]*page_id:' "$project_path/sources.yaml" 2>/dev/null) || page_count=0
        fi

        echo "## [$name](projects/$name/PROJECT.md)" >> "$index_file"
        echo "" >> "$index_file"
        echo "$description" >> "$index_file"
        echo "" >> "$index_file"
        echo "- **Confluence pages:** $page_count" >> "$index_file"
        echo "" >> "$index_file"
    done

    shopt -u nullglob

    if [ "$has_projects" = false ]; then
        echo "No projects yet. Run \`bash scripts/init-project.sh <project-name>\` to create one." >> "$index_file"
    fi
}

regenerate_index

# --- Done ---

echo ""
echo "Project '$PROJECT_NAME' created at: $PROJECT_DIR"
echo ""
echo "Next steps:"
echo "  1. Edit projects/$PROJECT_NAME/PROJECT.md with project details"
echo "  2. Add Confluence pages to projects/$PROJECT_NAME/sources.yaml"
echo "  3. Run: python scripts/confluence-sync.py --project $PROJECT_NAME"
