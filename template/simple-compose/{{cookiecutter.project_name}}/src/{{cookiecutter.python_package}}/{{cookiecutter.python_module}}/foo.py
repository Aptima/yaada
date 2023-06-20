from yaada.core import schema
from yaada.core.analytic import YAADAAnalytic, YAADAPipelineProcessor


class FooAnalytic(YAADAAnalytic):
    DESCRIPTION = "add foo=bar to any document"
    INPUT = {}
    OUTPUT = {}
    PARAMETERS_SCHEMA = {
        "type": "object",
        "properties": {
            "analyze_doc_type": {
                "description": "the type of document to analyze",
                "type": "string",
            },
            "analyze_query": {
                "description": "the elasticsearch query for fetching documents to analyze",
                "type": "object",
            },
        },
        "required": ["analyze_doc_type"],
    }
    REQUEST_SCHEMA = schema.make_request_schema(PARAMETERS_SCHEMA)

    def __init__(self):
        pass

    def run(self, context, request):
        q = {"query": {"match_all": {}}}

        if "analyze_query" in request["parameters"]:
            q = request["parameters"]["analyze_query"]

        analyze_doc_type = request["parameters"]["analyze_doc_type"]

        for doc in list(context.query(analyze_doc_type, q)):
            doc["foo"] = "bar"
            context.update(doc)


class FooProcessor(YAADAPipelineProcessor):
    def process(self, context, parameters, doc):
        doc["foo"] = "bar"
        return doc
