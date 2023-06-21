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

import json
import os
import subprocess

import click

from yaada.core.cli import common
from yaada.core.cli.analytic import *  # noqa: F401,F403
from yaada.core.cli.cf import *  # noqa: F401,F403
from yaada.core.cli.common import yaada
from yaada.core.cli.config import *  # noqa: F401,F403
from yaada.core.cli.data import *  # noqa: F401,F403
from yaada.core.cli.docker import DockerHelper
from yaada.core.cli.markdown import *  # noqa: F401,F403
from yaada.core.cli.project import Project
from yaada.core.cli.schema import *  # noqa: F401,F403
from yaada.core.cli.volumes import *  # noqa: F401,F403


class ServiceType(click.ParamType):
    name = "service"

    def shell_complete(self, ctx, param, incomplete):
        project = Project()
        docker = DockerHelper(project)
        services = docker.get_running_services()
        return [
            click.CompletionItem(name)
            for name in services
            if name.startswith(incomplete)
        ]


def build_images(project, images, no_cache, verbose, cwd=None):
    # path_to_core = project.get_core_path()
    # if path_to_core is not None and path_to_core.strip() != ".":
    #     core_project = Project(
    #         cwd=path_to_core, config_overrides=project.get_config_for_building_core()
    #     )
    #     build_images(
    #         core_project, images, no_cache=no_cache, verbose=verbose, cwd=path_to_core
    #     )

    docker = DockerHelper(project)
    for build in project.get_image_builds(images):
        # print(build)
        p = docker.build(
            image=build["image"],
            dockerfile=build["dockerfile"],
            context=build["context"],
            build_args=build.get("build_args", {}),
            tags=build.get("tags", project.get_project_tags()),
            no_cache=no_cache,
            verbose=verbose,
            cwd=cwd,
        )
        if p.returncode != 0:
            return


def push_images(project, images, registry, verbose):
    docker = DockerHelper(project)
    for build in project.get_image_builds(images):
        docker.push(
            image=build["image"],
            tags=project.get_project_tags(),
            verbose=verbose,
            registry=registry,
        )


@yaada.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def info(env):
    """Show info about the current YAADA project."""
    project = Project(env=env)

    print(json.dumps(project.config, indent=2))


@yaada.command()
def env():
    """Print list of available environments."""
    project = Project()
    for e in project.get_environments():
        print(e)


@yaada.command()
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option("--build", "-b", is_flag=True, default=False)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--wait", "-w", is_flag=True)
@click.option("--skip", "-s", is_flag=True, default=False)
@click.argument("services", type=ServiceType(), nargs=-1)
def up(verbose, compose, build, env, services, wait, skip):
    """Bring up docker services."""
    project = Project(env=env)
    docker = DockerHelper(project)
    if build:
        build_images(project, [], no_cache=False, verbose=verbose)

    docker.create_network(verbose=verbose)

    if not skip:
        for s in project.get_docker_before_up_run():
            parts = s.split()
            if len(parts) > 0:
                common.run_script(project, parts[0], parts[1:], verbose=verbose)

    docker.run_compose_command(
        "up",
        command_args=["-d"],
        verbose=verbose,
        compose=compose,
        cwd=project.get_project_path(),
    )
    docker.after_up_copy(verbose=verbose)
    if wait and not skip:
        common.wait_for_backend(project, timeout=120.0)

    if not skip:
        for s in project.get_docker_after_up_run():
            parts = s.split()
            if len(parts) > 0:
                common.run_script(project, parts[0], parts[1:], verbose=verbose)


@yaada.command()
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option("--remove-orphans", is_flag=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def down(verbose, compose, remove_orphans, env):
    """Bring down docker services."""
    project = Project(env=env)
    docker = DockerHelper(project)
    command_args = []
    if remove_orphans:
        command_args.append("--remove-orphans")
    docker.run_compose_command(
        "down",
        command_args=command_args,
        verbose=verbose,
        compose=compose,
        cwd=project.get_project_path(),
        check=False,
    )
    docker.delete_network(verbose=verbose)


@yaada.command()
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def ps(verbose, compose, env):
    """Show Docker containers running."""
    project = Project(env=env)
    docker = DockerHelper(project)
    docker.run_compose_command(
        "ps", verbose=verbose, compose=compose, cwd=project.get_project_path()
    )


@yaada.command()
@click.argument("service_name", type=ServiceType())
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def logs(service_name, verbose, compose, env):
    """Show Docker containers running."""
    project = Project(env=env)
    docker = DockerHelper(project)
    docker.run_compose_command(
        "logs",
        command_args=["-f", service_name],
        verbose=verbose,
        compose=compose,
        cwd=project.get_project_path(),
    )


@yaada.command()
@click.argument("service_name", type=ServiceType())
@click.argument("arguments", type=click.STRING, nargs=-1)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--no-tty", is_flag=True)
@click.option("--working-directory", "-w", default=None)
def shell(service_name, arguments, verbose, compose, env, no_tty, working_directory):
    """Create an interactive shell in existing container"""
    project = Project(env=env)
    docker = DockerHelper(project)
    exec_args = [service_name]
    command_args = list(arguments)
    if len(command_args) == 0:
        command_args = ["sh"]

    if no_tty:
        exec_args.insert(0, "-T")

    if working_directory is not None:
        exec_args = ["-w", working_directory] + exec_args

    docker.run_compose_command(
        "exec",
        command_args=exec_args + command_args,
        verbose=verbose,
        compose=compose,
        cwd=project.get_project_path(),
    )


@yaada.command()
@click.argument("arguments", type=click.STRING, nargs=-1)
@click.option("--verbose", "-v", is_flag=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def image_debug_shell(arguments, verbose, env):
    """Launch docker run for project image with arguments"""
    project = Project(env=env)
    docker = DockerHelper(project)

    docker_args = [
        "--rm",
        "-it",
        f"--network={project.get_docker_network_name()}",
        "-e",
        "OBJECT_STORAGE_URL=zenko:8000",
        "-e",
        "MQTT_HOSTNAME=mosquitto",
        "-e",
        "MQTT_PORT=1883",
        "-e",
        "ELASTICSEARCH_URL=http://opensearch:9200",
        "-e",
        "TIKA_SERVER_ENDPOINT=http://tika:9998",
    ]

    docker_args = docker_args + [
        f"{project.get_project_image()}:{project.get_current_project_tag()}"
    ]

    command_args = list(arguments)
    if len(command_args) == 0:
        command_args = ["/bin/bash"]

    docker.run_docker_command(
        "run",
        command_args=docker_args + command_args,
        verbose=verbose,
        cwd=project.get_project_path(),
    )


@yaada.command()
@click.argument("service_name", type=ServiceType())
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def start(service_name, verbose, compose, env):
    """Start a stopped service."""
    project = Project(env=env)
    docker = DockerHelper(project)
    docker.run_compose_command(
        "start",
        command_args=[service_name],
        verbose=verbose,
        compose=compose,
        cwd=project.get_project_path(),
    )


@yaada.command()
@click.argument("service_name", type=ServiceType())
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def stop(service_name, verbose, compose, env):
    """Stop a service."""
    project = Project(env=env)
    docker = DockerHelper(project)
    docker.run_compose_command(
        "stop",
        command_args=[service_name],
        verbose=verbose,
        compose=compose,
        cwd=project.get_project_path(),
    )


@yaada.command()
@click.argument("service_name", type=ServiceType())
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def restart(service_name, verbose, compose, env):
    """Restart a service."""
    project = Project(env=env)
    docker = DockerHelper(project)
    docker.run_compose_command(
        "restart",
        command_args=[service_name],
        verbose=verbose,
        compose=compose,
        cwd=project.get_project_path(),
    )


@yaada.command()
def bash_completions():
    """Setup bash completions."""
    if not os.getenv("SHELL", "").lower().endswith("bash"):
        print("Error: command only works from inside a bash shell")
        os.exit(1)

    subprocess.run(
        "_YDA_COMPLETE=source_bash yda > ~/.yaada-bash-completions.sh", shell=True
    )
    print("Run\n   source ~/.yaada-bash-completions.sh\nto activate.")
    print(
        "To enable for all future shells, add\n   source ~/.yaada-bash-completions.sh\nto your ~/.bash_profile or ~/.bashrc."
    )


class ScriptType(click.ParamType):
    name = "script"

    def shell_complete(self, ctx, param, incomplete):
        project = Project()
        scripts = project.get_scripts()
        return [
            click.CompletionItem(name)
            for name in scripts
            if name.startswith(incomplete)
        ]


# def script_completions(ctx, args, incomplete):
#   project = Project()
#   services = project.get_scripts()
#   return [k for k in services if k.startswith(incomplete)]


@yaada.command()
@click.argument("script", type=ScriptType(), required=False)
@click.argument("arguments", type=click.STRING, nargs=-1)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--compose", "-c", multiple=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--raw-command", "-r", is_flag=True, default=False)
@click.option("--use-shell", "-s", is_flag=True, default=False)
def run(script, arguments, verbose, compose, env, raw_command, use_shell):
    """Run a service in development mode."""
    project = Project(env=env)
    if script is None:
        for s in project.get_scripts():
            print(s)
        return
    common.run_script(
        project,
        script,
        arguments,
        verbose=verbose,
        compose=compose,
        raw_command=raw_command,
        use_shell=use_shell,
    )


@yaada.command()
@click.argument("images", type=click.STRING, nargs=-1)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--no-cache", is_flag=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def build(images, verbose, no_cache, env):
    """Build all project images."""

    project = Project(env=env)
    build_images(project, images, no_cache=no_cache, verbose=verbose)


@yaada.command()
@click.argument("images", type=click.STRING, nargs=-1)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--registry", type=click.STRING, default=None)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def push(images, verbose, registry, env):
    """Push all project images."""
    project = Project(env=env)
    push_images(project, images, registry=registry, verbose=verbose)


@yaada.command()
def download_nlp_resources():
    """Download python nlp resources"""
    # project = Project()
    from yaada.nlp import utils as nlputils

    nlputils.download_nlp_resources()


@yaada.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--timeout", type=click.FLOAT, default=120.0)
@click.option("--api-url", type=click.STRING, default=None)
def wait(env, timeout, api_url):
    """Wait for the backend to be ready."""
    project = Project(env=env)
    common.wait_for_backend(project, timeout=timeout, api_url=api_url)


@yaada.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def openapi_spec(env):
    """Print the current openapi spec as json."""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context
    from yaada.openapi.common import load_spec

    context = make_analytic_context(
        "CLI",
        init_pipelines=False,
        init_analytics=False,
        init_models=False,
        overrides=project.config,
        connect_to_services=False,
    )
    spec = load_spec(context)

    print(json.dumps(spec, indent=2))


if __name__ == "__main__":
    common.yaada()
