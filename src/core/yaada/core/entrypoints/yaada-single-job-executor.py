#!/usr/bin/env python
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

import argparse
import sys
import traceback

from yaada.core.analytic.context import make_analytic_context
from yaada.core.analytic.execution import sync_exec_analytic
from yaada.core.config import YAADAConfig
from yaada.core.infrastructure.providers import make_message_service


def execute_analytic(req, msg_service):
    try:
        c = make_analytic_context(
            req["analytic_name"],
            req["analytic_session_id"],
            req["parameters"],
            msg_service=msg_service,
        )
        c.msg_service.delete_retained_topic(
            c.msg_service.analytic_request_topic(
                req["analytic_name"], req["analytic_session_id"]
            )
        )
        status = sync_exec_analytic(
            c, req["analytic_name"], req["analytic_session_id"], req["parameters"]
        )
        print(f"completed {status}")
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="run a single analytic job")
    parser.add_argument(
        "-a",
        "--analytic",
        dest="analytic_name",
        help="The analytic name",
        required=True,
    )
    parser.add_argument(
        "-i",
        "--id",
        dest="analytic_session_id",
        help="The analytic session id",
        required=True,
    )

    args = parser.parse_args()

    ANALYTIC_NAME = args.analytic_name
    ANALYTIC_SESSION_ID = args.analytic_session_id
    config = YAADAConfig()
    msg_service = make_message_service(config)
    msg_service.set_analytic(ANALYTIC_NAME, ANALYTIC_SESSION_ID)
    msg_service.connect(f"worker-{ANALYTIC_NAME}-{ANALYTIC_SESSION_ID}")
    msg_service.subscribe_analytic_request(ANALYTIC_NAME, ANALYTIC_SESSION_ID)

    print("Ready for analytic requests...")

    while True:
        fetched = msg_service.fetch(timeout_ms=1000, max_count=1)
        for req in fetched:
            print(f"received {req}")
            execute_analytic(req, msg_service)
            sys.exit(0)
