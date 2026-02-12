"""CLI entrypoint for the analyze module."""

import json
from pathlib import Path

import click

from analyze.classifier import classify_issue
from analyze.entities import extract_keywords, extract_keywords_spacy, load_nlp
from analyze.models import AnalysisMetadata, AnalyzedData, IssueAnalysis, IssuePerson
from analyze.people import build_keyword_graph, resolve_identities
from analyze.suggest import suggest_rules


@click.command()
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    default="data/gathered.json",
    help="Path to gathered JSON file",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default="data/analyzed.json",
    help="Output JSON file path",
)
@click.option(
    "--keywords",
    multiple=True,
    help="Known keyword names to look for (can be repeated)",
)
@click.option(
    "--use-spacy-ner/--no-spacy-ner",
    default=False,
    help="Use spaCy NER for keyword extraction (slower)",
)
def main(
    input_path: Path,
    output_path: Path,
    keywords: tuple[str, ...],
    use_spacy_ner: bool,
) -> None:
    """Analyze consolidated support issues with NLP."""
    gathered = json.loads(input_path.read_text())
    # Support both "issues" (new) and "tickets" (legacy) for backwards compatibility
    issues = gathered.get("issues") or gathered.get("tickets", [])

    click.echo(f"Analyzing {len(issues)} issues...")

    known_keywords = set(keywords) if keywords else None
    nlp = load_nlp() if use_spacy_ner else None

    # Load NLP model once for all classifications
    classifier_nlp = load_nlp()

    # Classify each issue
    analyses: list[IssueAnalysis] = []
    for issue in issues:
        conversation_text = "\n".join(
            m.get("content", "") for m in issue.get("conversation", [])
        )
        title = issue.get("title", "")
        issue_id = issue.get("id", "")

        # Extract context from issue source (e.g., "github", "jira", "slack")
        # Can be used for context-specific classification rules
        context = issue.get("source", {}).get("source") if isinstance(issue.get("source"), dict) else None

        # Classify using NLP (which also extracts entities)
        # Pass issue_id for manual corrections and context for context-specific rules
        classification = classify_issue(
            title,
            conversation_text,
            classifier_nlp,
            issue_id=issue_id,
            context=context,
        )

        # Enhance with additional keyword extraction
        full_text = f"{title}\n{conversation_text}"
        found_keywords = extract_keywords(full_text, known_keywords)
        if use_spacy_ner and nlp:
            spacy_keywords = extract_keywords_spacy(nlp, full_text)
            found_keywords = sorted(set(found_keywords) | set(spacy_keywords))

        # Merge classifier's extracted entities with explicit keyword extraction
        all_keywords = sorted(set(classification.keywords) | set(found_keywords))
        classification.keywords = all_keywords

        # Extract people data from the issue
        people = [
            IssuePerson(
                source=person.get("source", ""),
                source_id=person.get("source_id", ""),
                name=person.get("name", ""),
                email=person.get("email"),
                role=person.get("role", ""),
            )
            for person in issue.get("people", [])
        ]

        # Extract primary source URL from references
        url = None
        references = issue.get("references", [])
        if references:
            url = references[0].get("url")

        analyses.append(
            IssueAnalysis(
                id=issue["id"],
                classification=classification,
                people=people,
                created_at=issue.get("created_at"),
                updated_at=issue.get("updated_at"),
                url=url,
                title=issue.get("title"),
            )
        )

    click.echo(f"Classified {len(analyses)} issues")

    # Resolve people identities and build graph
    people_graph, _ = resolve_identities(issues)
    click.echo(
        f"Resolved {len(people_graph.nodes)} unique people "
        f"with {len(people_graph.edges)} relationships"
    )

    # Build keyword co-occurrence graph
    keyword_graph = build_keyword_graph(analyses)
    click.echo(
        f"Found {len(keyword_graph.nodes)} keywords "
        f"with {len(keyword_graph.edges)} co-occurrences"
    )

    # Write output
    data = AnalyzedData(
        issues=analyses,
        people_graph=people_graph,
        keyword_graph=keyword_graph,
        metadata=AnalysisMetadata(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data.model_dump(mode="json", by_alias=True), indent=2)
    )
    click.echo(f"Written to {output_path}")


@click.command()
@click.option(
    "--analyzed",
    "analyzed_path",
    type=click.Path(exists=True, path_type=Path),
    default="data/analyzed.json",
    help="Path to analyzed JSON file with classifications",
)
@click.option(
    "--gathered",
    "gathered_path",
    type=click.Path(exists=True, path_type=Path),
    default="data/gathered.json",
    help="Path to gathered JSON file (needed for learning)",
)
@click.option(
    "--interactive/--no-interactive",
    default=False,
    help="Interactive mode: review and correct low-confidence issues",
)
@click.option(
    "--confidence-threshold",
    type=float,
    default=0.5,
    help="Flag classifications below this confidence for review",
)
@click.option(
    "--context",
    type=str,
    default=None,
    help="Context name for learned rules (e.g., 'azure-platform')",
)
def suggest(
    analyzed_path: Path,
    gathered_path: Path,
    interactive: bool,
    confidence_threshold: float,
    context: str | None,
) -> None:
    """Analyze classification results and learn from corrections.

    Two modes:
    1. Report mode (default): Show classification quality and suggestions
    2. Interactive mode (--interactive): Review issues and learn from corrections
    """
    from analyze.improve import (
        analyze_classification_quality,
        apply_learned_patterns,
        learn_from_correction,
    )

    # Analyze classification quality
    results = analyze_classification_quality(analyzed_path, confidence_threshold)

    if not results["issues"]:
        click.echo("No issues found in analyzed data")
        return

    click.echo(f"Analyzing {len(results['issues'])} classified issues...\n")

    # Report findings
    click.echo("Classification Summary:")
    for issue_type, issue_list in sorted(
        results["by_type"].items(), key=lambda x: -len(x[1])
    ):
        avg_conf = (
            sum(i["classification"]["confidence"] for i in issue_list)
            / len(issue_list)
            if issue_list
            else 0
        )
        click.echo(
            f"  {issue_type:15s}: {len(issue_list):4d} issues (avg confidence: {avg_conf:.2f})"
        )

    if not results["low_confidence"]:
        click.echo("\nAll classifications above threshold!")
        return

    click.echo(
        f"\n{len(results['low_confidence'])} low-confidence classifications (< {confidence_threshold})"
    )

    if not interactive:
        # Just show summary
        for item in results["low_confidence"][:10]:
            click.echo(
                f"  [{item['type']:12s}] {item['confidence']:.2f} - {item['summary']}"
            )
        if len(results["low_confidence"]) > 10:
            click.echo(f"  ... and {len(results['low_confidence']) - 10} more")
        click.echo("\nRun with --interactive to review and correct these")
        return

    # Interactive mode - review and learn
    click.echo("\n=== Interactive Learning Mode ===")
    click.echo("Review low-confidence issues and provide corrections.\n")

    corrections = []
    issue_types = ["outage", "defect", "enhancement", "inquiry", "routing_issue", "action", "skip"]

    for idx, item in enumerate(results["low_confidence"][:20], 1):  # Max 20
        click.echo(f"\n[{idx}/{min(20, len(results['low_confidence']))}]")
        click.echo(f"ID: {item['id']}")
        click.echo(f"Current: {item['type']} (confidence: {item['confidence']:.2f})")
        click.echo(f"Summary: {item['summary']}")

        # Find full issue
        full_issue = next(
            (i for i in results["issues"] if i.get("id") == item["id"]), None
        )

        if not full_issue:
            continue

        click.echo(f"\nWhat should this be? ({'/'.join(issue_types)})")
        correct_type = click.prompt("Type", type=click.Choice(issue_types), default="skip")

        if correct_type == "skip":
            continue

        if correct_type == item["type"]:
            click.echo("  (Same as current, skipping)")
            continue

        # Learn from this correction
        learned = learn_from_correction(full_issue, correct_type, gathered_path)
        click.echo(f"  Learned keywords: {', '.join(learned['keywords'][:3])}")

        corrections.append(
            {
                "issue_id": item["id"],
                "wrong_type": item["type"],
                "correct_type": correct_type,
                "learned_keywords": learned["keywords"],
            }
        )

    if not corrections:
        click.echo("\nNo corrections made")
        return

    # Apply learned patterns
    click.echo(f"\nApplying {len(corrections)} corrections...")
    rules_path = Path(__file__).parent.parent.parent / "classify_rules.custom.yaml"
    apply_learned_patterns(corrections, rules_path, context=context)

    click.echo(f"Updated {rules_path.name}")
    if context:
        click.echo(f"  Added patterns to context: {context}")
    click.echo(f"  Saved {len(corrections)} corrections")
    click.echo("\n  Re-run analyze to see improvements")
