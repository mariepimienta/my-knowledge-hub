"""Confluence REST API client with HTML/Markdown conversion utilities."""

import re

import requests
from markdownify import markdownify
import markdown as md_lib


class ConfluenceAPIError(Exception):
    """Custom exception for Confluence API errors."""

    def __init__(self, status_code, url, message):
        self.status_code = status_code
        self.url = url
        self.message = message
        super().__init__(f"Confluence API error {status_code} for {url}: {message}")


class ConfluenceClient:
    """Client for the Confluence REST API."""

    API_TIMEOUT = 30
    DOWNLOAD_TIMEOUT = 120

    def __init__(self, base_url, email, api_token):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (email, api_token)
        self.session.headers.update({"Accept": "application/json"})

    def _request(self, method, path, timeout=None, **kwargs):
        """Make an API request with error handling."""
        url = f"{self.base_url}{path}"
        timeout = timeout or self.API_TIMEOUT

        response = self.session.request(method, url, timeout=timeout, **kwargs)

        if response.status_code == 401:
            raise ConfluenceAPIError(
                401, url,
                "Authentication failed. Check your CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN."
            )
        if response.status_code == 429:
            raise ConfluenceAPIError(
                429, url,
                "Rate limited by Confluence. Wait a moment and try again."
            )
        if not response.ok:
            raise ConfluenceAPIError(
                response.status_code, url,
                response.text[:500]
            )

        return response

    def get_page(self, page_id):
        """Get a page with its body and version info.

        Returns dict with 'id', 'title', 'body.storage.value', 'version.number'.
        """
        response = self._request(
            "GET",
            f"/rest/api/content/{page_id}",
            params={"expand": "body.storage,version"}
        )
        return response.json()

    def get_child_pages(self, page_id):
        """Get all child pages of a given page, handling pagination.

        Returns list of child page metadata dicts.
        """
        children = []
        start = 0
        limit = 50

        while True:
            response = self._request(
                "GET",
                f"/rest/api/content/{page_id}/child/page",
                params={"start": start, "limit": limit}
            )
            data = response.json()
            results = data.get("results", [])
            children.extend(results)

            # Check if there are more pages
            if data.get("size", 0) < limit:
                break
            start += limit

        return children

    def get_page_tree(self, page_id):
        """Recursively build the full child page hierarchy.

        Returns a list of dicts: [{'id', 'title', 'children': [...]}]
        """
        children = self.get_child_pages(page_id)
        tree = []
        for child in children:
            node = {
                "id": child["id"],
                "title": child["title"],
                "children": self.get_page_tree(child["id"])
            }
            tree.append(node)
        return tree

    def get_attachments(self, page_id):
        """Get all attachments for a page, handling pagination.

        Returns list of attachment metadata dicts.
        """
        attachments = []
        start = 0
        limit = 50

        while True:
            response = self._request(
                "GET",
                f"/rest/api/content/{page_id}/child/attachment",
                params={"start": start, "limit": limit}
            )
            data = response.json()
            results = data.get("results", [])
            attachments.extend(results)

            if data.get("size", 0) < limit:
                break
            start += limit

        return attachments

    def download_attachment(self, download_url, dest_path):
        """Download an attachment to a local file path (streamed)."""
        # download_url may be relative
        if download_url.startswith("/"):
            url = f"{self.base_url}{download_url}"
        else:
            url = download_url

        response = self.session.get(url, stream=True, timeout=self.DOWNLOAD_TIMEOUT)
        if not response.ok:
            raise ConfluenceAPIError(
                response.status_code, url,
                f"Failed to download attachment: {response.text[:200]}"
            )

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def update_page(self, page_id, title, html_body, current_version):
        """Update a Confluence page with new HTML content.

        Args:
            page_id: The page ID to update.
            title: The page title.
            html_body: The new HTML body content.
            current_version: The current version number (will be incremented).

        Returns the updated page data.
        """
        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": html_body,
                    "representation": "storage"
                }
            }
        }
        response = self._request(
            "PUT",
            f"/rest/api/content/{page_id}",
            json=payload
        )
        return response.json()


def html_to_markdown(html):
    """Convert Confluence HTML storage format to markdown.

    Uses ATX-style headings and strips script/style tags.
    """
    # Strip script and style tags before conversion
    cleaned = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL)

    return markdownify(cleaned, heading_style="ATX", strip=["script", "style"])


def markdown_to_html(markdown_text):
    """Convert markdown to HTML for Confluence storage format."""
    return md_lib.markdown(markdown_text, extensions=["tables", "fenced_code"])
