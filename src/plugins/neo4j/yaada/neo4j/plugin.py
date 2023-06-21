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

import logging
import typing

import jmespath
from neo4j import GraphDatabase
from pyhocon import ConfigTree
from tqdm import tqdm

from yaada.core import default_log_level
from yaada.core.analytic.plugin import AnalyticContextPlugin

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


def vertex_props(props, prop_prefix, id_field):
    kwargs = {}
    prop_frags = []

    kwarg = f"{prop_prefix}_{id_field}"
    q = "{" + id_field + ": $" + kwarg + "}"
    kwargs[kwarg] = props[id_field]
    for k, v in props.items():
        if k == id_field:
            continue
        kwarg = f"{prop_prefix}_{k}"
        prop_frags.append(f"{prop_prefix}.{k}= ${kwarg}")
        kwargs[kwarg] = v
    # q = '{' + ', '.join(prop_frags) + '}'

    return q, prop_frags, kwargs


def prepare_doc_merge(vertex_label, vertex_id_field, v_props, edges):
    v_q, prop_frags, kwargs = vertex_props(v_props, "v", vertex_id_field)

    q = f"MERGE (v:{vertex_label} " + v_q + ")\n"
    if len(prop_frags) > 0:
        q = q + "ON CREATE SET " + ",".join(prop_frags) + "\n"
        q = q + "ON MATCH SET " + ",".join(prop_frags) + "\n"

    for i in range(len(edges)):
        e = edges[i]
        ev_q, e_prop_frags, e_kwargs = vertex_props(
            e["target_vertex_props"], f"e{i}", e["target_id_field"]
        )
        q = q + f"MERGE (e{i}:{e['target_vertex_label']} {ev_q})\n"
        if len(e_prop_frags) > 0:
            q = q + "ON CREATE SET " + ",".join(e_prop_frags) + "\n"
            q = q + "ON MATCH SET " + ",".join(e_prop_frags) + "\n"
        q = q + f"MERGE (v)-[:{e['edge_label']}]->(e{i})\n"
        kwargs = dict(**kwargs, **e_kwargs)

    return q, kwargs


class Neo4jPlugin(AnalyticContextPlugin):
    def register(self, context):
        context.neo4j = self
        self.context = context
        self.config = context.config.hocon.get("yaada.context.plugin.neo4j", {})
        self.uri = self.config["uri"]
        self.database = self.config["database"]
        username = self.config.get("username", None)
        password = self.config.get("password", None)
        if username is None or password is None:
            self.driver = GraphDatabase.driver(self.uri)
        else:
            self.driver = GraphDatabase.driver(self.uri, auth=(username, password))
        self.init_schema()

    def merge_config(self, my_config: ConfigTree):
        self.config = ConfigTree.merge_configs(self.config, my_config)
        self.init_schema()

    @staticmethod
    def _add_vertex_index(tx, vertex_label, vertex_property, unique):
        if unique:
            tx.run(
                f"CREATE CONSTRAINT {vertex_label}_{vertex_property} IF NOT EXISTS FOR (a:{vertex_label}) REQUIRE a.{vertex_property} IS UNIQUE"
            )
        else:
            tx.run(
                f"CREATE INDEX {vertex_label}_{vertex_property} IF NOT EXISTS FOR (a:{vertex_label}) ON (a.{vertex_property})"
            )

    @staticmethod
    def _merge_doc(tx, vertex_label, vertex_id_field, vertex_props, edges, log_cypher):
        q, kwargs = prepare_doc_merge(
            vertex_label, vertex_id_field, vertex_props, edges
        )
        try:
            if log_cypher:
                print(f"cypher:\n{q}")
                print(f"args:\n{kwargs}")
            tx.run(q, **kwargs)
        except Exception as e:
            logger.error(f"\n{q}\n{kwargs}")
            raise e

    def get_vertex_indexes(self):
        for doc_type in self.config["doc_types"]:
            logger.info(f"Neo4j.doc_type: schema for {doc_type}")
            vertex_label = self.config["doc_types"][doc_type].get(
                "vertex_label", doc_type
            )
            for field in self.config["doc_types"][doc_type].get("fields", []):
                if field.get("type", None) == "property":
                    name = field.get("name")
                    index = field.get("index", False)
                    if index:
                        yield (vertex_label, name, True)
                elif field.get("type", None) == "edge":
                    target_vertex_label = field.get("target_vertex_label")
                    target_id = field.get("target_id")
                    yield (target_vertex_label, target_id, True)

    def init_schema(self):
        with self.context.neo4j.driver.session(database="neo4j") as session:
            for vertex_label, vertex_property, unique in self.get_vertex_indexes():
                session.execute_write(
                    self._add_vertex_index, vertex_label, vertex_property, unique
                )

    def extract_target_vertex_props(self, data, fields, target_id):
        if len(fields) == 0:
            return {target_id: data[target_id]}
        else:
            return {f["name"]: jmespath.search(f["path"], data) for f in fields}

    def doc2graph(self, doc):
        vertex_props = {}
        edges = []
        vertex_id_field = "id"
        doc_type = doc["doc_type"]

        vertex_label = self.config["doc_types"][doc_type].get("vertex_label", doc_type)
        for field in self.config["doc_types"][doc_type].get("fields", []):
            if field.get("type", None) == "property":
                name = field.get("name")
                path = field.get("path")
                vertex_props[name] = jmespath.search(path, doc)
                index = field.get("index", False)
                if index:
                    vertex_id_field = name
                if not vertex_props[name]:
                    vertex_props[name] = field.get("default", "")
                if not vertex_props[name]:
                    continue
            elif field.get("type", None) == "edge":
                target_vertex_label = field.get("target_vertex_label")
                edge_label = field.get("edge_label")
                target_id = field.get("target_id")
                path = field.get("path")
                targets = jmespath.search(path, doc)
                if not targets:
                    continue
                if not isinstance(targets, typing.List):
                    targets = [targets]
                for val in targets:
                    if isinstance(val, dict):
                        e = dict(
                            target_vertex_label=target_vertex_label,
                            edge_label=edge_label,
                            target_id_field=target_id,
                            target_vertex_props=self.extract_target_vertex_props(
                                val, field.get("target_property_fields", []), target_id
                            ),
                        )
                        if e["target_vertex_props"].get(target_id, None) is not None:
                            edges.append(e)
                    else:
                        edges.append(
                            dict(
                                target_vertex_label=target_vertex_label,
                                edge_label=edge_label,
                                target_id_field=target_id,
                                target_vertex_props={target_id: val},
                            )
                        )

        return vertex_label, vertex_id_field, vertex_props, edges

    def ingest(self, docs, progress=False, log_cypher=False):
        with self.context.neo4j.driver.session(database="neo4j") as session:
            for doc in tqdm(docs, disable=not progress):
                vertex_label, vertex_id_field, vertex_props, edges = self.doc2graph(doc)
                session.execute_write(
                    self._merge_doc,
                    vertex_label,
                    vertex_id_field,
                    vertex_props,
                    edges,
                    log_cypher,
                )

    def node_counts(self):
        with self.driver.session() as s:
            result = s.run(
                """
            MATCH (n)
            RETURN labels(n) as labels,count(labels(n)) as count
            """
            )
            return [dict(**r) for r in result]

    def edge_counts(self):
        with self.driver.session() as s:
            result = s.run(
                """
            MATCH (n)-[e]->(n2)
            RETURN type(e) as edge_type,count(type(e)) as count
            """
            )
            return [dict(**r) for r in result]

    def source_dest_edge_counts(self):
        with self.driver.session() as s:
            result = s.run(
                """
            MATCH (n) -[e]-> (n2)
            RETURN labels(n) as source,type(e) as edge, count(type(e)) as count, labels(n2) as dest
            """
            )
            return [dict(**r) for r in result]

    def delete_nodes(self, node_label):
        with self.driver.session() as s:
            result = s.run(
                """
            MATCH (n WHERE $node_label IN labels(n))
            DETACH DELETE n
            """,
                node_label=node_label,
            )
            return [dict(**r) for r in result]
