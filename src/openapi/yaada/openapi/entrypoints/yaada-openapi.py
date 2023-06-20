#!/usr/bin/env python
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

import argparse

import connexion
from flask_cors import CORS
from yaada.core.analytic.context import make_analytic_context
from yaada.core.config import YAADAConfig
from yaada.openapi.common import load_spec

parser = argparse.ArgumentParser(description="Run YAADA's OpenAPI-based REST service.")
parser.add_argument("--debug", action="store_true")
if __name__ == "__main__":
    args = parser.parse_args()
    context = make_analytic_context("openapi")
    config = YAADAConfig()
    app = connexion.FlaskApp(__name__)

    @app.app.before_request
    def before_request_func():
        connexion.request.context = context

    spec = load_spec(context)
    app.add_api(spec)

    CORS(app.app)
    print(f"debug:{args.debug}")
    app.run(host=config.openapi_ip, port=config.openapi_port, debug=args.debug)
