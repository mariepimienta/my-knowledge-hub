#!/usr/bin/env python3
"""Sync Confluence pages to local markdown files.

Usage:
    python confluence-sync.py --project <name> [--page <page-name>] [--force]

Pulls pages (and their child pages recursively) from Confluence, converts HTML
to markdown, downloads attachments, and stores everything locally.
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
from lib.confluence_client import ConfluenceClient, ConfluenceAPIError, html_to_markdown


def slugify(title):
    """Convert a page title to a filesystem-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def rewrite_image_refs(markdown_text, page_id, assets_rel_path):
    """Rewrite image references in markdown to point to local assets."""
    def replace_image(match):
        alt = match.group(1)
        original_url = match.group(2)
        # Extract filename from URL
        filename = original_url.split("/")[-1].split("?")[0]
        local_name = f"{page_id}-{filename}"
        local_path = f"{assets_rel_path}/{local_name}"
        return f"![{alt}]({local_path})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, markdown_text)


def sync_page(client, page_id, dest_dir, assets_dir, metadata, page_config, force=False):
    """Sync a single page: fetch, convert, write markdown, download attachments.

    Args:
        client: ConfluenceClient instance.
        page_id: Confluence page ID.
        dest_dir: Directory to write the markdown file into.
        assets_dir: Directory for attachment downloads.
        metadata: Current sync metadata dict (mutated in place).
        page_config: Page config from sources.yaml.
        force: If True, sync even if version hasn't changed.

    Returns:
        (status, title) where status is 'synced', 'skipped', or 'failed'.
    """
    try:
        page_data = client.get_page(page_id)
    except ConfluenceAPIError as e:
        print(f"  ERROR fetching page {page_id}: {e}")
        return "failed", None

    title = page_data["title"]
    version = page_data["version"]["number"]
    page_id_str = str(page_id)

    # Check if we can skip
    existing = metadata.get(page_id_str, {})
    if not force and existing.get("version") == version:
        print(f"  Skipping '{title}' (version {version} unchanged)")
        return "skipped", title

    # Convert HTML to markdown
    html_body = page_data.get("body", {}).get("storage", {}).get("value", "")
    markdown_content = html_to_markdown(html_body)

    # Calculate relative path from dest_dir to assets_dir
    try:
        assets_rel = os.path.relpath(assets_dir, dest_dir)
    except ValueError:
        assets_rel = str(assets_dir)

    # Rewrite image references
    markdown_content = rewrite_image_refs(markdown_content, page_id_str, assets_rel)

    # Add title as H1
    markdown_content = f"# {title}\n\n{markdown_content}"

    # Write markdown file
    dest_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(title)
    md_path = dest_dir / f"{slug}.md"
    md_path.write_text(markdown_content, encoding="utf-8")
    print(f"  Synced '{title}' -> {md_path.relative_to(get_repo_root())}")

    # Download attachments
    if page_config.get("sync_attachments", True):
        try:
            attachments = client.get_attachments(page_id)
            assets_dir.mkdir(parents=True, exist_ok=True)
            for att in attachments:
                att_title = att["title"]
                download_url = att.get("_links", {}).get("download", "")
                if not download_url:
                    continue

                if page_config.get("attachment_prefix_with_page_id", True):
                    local_name = f"{page_id_str}-{att_title}"
                else:
                    local_name = att_title

                dest_path = assets_dir / local_name
                client.download_attachment(download_url, dest_path)
                print(f"    Attachment: {local_name}")
        except ConfluenceAPIError as e:
            print(f"  WARNING: Failed to fetch attachments for '{title}': {e}")

    # Update metadata
    metadata[page_id_str] = {
        "title": title,
        "version": version,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }

    return "synced", title


def sync_children(client, page_id, parent_dir, assets_dir, metadata, page_config, force=False):
    """Recursively sync child pages into nested subdirectories.

    Returns counts: (synced, skipped, failed)
    """
    synced = skipped = failed = 0

    if not page_config.get("sync_children", True):
        return synced, skipped, failed

    try:
        tree = client.get_page_tree(page_id)
    except ConfluenceAPIError as e:
        print(f"  WARNING: Failed to get child pages for {page_id}: {e}")
        return 0, 0, 1

    for node in tree:
        child_id = node["id"]
        child_title = node["title"]
        child_slug = slugify(child_title)

        # Children go into a subdirectory named after the parent slug
        child_dir = parent_dir

        status, _ = sync_page(
            client, child_id, child_dir, assets_dir, metadata, page_config, force
        )

        if status == "synced":
            synced += 1
        elif status == "skipped":
            skipped += 1
        else:
            failed += 1

        # Recurse into grandchildren — they go into a subdir named after this child
        if node.get("children"):
            grandchild_dir = child_dir / child_slug
            for grandchild in node["children"]:
                gc_status, gc_title = sync_page(
                    client, grandchild["id"], grandchild_dir, assets_dir,
                    metadata, page_config, force
                )
                if gc_status == "synced":
                    synced += 1
                elif gc_status == "skipped":
                    skipped += 1
                else:
                    failed += 1

                # Continue recursion for deeper levels
                if grandchild.get("children"):
                    gc_slug = slugify(grandchild.get("title", grandchild["id"]))
                    s, sk, f = sync_children_recursive(
                        client, grandchild, grandchild_dir / gc_slug,
                        assets_dir, metadata, page_config, force
                    )
                    synced += s
                    skipped += sk
                    failed += f

    return synced, skipped, failed


def sync_children_recursive(client, node, dest_dir, assets_dir, metadata, page_config, force=False):
    """Recursively sync a subtree of child pages."""
    synced = skipped = failed = 0

    for child in node.get("children", []):
        status, title = sync_page(
            client, child["id"], dest_dir, assets_dir, metadata, page_config, force
        )
        if status == "synced":
            synced += 1
        elif status == "skipped":
            skipped += 1
        else:
            failed += 1

        if child.get("children"):
            child_slug = slugify(child.get("title", child["id"]))
            s, sk, f = sync_children_recursive(
                client, child, dest_dir / child_slug,
                assets_dir, metadata, page_config, force
            )
            synced += s
            skipped += sk
            failed += f

    return synced, skipped, failed


def main():
    parser = argparse.ArgumentParser(
        description="Sync Confluence pages to local markdown files."
    )
    parser.add_argument(
        "--project", required=True,
        help="Project name (must match a directory under projects/)"
    )
    parser.add_argument(
        "--page",
        help="Sync only this page (by name from sources.yaml). Syncs all if omitted."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force sync even if page version hasn't changed."
    )
    args = parser.parse_args()

    # Load configs
    try:
        sources = load_project_sources(args.project)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        env = resolve_confluence_env()
    except EnvironmentError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    client = ConfluenceClient(env["base_url"], env["email"], env["api_token"])
    metadata = read_sync_metadata(args.project)

    project_dir = get_repo_root() / "projects" / args.project

    # Filter pages if --page specified
    pages = sources.get("pages", [])
    if args.page:
        pages = [p for p in pages if p.get("name") == args.page]
        if not pages:
            print(f"ERROR: Page '{args.page}' not found in sources.yaml", file=sys.stderr)
            sys.exit(1)

    total_synced = 0
    total_skipped = 0
    total_failed = 0

    for page_config in pages:
        page_name = page_config.get("name", "unknown")
        page_id = page_config.get("page_id")
        local_path = page_config.get("local_path", f"confluence/{slugify(page_name)}.md")

        print(f"\nSyncing page: {page_name} (ID: {page_id})")

        # Determine destination directory and assets directory
        dest_dir = project_dir / Path(local_path).parent
        assets_dir = project_dir / "confluence" / "assets"

        # Sync the parent page
        status, title = sync_page(
            client, page_id, dest_dir, assets_dir, metadata, page_config, args.force
        )

        if status == "synced":
            total_synced += 1
        elif status == "skipped":
            total_skipped += 1
        else:
            total_failed += 1

        # Sync child pages recursively
        parent_slug = slugify(title or page_name)
        children_dir = dest_dir / parent_slug
        s, sk, f = sync_children(
            client, page_id, children_dir, assets_dir, metadata, page_config, args.force
        )
        total_synced += s
        total_skipped += sk
        total_failed += f

    # Save metadata
    write_sync_metadata(args.project, metadata)

    # Print summary
    print(f"\n--- Sync Summary ---")
    print(f"  Synced:  {total_synced}")
    print(f"  Skipped: {total_skipped}")
    print(f"  Failed:  {total_failed}")

    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
