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

        # Classify using NLP (which also extracts entities)
        classification = classify_issue(title, conversation_text, classifier_nlp)

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

        analyses.append(
            IssueAnalysis(
                id=issue["id"],
                classification=classification,
                people=people,
                created_at=issue.get("created_at"),
                updated_at=issue.get("updated_at"),
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
