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

# yaada/config.py
import logging
import os
import os.path

from pyhocon import ConfigFactory

from yaada.core import default_log_level
from yaada.core.utility import to_bool

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


DEFAULT_CONTEXT_PLUGINS = ["yaada.core.infrastructure.migration.MigrationContextPlugin"]


class YAADAConfig:
    def __init__(self, config_name=None, overrides={}):
        self.load_config(config_name=config_name, overrides=overrides)

    def find_config_path(self, config_name="yaada.conf", overrides={}):
        cwd = os.getcwd()
        yaada_dir = os.path.abspath(os.path.dirname(__file__) + "/..")
        yaadaConfigPath = os.getenv("YAADA_CONFIG", config_name)

        config_directory = os.getenv("YAADA_CONFIG_DIRECTORY", None)

        logger.info(f"YAADA_CONFIG: {yaadaConfigPath}")
        config_path = None

        if os.path.isabs(yaadaConfigPath) and os.path.isfile(yaadaConfigPath):
            # config is defined with absolute path and exists
            config_path = yaadaConfigPath

        if config_path is None:
            # we need to search for the config, starting in the current directory, and
            # then up a a level, and finally in the yaada-core directory
            logger.info(f"current working directory: {cwd}")
            search_path = [
                cwd,
                f"{cwd}/conf",
                f"{cwd}/..",
                f"{cwd}/../conf",
                f"{cwd}/../../conf",
                yaada_dir,
                f"{yaada_dir}/conf",
            ]

            if "path_to_project" in overrides:
                search_path.insert(0, overrides["path_to_project"])
                search_path.insert(1, f"{overrides['path_to_project']}/conf")

            if config_directory is not None:
                search_path.insert(0, os.path.abspath(config_directory))
                search_path.insert(1, os.path.abspath("../" + config_directory))
            logger.info(f"looking for config in {search_path}")
            for p in search_path:
                path_to_try = os.path.abspath(f"{p}/{yaadaConfigPath}")
                if os.path.isfile(path_to_try):
                    config_path = path_to_try
                    break

        if config_path is None:
            raise Exception(f"Unable to find config file in {search_path}")
        logger.info(f"found config at `{config_path}`")
        return config_path

    def load_config(self, config_name=None, overrides={}):
        self.yaada_conf = None
        if config_name is None:
            self.config_path = self.find_config_path(overrides=overrides)
        else:
            self.config_path = self.find_config_path(config_name, overrides=overrides)

        self.hocon = ConfigFactory.parse_file(self.config_path)

        self.config_directory = os.path.dirname(self.config_path)
        self.project_directory = os.path.dirname(self.config_directory)
        self.schema_directory = os.getenv(
            "YAADA_SCHEMA_DIRECTORY", os.path.join(self.project_directory, "schema")
        )
        self.schema_modules = self.hocon.get("yaada.schema.modules", [])
        self.tenant = self.hocon.get("yaada.tenant", "default")
        self.data_prefix = self.hocon.get("yaada.data_prefix", "yaada")

        self.context_plugins = self.hocon.get("yaada.context.plugins", [])
        for plugin in DEFAULT_CONTEXT_PLUGINS[
            ::-1
        ]:  # reversed so that preserve ordering while inserting at slot 0
            if plugin not in self.context_plugins:
                self.context_plugins.insert(0, plugin)

        self.object_storage_enabled = to_bool(
            self.hocon.get("yaada.objectstorage.enabled", "true")
        )
        self.object_storage_access_key_id = self.hocon[
            "yaada.objectstorage.access_key_id"
        ]
        self.object_storage_secret_access_key = self.hocon[
            "yaada.objectstorage.secret_access_key"
        ]
        self.object_storage_url = self.hocon["yaada.objectstorage.url"]
        self.object_storage_location = self.hocon["yaada.objectstorage.location"]
        self.object_storage_bucket = self.hocon["yaada.objectstorage.bucket"]
        self.object_storage_secure = to_bool(self.hocon["yaada.objectstorage.secure"])
        self.object_storage_make_bucket = to_bool(
            self.hocon.get("yaada.objectstorage.make_bucket", "true")
        )
        self.message_provider = self.hocon["yaada.message_provider"]

        self.elasticsearch_url = self.hocon["yaada.elasticsearch.url"]
        self.elasticsearch_index_config = self.hocon.get(
            "yaada.elasticsearch.index.config", None
        )
        if self.elasticsearch_index_config is not None:
            self.elasticsearch_index_config = (
                self.elasticsearch_index_config.as_plain_ordered_dict()
            )
        self.elasticsearch_field_limit = self.hocon.get(
            "yaada.elasticsearch.mapping_field_limit", 1000
        )
        self.elasticsearch_index_has_ts = to_bool(
            self.hocon.get("yaada.elasticsearch.index_has_ts", False)
        )
        self.elasticsearch_username = self.hocon.get(
            "yaada.elasticsearch.username", None
        )
        self.elasticsearch_password = self.hocon.get(
            "yaada.elasticsearch.password", None
        )

        self.mqtt_hostname = self.hocon["yaada.mqtt.host"]
        self.mqtt_port = int(self.hocon["yaada.mqtt.port"])
        self.mqtt_ingest_topic = self.hocon["yaada.mqtt.topics.ingest"]
        self.mqtt_sink_topic = self.hocon["yaada.mqtt.topics.sink"]
        self.mqtt_sinklog_topic = self.hocon["yaada.mqtt.topics.sinklog"]
        self.mqtt_event_topic = self.hocon.get("yaada.mqtt.topics.sinklog", "event")

        self.ingest_buff_size = int(self.hocon["yaada.ingest.buffer.size"])
        self.ingest_buff_blocking_timeout = float(
            self.hocon["yaada.ingest.buffer.timeout"]
        )
        self.ingest_workers = int(self.hocon["yaada.ingest.workers"])
        self.analytic_workers = int(self.hocon.get("yaada.analytic.workers", 10))
        self.yaada_model_cache_size = int(self.hocon["yaada.modelcache.size"])

        self.yaada_load_analytics = os.getenv("YAADA_LOAD_ANALYTICS", None)
        self.yaada_analytics = self.hocon["yaada.analytics"]
        self.yaada_pipelines = self.hocon.get_config("yaada.pipelines")

        self.connection_timeout = int(self.hocon.get("yaada.connection_timeout", 60.0))

        self.openapi_ip = self.hocon.get("yaada.openapi.ip", "0.0.0.0")
        self.openapi_port = self.hocon.get("yaada.openapi.port", 5001)
        self.openapi_spec_module = self.hocon.get(
            "yaada.openapi.spec_module", "yaada.openapi"
        )


# class DevelopmentConfig(Config):
#     """Development configuration."""
#     DEBUG = True
#     BCRYPT_LOG_ROUNDS = 4


# class TestingConfig(Config):
#     """Testing configuration."""
#     DEBUG = True
#     TESTING = True
#     BCRYPT_LOG_ROUNDS = 4
#     PRESERVE_CONTEXT_ON_EXCEPTION = False


# class ProductionConfig(Config):
#     """Production configuration."""
#     DEBUG = False
#     FLASK_DEBUG = False
