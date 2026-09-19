"""Small Notion API client for the Content Opportunities data source."""

from __future__ import annotations

import os
from typing import Any

import requests

NOTION_VERSION = "2025-09-03"


class NotionClient:
    def __init__(self, token: str | None = None) -> None:
        token = token or os.environ.get("NOTION_API_KEY")
        if not token:
            raise RuntimeError("NOTION_API_KEY is required.")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.session.request(method, f"https://api.notion.com/v1{path}", timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def query_all(self, data_source_id: str) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        payload: dict[str, Any] = {"page_size": 100}
        while True:
            body = self._request("POST", f"/data_sources/{data_source_id}/query", json=payload)
            pages.extend(body["results"])
            if not body.get("has_more"):
                return pages
            payload["start_cursor"] = body["next_cursor"]

    def create_page(self, data_source_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/pages",
            json={"parent": {"type": "data_source_id", "data_source_id": data_source_id}, "properties": properties},
        )

