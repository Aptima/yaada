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

from textblob import TextBlob

from yaada.core.analytic import YAADAAnalytic, YAADAPipelineProcessor
from yaada.nlp.utils import ensure_textblob_corpora


class TextBlobSentiment(YAADAAnalytic):
    DESCRIPTION = "Extract Sentiment from text."
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
                "description": "the elasticsearch query for fetching documents to analyze",
                "type": "object",
            },
        },
        "required": ["analyze_doc_type", "analyze_feature"],
    }

    def __init__(self):
        ensure_textblob_corpora()

    def run(self, context, request):
        q = {"query": {"match_all": {}}}

        if "analyze_query" in request["parameters"]:
            q = request["parameters"]["analyze_query"]

        analyze_doc_type = request["parameters"]["analyze_doc_type"]
        analyze_feature = request["parameters"]["analyze_feature"]

        for doc in list(context.query(analyze_doc_type, q)):
            content = doc[analyze_feature]
            tb = TextBlob(content)
            id = f"{doc['id']}-{context.analytic_name}-{context.analytic_session_id}-{analyze_doc_type}-{analyze_feature}"
            r = {
                "_id": id,
                "id": id,
                "doc_type": "TextBlobSentiment",
                "polarity": tb.polarity,
                "subjectivity": tb.subjectivity,
                "analyzed_doc_type": analyze_doc_type,
                "analyzed_feature": analyze_feature,
                "analyzed_id": doc["id"],
            }
            # print(r)
            context.update(r)


class TextBlobStreamingSentiment(YAADAPipelineProcessor):
    def init(self, context, parameters):
        ensure_textblob_corpora()

    def process(self, context, parameters, doc):
        source = parameters["source"]
        target = parameters["target"]
        if not parameters.get("recompute", False) and target in doc:
            context.status["skipped"] = True
            context.status["message"] = f"'{target}' property already exists."
            return doc
        content = doc.get(source, None)
        if content:
            tb = TextBlob(content)
            doc[target] = {
                "polarity": tb.polarity,
                "subjectivity": tb.subjectivity,
            }
        return doc
