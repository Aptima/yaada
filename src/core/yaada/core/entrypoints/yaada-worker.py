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

import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

from yaada.core.analytic.context import make_analytic_context
from yaada.core.analytic.execution import (
    get_worker_labels,
    match_request_worker_label,
    sync_exec_analytic,
)
from yaada.core.config import YAADAConfig
from yaada.core.infrastructure.providers import (
    make_document_service,
    make_message_service,
)

ANALYTIC_NAME = "ingest_analytic_worker"
ANALYTIC_SESSION_ID = "0"
config = YAADAConfig()
msg_service = make_message_service(config)
msg_service.set_analytic(ANALYTIC_NAME, ANALYTIC_SESSION_ID)
msg_service.connect("analytic-worker-0")
doc_service = make_document_service(config)
msg_service.subscribe_analytic_request()


def execute_analytic(req):
    try:
        c = make_analytic_context(
            req["analytic_name"],
            req["analytic_session_id"],
            req["parameters"],
            msg_service=msg_service,
            doc_service=doc_service,
            init_analytics=False,
        )
        c.msg_service.delete_retained_topic(
            c.msg_service.analytic_request_topic(
                req["analytic_name"], req["analytic_session_id"]
            )
        )
        status = sync_exec_analytic(
            c, req["analytic_name"], req["analytic_session_id"], req["parameters"]
        )
        status_summary = {
            k: v for k, v in status.items() if k not in ["parameters", "@timestamp"]
        }
        print(f"completed:\n{json.dumps(status_summary,indent=2)}")
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)


if __name__ == "__main__":
    labels = get_worker_labels()

    context = make_analytic_context("worker")
    print(f"Worker labels: {labels}")
    print("Ready for analytic requests...")
    with ThreadPoolExecutor(max_workers=config.analytic_workers) as executor:
        while True:
            fetched = msg_service.fetch(timeout_ms=1000, max_count=1)
            for req in fetched:
                worker = req.get("worker", "default")
                if match_request_worker_label(labels, worker):
                    print(f"executing {req}")
                    executor.submit(execute_analytic, req)
                    # execute_analytic(req)
