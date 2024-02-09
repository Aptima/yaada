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

import ftfy
from langdetect import detect, detect_langs

from yaada.core import schema
from yaada.core.analytic import YAADAAnalytic


class LangDetection(YAADAAnalytic):
    DESCRIPTION = "Infer language from text using Python `langdetect` package."
    PARAMETERS_SCHEMA = {
        "type": "object",
        "properties": {
            "analyze_doc_type": {
                "description": "the type of document to analyze",
                "type": "string",
            },
            "analyze_feature": {
                "description": "the name of the text field on the document to use for analysis",
                "type": "string",
            },
            "analyze_query": {
                "description": "the opensearch query for fetching documents to analyze",
                "type": "object",
            },
            "language_feature": {
                "description": "the target feature to store the detected language",
                "type": "string",
            },
            "language_scores_feature": {
                "description": "the target feature to store top three possible languages with probabilities",
                "type": "object",
            },
        },
        "required": ["analyze_doc_type", "analyze_feature", "language_feature"],
    }
    REQUEST_SCHEMA = schema.make_request_schema(PARAMETERS_SCHEMA)

    def __init__(self):
        pass

    def run(self, context, request):
        analyze_doc_type = request["parameters"]["analyze_doc_type"]
        analyze_feature = request["parameters"]["analyze_feature"]
        language_feature = request["parameters"]["language_feature"]
        language_scores_feature = request["parameters"].get(
            "language_scores_feature", None
        )
        q = {"query": {"bool": {"must_not": {"exists": {"field": language_feature}}}}}

        if "analyze_query" in request["parameters"]:
            q = request["parameters"]["analyze_query"]

        docs = list(context.query(analyze_doc_type, q))

        print(f"processing {len(docs)} documents")

        for doc in docs:
            content = doc[analyze_feature]
            analyzed_doc = None
            try:
                analyzed_doc = ftfy.fix_text(content)
                doc[language_feature] = detect(analyzed_doc)
                if language_scores_feature:
                    doc[language_scores_feature] = {
                        o.lang: o.prob for o in detect_langs(analyzed_doc)
                    }
                context.update(doc)
            except Exception as e:
                print(str(e) + f": {analyzed_doc}")
