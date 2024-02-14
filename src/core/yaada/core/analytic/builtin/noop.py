from yaada.core import schema
from yaada.core.analytic import YAADAAnalytic

class NoOp(YAADAAnalytic):
    """
    This analytic does nothing and exists for testing purposes.
    """

    DESCRIPTION = "No Op"
    PARAMETERS_SCHEMA = {
        "type": "object",
        "properties": {
            "input": {
              "description": "string that will be returned unchanged",
              "type": "string"
            }
        },
        "required": ['input']
    }
    REQUEST_SCHEMA = schema.make_request_schema(PARAMETERS_SCHEMA)

    def __init__(self):
        pass

    def run(self, context, request):
        input = request["parameters"]["input"]
        return input