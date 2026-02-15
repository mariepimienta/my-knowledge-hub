"""Configuration loading and environment resolution for the knowledge hub."""

import json
import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv


def get_repo_root():
    """Resolve the repository root from this file's location."""
    return Path(__file__).resolve().parent.parent.parent


def load_global_settings():
    """Load global settings from config/global-settings.yaml."""
    settings_path = get_repo_root() / "config" / "global-settings.yaml"
    with open(settings_path, "r") as f:
        return yaml.safe_load(f)


def load_project_sources(project_name):
    """Load sources.yaml for a project, merged with global defaults.

    Returns a dict with 'pages' list, each page having all default fields applied.
    """
    settings = load_global_settings()
    defaults = settings.get("defaults", {})

    sources_path = get_repo_root() / "projects" / project_name / "sources.yaml"
    if not sources_path.exists():
        raise FileNotFoundError(
            f"No sources.yaml found for project '{project_name}' at {sources_path}"
        )

    with open(sources_path, "r") as f:
        sources = yaml.safe_load(f) or {}

    # Apply defaults and resolve URLs to page IDs
    pages = sources.get("pages", [])
    for page in pages:
        # If url is provided but page_id is not, extract it from the URL
        if "url" in page and "page_id" not in page:
            page["page_id"] = _extract_page_id(page["url"])

        for key, default_value in defaults.items():
            if key not in page:
                page[key] = default_value

    sources["pages"] = pages
    return sources


def _extract_page_id(url):
    """Extract the Confluence page ID from a full URL.

    Supports formats:
      - .../pages/12345678/Page+Title
      - .../pages/12345678
      - ...?pageId=12345678
    """
    # Try /pages/<id> pattern
    match = re.search(r"/pages/(\d+)", url)
    if match:
        return match.group(1)

    # Try ?pageId=<id> query parameter
    match = re.search(r"[?&]pageId=(\d+)", url)
    if match:
        return match.group(1)

    raise ValueError(
        f"Could not extract page ID from URL: {url}\n"
        f"Expected a URL containing /pages/<id> or ?pageId=<id>"
    )


def read_sync_metadata(project_name):
    """Read .sync-metadata.json for a project. Returns empty dict if missing or empty."""
    meta_path = get_repo_root() / "projects" / project_name / ".sync-metadata.json"
    if not meta_path.exists():
        return {}
    with open(meta_path, "r") as f:
        content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)


def write_sync_metadata(project_name, data):
    """Write .sync-metadata.json for a project."""
    meta_path = get_repo_root() / "projects" / project_name / ".sync-metadata.json"
    with open(meta_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def resolve_confluence_env():
    """Load .env and resolve Confluence credentials from environment.

    Returns a dict with 'base_url', 'email', 'api_token'.
    Raises EnvironmentError if any required variable is missing.
    """
    load_dotenv(get_repo_root() / ".env")

    settings = load_global_settings()
    env_vars = settings["confluence"]["env_vars"]

    result = {}
    missing = []

    for key, env_name in env_vars.items():
        value = os.environ.get(env_name)
        if not value:
            missing.append(env_name)
        else:
            result[key] = value

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in your Confluence credentials."
        )

    return result
