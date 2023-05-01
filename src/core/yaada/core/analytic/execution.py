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

import os
import re
import traceback

from jsonschema import validate

from yaada.core import analytic, utility


def sync_exec_analytic(
    context,
    analytic_name,
    analytic_session_id,
    parameters={},
    include_results=False,
    printer=None,
):
    c = context

    a = analytic.get_analytic(analytic_name)
    c.include_results_in_status(include_results)
    c._printer = printer
    req = dict(
        analytic_name=analytic_name,
        analytic_session_id=analytic_session_id,
        parameters=parameters,
    )
    status = {}
    result = None
    try:
        c._started()
        validate(req["parameters"], a.get_parameters_schema())
        result = a.run(context, req)
        c._finished()
    except Exception as e:
        c.error(traceback.format_exc())
        raise e
    status = {**c.status}
    if result is not None:
        status["return"] = utility.jsonify(result)
    if c.results_in_status:
        status["results"] = c._results
    c._results = []
    c._printer = None
    return status


def async_exec_analytic(
    msg_service,
    analytic_name,
    analytic_session_id,
    parameters={},
    worker="default",
    image=None,
    gpu=False,
    login=None,
):
    if image is None and "YAADA_PROJECT_IMAGE" in os.environ:
        image = os.environ.get("YAADA_PROJECT_IMAGE")
    msg_service.publish_analytic_request(
        analytic_name,
        analytic_session_id,
        parameters=parameters,
        worker=worker,
        image=image,
        gpu=gpu,
        login=login,
    )
    return dict(
        analytic_name=analytic_name,
        analytic_session_id=analytic_session_id,
        parameters=parameters,
        worker=worker,
        gpu=gpu,
    )


def get_worker_labels():
    labels = os.getenv("YAADA_WORKER_LABELS", "default")
    return [s.strip() for s in labels.split(",")]


def match_request_worker_label(labels, pattern):
    for label in labels:
        if re.match(pattern, label):
            return True
    return False
