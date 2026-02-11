# Custom Classification Guide

This guide explains how to improve classification results interactively with team-specific terminology and domain knowledge.

## Overview

The classification system supports three layers of customization:

1. **Base Rules** (`classify_rules.yaml`) - General classification patterns
2. **Custom Rules** (`classify_rules.custom.yaml`) - Team/domain-specific overrides
3. **Manual Corrections** - Direct fixes for misclassified issues

## Quick Start

### 1. Create Your Custom Rules File

```bash
cp analyze/classify_rules.custom.yaml.example analyze/classify_rules.custom.yaml
```

### 2. Add Team-Specific Terminology

Edit `analyze/classify_rules.custom.yaml` to add your domain-specific terms.

### 3. Re-analyze

```bash
npm run analyze
```

The analyzer will automatically pick up your custom rules and apply them.

## Custom Rules Structure

### Global Overrides

Add keywords that should apply to all issues regardless of source:

```yaml
overrides:
  outage:
    keywords:
      - "maintenance window"  # Team-specific term for planned outages
      - "pto"  # Your team uses this for scheduled downtime

  defect:
    keywords:
      - "regression in"  # Strong signal for bugs
      - "worked yesterday"
```

### Context-Specific Rules

Apply different rules based on the source of the issue (GitHub repo, Jira project, Slack channel):

```yaml
contexts:
  # Rules specific to Azure platform issues
  azure-platform:
    outage:
      weight: 2.5
      keywords:
        - "arm"  # Azure Resource Manager - infrastructure issues
        - "deployment failed"

    defect:
      weight: 1.5
      keywords:
        - "sdk"  # SDK issues are usually bugs, not questions

  # Rules for support team channel
  support-team:
    routing_issue:
      weight: 3.0  # High priority for routing
      keywords:
        - "escalate"
        - "tier 2"
        - "needs pm"
```

**How contexts work:**
- Context is determined by the issue's source (e.g., "github", "jira", "slack")
- For GitHub issues, you could map specific repos to contexts
- Context rules are merged with base rules
- Higher weights win when there are conflicts

### Keyword Overrides

Force specific keywords to always be included or excluded:

```yaml
keyword_overrides:
  always_include:
    - "Azure CLI"
    - "Resource Manager"
    - "Cosmos DB"

  always_exclude:
    - "GitHub"  # Too generic
    - "Microsoft"  # Not useful as a keyword
```

### Manual Corrections

Track misclassifications and override them directly:

```yaml
corrections:
  "Azure/azure-cli#12345": "defect"  # Was classified as inquiry
  "Azure/azure-sdk-for-python#67890": "enhancement"  # Was classified as defect
```

**Workflow:**
1. Run analysis and view dashboard
2. Find misclassified issues
3. Add issue ID → correct type to `corrections` section
4. Re-run analysis
5. The corrected issues will show with 99% confidence

## Interactive Workflow

### Step 1: Run Initial Analysis

```bash
npm run gather  # Fetch issues
npm run analyze # Classify with current rules
npm run dev     # View dashboard
```

### Step 2: Identify Issues

Browse the dashboard and look for:
- Issues classified with wrong type
- Keywords that are missing or incorrect
- Patterns specific to your team/domain

### Step 3: Update Custom Rules

Add to `classify_rules.custom.yaml`:

```yaml
# Example: You notice "deployment" issues are being missed
overrides:
  outage:
    keywords:
      - "deployment failed"
      - "deploy error"

# Example: Your team uses "spike" to mean investigation
overrides:
  inquiry:
    keywords:
      - "spike"
      - "investigation"
```

### Step 4: Add Manual Corrections

For specific misclassified issues:

```yaml
corrections:
  "company/repo#123": "outage"
  "company/repo#456": "enhancement"
```

### Step 5: Re-analyze and Verify

```bash
npm run analyze  # Re-run with new rules
# Refresh dashboard to see improvements
```

### Step 6: Iterate

Repeat steps 2-5 until classification quality is satisfactory.

## Understanding Weights

Weights determine how strongly a keyword signals a classification type:

- **0.7** - Weak signal (like "question" for inquiry)
- **1.0** - Standard signal (default)
- **1.5-2.0** - Strong signal (like modal verbs for enhancement)
- **2.5+** - Very strong signal (use for domain-specific overrides)

**Tips:**
- Use higher weights for domain-specific terms with non-obvious meanings
- Lower weights for terms that could mean multiple things
- Global overrides can set weights to override base rules

## Real-World Examples

### Example 1: Azure SDK Team

**Problem:** "SDK" issues are being classified as inquiries when they're usually bugs.

**Solution:**
```yaml
contexts:
  azure-sdk:
    defect:
      weight: 2.0
      keywords:
        - "sdk"
        - "client library"
        - "package version"
```

### Example 2: Support Team

**Problem:** Team uses "SEV0" to mean critical outage, but it's not in base rules.

**Solution:**
```yaml
overrides:
  outage:
    weight: 3.0  # Very high priority
    keywords:
      - "sev0"
      - "sev-0"
      - "severity 0"
```

### Example 3: Platform Team

**Problem:** "Migration" could mean enhancement OR outage depending on context.

**Solution:**
```yaml
contexts:
  platform:
    outage:
      weight: 2.0
      keywords:
        - "migration failed"
        - "migration error"

    enhancement:
      weight: 1.8
      keywords:
        - "migration plan"
        - "migrate to"
```

### Example 4: Keyword Cleanup

**Problem:** "GitHub Actions" is being extracted as a keyword but it's too generic.

**Solution:**
```yaml
keyword_overrides:
  always_exclude:
    - "GitHub"
    - "GitHub Actions"

  always_include:
    - "Actions Runner"  # More specific, actually useful
```

## Advanced: Per-Source Context Mapping

Currently, context is determined by the source type (github/jira/slack). To map specific repos to contexts:

1. Note the source field in `data/gathered.json`
2. Use that as the context name in your custom rules

For example, if you have issues from `Azure/azure-cli`:
- The source will be "github"
- You can create a context named "github" that applies to all GitHub issues
- Or modify the code to use repo name as context

## Validation

After adding custom rules, validate they're working:

```bash
# Re-analyze
npm run analyze

# Check the output
cat data/analyzed.json | jq '.issues[0].classification'
```

You should see:
- Corrected classifications have `confidence: 0.99`
- Issues matching your custom keywords have appropriate types
- Keywords listed match your expectations

## Tips for Success

1. **Start Small** - Add a few keywords at a time and test
2. **Use Corrections First** - For specific misclassifications, use corrections
3. **Patterns → Keywords** - When you see patterns, add to overrides
4. **Document Meanings** - Add comments explaining non-obvious terms
5. **Version Control** - Commit your custom rules to track changes
6. **Share Knowledge** - Team-specific rules help onboard new members

## Troubleshooting

**Q: My custom rules aren't being applied**
- Check file name is exactly `classify_rules.custom.yaml`
- Verify YAML syntax is valid
- Check indentation (use spaces, not tabs)
- Look for errors in console when running analyze

**Q: Corrections aren't working**
- Ensure issue ID format matches exactly (e.g., "Azure/azure-cli#123")
- Check that the type is valid (outage, defect, enhancement, inquiry, routing_issue)
- Re-run analyze after adding corrections

**Q: Context rules not applying**
- Verify context name matches the source field in gathered data
- Check `data/gathered.json` to see what source values are present
- Context names are case-sensitive

## Next Steps

- Build up your custom rules as you review dashboard results
- Share your `classify_rules.custom.yaml` with your team
- Use corrections to build training data for future improvements
- Consider adding new base categories if your domain needs them

---

For questions or issues, see the main README.md or file an issue.
