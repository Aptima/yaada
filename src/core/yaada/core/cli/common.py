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

import subprocess
import sys

import click

from yaada.core.cli.docker import DockerHelper
from yaada.core.cli.project import Project
from yaada.core.config import YAADAConfig
from yaada.core.utility import wait_flask


def print_help(ctx, message, value):
    if value is False:
        return
    if message is not None:
        click.echo(message)
    click.echo(ctx.get_help())
    ctx.exit()


def fatal_error(msg):
    click.echo(msg)
    sys.exit(0)


# project = Project()
# docker = DockerHelper(project)


@click.group(context_settings={"show_default": True})
def yaada():
    """A CLI for developing/controlling YAADA-based projects."""


@yaada.group()
def volume():
    """Volume subcommands."""


@yaada.group()
def data():
    """Data subcommands."""


@yaada.group()
def schema():
    """Schema subcommands."""


@yaada.group()
def analytic():
    """Analytic subcommands."""


@yaada.group()
def cf():
    """CloudFormation subcommands."""


@yaada.group()
def md():
    """Generating project documentation"""


@yaada.group()
def config():
    """Write project configuration"""


class EnvironmentsType(click.ParamType):
    name = "environment"

    def shell_complete(self, ctx, param, incomplete):
        project = Project()
        return [
            click.CompletionItem(name)
            for name in project.get_environments()
            if name.startswith(incomplete)
        ]


# def env_completions(ctx, args, incomplete):
#   project = Project()
#   return [k for k in project.get_environments() if k.startswith(incomplete)]


def watch_output(output_func, **kwargs):
    import curses
    import sys
    import time

    if not sys.stdout.isatty():
        print("Not available outside tty console")
        return

    def c(stdscr):
        stdscr.nodelay(1)

        while True:
            c = stdscr.getch()
            if c == ord("q"):
                break  # Exit the while loop
            else:
                stdscr.clear()
                stdscr.addstr(0, 0, "(Press 'q' to exit)")
                out = output_func(**kwargs)
                try:
                    stdscr.addstr(1, 0, out)
                except curses.error:
                    pass
                stdscr.refresh()
                time.sleep(2)

    curses.wrapper(c)


def wait_for_backend(project, timeout=60.0, flask_url=None):
    config = YAADAConfig(overrides=project.config)
    config.connection_timeout = timeout
    from yaada.core.analytic.context import make_analytic_context

    print("Waiting for backend...", file=sys.stderr)

    context = make_analytic_context(
        "CLI", init_pipelines=False, config=config, overrides=project.config
    )
    context.document_counts()
    if flask_url is None:
        flask_url = f"http://{project.config.get('hostname','localhost')}:5000"
    wait_flask(flask_url, timeout)

    print("READY")


def run_script(
    project,
    script,
    arguments,
    verbose=False,
    compose=[],
    raw_command=False,
    use_shell=False,
):
    docker = DockerHelper(project)
    if script is None:
        for s in project.get_scripts():
            print(s)
        return
    my_vars = project.get_active_variables()

    stop_service = None
    cwd = None

    if not raw_command:
        command = project.get_script_command(script) + list(arguments)
        script_shell = project.get_script_shell(script)
        if script_shell is not None:
            use_shell = use_shell or script_shell
        if use_shell:
            # if we're in shell mode, command is going to be passed as single string, so need to quote arguments
            command = command[:1] + [f'"{c}"' for c in command[1:]]
        stop_service = project.get_script_stop_service(script)
        cwd = project.get_script_cwd(script)

        vars = project.get_script_variables(script)
        my_vars = {**my_vars, **vars}
    else:
        command = [script] + list(arguments)

    my_vars = {k: str(v) for k, v in my_vars.items()}

    if stop_service is not None:
        docker.run_compose_command(
            "stop",
            command_args=[stop_service],
            verbose=verbose,
            compose=compose,
            cwd=project.get_project_path(),
        )

    if use_shell:
        command = " ".join(command)
    if verbose:
        print(dict(command=command, env=my_vars, cwd=cwd, shell=use_shell))
    subprocess.run(command, env=my_vars, cwd=cwd, shell=use_shell, check=True)
