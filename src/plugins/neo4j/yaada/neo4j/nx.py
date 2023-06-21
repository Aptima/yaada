import networkx as nx


def neo4jnx(g):
    """
    Transform Neo4j query response into a NetworkX MultiDiGraph.
    """
    G = nx.MultiDiGraph()
    for node in g.nodes:
        label = list(node.labels)[0]
        G.add_node(node.element_id, label=label, **node)

    for rel in g.relationships:
        G.add_edge(
            rel.start_node.element_id,
            rel.end_node.element_id,
            key=rel.element_id,
            type=rel.type,
            properties=rel._properties,
        )
    return G
