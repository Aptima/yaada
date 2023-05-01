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

import hashlib
import json

from tqdm import tqdm

from yaada.core import schema, utility
from yaada.core.analytic import YAADAAnalytic
from yaada.dataset.utils import download_to_temp

SQUAD_URL_BASE = "https://rajpurkar.github.io/SQuAD-explorer/dataset"

# SQUAD_1_1_URL = "https://rajpurkar.github.io/SQuAD-explorer/dataset/train-v1.1.json"
# SQUAD_2_0_URL = "https://rajpurkar.github.io/SQuAD-explorer/dataset/train-v2.0.json"


def squad_download_parse(version, dataset):
    url = f"{SQUAD_URL_BASE}/{dataset}-{version}.json"
    tf = download_to_temp(url)
    data = json.load(tf)

    for data in data.get("data", []):
        title = data["title"]
        for paragraph in data.get("paragraphs", []):
            doc = dict()
            doc["title"] = title
            doc["dataset"] = dataset
            doc["version"] = version
            doc["doc_type"] = "SQuADParagraph"
            doc["content"] = paragraph["context"]
            # create doc id as sha256 hash over title, version, dataset, and pragraph content
            m = hashlib.sha256()
            m.update(title.encode("utf-8"))
            m.update(dataset.encode("utf-8"))
            m.update(version.encode("utf-8"))
            m.update(doc["content"].encode("utf-8"))
            doc["_id"] = m.hexdigest()
            doc["question_ids"] = []

            for q in paragraph.get("qas", []):
                qdoc = q.copy()
                qdoc["title"] = title
                qdoc["dataset"] = dataset
                qdoc["version"] = version
                qdoc["doc_type"] = "SQuADQuestion"
                qdoc["paragraph_id"] = doc["_id"]
                _id = q["id"]
                doc["question_ids"].append(_id)
                q["_id"] = _id
                yield qdoc

            yield doc

    tf.close()


class DownloadSquad(YAADAAnalytic):
    DESCRIPTION = "Scrape page content for url in arbitrary document."
    PARAMETERS_SCHEMA = {
        "description": "scrape articles",
        "type": "object",
        "properties": {
            "version": {
                "description": "SQuAD version",
                "type": "string",
                "enum": ["v1.1", "v2.0"],
            },
            "dataset": {
                "description": "training vs dev set. Test set is not available.",
                "type": "string",
                "enum": ["train", "dev"],
            },
        },
        "required": ["version", "dataset"],
    }
    REQUEST_SCHEMA = schema.make_request_schema(PARAMETERS_SCHEMA)

    def __init__(self):
        pass

    def run(self, context, request):
        version = request.get("parameters", {}).get("version")
        dataset = request.get("parameters", {}).get("dataset")

        for chunk in utility.batched_generator(
            tqdm(squad_download_parse(version, dataset)), 50
        ):
            context.update(chunk, sync=True)
