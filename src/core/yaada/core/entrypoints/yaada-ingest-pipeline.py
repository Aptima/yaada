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

import concurrent.futures
import itertools
import threading
import time

from yaada.core import utility
from yaada.core.analytic.context import make_analytic_context
from yaada.core.analytic.pipeline import make_pipeline


# adapted from https://julien.danjou.info/atomic-lock-free-counters-in-python/
class FastWriteCounter(object):
    def reset(self):
        with self._read_lock:
            self._number_of_read = 0
            self._counter = itertools.count()

    def __init__(self):
        self._read_lock = threading.Lock()
        self.reset()

    def increment(self):
        next(self._counter)

    def value(self):
        with self._read_lock:
            value = next(self._counter) - self._number_of_read
            self._number_of_read += 1
        return value


def process_document(doc, pipeline, msg_service, counter):
    mydoc = utility.assign_document_id(doc)
    mydoc = pipeline.process_document(mydoc)
    counter.increment()
    if mydoc:
        msg_service.publish_sink(mydoc)
    msg_service.delete_retained_topic(doc["_topic"])


if __name__ == "__main__":
    ANALYTIC_NAME = "ingest_pipeline_worker"
    ANALYTIC_SESSION_ID = "0"
    context = make_analytic_context(ANALYTIC_NAME, ANALYTIC_SESSION_ID)
    msg_service = context.msg_service
    msg_service.subscribe_ingest()

    pipeline = make_pipeline(context)
    print(f"INGEST_BUFF_SIZE={context.config.ingest_buff_size}")
    print("Ready for ingest...")
    received_count = 0
    reported_count = 0
    processed_counter = FastWriteCounter()
    start_t = time.time()
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=context.config.ingest_workers
    ) as e:
        while True:
            fetched = msg_service.fetch(
                timeout_ms=1000, max_count=context.config.ingest_buff_size
            )
            for doc in fetched:
                received_count = received_count + 1
                e.submit(
                    process_document, doc, pipeline, msg_service, processed_counter
                )
                # process_document(doc,pipeline,msg_service,processed_counter)
                # mydoc = utility.assign_document_id(doc)
                # mydoc = pipeline.process_document(mydoc)

                # if mydoc:
                #   msg_service.publish_sink(mydoc)
                # msg_service.delete_retained_topic(doc['_topic'])

            processed_count = processed_counter.value()
            backlog = received_count - processed_count

            current_t = time.time()

            if reported_count != processed_count:
                delta_t = current_t - start_t
                delta_c = processed_count - reported_count
                reported_count = processed_count

                millis = int(delta_t * 1000)
                print(
                    f"processed {delta_c} in {millis}ms (avg {delta_c/delta_t}/s) total={processed_count} backlog={backlog}"
                )
            start_t = current_t

            while (
                backlog > context.config.ingest_buff_size
            ):  # if backlog gets to large, don't fetch more documents until cought up a bit. poor man's backpressure
                time.sleep(0.1)
                processed_count = processed_counter.value()
                backlog = received_count - processed_count
