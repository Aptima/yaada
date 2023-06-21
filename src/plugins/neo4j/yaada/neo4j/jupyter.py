# Copyright (c) 2023 Aptima, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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
