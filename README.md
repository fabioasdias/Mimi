# Mîmî

Aggregates support requests across multiple services (Jira, Slack, GitHub Issues, etc.), consolidates cross-referenced tickets, and analyzes them with NLP.

## About the Name

**Mîmî** comes from Michif/Cree, where it affectionately describes someone who fusses or makes their voice heard to get what they need. 
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
      state: all           # "open", "closed", or "all" (default: "all")
      since_days: 30       # Optional: limit to recently updated issues
```

Auth values support `${ENV_VAR}` syntax so secrets stay out of the file.

**Issue Status Filtering:**
- **GitHub**: Use `state: open` to get only open issues, `state: closed` for closed, or `state: all` (default) for both
- **Jira**: Add status conditions to your JQL, e.g., `"status NOT IN (Done, Closed) AND updated >= -30d"`
- **Slack**: No status concept (all threads are fetched)

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

## Custom Classification

The analyzer supports team-specific terminology and domain knowledge through custom rules. This is essential for handling words with non-obvious meanings in your context.

### Quick Start

```bash
# Create custom rules file
cp analyze/classify_rules.custom.yaml.example analyze/classify_rules.custom.yaml

# Edit to add your team-specific terms
vim analyze/classify_rules.custom.yaml

# Re-run analysis
npm run analyze
```

### Features

- **Context-Aware Rules**: Different classification rules per source/team
- **Global Overrides**: Force specific keywords to signal certain types
- **Manual Corrections**: Override misclassified issues by ID
- **Keyword Overrides**: Force-include or exclude specific keywords

### Example Custom Rules

```yaml
# Team-specific terminology
contexts:
  azure-platform:
    outage:
      weight: 2.5
      keywords:
        - "arm"  # Azure Resource Manager - often infrastructure issues

# Global overrides for all issues
overrides:
  outage:
    keywords:
      - "maintenance window"  # Your team's term for planned downtime

# Manual corrections
corrections:
  "Azure/azure-cli#12345": "defect"  # Was wrongly classified as inquiry
```

**See [CUSTOM_CLASSIFICATION.md](CUSTOM_CLASSIFICATION.md) for detailed guide and examples.**

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
