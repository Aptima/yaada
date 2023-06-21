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

import copy
import importlib
import os
import re
from typing import Any, Dict, List

from ruamel.yaml import YAML

from yaada.core.analytic.context import AnalyticContext
from yaada.core.schema import SchemaManager

global spec
spec = None


def load_spec(context: AnalyticContext):
    global spec
    config = context.config
    spec_module = config.openapi_spec_module
    mod = importlib.import_module(spec_module)
    if hasattr(mod, "load_api_spec"):
        func = getattr(mod, "load_api_spec")
        assert callable(func)
        spec = func(context)
        return spec
    specfile = f"{os.path.dirname(mod.__file__)}/openapi.yaml"
    if os.path.isfile(specfile):
        spec = load_openapi_spec(context, specfile)
        return spec


def load_openapi_spec(context: AnalyticContext, path_to_spec: str):
    yaml = YAML(typ="safe")

    with open(path_to_spec, "r") as f:
        spec = yaml.load(f)
        newspec = transform_schema_spec(context.schema_manager, spec)
        return newspec


def load_api_spec(context: AnalyticContext):
    spec_path = os.path.join(os.path.dirname(__file__), "openapi.yaml")
    return load_openapi_spec(context, spec_path)


def deep_dict_set(data: Dict, keys: List[str], value: Any):
    if len(keys) == 1:
        data[keys[0]] = value
    elif len(keys) > 1:
        key = keys.pop(0)
        if key not in data:
            data[key] = {}
        deep_dict_set(data[key], keys, value)
    return data


def link2schema(name):
    parts = re.split(r"[\-\_]", name)
    newname = "".join([f"{x[0].upper()}{x[1:]}" for x in parts])
    if not newname.lower().endswith("link"):
        newname = newname + "Link"
    return newname


def def2schema(name):
    parts = re.split(r"[\-\_]", name)
    newname = "".join([f"{x[0].upper()}{x[1:]}" for x in parts]) + "Def"
    if not newname.lower().endswith("def"):
        newname = newname + "Def"
    return newname


def type2schema(name):
    parts = re.split(r"[\-\_]", name)
    return "".join([f"{x[0].upper()}{x[1:]}" for x in parts])


def transform_ref(schema_manager: SchemaManager, ref):
    if ref.startswith(schema_manager.DEFINITION_PREFIX):
        return "#/components/schemas/" + def2schema(
            ref[len(schema_manager.DEFINITION_PREFIX) :]
        )
    elif ref.startswith(schema_manager.LINK_PREFIX):
        return "#/components/schemas/" + link2schema(
            ref[len(schema_manager.LINK_PREFIX) :]
        )


def transform_schema(schema_manager: SchemaManager, schema: Dict):
    my_schema = copy.deepcopy(schema)
    if "definitions" in my_schema:
        del my_schema["definitions"]
    if "links" in my_schema:
        del my_schema["links"]
    for p, s in list(schema_manager.find_refs(my_schema)):
        deep_dict_set(my_schema, p + ["$ref"], transform_ref(schema_manager, s))
    return my_schema


def transform_schema_spec(schema_manager: SchemaManager, original_spec={}):
    spec = copy.deepcopy(original_spec)
    for name, schema in schema_manager.common_links.items():
        deep_dict_set(
            spec,
            ["components", "schemas", link2schema(name)],
            transform_schema(schema_manager, schema),
        )
    for name, schema in schema_manager.common_definitions.items():
        deep_dict_set(
            spec,
            ["components", "schemas", def2schema(name)],
            transform_schema(schema_manager, schema),
        )
    for name, schema in schema_manager.doc_type_schemas.items():
        deep_dict_set(
            spec,
            ["components", "schemas", type2schema(name)],
            transform_schema(schema_manager, schema),
        )
    return spec
