# Support Ticket Aggregator

Aggregates support requests across multiple services (Jira, Slack, GitHub Issues, etc.), consolidates cross-referenced tickets, and analyzes them with NLP.

## Architecture

Three decoupled modules connected by JSON files:

```
sources.yaml ──> [gather] ──> data/gathered.json ──> [analyze] ──> data/analyzed.json ──> [dashboard]
```

| Module | Tech | Purpose |
|-----------|----------------|---------|
| `gather/` | Python (uv) | Query APIs, cross-reference tickets, merge conversations |
| `analyze/` | Python (uv) | NLP classification, service extraction, people graph |
| `dashboard/` | Astro + Svelte (bun) | Linked-view dashboard reading JSON files |

Modules are fully independent — run them separately to avoid unnecessary API calls, and swap data sources without touching downstream code.

## Configuration

All data sources are configured in `sources.yaml` (see `sources.example.yaml`). Each source has a type, auth credentials, and API-specific filters:

```yaml
sources:
  company-jira:
    type: jira
    auth:
      base_url: https://company.atlassian.net
      email: you@company.com
      api_token: ${JIRA_API_TOKEN}    # resolved from env vars
    filters:
      jql: "project in (AUTH, PLAT) AND updated >= -30d"

  support-slack:
    type: slack
    auth:
      bot_token: ${SLACK_BOT_TOKEN}
    filters:
      channels: [C_SUPPORT, C_BILLING]
      oldest_days: 30

  platform-github:
    type: github
    auth:
      token: ${GITHUB_TOKEN}
    filters:
      repos: [company/platform]
      labels: [bug, support]
      state: all
```

Auth values support `${ENV_VAR}` syntax so secrets stay out of the file.

## Usage

### Gather
```bash
cd gather/
uv run gather --config ../sources.yaml --output ../data/gathered.json
uv run gather --config ../sources.yaml --since 2026-01-01
```

### Analyze
```bash
cd analyze/
uv run analyze --input ../data/gathered.json --output ../data/analyzed.json
uv run analyze --input ../data/gathered.json --services auth-service --services billing-service
```

### Dashboard
```bash
cd dashboard/
# Copy JSON data into public/data/ for the frontend
bun run dev
```

## JSON Schemas

### gathered.json

Each ticket is consolidated from one or more sources, with cross-references merged and conversations interleaved chronologically.

```json
{
  "tickets": [{
    "id": "uuid",
    "references": [
      {"source": "jira", "id": "PROJ-1234", "url": "..."},
      {"source": "slack", "id": "...", "channel": "...", "thread_ts": "..."}
    ],
    "title": "...",
    "status": "...",
    "created_at": "ISO8601",
    "updated_at": "ISO8601",
    "people": [{"source": "jira", "source_id": "...", "name": "...", "email": "...", "role": "reporter"}],
    "conversation": [{"source": "jira", "author": "...", "author_source_id": "...", "timestamp": "ISO8601", "content": "..."}]
  }],
  "metadata": {"gathered_at": "ISO8601", "sources": ["jira", "slack"]}
}
```

### analyzed.json

Classifications, people graph (identity resolution across sources), and service co-occurrence graph.

See `data/samples/analyzed.json` for a complete example.

## Status

### gather/ — IN PROGRESS
- [x] Project scaffolding (pyproject.toml, uv)
- [x] YAML config with per-source auth + filters
- [x] Connector ABC (`BaseConnector`)
- [x] Jira connector
- [x] Slack connector
- [x] GitHub Issues connector
- [x] Consolidator (cross-reference matching via union-find)
- [x] CLI entrypoint
- [ ] Install deps and test run
- [ ] Iterate on output quality

### analyze/ — SCAFFOLDED, NOT STARTED
- [x] Project scaffolding (pyproject.toml, uv)
- [x] Pydantic models for output schema
- [x] Rule-based classifier (keyword patterns)
- [x] Service entity extraction (regex + spaCy NER)
- [x] People identity resolution (email + fuzzy name)
- [x] Graph building (networkx)
- [x] CLI entrypoint
- [ ] Install deps and test run
- [ ] Iterate on classification quality

### dashboard/ — SCAFFOLDED, NOT STARTED
- [x] Astro + Svelte + D3 installed
- [ ] TypeScript types
- [ ] Shared filter store
- [ ] Ticket table view
- [ ] Classification breakdown chart
- [ ] Timeline chart
- [ ] People/service graph
- [ ] Linked view interactions

### data/samples/
- [x] `gathered.json` — 5 sample tickets across Jira + Slack
- [x] `analyzed.json` — classifications + people/service graphs
