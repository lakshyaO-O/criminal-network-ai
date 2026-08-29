"""Graph construction from entity-relationship data."""

import networkx as nx
from typing import List, Dict, Any


def build_graph(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) nx.Graph:
    """Build a NetworkX graph from extracted entities and relationships.

    Args:
        entities: List of entity dicts from entity extraction.
        relationships: List of relationship dicts.

    Returns:
        NetworkX Graph object representing the criminal network.
    """
    G = nx.Graph()

    # Add nodes
    for entity in entities:
        G.add_node(
            entity['text'],
            type=entity['type'],
            confidence=entity.get('confidence', 0.0),
        )

    # Add edges from relationships
    for rel in relationships:
        source = rel.get('source', '')
        target = rel.get('target', '')
        weight = rel.get('weight', 1.0)

        if source in G and target in G:
            G.add_edge(source, target, weight=weight)
        else:
            # Add missing nodes
            if source not in G:
                G.add_node(source)
            if target not in G:
                G.add_node(target)
            G.add_edge(source, target, weight=weight)

    return G


def compute_centrality(G: nx.Graph) -> Dict[str, float]:
    """Compute degree centrality for network nodes.

    Args:
        G: NetworkX graph.

    Returns:
        Dictionary mapping node names to centrality scores.
    """
    return nx.degree_centrality(G)