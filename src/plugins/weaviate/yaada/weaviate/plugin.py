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
import uuid

import jmespath
import weaviate
from pyhocon import ConfigTree
from tqdm import tqdm

from yaada.core import default_log_level
from yaada.core.analytic.plugin import AnalyticContextPlugin

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class WeaviatePlugin(AnalyticContextPlugin):
    def init(self):
        self.doc_type_fields = {
            doc_type: c.get("fields")
            for doc_type, c in self.config.get("doc_types").items()
        }
        self.doc_type_schemas = {
            doc_type: c.get("schema").as_plain_ordered_dict()
            for doc_type, c in self.config.get("doc_types").items()
        }
        for doc_type, schema in self.doc_type_schemas.items():
            if "class" not in schema:
                schema["class"] = doc_type
            if "properties" not in schema:
                schema["properties"] = []
        self.update_schemas()

    def register(self, context):
        context.weaviate = self
        self.context = context
        self.config = context.config.hocon.get("yaada.context.plugin.weaviate", {})
        url = self.config.get("url", None)
        self.client = weaviate.Client(url)
        self.init()

    def merge_config(self, my_config: ConfigTree):
        self.config = ConfigTree.merge_configs(self.config, my_config)
        self.init()

    def get_doc_type_class(self, doc_type):
        return self.doc_type_schemas.get(doc_type, {}).get("class", None)

    def get_fields(self, doc_type):
        return self.doc_type_fields.get(doc_type, [])

    def update_schemas(self):
        for doc_type in self.doc_type_schemas:
            self.update_class(doc_type)

    def update_class(self, doc_type):
        class_name = self.get_doc_type_class(doc_type)
        schema = self.doc_type_schemas.get(doc_type)
        try:
            self.client.schema.create_class(schema)
            logger.info(
                f"WeaviatePlugin.update_schemas: created schema for {class_name}"
            )
        except weaviate.exceptions.UnexpectedStatusCodeException:
            class_obj = self.client.schema.get(class_name)
            schema_config = {k: v for k, v in schema.items() if k not in ["properties"]}
            self.client.schema.update_config(schema["class"], schema_config)
            logger.info(
                f"WeaviatePlugin.update_schemas: update schema for {schema['class']}"
            )
            for my_prop in schema.get("properties", []):
                for their_prop in class_obj.get("properties", []):
                    if my_prop["name"] == their_prop["name"]:
                        # print(f"found {my_prop['name']} in {class_name}")
                        break
                else:  # prop wasn't found, so let's add it
                    self.client.schema.property.create(class_name, my_prop)
                    logger.info(
                        f"WeaviatePlugin.update_schemas: added property {class_name} {my_prop}"
                    )

    def delete_class(self, doc_type):
        class_name = self.get_doc_type_class(doc_type)
        self.client.schema.delete_class(class_name)

    def prepare_object(self, doc):
        doc_type = doc["doc_type"]
        class_name = self.get_doc_type_class(doc_type)
        props = {}

        fields = self.get_fields(doc_type)
        for f in fields:
            val = jmespath.search(f["path"], doc)
            if val is not None:
                props[f["name"]] = val
            else:
                props[f["name"]] = f["default"]

        return class_name, props, doc.get("uuid4", str(uuid.uuid4()))

    def ingest(self, docs, batch_size=10, progress=False):
        with self.client.batch as batch:
            batch.batch_size = batch_size
            for doc in tqdm(docs, disable=not progress):
                if doc["doc_type"] not in self.doc_type_schemas:
                    logger.info(
                        f"WeaviatePlugin.ingest: skipping {doc['doc_type']} {doc['id']} because no schema configured."
                    )
                    continue
                class_name, props, id = self.prepare_object(doc)
                batch.add_data_object(props, class_name, id)

    def ask(
        self, question, doc_type, search_props, return_props=["xid"], num_results=1
    ):
        class_name = self.get_doc_type_class(doc_type)
        ask = {"question": question, "properties": search_props}
        result = (
            self.client.query.get(
                class_name,
                return_props
                + [
                    "_additional {answer {hasAnswer certainty property result startPosition endPosition} }"
                ],
            )
            .with_ask(ask)
            .with_limit(num_results)
            .do()
        )
        return result.get("data", {}).get("Get", {}).get(class_name, [])

    def search(self, text, doc_type, return_props=["xid"], num_results=10):
        nearText = {"concepts": [text]}
        class_name = self.get_doc_type_class(doc_type)
        result = (
            self.client.query.get(class_name, return_props)
            .with_near_text(nearText)
            .with_limit(num_results)
            .do()
        )
        return result.get("data", {}).get("Get", {}).get(class_name, [])
