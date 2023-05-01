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

import logging
import traceback
from datetime import datetime

from yaada.core import analytic, default_log_level, utility

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class ProcessingStep:
    def __init__(self, name, pipeline_processor, params, doc_type):
        self.pipeline_processor = pipeline_processor
        self.parameters = params
        self.name = name
        self.doc_type = doc_type

        pipeline_processor.doc_type = doc_type

    def __repr__(self):
        return f"ProcessingStep(name={self.name},pipeline_processor={repr(self.pipeline_processor)},parameters={repr(self.parameters)})"


global _pipeline
_pipeline = None


def make_pipeline(context):
    global _pipeline
    if _pipeline is None:
        logger.info("Loading PIPELINES")
        _pipeline = YaadaPipeline(context)
        _pipeline.from_config(context.config.yaada_pipelines)
    return _pipeline


class YaadaPipeline:
    def __init__(self, context):
        self.context = context

        self.document_pipelines = {}

    def add_step(self, context, doc_type, name, parameters):
        ps = ProcessingStep(
            name, analytic.get_pipeline_processor(name), parameters, doc_type
        )
        self.document_pipelines[doc_type].append(ps)
        ps.pipeline_processor.init(parameters=ps.parameters, context=context)

    def from_config(self, pipeline_config):
        logger.info(f"YaadaPipeline:{pipeline_config}")
        self.pipeline_config = pipeline_config
        context = self.context
        for doc_type in pipeline_config:
            self.document_pipelines[doc_type] = []
            for processor_conf in pipeline_config[doc_type].get_list("processors"):
                self.add_step(
                    context,
                    doc_type,
                    processor_conf["name"],
                    dict(processor_conf["parameters"]),
                )
            logger.info(f"{doc_type}=\n{self.document_pipelines[doc_type]}")

    def process_document(self, doc):
        doc["_pipeline"] = []
        if doc["doc_type"] in self.document_pipelines:
            context = self.context
            for i, step in enumerate(self.document_pipelines[doc["doc_type"]]):
                context.set_analytic_name(step.pipeline_processor.__class__.__name__)
                context.set_analytic_session_id(utility.urlencode(doc["_id"]))
                context.status = dict(output_stats={}, input_stats={})
                params = {}
                params.update(step.parameters)
                params.update(
                    step.pipeline_processor.get_per_document_pipeline_parameters(doc)
                )
                step_data = dict(
                    step_name=step.pipeline_processor.__class__.__name__,
                    parameters=params,
                    start_time=datetime.utcnow(),
                )
                try:
                    doc = step.pipeline_processor.process(context, params, doc)
                    if context.status is not None:
                        step_data["status"] = context.status
                except Exception as ex:
                    step_data["error"] = True
                    step_data["message"] = utility.traceback2str(ex)
                    traceback.print_exc()
                step_data["finish_time"] = datetime.utcnow()
                step_data["compute_duration_seconds"] = (
                    step_data["finish_time"] - step_data["start_time"]
                ).total_seconds()
                if doc is None:
                    break
                doc["_pipeline"].append(step_data)
        return doc
