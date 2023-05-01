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

import io
import logging
import re

import chardet
import tika
from tika import parser

from yaada.core import default_log_level, utility
from yaada.core.analytic import YAADAPipelineProcessor

tika.TikaClientOnly = True
logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class ArtifactExtractTextContent(YAADAPipelineProcessor):
    def process(self, context, parameters, doc):
        target = parameters["target"]
        artifact_type = parameters["artifact_type"]
        encoding = parameters.get("encoding", None)
        accept_extensions = parameters.get("accept_extensions", [])
        accept_regexes = parameters.get("accept_regexes", [])
        # doc = rewrite_artifact_section(doc,artifact_type)
        if artifact_type in doc.get("artifacts", {}):
            for blob in doc["artifacts"][artifact_type]:
                if not parameters.get("recompute", False) and "content" in blob:
                    continue
                if not all([x in blob for x in ["filename", "remote_file_path"]]):
                    continue
                if any(
                    (
                        blob["filename"].lower().endswith(ext)
                        for ext in accept_extensions
                    )
                ) or any(
                    (re.match(regex, blob["filename"]) for regex in accept_regexes)
                ):
                    tf = context.ob_service.fetch_file_to_temp(blob["remote_file_path"])
                    try:

                        if encoding:
                            # rawdata = tf.read()
                            # content = rawdata.decode(encoding)
                            content = io.TextIOWrapper(tf, encoding=encoding).read()
                        else:
                            rawdata = tf.read()
                            detected_encoding = chardet.detect(rawdata)
                            context.status["detected_encoding"] = detected_encoding
                            tf.seek(0)
                            content = io.TextIOWrapper(
                                tf,
                                encoding=detected_encoding["encoding"],
                                errors="ignore",
                            ).read()
                            blob["content"] = content
                        if len(doc["artifacts"][artifact_type]) == 1:
                            doc[target] = blob["content"]

                    except Exception as ex:
                        context.status["error"] = True
                        context.status["message"] = utility.traceback2str(ex)
                        logger.error("error extracting content", exc_info=True)
                else:
                    context.status["message"] = "skipping unhandled content"
        else:
            context.status["message"] = "no blob data to extract"

        return doc


class ArtifactExtractWithTika(YAADAPipelineProcessor):
    def process(self, context, parameters, doc):
        accept_extensions = parameters.get("accept_extensions", [])
        accept_regexes = parameters.get("accept_regexes", [])
        tika_endpoint = parameters["tika_endpoint"]
        target = parameters["target"]
        artifact_type = parameters["artifact_type"]
        date_target = parameters.get("date_target", "timestamps")

        # doc = rewrite_artifact_section(doc,artifact_type)

        if artifact_type in doc.get("artifacts", {}):
            for blob in doc["artifacts"][artifact_type]:
                if not parameters.get("recompute", False) and "tika" in blob:
                    continue
                if not all([x in blob for x in ["filename", "remote_file_path"]]):
                    continue
                if any(
                    (
                        blob["filename"].lower().endswith(ext)
                        for ext in accept_extensions
                    )
                ) or any(
                    (re.match(regex, blob["filename"]) for regex in accept_regexes)
                ):
                    tf = context.ob_service.fetch_file_to_temp(blob["remote_file_path"])
                    try:
                        parsed = parser.from_file(tf.name, tika_endpoint)
                        blob["tika"] = parsed
                        c = parsed.get("content", "")
                        if c:
                            blob["content"] = c.strip()
                        blob["date"] = (
                            blob["tika"].get("metadata", {}).get("date", None)
                        )

                        if len(doc["artifacts"][artifact_type]) == 1:
                            doc[target] = blob["content"]
                            if date_target not in doc:
                                doc[date_target] = []
                            doc[date_target].append(blob["date"])
                    except Exception:
                        logger.error("error extracting content", exc_info=True)
                else:
                    context.status["message"] = "skipping unhandled content"
        else:
            context.status["message"] = "no blob data to extract"

        return doc
