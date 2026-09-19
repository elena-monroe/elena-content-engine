"""Content Scout: Search Console → OpenAI evaluation → Notion opportunities.

This is a behavioral migration of the `Elena Content Scout` n8n export. It
preserves its model, prompt rules, output schema, `Skip` filter, and Notion
property mapping. Use --dry-run first; it is the default for manual Actions runs.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from openai import OpenAI

from src.notion import NotionClient
from src.search_console import fetch_query_metrics

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (ROOT / "prompts" / "content_scout.txt").read_text(encoding="utf-8")
DATA_SOURCE_ID = "3d70d1ff-9a3a-80b0-a8cb-000bd584fdcb"
SITE_URL = "sc-domain:elenamonroephotography.com"

TOPIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "source_query": {"type": "string"},
                    "impressions": {"type": "number"},
                    "clicks": {"type": "number"},
                    "ctr": {"type": "number"},
                    "position": {"type": "number"},
                    "score": {"type": "number"},
                    "recommendation": {"type": "string"},
                    "search_intent": {"type": "string"},
                    "business_relevance": {"type": "number"},
                    "elena_pov": {"type": "number"},
                    "originality": {"type": "number"},
                    "local_relevance": {"type": "number"},
                    "why_it_matters": {"type": "string"},
                    "elena_perspective": {"type": "string"},
                },
                "required": [
                    "topic", "source_query", "impressions", "clicks", "ctr", "position", "score",
                    "recommendation", "search_intent", "business_relevance", "elena_pov", "originality",
                    "local_relevance", "why_it_matters", "elena_perspective",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["topics"],
    "additionalProperties": False,
}


def plain_text(value: list[dict[str, Any]] | None) -> str:
    return "".join(item.get("plain_text", item.get("text", {}).get("content", "")) for item in value or [])


def page_to_existing_opportunity(page: dict[str, Any]) -> dict[str, str]:
    """Convert a Notion page to the compact context the n8n code node produced."""
    props = page.get("properties", {})
    title = plain_text(props.get("Topic", {}).get("title"))
    return {
        "id": page.get("id", ""),
        "topic": title,
        "source_query": plain_text(props.get("Source Query", {}).get("rich_text")),
        "status": props.get("Status", {}).get("status", {}).get("name", ""),
        "scout_status": props.get("Scout Status", {}).get("select", {}).get("name", ""),
        "recommendation": props.get("AI Recommendation", {}).get("select", {}).get("name", ""),
        "search_intent": props.get("Search Intent", {}).get("select", {}).get("name", ""),
    }


def evaluate_topics(search_data: list[dict[str, Any]], existing: list[dict[str, str]]) -> list[dict[str, Any]]:
    user_context = (
        "CURRENT SEARCH CONSOLE DATA:\n"
        f"{json.dumps(search_data, ensure_ascii=False)}\n\n"
        "EXISTING CONTENT OPPORTUNITIES:\n"
        f"{json.dumps(existing, ensure_ascii=False)}"
    )
    response = OpenAI().responses.create(
        model="gpt-4o-mini",
        input=[{"role": "system", "content": PROMPT}, {"role": "user", "content": user_context}],
        text={"format": {"type": "json_schema", "name": "content_scout", "strict": True, "schema": TOPIC_SCHEMA}},
    )
    return json.loads(response.output_text)["topics"]


def valid_topics(topics: list[dict[str, Any]], search_data: list[dict[str, Any]], existing: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Keep n8n's non-Skip filter and reject fabricated or exact-duplicate source data."""
    metrics_by_query = {item["query"]: item for item in search_data}
    existing_queries = {item["source_query"].casefold() for item in existing if item["source_query"]}
    kept: list[dict[str, Any]] = []
    for topic in topics:
        source = topic["source_query"]
        metrics = metrics_by_query.get(source)
        if topic["recommendation"] == "Skip" or source.casefold() in existing_queries:
            continue
        if not metrics or any(topic[key] != metrics[key] for key in ("impressions", "clicks", "ctr", "position")):
            raise ValueError(f"Topic for {source!r} did not preserve its Search Console metrics.")
        kept.append(topic)
    return kept


def rich_text(value: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": value}}] if value else []


def notion_properties(topic: dict[str, Any]) -> dict[str, Any]:
    """Exact property mapping from the original Create a database page node."""
    return {
        "Topic": {"title": rich_text(topic["topic"])},
        "Status": {"status": {"name": "Not started"}},
        "Business Relevance": {"number": topic["business_relevance"]},
        "Elena POV": {"number": topic["elena_pov"]},
        "Originality": {"number": topic["originality"]},
        "Local Relevance": {"number": topic["local_relevance"]},
        "Search Question": {"rich_text": rich_text(topic["topic"])},
        "Content Type": {"multi_select": [{"name": "Blog"}]},
        "Notes": {"rich_text": rich_text(topic["why_it_matters"])},
        "Scout Status": {"select": {"name": "scored"}},
        "Search Intent": {"select": {"name": topic["search_intent"]}},
        "Why it matters": {"rich_text": rich_text(topic["why_it_matters"])},
        "AI Recommendation": {"select": {"name": topic["recommendation"]}},
        "Source Query": {"rich_text": rich_text(topic["source_query"])},
        "Impressions": {"number": topic["impressions"]},
        "Clicks": {"number": topic["clicks"]},
        "CTR": {"number": topic["ctr"]},
        "Average Position": {"number": topic["position"]},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print candidates; do not write to Notion.")
    parser.add_argument("--enforce-schedule", action="store_true", help="Run only at Monday 8 AM America/Los_Angeles.")
    args = parser.parse_args()
    if args.enforce_schedule:
        now = datetime.now(ZoneInfo("America/Los_Angeles"))
        if now.weekday() != 0 or now.hour != 8:
            print(f"Skipping: local time is {now:%A %H:%M %Z}, not Monday 08:xx.")
            return

    data_source_id = os.environ.get("CONTENT_OPPORTUNITIES_DATA_SOURCE_ID", DATA_SOURCE_ID)
    site_url = os.environ.get("SEARCH_CONSOLE_SITE_URL", SITE_URL)
    notion = NotionClient()
    existing = [page_to_existing_opportunity(page) for page in notion.query_all(data_source_id)]
    search_data = fetch_query_metrics(site_url)
    topics = valid_topics(evaluate_topics(search_data, existing), search_data, existing)
    if args.dry_run:
        print(json.dumps(topics, ensure_ascii=False, indent=2))
        return
    for topic in topics:
        notion.create_page(data_source_id, notion_properties(topic))
        print(f"Created: {topic['topic']}")


if __name__ == "__main__":
    main()

