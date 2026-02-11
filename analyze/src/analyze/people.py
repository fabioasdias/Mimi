"""Identity resolution and people graph building.

Correlates people across sources by email (exact) and display name (fuzzy).
Builds a networkx graph of people ↔ issues ↔ keywords.
"""

from uuid import uuid4

import networkx as nx
from rapidfuzz import fuzz

from analyze.models import (
    GraphEdge,
    Identity,
    PeopleGraph,
    PersonNode,
    KeywordEdge,
    KeywordGraph,
    KeywordNode,
    IssueAnalysis,
)

# Minimum fuzzy match score to consider names as the same person
NAME_MATCH_THRESHOLD = 85


def _person_key(source: str, source_id: str) -> str:
    return f"{source}:{source_id}"


def resolve_identities(
    gathered_issues: list[dict],
) -> tuple[PeopleGraph, dict[str, str]]:
    """Resolve people identities across sources.

    Returns:
        - PeopleGraph with merged person nodes
        - Mapping from (source:source_id) -> person node id
    """
    # Collect all raw person entries
    raw_people: list[dict] = []
    for issue in gathered_issues:
        for person in issue.get("people", []):
            raw_people.append(person)

    # Build identity groups using union-find
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Index by email and name
    by_email: dict[str, list[str]] = {}
    by_name: dict[str, list[tuple[str, str]]] = {}  # name -> [(key, name)]

    for person in raw_people:
        key = _person_key(person["source"], person["source_id"])
        parent.setdefault(key, key)

        email = person.get("email")
        if email:
            email_lower = email.lower()
            if email_lower in by_email:
                for other_key in by_email[email_lower]:
                    union(key, other_key)
            by_email.setdefault(email_lower, []).append(key)

        name = person.get("name", "")
        if name:
            name_lower = name.lower()
            by_name.setdefault(name_lower, []).append((key, name))

    # Fuzzy name matching across different sources
    name_groups = list(by_name.values())
    for i, group_a in enumerate(name_groups):
        for group_b in name_groups[i + 1 :]:
            for key_a, name_a in group_a:
                for key_b, name_b in group_b:
                    # Only match across different sources
                    src_a = key_a.split(":")[0]
                    src_b = key_b.split(":")[0]
                    if src_a == src_b:
                        continue

                    score = fuzz.ratio(name_a.lower(), name_b.lower())
                    if score >= NAME_MATCH_THRESHOLD:
                        union(key_a, key_b)

    # Build merged person nodes
    groups: dict[str, list[dict]] = {}
    key_to_person: dict[str, dict] = {}
    for person in raw_people:
        key = _person_key(person["source"], person["source_id"])
        root = find(key)
        groups.setdefault(root, []).append(person)
        key_to_person[key] = person

    nodes: list[PersonNode] = []
    key_to_node_id: dict[str, str] = {}

    for root, members in groups.items():
        node_id = str(uuid4())

        # Pick the best label (prefer one with email)
        label = members[0].get("name", "Unknown")
        for m in members:
            if m.get("email"):
                label = m["name"]
                break

        identities: list[Identity] = []
        seen: set[str] = set()
        for m in members:
            mid = _person_key(m["source"], m["source_id"])
            if mid not in seen:
                seen.add(mid)
                identities.append(
                    Identity(
                        source=m["source"],
                        source_id=m["source_id"],
                        email=m.get("email"),
                        display_name=m.get("name"),
                    )
                )
            key_to_node_id[mid] = node_id

        nodes.append(
            PersonNode(id=node_id, label=label, identities=identities)
        )

    # Build edges (person → issue)
    edges: list[GraphEdge] = []
    for issue in gathered_issues:
        issue_id = issue["id"]
        seen_edges: set[tuple[str, str]] = set()
        for person in issue.get("people", []):
            key = _person_key(person["source"], person["source_id"])
            node_id = key_to_node_id.get(key)
            if node_id and (node_id, issue_id) not in seen_edges:
                seen_edges.add((node_id, issue_id))
                edges.append(
                    GraphEdge(
                        **{
                            "from": node_id,
                            "to": issue_id,
                            "role": person.get("role", "participant"),
                        }
                    )
                )

    # Add same-identity edges between merged nodes
    for root, members in groups.items():
        sources = {m["source"] for m in members}
        if len(sources) > 1:
            # This person was found in multiple sources
            node_id = key_to_node_id[_person_key(members[0]["source"], members[0]["source_id"])]
            for m in members[1:]:
                other_key = _person_key(m["source"], m["source_id"])
                other_node = key_to_node_id.get(other_key)
                if other_node and other_node == node_id:
                    # Same node — no need for an edge
                    continue

    return PeopleGraph(nodes=nodes, edges=edges), key_to_node_id


def build_keyword_graph(analyses: list[IssueAnalysis]) -> KeywordGraph:
    """Build a co-occurrence graph of keywords from issue analyses."""
    g = nx.Graph()

    for analysis in analyses:
        keywords = analysis.classification.keywords
        for kw in keywords:
            if not g.has_node(kw):
                g.add_node(kw, issue_count=0)
            g.nodes[kw]["issue_count"] += 1

        # Add co-occurrence edges
        for i, kw_a in enumerate(keywords):
            for kw_b in keywords[i + 1 :]:
                if g.has_edge(kw_a, kw_b):
                    g[kw_a][kw_b]["co_occurrence"] += 1
                else:
                    g.add_edge(kw_a, kw_b, co_occurrence=1)

    nodes = [
        KeywordNode(id=n, issue_count=g.nodes[n].get("issue_count", 0))
        for n in g.nodes
    ]
    edges = [
        KeywordEdge(
            **{
                "from": u,
                "to": v,
                "co_occurrence": d.get("co_occurrence", 0),
            }
        )
        for u, v, d in g.edges(data=True)
    ]

    return KeywordGraph(nodes=nodes, edges=edges)
