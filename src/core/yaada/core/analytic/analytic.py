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

import importlib
import inspect
import logging
import time
from abc import ABC, abstractmethod

from yaada.core import default_log_level, utility
from yaada.core.analytic.model import ModelBase

registered_analytics = {}
registered_models = {}
registered_pipeline_processors = {}
logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class YAADAAnalytic(ABC):
    @abstractmethod
    def run(self, context, request):
        pass

    def get_input_schemas(self):
        utility.method_deprecated()
        return {}

    def get_output_schemas(self):
        utility.method_deprecated()
        return {}

    def get_parameters_schema(self):
        return self.PARAMETERS_SCHEMA

    def get_description(self):
        return self.DESCRIPTION

    def get_request_schema(self):
        return self.REQUEST_SCHEMA


class YAADAPipelineProcessor(ABC):
    @abstractmethod
    def process(self, context, parameters, doc):
        pass

    def init(self, parameters, context):
        pass

    def get_per_document_pipeline_parameters(self, doc):
        pipeline_step_name = self.__class__.__name__
        if "parameters" in doc and pipeline_step_name in doc["parameters"]:
            return doc["parameters"][pipeline_step_name]
        return utility.nestify_dict(
            doc,
            delimiter=".",
            prefix=f"parameters.{pipeline_step_name}.",
            strip_prefix=True,
        )


def register_analytic(name, clazz):
    a = clazz()
    registered_analytics[name] = a


def register_model(name, clazz):
    full_name = f"{inspect.getmodule(clazz).__name__}.{clazz.__name__}"
    if (
        full_name == name
    ):  # we only want the original definitions registered, not where it was imported.
        registered_models[name] = clazz


def register_pipeline_processor(name, clazz):
    # a = clazz()
    registered_pipeline_processors[name] = clazz


def get_analytic(name):
    return registered_analytics[name]


def get_analytics():
    return list(registered_analytics.keys())


def get_pipeline_processor(name):
    return registered_pipeline_processors[name]()


def get_pipeline_processors():
    return list(registered_pipeline_processors.keys())


def get_model_class(name):
    return registered_models[name]


def get_models():
    return list(registered_models.keys())


def find_and_register(config, analytics=True, pipelines=True, models=True):
    logger.info("analytic:find_and_register")
    analytic_packages = []
    if config.yaada_load_analytics is not None:
        analytic_packages = analytic_packages + config.yaada_load_analytics.split(";")

    if config.yaada_analytics is not None:
        analytic_packages = analytic_packages + config.yaada_analytics

    logger.info(f"analytic:find_and_register:packages {analytic_packages}")
    for pkg in analytic_packages:
        start_t = time.time()
        mod = importlib.import_module(pkg)
        for name, obj in ((n, o) for (n, o) in inspect.getmembers(mod)):
            if (
                analytics
                and inspect.isclass(obj)
                and issubclass(obj, YAADAAnalytic)
                and obj is not YAADAAnalytic
            ):
                logger.info(f"##found analytic {obj.__name__} located in {pkg}")
                register_analytic(f"{pkg}.{obj.__name__}", obj)
            elif (
                pipelines
                and inspect.isclass(obj)
                and issubclass(obj, YAADAPipelineProcessor)
                and obj is not YAADAPipelineProcessor
            ):
                logger.info(
                    f"##found pipeline processor {obj.__name__} located in {pkg}"
                )
                register_pipeline_processor(f"{pkg}.{obj.__name__}", obj)
            elif (
                models
                and inspect.isclass(obj)
                and issubclass(obj, ModelBase)
                and obj is not ModelBase
            ):
                logger.info(f"##found Model {obj.__name__} located in {pkg}")
                register_model(f"{pkg}.{obj.__name__}", obj)
        end_t = time.time()
        logger.info(f"##{pkg} loaded in {end_t-start_t} seconds")


def analytic_description(analytic_name):
    r = dict(
        name=analytic_name,
        description=get_analytic(analytic_name).get_description(),
        request_schema=get_analytic(analytic_name).get_request_schema(),
    )
    return r
