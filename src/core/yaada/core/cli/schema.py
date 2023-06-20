# Copyright (c) 2022 Aptima, Inc.
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
import sys

import click
from ruamel.yaml.main import round_trip_dump as yaml_dump
from yaada.core.cli import common
from yaada.core.cli.project import Project


@common.schema.command()
@click.argument(
    "source",
    type=click.Path(
        exists=True, readable=True, resolve_path=True, dir_okay=False, file_okay=True
    ),
    required=False,
)
@click.option("--doc-type", type=click.STRING, default=None)
@click.option("--ldjson", "-l", is_flag=True, default=False)
@click.option("--produce-yaml", "-y", is_flag=True, default=False)
@click.option("--include-document-base", "-i", is_flag=True, default=False)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def infer(source, doc_type, ldjson, produce_yaml, include_document_base, env):
    """Infer a json-schema from file or stdin"""
    project = Project(env=env)
    from yaada.core.config import YAADAConfig
    from yaada.core.schema import SchemaManager

    config = YAADAConfig(project.config["config"], overrides=project.config)
    sm = SchemaManager(config)

    def gen(lines):
        for line in lines:
            yield json.loads(line.strip())

    def infer(f, is_ldjson, produce_yaml):
        s = None
        if not is_ldjson:
            data = json.load(f)
            s = sm.json_schema_from_data(
                [data],
                # to_json=True,
                doc_type=doc_type,
                include_document_base=include_document_base,
            )
        else:
            s = sm.json_schema_from_data(
                gen(f.readlines()),
                # to_json=True,
                doc_type=doc_type,
                include_document_base=include_document_base,
            )
        if produce_yaml:
            print(yaml_dump(s))
        else:
            print(json.dumps(s, indent=2))

    if source is not None:
        with open(source) as f:
            infer(f, ldjson, produce_yaml)
    else:
        infer(sys.stdin, ldjson, produce_yaml)


@common.schema.command()
@click.argument("doc_type", type=click.STRING, required=False, default=None)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def show(doc_type, env):
    """Print the json schema for doc_type"""
    project = Project(env=env)
    from yaada.core.config import YAADAConfig
    from yaada.core.schema import SchemaManager

    config = YAADAConfig(project.config["config"], overrides=project.config)
    sm = SchemaManager(config)

    if doc_type is None:
        print(list(sm.doc_type_schemas.keys()))
    else:
        s = sm.get_document_schema(doc_type)
        print(json.dumps(s, indent=2))
