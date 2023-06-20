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

import copy
import importlib
import logging
import os
from glob import glob

from deepmerge import Merger
from genson import SchemaBuilder
from jsonschema.exceptions import ValidationError
from openapi_schema_validator import (  # we use OpenAPI 3.0 validation because that is what Connexion supports. Once Connexion supports 3.1, we should consider upgrading
    OAS30Validator,
    validate,
)
from ruamel.yaml import YAML
from yaada.core import default_log_level, utility
from yaada.core.config import YAADAConfig

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


yaml = YAML(typ="safe")

DOCUMENT_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "document.yaml")
ANALYTIC_REQUEST_PATH = os.path.join(os.path.dirname(__file__), "analytic_request.yaml")
SCHEMA_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schemaschema.yaml")
base_document_schema = yaml.load(open(DOCUMENT_SCHEMA_PATH, "r"))
analytic_request_schema = yaml.load(open(ANALYTIC_REQUEST_PATH, "r"))
schemaschema = yaml.load(open(SCHEMA_SCHEMA_PATH, "r"))

# dynamically update the schema schema to allow top level to have links and definitions sections.

schemaschema["definitions"]["SchemaRoot"] = dict(
    **schemaschema["definitions"]["Schema"]
)
schemaschema["definitions"]["SchemaRoot"]["properties"]["definitions"] = schemaschema[
    "definitions"
]["Schema"]["properties"]["properties"]
schemaschema["definitions"]["SchemaRoot"]["properties"]["links"] = schemaschema[
    "definitions"
]["Schema"]["properties"]["properties"]


class UnresolvedReference(Exception):
    """Exception raised when a schema refers to a definition or link that isn't in common defs/links or schema itself"""

    def __init__(self, ref):
        self.message = f"Unable to resolve schema reference '{ref}' "
        super().__init__(self.message)


class InvalidSchema(Exception):
    """Exception raised when a schema is invalid for reasons such as unresolved references."""

    def __init__(self, schema_name, reason):
        self.message = f"'{schema_name}' invalid due to:\n  {reason}"
        super().__init__(self.message)


DEFINITION_PREFIX = "#/definitions/"
LINK_PREFIX = "#/links/"


class SchemaManager:
    DEFINITION_PREFIX = DEFINITION_PREFIX
    LINK_PREFIX = LINK_PREFIX

    def __init__(self, config: YAADAConfig):
        self.doc_type_schemas = {}

        self.base_document_schema = base_document_schema
        self.common_definitions = self.base_document_schema.get("definitions", {})
        self.common_links = self.base_document_schema.get("links", {})
        self.analytic_request_schema = analytic_request_schema
        self._load_definitions_dir(
            os.path.join(os.path.dirname(__file__), "definitions")
        )
        self._load_links_dir(os.path.join(os.path.dirname(__file__), "links"))
        self._find_and_register(config)
        self.config = config

        self._load_schema_dir(config.schema_directory)

    def validate_document(self, doc):
        s = self.get_document_schema(doc["doc_type"])
        validate(doc, s, cls=OAS30Validator)

    def load_from_path(self, filepath):
        """open a file and load to dictionary from a yaml"""
        with open(filepath, "r") as f:
            return yaml.load(f)

    def combined_defs(self, schema):
        combined = dict(**self.common_definitions)
        combined.update(schema.get("definitions", {}))
        return combined

    def combined_links(self, schema):
        combined = dict(**self.common_links)
        combined.update(schema.get("links", {}))
        return combined

    def definitions_used(self, schema, definitions):
        for p, ref in self.find_refs(schema):
            if ref.startswith(DEFINITION_PREFIX):
                x = ref[len(DEFINITION_PREFIX) :]
                yield x, ref
                # we need to recurse because definitions can refer to other definitions
                try:
                    for y in self.definitions_used(definitions[x], definitions):
                        yield y
                except KeyError:
                    raise UnresolvedReference(ref)

    def links_used(self, schema, definitions):
        for p, ref in self.find_refs(schema):
            if ref.startswith(LINK_PREFIX):
                x = ref[len(LINK_PREFIX) :]
                yield x, ref
            elif ref.startswith(DEFINITION_PREFIX):
                x = ref[len(DEFINITION_PREFIX) :]
                for y in self.links_used(definitions[x], definitions):
                    yield y

    def update_doc_type_schema(self, doc_type, schema=None, schema_file_path=None):
        try:
            my_merger = Merger(
                # pass in a list of tuple, with the
                # strategies you are looking to apply
                # to each type.
                [(list, ["override"]), (dict, ["merge"])],
                # next, choose the fallback strategies,
                # applied to all other types:
                ["override"],
                # finally, choose the strategies in
                # the case where the types conflict:
                ["override"],
            )
            base_schema = self.get_document_schema(doc_type=doc_type)

            required = set(base_schema.get("required", []))

            my_schema = copy.deepcopy(base_schema)

            if schema is not None:
                my_merger.merge(my_schema, schema)
                required = required.union(set(schema.get("required", [])))
                # builder.add_schema(schema)
            if schema_file_path is not None:
                logger.info(f"loading '{doc_type}' from '{schema_file_path}'")
                with open(schema_file_path) as infile:
                    s = yaml.load(infile)
                    required = required.union(set(s.get("required", [])))
                    my_merger.merge(my_schema, s)

            newschema = my_schema
            newschema["required"] = list(required)

            if "definitions" not in newschema:
                newschema["definitions"] = {}
            if "links" not in newschema:
                newschema["links"] = {}
            defs = self.combined_defs(newschema)
            links = self.combined_links(newschema)
            for definition_name, ref in self.definitions_used(
                newschema, definitions=defs
            ):
                if definition_name in defs:
                    if definition_name not in newschema["definitions"]:
                        newschema["definitions"][
                            definition_name
                        ] = self.common_definitions[definition_name]
                else:
                    raise UnresolvedReference(ref)
            for link_name, ref in self.links_used(newschema, definitions=defs):
                if link_name in links:
                    if link_name not in newschema["definitions"]:
                        newschema["links"][link_name] = self.common_links[link_name]
                else:
                    raise UnresolvedReference(ref)

            self.doc_type_schemas[doc_type] = newschema

            if "doc_type" not in newschema["properties"]:
                newschema["properties"]["doc_type"] = dict(type="string")

            validate(newschema, schemaschema, cls=OAS30Validator)

            logger.debug(f"{doc_type}={newschema}")
        except UnresolvedReference as reason:
            raise InvalidSchema(doc_type, reason)
        except ValidationError as reason:
            raise InvalidSchema(doc_type, reason)

    def get_document_schema(self, doc_type=None):
        if doc_type is None:
            return self.base_document_schema
        else:
            return self.doc_type_schemas.get(doc_type, self.base_document_schema)

    def json_schema_from_data(
        self, docs, doc_type=None, to_json=False, include_document_base=False
    ):
        builder = SchemaBuilder()
        if include_document_base:
            builder.add_schema(self.get_document_schema(doc_type=doc_type))
        _docs = []
        if utility.isiterable(docs):
            _docs = docs
        else:
            _docs.append(docs)
        for doc in _docs:
            builder.add_object(doc)

        if to_json:
            return builder.to_json(indent=2)
        else:
            return builder.to_schema()

    def files_from_dir(self, dirpath):
        return (
            glob(f"{dirpath}/*.json")
            + glob(f"{dirpath}/*.yaml")
            + glob(f"{dirpath}/*.yml")
        )

    def _load_config_dir(self, dirpath):
        files = self.files_from_dir(dirpath)
        for f in files:
            basename = os.path.basename(f)
            name = os.path.splitext(basename)[0]
            with open(f) as infile:
                s = yaml.load(infile)
                yield (name, s)

    def _load_schema_dir(self, schema_dir_path):
        logger.info(f"loading schemas from {schema_dir_path}")

        defs_path = os.path.join(schema_dir_path, "definitions")
        links_path = os.path.join(schema_dir_path, "links")
        if os.path.isdir(defs_path):
            self._load_definitions_dir(defs_path)
        if os.path.isdir(links_path):
            self._load_links_dir(links_path)

        for doc_type, s in self._load_config_dir(schema_dir_path):
            self.update_doc_type_schema(doc_type, schema=s)

    def _load_definitions_dir(self, dirpath):
        logger.info(f"loading definitions from {dirpath}")
        for def_name, s in self._load_config_dir(dirpath):
            self.add_common_definition(def_name, s)

    def _load_links_dir(self, dirpath):
        logger.info(f"loading links from {dirpath}")
        for def_name, s in self._load_config_dir(dirpath):
            self.add_common_links(def_name, s)

    def _find_and_register(self, config):
        if config.schema_modules:
            for mod_name in config.schema_modules:
                mod = importlib.import_module(mod_name)
                if hasattr(mod, "initialize"):
                    mod.initialize(self)
                schema_dir = os.path.dirname(os.path.realpath(mod.__file__))
                self._load_schema_dir(schema_dir)

    def add_common_definition(self, name, definition):
        logger.info(f"adding common schema definition '{name}'")
        self.common_definitions[name] = definition

    def add_common_links(self, name, link):
        logger.info(f"adding common schema link '{name}'")
        self.common_links[name] = link

    def get_link_dests(self, link_type):
        props = self.common_links[link_type].get("properties", {})
        if "doc_type" in props:
            if "const" in props["doc_type"]:
                return [props["doc_type"]["const"]]
            elif "enum" in props["doc_type"]:
                return props["doc_type"]["enum"]

    def schema_links(self, doc_type):
        """search schema properties for references to a links. resursively searches through referenced definitions."""

        def links(schema, definitions):
            for p, ref in self.find_refs(schema):
                if p[0] == "properties" and ref.startswith(
                    LINK_PREFIX
                ):  # if the path to the ref starts with properties and it is a link ref
                    reversed = p[::-1]
                    if reversed[0] == "items":
                        reversed.pop(0)
                    yield reversed[0], ref[
                        len(LINK_PREFIX) :
                    ], "multiple" if "items" in p else "single"
                elif p[0] in ["properties", "items"] and ref.startswith(
                    DEFINITION_PREFIX
                ):  # if the path to the ref starts with properties and it is a definition ref, we need to see if there are any links in the definition
                    definition_name = ref[len(DEFINITION_PREFIX) :]
                    for e, l in links(definitions[definition_name], definitions):
                        yield e, l, "multiple" if "items" in p else "single"

        schema = self.doc_type_schemas[doc_type]
        defs = schema.get("definitions", {})
        for edge_name, link_type, cardinality in links(schema, defs):
            links_dests = self.get_link_dests(link_type)
            if links_dests:
                for dest in links_dests:
                    yield doc_type, edge_name, dest, cardinality

    def schema_graph(self):
        """extract schema graph from links and return as networkx graph"""
        import networkx as nx

        G = nx.MultiDiGraph()
        for dt in self.doc_type_schemas.keys():
            G.add_node(dt)
            for source, edge_label, dest, cardinality in self.schema_links(dt):
                G.add_edge(source, dest, label=edge_label, cardinality=cardinality)

        return G

    def find_refs(self, schema_dict, key_path=[]):
        for k, v in schema_dict.items():
            if k == "$ref":
                yield key_path, v
            elif isinstance(v, dict):
                for p, s in self.find_refs(v, key_path + [k]):
                    yield p, s


def make_request_schema(parameters_schema):
    s = copy.deepcopy(analytic_request_schema)
    s["properties"]["parameters"] = parameters_schema
    return s
