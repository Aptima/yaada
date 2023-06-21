import dash_cytoscape as cyto
from dash import html
from jupyter_dash import JupyterDash


def label_getter(data):
    label = data["label"]
    name = None
    if "name" in data:
        name = data["name"]
    elif "title" in data:
        name = data["title"]
    else:
        name = data["id"]

    if label == name:
        return f"{label}"
    else:
        return f"{label} ({name})"


def nx2cyto(G, label_func=label_getter):
    """
    Transform a NetworkX graph into format that Dash Cytoscape expects.
    """
    # pos=nx.fruchterman_reingold_layout(G, iterations=2000, threshold=1e-10)
    nodes = [
        {"data": {"id": node_id, "label": label_func(node_data)}}
        for node_id, node_data in G.nodes(data=True)
    ]

    edges = []
    for source, target, edge_data in G.edges(data=True):
        edges.append(
            {"data": {"source": source, "target": target, "label": edge_data["type"]}}
        )

    elements = nodes + edges

    return elements


def vis_nx(G):
    """
    Visualize a NetworkX Graph in Jupyter
    """
    app = JupyterDash(__name__)
    app.layout = html.Div(
        [
            cyto.Cytoscape(
                id="cytoscape-two-nodes",
                layout={
                    "name": "cose",
                    "idealEdgeLength": 100,
                    "nodeOverlap": 20,
                    "refresh": 20,
                    "fit": True,
                    "padding": 30,
                    "randomize": False,
                    "componentSpacing": 100,
                    "nodeRepulsion": 400000,
                    "edgeElasticity": 100,
                    "nestingFactor": 5,
                    "gravity": 80,
                    "numIter": 1000,
                    "initialTemp": 200,
                    "coolingFactor": 0.95,
                    "minTemp": 1.0,
                },
                style={"width": "100%", "height": "600px"},
                elements=nx2cyto(G),
                stylesheet=[
                    {
                        "selector": "node",
                        "style": {
                            "label": "data(label)",
                            # 'width':2,
                            # 'hight':2
                        },
                    },
                    {
                        "selector": "edge",
                        "style": {
                            "label": "data(label)",
                            "target-arrow-shape": "vee",
                            "curve-style": "bezier"
                            # 'arrow-scale': 10,
                            # 'line-color': 'red',
                            # 'target-arrow-color': 'red',
                        },
                    },
                ],
            )
        ]
    )
    app.run_server(mode="inline")
