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

import uuid

import connexion
from jsonschema import validate

from yaada.core import analytic, utility
from yaada.core.analytic.execution import async_exec_analytic, sync_exec_analytic


def get_analytic_list():
    return dict(analytics=analytic.get_analytics())


def get_analytic_description(analytic_name):
    return analytic.analytic_description(analytic_name)


def sync_exec(body):
    a = analytic.get_analytic(body["analytic_name"])

    if "analytic_session_id" not in body:
        body["analytic_session_id"] = str(uuid.uuid4())

    validate(body, a.REQUEST_SCHEMA)

    c = connexion.request.context.create_derived_context(
        body["analytic_name"], body["analytic_session_id"], body["parameters"]
    )

    status = sync_exec_analytic(
        c,
        body["analytic_name"],
        body["analytic_session_id"],
        body["parameters"],
        include_results=body.get("include_results", False),
    )

    return utility.deepcopy_ts(status)


def async_exec(body):
    a = analytic.get_analytic(body["analytic_name"])

    if "analytic_session_id" not in body:
        body["analytic_session_id"] = str(uuid.uuid4())

    validate(body, a.REQUEST_SCHEMA)

    c = connexion.request.context.create_derived_context(
        body["analytic_name"], body["analytic_session_id"], body["parameters"]
    )

    status = async_exec_analytic(
        c.msg_service,
        body["analytic_name"],
        body["analytic_session_id"],
        body["parameters"],
    )

    return utility.deepcopy_ts(status)


def get_analytic_status(analytic_name, analytic_session_id):
    r = connexion.request.context.doc_service.get_analytic_session_status(
        analytic_name, analytic_session_id
    )
    return r


def get_analytic_sessions(analytic_name):
    c = connexion.request.context
    r = dict(
        active=c.doc_service.get_active_analytic_sessions(analytic_name),
        error=c.doc_service.get_error_analytic_sessions(analytic_name),
        finished=c.doc_service.get_finished_analytic_sessions(analytic_name),
    )
    return r


def get_analytic_session_counts():
    c = connexion.request.context
    return c.doc_service.get_analytic_session_counts()
