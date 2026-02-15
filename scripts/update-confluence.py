#!/usr/bin/env python3
"""Push local markdown content to a Confluence page.

Usage:
    python update-confluence.py --project <name> --page <page-name> --file <path>
    python update-confluence.py --project <name> --page <page-name> --stdin

Converts markdown to HTML and updates the specified Confluence page, then
re-syncs the page locally.
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts/ to sys.path so `from lib import ...` works from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.config import (
    get_repo_root,
    load_project_sources,
    read_sync_metadata,
    resolve_confluence_env,
    write_sync_metadata,
)
from lib.confluence_client import (
    ConfluenceClient,
    ConfluenceAPIError,
    html_to_markdown,
    markdown_to_html,
)


def slugify(title):
    """Convert a page title to a filesystem-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def main():
    parser = argparse.ArgumentParser(
        description="Push local markdown to a Confluence page."
    )
    parser.add_argument(
        "--project", required=True,
        help="Project name (must match a directory under projects/)"
    )
    parser.add_argument(
        "--page", required=True,
        help="Page name (as defined in sources.yaml)"
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file",
        help="Path to the markdown file to push"
    )
    input_group.add_argument(
        "--stdin", action="store_true",
        help="Read markdown content from stdin"
    )

    args = parser.parse_args()

    # Load configs
    try:
        sources = load_project_sources(args.project)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Find the page config
    page_config = None
    for p in sources.get("pages", []):
        if p.get("name") == args.page:
            page_config = p
            break

    if page_config is None:
        print(f"ERROR: Page '{args.page}' not found in sources.yaml for project '{args.project}'",
              file=sys.stderr)
        sys.exit(1)

    # Check access level
    access = page_config.get("access", "read-only")
    if access == "read-only":
        print(
            f"ERROR: Page '{args.page}' is configured as read-only. "
            f"Change 'access' to 'read-write' in sources.yaml to enable updates.",
            file=sys.stderr
        )
        sys.exit(1)

    page_id = page_config["page_id"]

    # Resolve Confluence credentials
    try:
        env = resolve_confluence_env()
    except EnvironmentError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Read content
    if args.stdin:
        content = sys.stdin.read()
    else:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ERROR: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        content = file_path.read_text(encoding="utf-8")

    if not content.strip():
        print("ERROR: Content is empty. Refusing to update with blank content.", file=sys.stderr)
        sys.exit(1)

    # Convert markdown to HTML
    html_body = markdown_to_html(content)

    # Create client and get current page state
    client = ConfluenceClient(env["base_url"], env["email"], env["api_token"])

    try:
        current_page = client.get_page(page_id)
    except ConfluenceAPIError as e:
        print(f"ERROR: Failed to fetch current page state: {e}", file=sys.stderr)
        sys.exit(1)

    current_version = current_page["version"]["number"]
    title = current_page["title"]

    # Update the page
    try:
        updated = client.update_page(page_id, title, html_body, current_version)
    except ConfluenceAPIError as e:
        print(f"ERROR: Failed to update page: {e}", file=sys.stderr)
        sys.exit(1)

    new_version = updated["version"]["number"]
    print(f"Updated '{title}' to version {new_version}")

    # Re-sync: fetch the updated page and write it locally
    try:
        page_data = client.get_page(page_id)
        updated_html = page_data.get("body", {}).get("storage", {}).get("value", "")
        updated_md = html_to_markdown(updated_html)
        updated_md = f"# {title}\n\n{updated_md}"

        project_dir = get_repo_root() / "projects" / args.project
        local_path = page_config.get("local_path", f"confluence/{slugify(title)}.md")
        dest_path = project_dir / local_path

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(updated_md, encoding="utf-8")
        print(f"Re-synced local copy: {dest_path.relative_to(get_repo_root())}")

        # Update metadata
        metadata = read_sync_metadata(args.project)
        metadata[str(page_id)] = {
            "title": title,
            "version": new_version,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        write_sync_metadata(args.project, metadata)

    except Exception as e:
        print(f"WARNING: Page updated on Confluence but local re-sync failed: {e}",
              file=sys.stderr)
        print("Run confluence-sync.py to update your local copy.", file=sys.stderr)


if __name__ == "__main__":
    main()
