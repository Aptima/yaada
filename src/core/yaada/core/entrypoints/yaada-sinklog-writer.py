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
import json
import os
import sys
from datetime import datetime

from yaada.core import utility
from yaada.core.config import YAADAConfig
from yaada.core.infrastructure.providers import make_message_service


class TimestampedAppender:
    def __init__(self, output, basename):
        self.output = output
        self.basename = basename
        self.current_output_file_path = ""
        self.current_output_file = None

    def open_output_file(self):
        self.current_output_file = open(self.current_output_file_path, "a")

    def get_current_output(self):
        ts = datetime.now().strftime("%Y%m%d")
        path = os.path.join(self.output, f"{self.basename}-{ts}.ldjson")

        if self.current_output_file_path == "":
            self.current_output_file_path = path
            self.open_output_file()
        elif self.current_output_file_path == path:
            pass
        else:
            self.current_output_file.close()
            self.current_output_file_path = path
            self.open_output_file()
        return self.current_output_file

    def append(self, data: dict):
        out = self.get_current_output()
        out.write(json.dumps(data, cls=utility.DateTimeEncoder) + "\n")
        out.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export all documents from the elasticsearch index"
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        help="Write messages to sinklog files in output directory",
        required=False,
        default=".",
    )
    parser.add_argument(
        "-b",
        "--basename",
        dest="basename",
        help="Basename for generated files",
        required=False,
        default="sinklog",
    )

    args = parser.parse_args()
    abspath = os.path.abspath(args.output)
    print(f"Writing to output directory: {abspath}")
    if not os.path.isdir(abspath):
        print(f"Error: output directory doesn't exist: {abspath}")
        sys.exit(1)

    ANALYTIC_NAME = "sinklog-writer"
    ANALYTIC_SESSION_ID = "0"
    config = YAADAConfig()
    msg_service = make_message_service(config)
    msg_service.set_analytic(ANALYTIC_NAME, ANALYTIC_SESSION_ID)
    msg_service.connect("sinklog-0")

    msg_service.subscribe_sinklog()

    appender = TimestampedAppender(abspath, args.basename)

    while True:
        fetched = msg_service.fetch(max_count=config.ingest_buff_size)
        # print(f"fetched {len(fetched)}")
        for doc in fetched:
            appender.append(doc)
        if len(fetched) > 0:
            print(f"wrote {len(fetched)} logs")
