"""CLI entrypoint for the analyze module."""

import json
from pathlib import Path

import click

from analyze.classifier import classify_ticket
from analyze.entities import extract_services, extract_services_spacy, load_nlp
from analyze.models import AnalysisMetadata, AnalyzedData, TicketAnalysis
from analyze.people import build_service_graph, resolve_identities


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
    """Analyze consolidated support tickets with NLP."""
    gathered = json.loads(input_path.read_text())
    tickets = gathered.get("tickets", [])

    click.echo(f"Analyzing {len(tickets)} tickets...")

    known_services = set(services) if services else None
    nlp = load_nlp() if use_spacy_ner else None

    # Classify each ticket
    analyses: list[TicketAnalysis] = []
    for ticket in tickets:
        conversation_text = "\n".join(
            m.get("content", "") for m in ticket.get("conversation", [])
        )
        title = ticket.get("title", "")

        classification = classify_ticket(title, conversation_text)

        # Extract services
        full_text = f"{title}\n{conversation_text}"
        found_services = extract_services(full_text, known_services)
        if nlp:
            spacy_services = extract_services_spacy(nlp, full_text)
            found_services = sorted(set(found_services) | set(spacy_services))

        classification.services = found_services

        analyses.append(
            TicketAnalysis(
                id=ticket["id"],
                classification=classification,
            )
        )

    click.echo(f"Classified {len(analyses)} tickets")

    # Resolve people identities and build graph
    people_graph, _ = resolve_identities(tickets)
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
        tickets=analyses,
        people_graph=people_graph,
        service_graph=service_graph,
        metadata=AnalysisMetadata(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data.model_dump(mode="json", by_alias=True), indent=2)
    )
    click.echo(f"Written to {output_path}")
