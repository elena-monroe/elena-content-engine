"""Google Search Console query retrieval."""

from __future__ import annotations

import json
import os
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

READONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def fetch_query_metrics(site_url: str, service_account_json: str | None = None) -> list[dict[str, Any]]:
    """Return the query-level data used by the original n8n Search Console node."""
    service_account_json = service_account_json or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is required.")
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(service_account_json), scopes=[READONLY_SCOPE]
    )
    service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
    response = service.searchanalytics().query(
        siteUrl=site_url,
        body={"dimensions": ["query"], "rowLimit": 25000},
    ).execute()
    return [
        {
            "query": row["keys"][0],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": row["ctr"],
            "position": row["position"],
        }
        for row in response.get("rows", [])
    ]

