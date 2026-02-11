# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Support ticket aggregator that gathers issues from multiple sources (Jira, Slack, GitHub), consolidates cross-referenced tickets, analyzes them with NLP, and visualizes insights in a dashboard.

Three decoupled modules connected by JSON:
```
sources.yaml → [gather] → data/gathered.json → [analyze] → data/analyzed.json → [dashboard]
```

- **gather/** (Python): API connectors, cross-reference matching, conversation merging
- **analyze/** (Python): NLP classification, keyword extraction, people graph, identity resolution
- **dashboard/** (Astro + Svelte): Interactive visualizations with linked views

## Development Commands

### gather/ (Python + uv)

```bash
cd gather/

# Install dependencies
uv sync

# Run tests
uv run pytest
uv run pytest tests/test_consolidator.py -v

# Run with coverage
uv run pytest --cov=gather --cov-report=html

# Execute gather
uv run gather --config ../sources.yaml --output ../data/gathered.json
uv run gather --config ../sources.yaml --since 2026-01-01
```

### analyze/ (Python + uv)

```bash
cd analyze/

# Install dependencies (includes spaCy NLP model)
uv sync

# Download spaCy model if needed
uv run python -m spacy download en_core_web_sm

# Run tests
uv run pytest
uv run pytest tests/test_classifier.py::test_linguistic_features -v

# Run with coverage
uv run pytest --cov=analyze --cov-report=html

# Execute analyze
uv run analyze --input ../data/gathered.json --output ../data/analyzed.json
uv run analyze --input ../data/gathered.json --keywords auth-service billing-service

# Suggest new classification rules
uv run analyze-suggest --input ../data/analyzed.json
```

### dashboard/ (Astro + Svelte + bun)

```bash
cd dashboard/

# Install dependencies
bun install

# Development server (localhost:4321)
bun run dev

# Build for production
bun run build

# Preview production build
bun run preview
```

Note: Dashboard reads JSON files client-side from `public/data/`. Copy analyzed.json there before running.

## Architecture Details

### gather/ - Cross-Reference Consolidation

- **Connectors** ([gather/src/gather/connectors/](gather/src/gather/connectors/)): API clients for Jira, Slack, GitHub implementing `BaseConnector` ABC
  - **GitHub**: Supports `state` filter - `"open"`, `"closed"`, or `"all"` (default: `"all"`)
  - **Jira**: Uses JQL for filtering - add status conditions to exclude closed issues
  - **Slack**: No status concept (all threads fetched)
- **Consolidator** ([gather/src/gather/consolidator.py](gather/src/gather/consolidator.py)): Union-find algorithm to cluster issues that cross-reference each other (e.g., JIRA-123 mentioned in Slack thread)
- **Models** ([gather/src/gather/models.py](gather/src/gather/models.py)): `RawIssue` → `ConsolidatedIssue` with merged conversations and deduplicated people

Key insight: Cross-references are extracted via regex patterns (`PROJ-123`, `#12345`) from conversation text, then unified into single consolidated issues. By default, **all issue statuses are included** (both open and closed) for complete historical analysis.

### analyze/ - NLP Classification & Graphs

- **Classifier** ([analyze/src/analyze/classifier.py](analyze/src/analyze/classifier.py)): Linguistic feature extraction using spaCy (dependency parsing, POS tags, modals, negation, imperatives) combined with weighted keyword matching from `classify_rules.yaml`
- **Entities** ([analyze/src/analyze/entities.py](analyze/src/analyze/entities.py)): Keyword extraction using regex patterns + spaCy NER filtering
- **People** ([analyze/src/analyze/people.py](analyze/src/analyze/people.py)): Identity resolution across sources via email exact matching + fuzzy name matching (rapidfuzz)
- **Models** ([analyze/src/analyze/models.py](analyze/src/analyze/models.py)): `Classification`, `PersonNode`, `KeywordGraph` - output schema matching TypeScript types

Classification categories (editable in [analyze/classify_rules.yaml](analyze/classify_rules.yaml)):
- `outage` (weight 1.0): downtime, 500 errors, incidents
- `defect` (weight 0.8): bugs, errors, regressions
- `enhancement` (weight 0.9): feature requests, RFCs
- `routing_issue` (weight 0.9): misrouted tickets
- `inquiry` (weight 0.7): questions, documentation gaps

### dashboard/ - Linked Visualizations

- **Store** ([dashboard/src/lib/store.ts](dashboard/src/lib/store.ts)): Svelte writable stores for global filter state (selected keywords, people, date ranges)
- **Types** ([dashboard/src/lib/types.ts](dashboard/src/lib/types.ts)): TypeScript interfaces matching analyzed.json schema
- **Components** ([dashboard/src/components/](dashboard/src/components/)): Self-contained Svelte components using D3 for rendering:
  - `TemporalKeywordFlow`: Timeline showing keyword activity over time, colored by issue type with interactive bubbles
  - `KeywordTypeMatrix`: Heatmap of keywords vs classification types
  - `PeopleKeywordMatrix`: Heatmap of people vs keywords
  - `KeywordCooccurrence`: Network graph showing keyword relationships
  - `ClassificationBreakdown`: Pie/bar chart of issue types
  - All components subscribe to filter store for linked interactions

Data flow: `index.astro` fetches JSON client-side → passes to components → components render + update store → store changes trigger reactive re-renders.

## Configuration

### sources.yaml

All data sources configured here with per-source auth and filters. Supports `${ENV_VAR}` substitution.

Example:
```yaml
sources:
  company-jira:
    type: jira
    auth:
      base_url: https://company.atlassian.net
      email: you@company.com
      api_token: ${JIRA_API_TOKEN}
    filters:
      jql: "project = PROJ AND updated >= -30d"
```

See [sources.example.yaml](sources.example.yaml) for complete examples.

### classify_rules.yaml

Keyword-based classification rules ([analyze/classify_rules.yaml](analyze/classify_rules.yaml)). Each category has:
- `weight`: Importance multiplier (0.0-1.0)
- `keywords`: List of phrases/terms to match

Classifier combines keyword scores with linguistic features (questions, modals, imperatives) to determine final classification.

## Data Schemas

### gathered.json

Consolidated issues with interleaved conversations:
- `tickets[]`: Array of consolidated issues
  - `id`: UUID
  - `references[]`: Source-specific IDs (Jira key, Slack thread_ts, GitHub issue number)
  - `people[]`: Deduplicated participants with roles
  - `conversation[]`: Chronologically sorted messages from all sources

### analyzed.json

Classifications and graphs:
- `issues[]`: Per-issue classifications with confidence scores
- `people_graph`: Nodes (resolved identities) + edges (co-participation)
- `keyword_graph`: Nodes (keywords) + edges (co-occurrence counts)
- `metadata`: Timestamps and classifier info

## Key Implementation Patterns

1. **Modularity**: Each module is independently runnable with file-based I/O. This avoids coupling and allows iterative development (run gather once, iterate on analyze many times).

2. **Union-Find for Consolidation**: Issues mentioning each other get clustered into single consolidated records. Algorithm is in [gather/src/gather/consolidator.py](gather/src/gather/consolidator.py).

3. **Linguistic Classification**: Unlike pure keyword matching, the classifier uses spaCy to understand sentence structure (questions vs statements, imperatives vs descriptions) for better accuracy. See [analyze/src/analyze/classifier.py](analyze/src/analyze/classifier.py).

4. **Identity Resolution**: People are matched across sources via exact email match (highest confidence) or fuzzy name matching with configurable threshold. Implemented in [analyze/src/analyze/people.py](analyze/src/analyze/people.py).

5. **Client-Side Dashboard**: No backend needed - all data loaded and filtered in browser. Svelte stores enable reactive linked views where selecting a keyword filters all charts simultaneously.

## Testing

Both Python modules use pytest with coverage reporting:
```bash
uv run pytest --cov=<module> --cov-report=html
```

Tests cover:
- Connector API mocking (httpx responses)
- Consolidation algorithm correctness
- Classification with sample inputs
- People identity resolution edge cases
