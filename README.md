# Elena Content Engine

This repository replaces n8n's orchestration layer while keeping Notion as the editorial workspace, Google Search Console as the search-data source, and OpenAI as the evaluator.

## Content Scout

The first migration is a behavioral replacement for the `Elena Content Scout` n8n workflow:

```text
Monday, 8 AM Pacific
  → Google Search Console query data
  → existing Notion Content Opportunities
  → OpenAI topic evaluation
  → discard Skip recommendations
  → create Content Opportunity pages in Notion
```

The script preserves the original `gpt-4o-mini` model, editorial constraints, output schema, output ranking, Notion field mapping, and `Skip` filter. It also refuses an OpenAI response that changes a query's Search Console metrics and does not create a page whose exact source query already exists.

### Before the first live run

1. Create a Notion internal integration with access to the **Content Opportunities** data source.
2. Create or reuse a Google service account, add it as a user for the `sc-domain:elenamonroephotography.com` Search Console property, and export its JSON credentials.
3. In GitHub, open **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI API key |
| `NOTION_API_KEY` | Notion integration token |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Entire Google service-account JSON file, as one secret |

The Content Opportunities data source ID and Search Console property are already set from the n8n export. Change them only if the underlying Notion or Search Console setup changes.

### Safely testing it

Open **Actions → Content Scout → Run workflow**. Its manual run defaults to **dry run**, which prints proposed opportunities but writes nothing to Notion. Review that output against n8n first. Only set `dry_run` to false once the results look right.

The scheduled job runs at 8 AM America/Los_Angeles on Mondays, including across daylight saving time. GitHub schedules can be delayed, but the script will not run at the other UTC hour used to cover the seasonal clock shift.

Keep the n8n workflow enabled until several dry runs and at least one live GitHub run have been checked. Do not run both live workflows simultaneously: they can each create opportunities before the other sees them.

## Repository layout

```text
.github/workflows/content-scout.yml  GitHub Action schedule and manual run
prompts/content_scout.txt            Versioned editorial instructions
src/search_console.py                Query-level Search Console retrieval
src/notion.py                        Notion data-source query and page creation
src/content_scout.py                 Content Scout orchestration
```
