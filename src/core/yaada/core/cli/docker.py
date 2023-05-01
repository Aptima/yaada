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
import subprocess
import sys

import click


class DockerHelper:
    def __init__(self, project):
        self.project = project
        self.path_to_project = project.get_project_path()

    def run_docker_command(
        self,
        command,
        flags={},
        args=[],
        command_flags={},
        command_args=[],
        verbose=False,
        capture_output=False,
        cwd=None,
        check=True,
    ):
        my_env = self.project.get_active_variables()

        cmd = ["docker"]

        for k, v in flags.items():
            cmd.extend([k, v])

        cmd.extend(args)

        cmd.append(command)
        for k, v in command_flags.items():
            cmd.extend([k, v])

        cmd.extend(command_args)

        if verbose:
            # print(json.dumps(my_env,indent=2))
            # print(f"cwd:{cwd}")
            print(cmd)
        if capture_output:
            return subprocess.run(
                cmd, stdout=subprocess.PIPE, env=my_env, cwd=cwd, check=check
            )
        else:
            return subprocess.run(cmd, env=my_env, cwd=cwd, check=check)

    def run_compose_command(
        self,
        command,
        compose=[],
        flags={},
        args=[],
        command_flags={},
        command_args=[],
        verbose=False,
        capture_output=False,
        cwd=None,
        check=True,
    ):
        my_env = self.project.get_active_variables()

        cmd = ["docker-compose"]
        if len(compose) == 0:
            compose = self.project.config["docker"]["default_composes"]
        for n in compose:
            cmd.extend(["-f", self.project.config["docker"]["composes"][n]["file"]])

        for k, v in flags.items():
            cmd.extend([k, v])

        cmd.extend(args)

        cmd.append(command)
        for k, v in command_flags.items():
            cmd.extend([k, v])

        cmd.extend(command_args)

        if verbose:
            print(json.dumps(my_env, indent=2))
            print(cmd)
        if capture_output:
            return subprocess.run(
                cmd, env=my_env, cwd=cwd, stdout=subprocess.PIPE, check=check
            )
        else:
            return subprocess.run(cmd, env=my_env, cwd=cwd, check=check)

    def create_network(self, verbose=False):
        self.run_docker_command(
            "network",
            command_args=["create", self.project.get_docker_network_name()],
            verbose=verbose,
            check=False,
        )

    def delete_network(self, verbose=False):
        self.run_docker_command(
            "network",
            command_args=["rm", self.project.get_docker_network_name()],
            verbose=verbose,
            check=False,
        )

    def get_running_services(self):
        try:
            return (
                self.run_compose_command(
                    "ps",
                    command_args=["--services"],
                    capture_output=True,
                    check=False,
                    cwd=self.project.get_project_path(),
                )
                .stdout.decode("utf-8")
                .split()
            )
        except Exception as e:
            print(e)
            return []

    def get_running_containers(self, prefix=""):
        try:
            return [
                x
                for x in self.run_docker_command(
                    "ps",
                    command_args=["--format", "{{.Names}}"],
                    capture_output=True,
                    check=False,
                    cwd=self.project.get_project_path(),
                )
                .stdout.decode("utf-8")
                .split()
                if x.startswith(prefix)
            ]
        except Exception as e:
            print(e)
            return []

    def get_project_volumes(self):
        try:
            return [
                v
                for v in self.run_docker_command(
                    "volume", command_args=["ls"], capture_output=True, check=False
                )
                .stdout.decode("utf-8")
                .split()
                if v.startswith(
                    self.project.config["variables"]["COMPOSE_PROJECT_NAME"]
                )
            ]
        except Exception as e:
            print(e)
            return []

    def build(
        self,
        image,
        dockerfile,
        context,
        build_args,
        tags,
        no_cache=False,
        verbose=False,
        cwd=None,
    ):
        args = []
        if no_cache:
            args.append("--no-cache")
        for t in tags:
            args.extend(["-t", f"{image}:{t}"])
        args.extend(["-f", dockerfile])

        if verbose:
            args.extend(["--progress=plain"])

        for name, value in build_args.items():
            args.extend(["--build-arg", f"{name}={value}"])

        args.append(context)

        return self.run_docker_command(
            "build", command_args=args, verbose=verbose, cwd=cwd
        )

    def push(self, image, tags, registry=None, verbose=False):
        if registry is None:
            registry = (
                self.project.config.get("docker", {}).get("registry", "").rstrip("/")
            )
        if registry == "":
            click.echo("No registry specified or available in configuration")
            sys.exit(0)
        for t in tags:
            self.run_docker_command(
                "tag",
                command_args=[f"{image}:{t}", f"{registry}/{image}:{t}"],
                verbose=verbose,
            )
            self.run_docker_command(
                "push", command_args=[f"{registry}/{image}:{t}"], verbose=verbose
            )

    def pull_core(self, registry=None, verbose=False):
        images = self.project.get_core_images()
        tag = self.project.config.get("yaada_core_version")
        if registry is None:
            registry = (
                self.project.config.get("docker", {}).get("registry", "").rstrip("/")
            )
        if registry == "":
            click.echo("No registry specified or available in configuration")
            sys.exit(0)

        for image in images:
            self.run_docker_command(
                "pull", command_args=[f"{registry}/{image}:{tag}"], verbose=verbose
            )
            self.run_docker_command(
                "tag",
                command_args=[f"{registry}/{image}:{tag}", f"{image}:{tag}"],
                verbose=verbose,
            )

    def after_up_copy(self, verbose):
        # print(self.get_running_services())
        for f in self.project.get_docker_after_up_copy():
            source = f["source"]
            dest = f["dest"]
            container_prefix = (
                f"{self.project.get_docker_compose_project_name()}_{f['container']}_"
            )
            containers = self.get_running_containers(container_prefix)
            for c in containers:
                print(f"copy {source} to {dest} on {c}")
                self.run_docker_command(
                    "cp", command_args=[source, f"{c}:{dest}"], verbose=verbose
                )
