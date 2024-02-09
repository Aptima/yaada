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

import click

from yaada.core.cli import common
from yaada.core.cli.project import Project


@common.analytic.command()
def ls():
    """List analytics in local environment"""
    project = Project()
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    for s in context.analytic_description():
        print(s)


@common.analytic.command()
@click.argument("analytic_name", type=click.STRING, required=False, default=None)
@click.argument("analytic_session_id", type=click.STRING, required=False, default=None)
@click.option("--watch", "-w", is_flag=True, default=False)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def session(analytic_name, analytic_session_id, watch, env):
    """Show active analytic sessions"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )

    def output(context, analytic_name, analytic_session_id):
        if analytic_name is not None and analytic_session_id is not None:
            return json.dumps(
                context.doc_service.get_analytic_session_status(
                    analytic_name, analytic_session_id
                ),
                indent=2,
            )
        elif analytic_name is not None:
            r = dict(
                active=context.doc_service.get_active_analytic_sessions(analytic_name),
                error=context.doc_service.get_error_analytic_sessions(analytic_name),
                finished=context.doc_service.get_finished_analytic_sessions(
                    analytic_name
                ),
            )
            return json.dumps(r, indent=2)
        else:
            return json.dumps(
                context.doc_service.get_analytic_session_counts(), indent=2
            )

    if watch:
        common.watch_output(
            output,
            context=context,
            analytic_name=analytic_name,
            analytic_session_id=analytic_session_id,
        )
    else:
        print(output(context, analytic_name, analytic_session_id))


@common.analytic.command()
@click.argument("analytic_name", type=click.STRING)
@click.argument("analytic_session_id", type=click.STRING)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def watch(analytic_name, analytic_session_id, env):
    """watch an analytic sessions"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context
    from yaada.core.analytic.watcher import watch_analytic_output

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    watch_analytic_output(context, analytic_name, analytic_session_id)


@common.analytic.command()
@click.argument("analytic_name", type=click.STRING, required=False, default=None)
@click.argument("analytic_session_id", type=click.STRING, required=False, default=None)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def delete(analytic_name, analytic_session_id, env):
    """Delete session info from OpenSearch."""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    if analytic_name is not None and analytic_session_id is not None:
        if (
            input(
                f"Delete analytic session data for: {analytic_name} {analytic_session_id}? (y/n)"
            )
            == "y"
        ):
            context.doc_service.delete_analytic_session(
                analytic_name, analytic_session_id
            )
    elif analytic_name is not None:
        if (
            input(f"Delete all analytic session data for: {analytic_name}? (y/n)")
            == "y"
        ):
            context.doc_service.delete_analytic_sessions(analytic_name)
    else:
        if input("Delete ALL analytic session data? (y/n)") == "y":
            context.doc_service.delete_analytic_sessions()
