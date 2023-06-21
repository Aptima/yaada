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

import json
from collections import OrderedDict

import click

from yaada.core.cli import common
from yaada.core.cli.project import Project


def get_property_type(k, v):
    if "type" not in v:
        if "$ref" in v:
            if v["$ref"] == "#/definitions/artifacts":
                return "Artifact"
            elif v["$ref"] == "#/definitions/refs":
                return "TextReferences"
            elif v["$ref"] == "#/definitions/document-links":
                return "DocumentLinks"
            elif v["$ref"] == "#/definitions/document-link":
                return "DocumentLink"

        else:
            return "Any"
    if v["type"] == "array":
        if "items" in v:
            return f"array<{v['items'].get('type','Any')}>"
    return v["type"]


def get_property_link(k, v):
    if "type" not in v:
        if "$ref" in v:
            if v["$ref"] == "#/definitions/document-links":
                return k, v.get("title", "Any")
            elif v["$ref"] == "#/definitions/document-link":
                return k, v.get("title", "Any")
            elif v["$ref"].startswith("#/links/"):
                return k, v.get("title", "Any")


def generate_datamodel_section(
    project, config, schema_manager, doc_type=None, distance=1
):
    from textwrap import dedent

    import networkx as nx

    print(
        dedent(
            """\
  # Data Model
  """
        )
    )
    print(
        dedent(
            """\
  ```mermaid
  graph LR
  """
        )
    )
    G = schema_manager.schema_graph()

    if doc_type is not None:
        # geenrate the neighborhood graph from the doc_type
        G = nx.generators.ego_graph(G, doc_type, radius=distance, undirected=True)

    for dt in G.nodes:
        print(f"    {dt}[{dt}]")
        for src, dest, data in G.out_edges(dt, data=True):
            if (
                doc_type is None or src == doc_type or dest == doc_type
            ):  # if we're showing a doc_type specific graph, only show edges that contect to that doc_type
                print(f"    {src} -- {data['label']} --> {dest}")

    print("```")


def generate_analytics_section(project, config, schema_manager, analytics_dict):
    from textwrap import dedent

    print(
        dedent(
            """\
  # Analytics
  """
        )
    )

    print(
        dedent(
            """\
  ```mermaid
  graph LR
  """
        )
    )
    for name, rec in analytics_dict.items():
        print(f"    {name}({name})")

        for c in rec["calls"]:
            print(f"    {name}-- calls --> {c}")

    print("```")
    for analytic_name, rec in analytics_dict.items():
        print(f"## `{analytic_name}`\n")

        desc = rec["desc"]
        print(desc["description"] + "\n")

        print("Paramater schema:\n")
        print("```")
        print(
            json.dumps(
                desc.get("request_schema", {})
                .get("properties", {})
                .get("parameters", {})
                .get("properties", {}),
                indent=2,
            )
        )
        print("```")

        if len(rec["calls"]) > 0:
            print(
                dedent(
                    f"""\
      ```mermaid
      graph TD
          {analytic_name}({analytic_name})
      """
                )
            )
            for c in rec["calls"]:
                print(f"   {analytic_name}-- calls --> {c}")

            print("```")


def generate_pipelines_section(
    project, config, schema_manager, analytics_dict, pipelines_dict
):
    from textwrap import dedent

    print(
        dedent(
            """\
  # Processing Pipelines
  """
        )
    )

    for name, p in pipelines_dict.items():
        print(f"## Pipeline for `{name}`")
        if len(p) > 0:
            print(
                dedent(
                    """\
      ```mermaid
      graph TD
      """
                )
            )
            last_step = None
            for i in range(len(p)):
                step = p[i]
                # print("    subgraph Pipeline")
                print(f"    {i}([{step['name']}])")
                if last_step is not None:
                    print(f"    {last_step} -- pipeline --> {i}")
                for c in step["calls"]:
                    print(f"    {c}({c})")
                    print(f"    {i} -- analytic --> {c}")
                last_step = i
            print("```")
        else:
            print("N/A")

        # last_step = None
        # for i in range(len(p)):
        #   step = p[i]
        #   print("    subgraph Analytics")
        #   for c in step['calls']:
        #     print(f"    {c}({c})")
        #     print(f"    {i} -- calls --> {c}")
        #   last_step = i
        #   print("    end")


def get_analytics_model(project, context):
    from yaada.core.analytic import analytic_description, get_analytic, get_analytics

    all_analytics = get_analytics()
    analytics_dict = OrderedDict()
    for analytic_name in all_analytics:
        rec = dict(
            name=analytic_name, desc=analytic_description(analytic_name), calls=set()
        )
        a = get_analytic(analytic_name)
        names_used = a.run.__func__.__code__.co_names
        if "async_exec_analytic" in names_used or "sync_exec_analytic" in names_used:
            constants = a.run.__func__.__code__.co_consts
            for c in constants:
                if c in all_analytics:
                    rec["calls"].add(c)

        analytics_dict[analytic_name] = rec
    return analytics_dict


def get_pipelines_model(project, context, analytic_model):
    pipelines_dict = OrderedDict()
    for doc_type, p in context._document_pipeline.document_pipelines.items():
        steps = []
        for s in p:
            step = dict(name=s.name, parameters=s.parameters, calls=set())
            names_used = s.pipeline_processor.process.__func__.__code__.co_names
            if (
                "async_exec_analytic" in names_used
                or "sync_exec_analytic" in names_used
            ):
                constants = s.pipeline_processor.process.__func__.__code__.co_consts
                for c in constants:
                    if c in analytic_model:
                        step["calls"].add(c)
            steps.append(step)
        pipelines_dict[doc_type] = steps
    return pipelines_dict


@common.md.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--doc-type", type=click.STRING, default=None)
@click.option("--distance", type=click.INT, default=1)
def datamodel(env, doc_type, distance):
    """Generate markdown for document schemas"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=True, overrides=project.config, connect_to_services=False
    )
    generate_datamodel_section(
        project, context.config, context.schema_manager, doc_type, distance
    )


@common.md.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def analytics(env):
    """Generate markdown for analytics"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=True, overrides=project.config, connect_to_services=False
    )

    analytics_model = get_analytics_model(project, context)
    generate_analytics_section(
        project, context.config, context.schema_manager, analytics_model
    )


@common.md.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def pipelines(env):
    """Generate markdown for processing pipelines"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=True, overrides=project.config, connect_to_services=False
    )

    analytics_model = get_analytics_model(project, context)
    pipelines_model = get_pipelines_model(project, context, analytics_model)
    generate_pipelines_section(
        project,
        context.config,
        context.schema_manager,
        analytics_model,
        pipelines_model,
    )
