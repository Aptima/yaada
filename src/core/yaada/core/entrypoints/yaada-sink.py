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

from yaada.core.config import YAADAConfig
from yaada.core.infrastructure.providers import (
    make_document_service,
    make_message_service,
)

if __name__ == "__main__":
    config = YAADAConfig()
    ANALYTIC_NAME = "es_sink_worker"
    ANALYTIC_SESSION_ID = "0"
    msg_service = make_message_service(config)
    msg_service.set_analytic(ANALYTIC_NAME, ANALYTIC_SESSION_ID)
    msg_service.connect("sink-0")
    doc_service = make_document_service(config)

    print(f"INGEST_BUFF_SIZE:{config.ingest_buff_size}")
    msg_service.subscribe_sink()

    doc_service.init_indexes()
    total = 0

    while True:
        docs = []

        fetched = msg_service.fetch(max_count=config.ingest_buff_size)

        count = len(fetched)

        # print(f"fetched {count}")

        for i in range(len(fetched)):
            doc = fetched[i]
            doc_service.enqueue_document(doc)
            if doc_service.is_time_to_flush():
                doc_service.flush_documents()
            total = total + 1
        # print(f"trying to flush")
        doc_service.flush_documents(raise_ingest_error=False)
        # print(f"acking")
        for i in range(len(fetched)):
            doc = fetched[i]
            # print(f'acking {i}')
            msg_service.delete_retained_topic(doc["_topic"])
            msg_service.publish_sinklog(doc)
        if count > 0:
            print(f"flushed {total} documents total")
        # status = dict()
        # status['@timestamp'] = datetime.utcnow()
        # status['count'] = len(docs)
        # if status['count'] > 0:
        #   doc_service.send_ingest_status(status)
