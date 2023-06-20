import importlib
import inspect
import logging
import time
from abc import ABC, abstractmethod

from yaada.core import default_log_level

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class AnalyticContextPlugin(ABC):
    @abstractmethod
    def register(self, context):
        pass


def register_context_plugins(context):
    config = context.config

    plugins = config.context_plugins

    logger.info(f"loading {plugins}")
    for plugin in plugins:
        start_t = time.time()
        module_name, class_name = plugin.rsplit(".", 1)
        mod = importlib.import_module(module_name)
        clazz = getattr(mod, class_name)
        if not (inspect.isclass(clazz) and issubclass(clazz, AnalyticContextPlugin)):
            raise Exception(f"{plugin} is not a valid AnalyticContextPlugin")

        logger.info(f"found plugin {clazz.__name__} located in {mod}")

        instance = clazz()
        instance.register(context)

        end_t = time.time()
        logger.info(f"##{plugin} loaded in {end_t-start_t} seconds")
