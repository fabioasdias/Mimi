"""CLI entrypoint for the analyze module."""

import json
from pathlib import Path

import click

from analyze.classifier import classify_issue
from analyze.entities import extract_services, extract_services_spacy, load_nlp
from analyze.models import AnalysisMetadata, AnalyzedData, IssueAnalysis
from analyze.people import build_service_graph, resolve_identities
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
    "--services",
    multiple=True,
    help="Known service names to look for (can be repeated)",
)
@click.option(
    "--use-spacy-ner/--no-spacy-ner",
    default=False,
    help="Use spaCy NER for service extraction (slower)",
)
def main(
    input_path: Path,
    output_path: Path,
    services: tuple[str, ...],
    use_spacy_ner: bool,
) -> None:
    """Analyze consolidated support issues with NLP."""
    gathered = json.loads(input_path.read_text())
    # Support both "issues" (new) and "tickets" (legacy) for backwards compatibility
    issues = gathered.get("issues") or gathered.get("tickets", [])

    click.echo(f"Analyzing {len(issues)} issues...")

    known_services = set(services) if services else None
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

        # Classify using NLP (which also extracts entities)
        classification = classify_issue(title, conversation_text, classifier_nlp)

        # Enhance with additional service extraction
        full_text = f"{title}\n{conversation_text}"
        found_services = extract_services(full_text, known_services)
        if use_spacy_ner and nlp:
            spacy_services = extract_services_spacy(nlp, full_text)
            found_services = sorted(set(found_services) | set(spacy_services))

        # Merge classifier's extracted entities with explicit service extraction
        all_services = sorted(set(classification.services) | set(found_services))
        classification.services = all_services

        analyses.append(
            IssueAnalysis(
                id=issue["id"],
                classification=classification,
            )
        )

    click.echo(f"Classified {len(analyses)} issues")

    # Resolve people identities and build graph
    people_graph, _ = resolve_identities(issues)
    click.echo(
        f"Resolved {len(people_graph.nodes)} unique people "
        f"with {len(people_graph.edges)} relationships"
    )

    # Build service co-occurrence graph
    service_graph = build_service_graph(analyses)
    click.echo(
        f"Found {len(service_graph.nodes)} services "
        f"with {len(service_graph.edges)} co-occurrences"
    )

    # Write output
    data = AnalyzedData(
        issues=analyses,
        people_graph=people_graph,
        service_graph=service_graph,
        metadata=AnalysisMetadata(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data.model_dump(mode="json", by_alias=True), indent=2)
    )
    click.echo(f"Written to {output_path}")


@click.command()
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    default="data/gathered.json",
    help="Path to gathered JSON file",
)
def suggest(input_path: Path) -> None:
    """Suggest new classification keywords based on gathered data."""
    click.echo(f"Analyzing {input_path} for keyword suggestions...")

    results = suggest_rules(input_path)

    click.echo(f"\nAnalyzed {results['total_issues']} issues")
    click.echo("\nSentiment distribution:")
    for sentiment, count in results["sentiment_distribution"].items():
        pct = count / results["total_issues"] * 100
        click.echo(f"  {sentiment}: {count} ({pct:.1f}%)")

    click.echo("\nTop 30 suggested keywords:")
    for keyword, freq in results["suggested_keywords"]:
        click.echo(f"  {keyword:20s} ({freq} occurrences)")

    click.echo(
        "\nTo add keywords: edit analyze/classify_rules.yaml and re-run analyze"
    )
