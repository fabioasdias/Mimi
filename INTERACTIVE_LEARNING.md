# Interactive Classification Learning

Instead of manually editing YAML, the system learns from your corrections.

## Quick Start

```bash
cd analyze

# 1. Run initial classification
uv run analyze --input ../data/gathered.json --output ../data/analyzed.json

# 2. Review and correct classifications interactively
uv run analyze-suggest --interactive

# 3. Re-analyze with learned improvements
uv run analyze --input ../data/gathered.json --output ../data/analyzed.json
```

## How It Works

### Interactive Mode

```bash
uv run analyze-suggest \
  --analyzed ../data/analyzed.json \
  --gathered ../data/gathered.json \
  --interactive \
  --confidence-threshold 0.6
```

The system will:
1. **Show you** low-confidence classifications one by one
2. **Ask you** what the correct type should be
3. **Learn** keywords from your corrections
4. **Update rules** automatically based on patterns it discovers

### Example Session

```
🎓 Interactive Learning Mode

[1/15]
ID: Azure/azure-cli#12345
Current: inquiry (confidence: 0.42)
Summary: deployment fails with timeout error

What should this be? (outage/defect/enhancement/inquiry/routing_issue/skip)
Type: outage
  ✓ Learned keywords: deployment, timeout, fails

[2/15]
ID: Azure/azure-sdk-for-python#67890
Current: defect (confidence: 0.38)
Summary: feature request for async support

What should this be?
Type: enhancement
  ✓ Learned keywords: async, request, support
  
📝 Applying 2 corrections...
✓ Updated classify_rules.custom.yaml
  Added patterns with weight 1.5
  Saved 2 corrections

  Re-run analyze to see improvements
```

## Context-Specific Learning

Learn rules specific to a dataset or team:

```bash
uv run analyze-suggest --interactive --context "azure-platform"
```

This adds learned patterns to the `azure-platform` context in custom rules, so they only apply when classifying issues from that context.

## What Gets Learned

From each correction, the system:

1. **Extracts distinctive keywords** from the issue text
2. **Adds them to classification rules** with higher weight (1.5)
3. **Stores the correction** for direct lookup (99% confidence)
4. **Associates with context** if specified

Example learned rule:
```yaml
overrides:
  outage:
    weight: 1.5
    keywords:
      - deployment
      - timeout
      - fails

corrections:
  "Azure/azure-cli#12345": "outage"
```

## Report Mode (Default)

Without `--interactive`, just shows analysis:

```bash
uv run analyze-suggest
```

Shows classification quality and suggestions without interaction.

## Iterative Improvement

1. **First pass**: Run analyze, many low-confidence results
2. **Learn**: Use --interactive to correct 10-20 issues
3. **Improve**: Re-run analyze, see better results
4. **Repeat**: Learn from remaining low-confidence issues
5. **Converge**: Classification quality improves with each iteration

The system gets smarter with every correction you make.
