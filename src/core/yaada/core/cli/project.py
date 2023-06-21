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

import glob
import json
import logging
import os
import re
import subprocess
import sys

from deepmerge import Merger
from git import Repo
from ruamel.yaml import YAML

from yaada.core import default_log_level
from yaada.core.utility import create_service_overrides

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


def get_docker_info():
    cmd = ["docker", "info", "--format", "{{json . }}"]
    out = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    return json.loads(out.stdout)


docker_arch_to_platform = {
    "x86_64": "amd64",  # value for intel Mac and ubuntu on intel/amd
    "aarch64": "arm64",
}


def get_platform_from_docker():
    arch = get_docker_info()["Architecture"]
    return docker_arch_to_platform.get(arch, "amd64")


class NoProjectFound(Exception):
    def __init__(self):
        super().__init__(
            self,
            "No yaada.yaml found in current directory. Most `yda` CLI commands need to be run from a directory containing a `yaada.yaml` configuration.",
        )


my_merger = Merger(
    # pass in a list of tuple, with the
    # strategies you are looking to apply
    # to each type.
    [(list, ["override"]), (dict, ["merge"])],
    # next, choose the fallback strategies,
    # applied to all other types:
    ["override"],
    # finally, choose the strategies in
    # the case where the types conflict:
    ["override"],
)


def strip_none_values(obj):
    if isinstance(obj, (list, tuple, set)):
        return type(obj)(strip_none_values(x) for x in obj if x is not None)
    elif isinstance(obj, dict):
        return type(obj)(
            (strip_none_values(k), strip_none_values(v))
            for k, v in obj.items()
            if k is not None and v is not None
        )
    else:
        return obj


def get_yaada_core_version():
    if sys.version_info.major < 3:
        return None
    if sys.version_info.minor < 8:  # python version < 3.8
        import pkg_resources

        return str(pkg_resources.get_distribution("yaada-core").version)
    else:  # python version >= 3.8
        from importlib.metadata import version

        return str(version("yaada-core"))


class Project:
    def __init__(
        self,
        configs=["yaada.yml", "yaada.yaml"],
        env=None,
        cwd=".",
        config_overrides={},
    ):
        self.cwd = cwd
        self.config = {
            "yaada_core_version": get_yaada_core_version(),
            "env": ["local"],
            "docker": {},
        }
        if "YAADA_HOSTNAME" in os.environ:
            self.config["hostname"] = os.getenv("YAADA_HOSTNAME")
        config_paths = []

        for p in configs:
            if os.path.isabs(p):
                config_paths.append(p)
            else:
                config_paths.append(os.path.join(self.cwd, p))

        expanded = self.expand_configs(config_paths)

        if len(expanded) == 0:
            raise NoProjectFound()

        for p in expanded:
            logger.info(f"loading: {p}")
            self.merge_config(self.load_yaml(p))

        if env is None:
            env = self.config["env"]

        for e in env:
            self.merge_config(self.config["environments"][e])

        self.merge_config(config_overrides)

        self.config = strip_none_values(self.config)

        self.init_environment()
        self.set_elasticsearch_variables()
        self.set_objectstorage_variables()
        self.set_mqtt_variables()
        self.replace_docker_build_variables()
        self.replace_script_run_variables()
        self.resolve_path_variables()
        # load customized variables into current process environment
        for k, v in self.config["variables"].items():
            os.environ[k] = v

    def resolve_path_variables(self):
        for k in self.config["variables"]:
            v = self.config["variables"][k]
            if isinstance(v, dict):
                value = v.get("value")
                replace = v.get("replace_absolute", False)
                if replace:
                    value = os.path.abspath(value)
                self.config["variables"][k] = value

    def write_side_config(self, name, config_data):
        config_path = os.path.join(self.cwd, f"yaada.{name}.yml")
        data = self.load_yaml(config_path)
        if data is None:
            data = {}
        my_merger.merge(data, config_data)

        with open(config_path, "w") as f:
            yaml = YAML()
            yaml.dump(data, f)

    def substitute_variables(self, obj: dict):
        obj_copy = obj.copy()
        for name, value in obj_copy.items():
            if isinstance(value, str):
                m = re.match(r"""\w*\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}\w*""", value)
                if m:
                    variable_name = m.group(1)
                    if variable_name in self.config.get("variables", {}):
                        obj_copy[name] = self.config.get("variables", {}).get(
                            variable_name
                        )
        return obj_copy

    def replace_docker_build_variables(self):
        for name, build in self.config.get("docker", {}).get("build", {}).items():
            if "build_args" in build:
                build["build_args"] = self.substitute_variables(build["build_args"])

    def replace_script_run_variables(self):
        for script_name, script_body in self.config.get("script", {}).items():
            if "variables" in script_body:
                script_body["variables"] = self.substitute_variables(
                    script_body["variables"]
                )

    def get_environments(self):
        return list(self.config.get("environments", {}).keys())

    def get_s3_buckets(self):
        return list(self.config.get("s3", {}).get("buckets", {}).keys())

    def get_s3_bucket_config(self, bucket):
        c = self.config.get("s3", {}).get("buckets", {}).get(bucket, {})
        if "bucket" not in c:
            c["bucket"] = bucket
        return c

    def expand_configs(self, configs):
        paths = []
        for c in configs:
            paths.append(c)
            base, ext = os.path.splitext(c)
            pattern = f"{base}.*{ext}"
            for p in glob.glob(pattern):
                paths.append(p)
        return [p for p in paths if os.path.exists(p)]  # only return configs that exist

    def set_env(self, env):
        self.current_env = env

    def init_environment(self):
        self.init_env_var(
            "COMPOSE_PROJECT_NAME", default=self.get_docker_compose_project_name()
        )
        # self.init_env_var("CORE_GIT_HASH", default=self.get_core_git_hash())
        self.init_env_var("PROJECT_GIT_HASH", default=self.get_project_git_hash())
        # self.init_env_var("YAADA_CORE_IMAGE", default=self.get_current_core_image())
        # self.init_env_var(
        #     "YAADA_CORE_IMAGE_TAG", default=self.get_current_core_image_tag()
        # )
        self.init_env_var(
            "YAADA_PROJECT_IMAGE", default=self.get_current_project_image()
        )
        self.init_env_var("PROJECT_IMAGE_TAG", default=self.get_current_project_tag())
        self.init_env_var("YAADA_NETWORK_NAME", default=self.get_docker_network_name())
        self.init_env_var("DOCKER_PLATFORM", default=self.get_docker_platform())
        if "tenant" in self.config:
            self.set_env_var("YAADA_TENANT", self.config["tenant"])
        if "prefix" in self.config:
            self.set_env_var("YAADA_DATA_PREFIX", self.config["prefix"])
        if "config" in self.config:
            self.set_env_var("YAADA_CONFIG", self.config["config"])

        path_to_project = os.path.abspath(self.get_project_path())

        # if path_to_project is not None:
        self.set_env_var(
            "YAADA_CONFIG_DIRECTORY", os.path.join(f"{path_to_project}", "conf")
        )

    def load_yaml(self, config_path):
        if os.path.exists(config_path):
            with open(config_path) as f:
                yaml = YAML()
                config = yaml.load(f.read())
                return config

    def merge_config(self, config):
        my_merger.merge(self.config, config)

    def set_elasticsearch_variables(self):
        overrides = create_service_overrides("elasticsearch", self.config)

        if any([x in overrides for x in ["hostname", "port", "protocol"]]):
            protocol = overrides.get("protocol", "http")
            hostname = overrides.get("hostname", "localhost")
            port = overrides.get("port", "9200")
            self.set_env_var("ELASTICSEARCH_URL", f"{protocol}://{hostname}:{port}")
        if "username" in overrides:
            self.set_env_var("ELASTICSEARCH_USERNAME", overrides.get("username"))
        if "password" in overrides:
            self.set_env_var("ELASTICSEARCH_PASSWORD", overrides.get("password"))

    def set_mqtt_variables(self):
        overrides = create_service_overrides("mqtt", self.config)

        if "hostname" in overrides:
            self.set_env_var("MQTT_HOSTNAME", overrides.get("hostname"))
        if "port" in overrides:
            self.set_env_var("MQTT_PORT", overrides.get("port"))

        if "ingest" in overrides:
            self.set_env_var("MQTT_INGEST_TOPIC", overrides.get("ingest"))
        if "sink" in overrides:
            self.set_env_var("MQTT_SINK_TOPIC", overrides.get("sink"))
        if "sinklog" in overrides:
            self.set_env_var("MQTT_SINKLOG_TOPIC", overrides.get("sinklog"))

    def set_objectstorage_variables(self):
        overrides = create_service_overrides("objectstorage", self.config)

        if any([x in overrides for x in ["hostname", "port"]]):
            hostname = overrides.get("hostname", "localhost")
            port = overrides.get("port", "8000")
            self.set_env_var("OBJECT_STORAGE_URL", f"{hostname}:{port}")
        self.set_env_var("OBJECT_STORAGE_ENABLED", overrides.get("enabled", True))

        if "bucket" in overrides:
            self.set_env_var("OBJECT_STORAGE_BUCKET", overrides.get("bucket"))
        if "secure" in overrides:
            self.set_env_var("OBJECT_STORAGE_SECURE", overrides.get("secure"))
        if "location" in overrides:
            self.set_env_var("OBJECT_STORAGE_LOCATION", overrides.get("location"))
        if "access_key_id" in overrides:
            self.set_env_var(
                "OBJECT_STORAGE_ACCESS_KEY_ID", overrides.get("access_key_id")
            )
        if "secret_access_key" in overrides:
            self.set_env_var(
                "OBJECT_STORAGE_SECRET_ACCESS_KEY", overrides.get("secret_access_key")
            )
        if "make_bucket" in overrides:
            self.set_env_var("OBJECT_STORAGE_MAKE_BUCKET", overrides.get("make_bucket"))

    def get_active_variables(self):
        my_env = os.environ.copy()
        for k, v in self.config.get("variables", {}).items():
            my_env[k] = v
        return my_env

    def set_env_var(self, variable, value):
        if "variables" not in self.config:
            self.config["variables"] = {}
        self.config["variables"][variable] = str(value)

    def init_env_var(self, variable, default=None):
        # if its in the root variables, use that.
        # else, use default
        if "variables" not in self.config:
            self.config["variables"] = {}

        newval = self.config.get("variables", {}).get(
            variable, None
        )  # then try root variables
        if newval is None:
            newval = default  # and lastly failover to default
        if newval is not None:
            self.config["variables"][variable] = newval

    # def get_core_git_hash(self):
    #     try:
    #         path_to_core = self.get_core_path()
    #         if path_to_core is not None:
    #             repo = Repo(path_to_core)
    #             return repo.head.commit.hexsha
    #     except Exception:
    #         pass

    def get_project_path(self):
        return self.config.get("path_to_project", ".")

    # def get_core_path(self):
    #     return self.config.get("path_to_core", None)

    def get_project_git_hash(self):
        try:
            repo = Repo(self.cwd)
            return repo.head.commit.hexsha
        except Exception:
            pass

    def get_scripts(self):
        return list(self.config["script"].keys())

    def get_script_as_list(self, command):
        if isinstance(command, list):
            return command
        else:
            return command.split()

    def get_script_command(self, script_name):
        command = self.config["script"][script_name]
        if isinstance(command, dict):
            return self.get_script_as_list(command["command"])
        else:
            return self.get_script_as_list(command)

    def get_script_stop_service(self, script_name):
        command = self.config["script"][script_name]
        if isinstance(command, dict):
            return command.get("stop_service", None)

    def get_script_cwd(self, script_name):
        command = self.config["script"][script_name]
        if isinstance(command, dict):
            return command.get("cwd", None)
        return None

    def get_script_shell(self, script_name):
        command = self.config["script"][script_name]
        if isinstance(command, dict):
            return command.get("shell", None)
        return None

    def get_script_variables(self, script_name):
        command = self.config["script"][script_name]
        if isinstance(command, dict):
            return command.get("variables", {})
        return None

    # def get_core_tags(self):
    #     tags = ["latest", self.config["yaada_core_version"]]
    #     if self.config["yaada_core_version"].endswith("-snapshot"):
    #         tags.append(self.get_core_git_hash())
    #     return tags

    # def get_core_image(self):
    #     return self.config.get("docker", {}).get("core_image", "yaada/yaada")

    # def get_current_core_image_tag(self):
    #     if (
    #         self.config["yaada_core_version"].endswith("-snapshot")
    #         and self.get_core_git_hash()
    #     ):
    #         return f"{self.get_core_git_hash()}"
    #     else:
    #         return f"{self.config['yaada_core_version']}"

    # def get_current_core_image(self):
    #     if (
    #         self.config["yaada_core_version"].endswith("-snapshot")
    #         and self.get_core_git_hash()
    #     ):
    #         return f"{self.get_core_image()}:{self.get_core_git_hash()}"
    #     else:
    #         return f"{self.get_core_image()}:{self.config['yaada_core_version']}"

    def get_project_tags(self):
        tags = ["latest", self.config["project_version"]]
        if self.config["project_version"].endswith("-snapshot"):
            t = self.get_project_git_hash()
            if t is not None:
                tags.append(t)
        return tags

    def get_project_image(self):
        return self.config.get("docker", {}).get(
            "project_image", f"aptima/{self.config['project_name']}"
        )

    def get_current_project_tag(self):
        if self.get_docker_tag() == "LATEST":
            return "latest"
        elif self.get_docker_tag() == "GITHASH":
            return f"{self.get_project_git_hash()}"
        elif self.get_docker_tag() == "VERSION":
            return f"{self.config['project_version']}"

    def get_current_project_image(self):
        return f"{self.get_project_image()}:{self.get_current_project_tag()}"

    def get_image_builds(self, images):
        if len(images) == 0:
            return self.config["docker"]["build"].values()
        else:
            return [
                self.config["docker"]["build"][image]
                for image in images
                if image in self.config["docker"]["build"]
            ]

    def get_image_build(self, image: str):
        return self.config["docker"]["build"][image]

    def get_docker_tag(self):
        return self.config.get("docker", {}).get("tag", None)

    # def get_core_images(self):
    #     return self.config.get("docker", {}).get(
    #         "core_images",
    #         [
    #             "yaada/yaada",
    #             "yaada/yaada-mosquitto",
    #         ],
    #     )

    def get_project_images(self):
        return [build["image"] for build in self.get_image_builds([])]

    def get_docker_network_name(self):
        return (
            self.config.get("docker", {})
            .get("network", {})
            .get("name", "yaada-shared-infrastructure")
        )

    def get_docker_platform(self):
        return self.config.get("docker", {}).get("platform", get_platform_from_docker())

    def get_docker_after_up_copy(self):
        return self.config.get("docker", {}).get("after_up", {}).get("copy", [])

    def get_docker_compose_project_name(self):
        return self.config.get("docker", {}).get("compose_project_name", "yaada")

    def get_docker_after_up_wait(self):
        return self.config.get("docker", {}).get("after_up", {}).get("wait", False)

    def get_docker_after_up_run(self):
        return self.config.get("docker", {}).get("after_up", {}).get("run", [])

    def get_docker_before_up_run(self):
        return self.config.get("docker", {}).get("before_up", {}).get("run", [])

    def get_config_for_building_core(self):
        return {"docker": {"platform": self.get_docker_platform()}}
