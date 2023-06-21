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
import sys

import click

from yaada.core.cli import common
from yaada.core.cli.project import Project


@common.data.command()
@click.argument(
    "destination", type=click.Path(exists=False, writable=True, resolve_path=True)
)
@click.option("--doc-type", type=click.STRING, default="*")
@click.option("--query", type=click.STRING, default='{"query":{"match_all":{}}}')
@click.option("--scroll", type=click.STRING, default="24h")
@click.option("--scroll-size", type=click.INT, default=100)
@click.option("--skip-artifacts", is_flag=True, default=False)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def save_tar(destination, doc_type, query, scroll, scroll_size, skip_artifacts, env):
    """Save data to tarball"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    q = json.loads(query)
    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    context.migration.save_archive_to_tar(
        destination,
        doc_type=doc_type,
        query=q,
        scroll=scroll,
        scroll_size=scroll_size,
        include_artifacts=not skip_artifacts,
    )


@common.data.command()
@click.argument(
    "source",
    type=click.Path(
        exists=True, readable=True, resolve_path=True, dir_okay=False, file_okay=True
    ),
)
@click.option(
    "--process",
    is_flag=True,
    default=False,
    help="Run data through ingest pipelines while loading.",
)
@click.option(
    "--async",
    "not_sync",
    is_flag=True,
    default=False,
    help="Load data through asynchronous ingest pipeline rather than in local cli process.",
)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def load_tar(source, process, not_sync, env):
    """Load data from tarball"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=process, overrides=project.config
    )

    context.migration.load_archive_from_tar(source, process=process, sync=not not_sync)


@common.data.command()
@click.argument(
    "destination", type=click.Path(exists=False, writable=True, resolve_path=True)
)
@click.option("--doc-type", type=click.STRING, default="*")
@click.option("--query", type=click.STRING, default='{"query":{"match_all":{}}}')
@click.option("--scroll", type=click.STRING, default="24h")
@click.option("--scroll-size", type=click.INT, default=100)
@click.option("--skip-artifacts", is_flag=True, default=False)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def save_dir(destination, doc_type, query, scroll, scroll_size, skip_artifacts, env):
    """Create a data archive directory containing documents data and binary artifacts based on query"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    q = json.loads(query)
    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    context.migration.save_archive_to_directory(
        destination,
        doc_type=doc_type,
        query=q,
        scroll=scroll,
        scroll_size=scroll_size,
        include_artifacts=not skip_artifacts,
    )


@common.data.command()
@click.argument(
    "source",
    type=click.Path(
        exists=True, readable=True, resolve_path=True, dir_okay=True, file_okay=False
    ),
)
@click.option(
    "--process",
    is_flag=True,
    default=False,
    help="Run data through ingest pipelines while loading.",
)
@click.option(
    "--async",
    "not_sync",
    is_flag=True,
    default=False,
    help="Load data through asynchronous ingest pipeline rather than in local cli process.",
)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def load_dir(source, process, not_sync, env):
    """Load data from directory"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )

    context.migration.load_archive_from_directory(
        source, process=process, sync=not not_sync
    )


@common.data.command()
@click.argument(
    "destination",
    type=click.Path(exists=False, writable=True, resolve_path=True),
    default=None,
    required=False,
)
@click.option("--doc-type", type=click.STRING, default="*")
@click.option("--query", type=click.STRING, default='{"query":{"match_all":{}}}')
@click.option("--scroll", type=click.STRING, default="24h")
@click.option("--scroll-size", type=click.INT, default=100)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def save_ldjson(destination, doc_type, query, scroll, scroll_size, env):
    """Export documents to an ldjson file"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    q = json.loads(query)
    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )

    if destination is not None:
        context.migration.save_ldjson_to_file(
            destination,
            doc_type=doc_type,
            query=q,
            scroll=scroll,
            scroll_size=scroll_size,
            binary=True,
        )
    else:
        context.migration.export_to_ldjson_stream(
            sys.stdout,
            doc_type=doc_type,
            query=q,
            scroll=scroll,
            scroll_size=scroll_size,
        )


@common.data.command()
@click.argument(
    "source",
    type=click.Path(
        exists=True, readable=True, resolve_path=True, dir_okay=False, file_okay=True
    ),
    required=False,
)
@click.option(
    "--process",
    is_flag=True,
    default=False,
    help="Run data through ingest pipelines while loading.",
)
@click.option(
    "--async",
    "not_sync",
    is_flag=True,
    default=False,
    help="Load data through asynchronous ingest pipeline rather than in local cli process.",
)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option(
    "--batch-size",
    required=False,
    type=int,
    default=10,
    show_default=True,
    help="Used for optimizing synchronous ingest speed.",
)
@click.option(
    "--no-validate",
    is_flag=True,
    default=False,
    help="Disable schema validation during ingest.",
)
@click.option(
    "--lazy-load",
    is_flag=True,
    default=False,
    help="Don't read whole file into memory. Will not see progress bar at ingest time.",
)
def load_ldjson(source, process, not_sync, env, batch_size, no_validate, lazy_load):
    """Load data from line-delimited json"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )

    if source is not None:
        context.migration.load_ldjson_from_file(
            source,
            process=process,
            sync=not not_sync,
            batch_size=batch_size,
            validate=not no_validate,
            realize=not lazy_load,
        )
    else:
        context.migration.import_from_ldjson_stream(
            sys.stdin,
            process=process,
            sync=not not_sync,
            batch_size=batch_size,
            validate=not no_validate,
            realize=not lazy_load,
        )


@common.data.command()
@click.argument("from_env", type=common.EnvironmentsType())
@click.argument("to_env", type=common.EnvironmentsType())
@click.option("--doc-type", type=click.STRING, default="*")
@click.option("--query", type=click.STRING, default='{"query":{"match_all":{}}}')
@click.option("--scroll", type=click.STRING, default="24h")
@click.option("--scroll-size", type=click.INT, default=100)
@click.option(
    "--process",
    is_flag=True,
    default=False,
    help="Run data through ingest pipelines while loading.",
)
@click.option(
    "--async",
    "not_sync",
    is_flag=True,
    default=False,
    help="Load data through asynchronous ingest pipeline rather than in local cli process.",
)
def copy(from_env, to_env, doc_type, query, scroll, scroll_size, process, not_sync):
    """Copy data between two yaada environments."""
    from yaada.core.analytic.context import make_analytic_context

    from_project = Project(env=[from_env])
    from_context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=from_project.config
    )

    to_project = Project(env=[to_env])
    to_context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=to_project.config
    )

    q = json.loads(query)

    from_context.migration.to_context(
        to_context,
        doc_type=doc_type,
        query=q,
        scroll=scroll,
        scroll_size=scroll_size,
        process=process,
        sync=not not_sync,
    )


@common.data.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--watch", "-w", is_flag=True, default=False)
def counts(env, watch):
    """Print doc counts"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )

    def output(context):
        return json.dumps(context.document_counts(), indent=2)

    if watch:
        common.watch_output(output, context=context)
    else:
        print(output(context))


@common.data.command()
@click.argument("doc_type", type=click.STRING)
@click.argument("term", type=click.STRING)
@click.argument("query", type=click.STRING, default='{"query":{"match_all":{}}}')
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def terms(doc_type, term, query, env):
    """Print terms aggregation"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    q = json.loads(query)
    print(json.dumps(context.term_counts(doc_type, term, query=q), indent=2))


@common.data.command()
@click.argument("doc_type", type=click.STRING)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def ts(doc_type, env):
    """Get earliest and latest timestamps"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    q = {
        "size": 0,
        "aggs": {
            "min_date": {"min": {"field": "@timestamp", "format": "yyyy-MM-dd"}},
            "max_date": {"max": {"field": "@timestamp", "format": "yyyy-MM-dd"}},
        },
    }
    print(
        json.dumps(
            context.rawquery(doc_type, query=q).get("aggregations", {}), indent=2
        )
    )


@common.data.command()
@click.argument("doc_type", type=click.STRING)
@click.argument("field", type=click.STRING, nargs=-1)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def mapping(doc_type, field, env):
    """Print elasticsearch mapping"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    print(json.dumps(context.document_mappings(doc_type, *list(field)), indent=2))


@common.data.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def load_geonames(env):
    """Load geonames dataset into Elasticsearch.

    This script is adapted from code with Copyright (c) 2016 Open Event Data Alliance
    Provided with MIT license at https://github.com/openeventdata/es-geonames
    """
    project = Project(env=env)

    from yaada.core.cli.geonames import load_geonames

    load_geonames(project)


@common.data.command()
@click.argument("doc_type", type=click.STRING)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def del_index(doc_type, env):
    """Print terms aggregation"""
    if (
        input(f"Are you sure you want to delete whole index: {doc_type}? (y/N)").lower()
        == "y"
    ):
        project = Project(env=env)
        from yaada.core.analytic.context import make_analytic_context

        context = make_analytic_context(
            "CLI", init_pipelines=False, overrides=project.config
        )
        context.delete_index(doc_type)
        print("Done.")
    else:
        print("Canceling...")


@common.data.command()
@click.argument("bucket_name", type=click.STRING, required=False, default=None)
@click.argument("path_prefix", type=click.STRING, required=False, default="")
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def s3_ls(bucket_name, path_prefix, env):
    """List files in bucket"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    if bucket_name is None:
        for b in context.migration.list_buckets():
            print(b["Name"])
    else:
        s3_config = project.get_s3_bucket_config(bucket_name)
        bucket = context.migration.make_s3_bucket(**s3_config)
        for fn in bucket.list_filenames(prefix=path_prefix):
            print(fn)
        # print(json.dumps(list(bucket.list_filenames(prefix=path_prefix,recursive=recursive)),indent=2))


@common.data.command()
@click.argument("bucket_name", type=click.STRING, required=True)
@click.argument("remote_path", type=click.STRING, required=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def s3_rm(bucket_name, remote_path, env):
    """Delete a file from the bucket"""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    s3_config = project.get_s3_bucket_config(bucket_name)
    bucket = context.migration.make_s3_bucket(**s3_config)
    if (
        input(
            f"Are you sure you want to delete remote file: s3://{bucket.bucket}/{remote_path}? (y/N)"
        ).lower()
        == "y"
    ):
        bucket.delete_remote_file(remote_path)
    else:
        print("Canceling...")


@common.data.command()
@click.argument("bucket_name", type=click.STRING, required=True)
@click.argument("remote_path", type=click.STRING, required=True)
@click.argument(
    "local_path",
    type=click.Path(
        exists=False, file_okay=True, dir_okay=True, writable=True, resolve_path=True
    ),
    required=False,
    default=".",
)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def s3_download(bucket_name, remote_path, local_path, env):
    """Download a file from bucket."""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    s3_config = project.get_s3_bucket_config(bucket_name)
    bucket = context.migration.make_s3_bucket(**s3_config)

    if os.path.isdir(local_path):
        local_path = os.path.join(local_path, os.path.basename(remote_path))

    if input(f"Downloading {local_path}. Is this correct? (y/N)").lower() == "y":
        if os.path.exists(local_path):
            if input(f"{local_path} exists. Overwrite? (y/N)").lower() != "y":
                print("Canceling...")
                return

        bucket.fetch_file(remote_path, local_path)
    else:
        print("Canceling...")


@common.data.command()
@click.argument("bucket_name", type=click.STRING, required=True)
@click.argument(
    "local_path",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True
    ),
    required=True,
)
@click.argument("remote_path", type=click.STRING, required=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def s3_upload(bucket_name, local_path, remote_path, env):
    """Upload a file to bucket."""
    project = Project(env=env)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    s3_config = project.get_s3_bucket_config(bucket_name)
    bucket = context.migration.make_s3_bucket(**s3_config)

    with open(local_path, "rb") as f:
        bucket.put_file(remote_path, f)


# @common.data.command()
# @click.argument("bucket_name", type=click.STRING)
# @click.argument("remote_path", type=click.STRING)
# @click.option("--doc-type", type=click.STRING, default="*")
# @click.option("--query", type=click.STRING, default='{"query":{"match_all":{}}}')
# @click.option("--scroll", type=click.STRING, default="24h")
# @click.option("--scroll-size", type=click.INT, default=100)
# @click.option("--skip-artifacts", is_flag=True, default=False)
# @click.option(
#     "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
# )
# def s3_save_tar(
#     bucket_name, remote_path, doc_type, query, scroll, scroll_size, skip_artifacts, env
# ):
#     """Save data to tarball in s3."""

#     valid_extensions = ['.tar','.tgz']

#     if not any([remote_path.endswith(ext) for ext in valid_extensions]):
#         raise Exception(f'`remote_path` must be a file with extention in {valid_extensions}')

#     project = Project(env=env)
#     s3_config = project.get_s3_bucket_config(bucket_name)
#     from yaada.core.analytic.context import make_analytic_context

#     context = make_analytic_context(
#         "CLI", init_pipelines=False, overrides=project.config
#     )
#     bucket = context.migration.make_s3_bucket(**s3_config)
#     q = json.loads(query)

#     context.migration.save_archive_to_s3_tar(
#         bucket,
#         remote_path,
#         doc_type=doc_type,
#         query=q,
#         scroll=scroll,
#         scroll_size=scroll_size,
#         include_artifacts=not skip_artifacts,
#     )


# @common.data.command()
# @click.argument("bucket_name", type=click.STRING)
# @click.argument("remote_path", type=click.STRING)
# @click.option(
#     "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
# )
# @click.option('--no-validate', is_flag=True, default=False, help="Disable schema validation during ingest.")
# def s3_load_tar(bucket_name, remote_path, env, no_validate):
#     """Load data from tarball in s3."""
#     project = Project(env=env)
#     s3_config = project.get_s3_bucket_config(bucket_name)
#     from yaada.core.analytic.context import make_analytic_context

#     context = make_analytic_context(
#         "CLI", init_pipelines=False, overrides=project.config
#     )
#     bucket = context.migration.make_s3_bucket(**s3_config)

#     context.migration.load_archive_from_s3_tar(bucket, remote_path, validate = not no_validate)


# @common.data.command()
# @click.argument("bucket_name", type=click.STRING)
# @click.argument("prefix", type=click.STRING)
# @click.option("--doc-type", type=click.STRING, default="*")
# @click.option("--query", type=click.STRING, default='{"query":{"match_all":{}}}')
# @click.option("--scroll", type=click.STRING, default="24h")
# @click.option("--scroll-size", type=click.INT, default=100)
# @click.option("--skip-artifacts", is_flag=True, default=False)
# @click.option(
#     "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
# )
# def s3_save(
#     bucket_name, prefix, doc_type, query, scroll, scroll_size, skip_artifacts, env
# ):
#     """Save data to s3 in directory archive structure."""
#     project = Project(env=env)
#     s3_config = project.get_s3_bucket_config(bucket_name)
#     from yaada.core.analytic.context import make_analytic_context

#     context = make_analytic_context(
#         "CLI", init_pipelines=False, overrides=project.config
#     )
#     bucket = context.migration.make_s3_bucket(**s3_config)
#     q = json.loads(query)

#     context.migration.save_archive_to_s3(
#         bucket,
#         prefix,
#         doc_type=doc_type,
#         query=q,
#         scroll=scroll,
#         scroll_size=scroll_size,
#         include_artifacts=not skip_artifacts,
#     )


# @common.data.command()
# @click.argument("bucket_name", type=click.STRING)
# @click.argument("prefix", type=click.STRING)
# @click.option(
#     "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
# )
# @click.option('--no-validate', is_flag=True, default=False, help="Disable schema validation during ingest.")
# def s3_load(bucket_name, prefix, env, no_validate):
#     """Load data from s3 directory structure"""
#     project = Project(env=env)
#     s3_config = project.get_s3_bucket_config(bucket_name)
#     from yaada.core.analytic.context import make_analytic_context

#     context = make_analytic_context(
#         "CLI", init_pipelines=False, overrides=project.config
#     )
#     bucket = context.migration.make_s3_bucket(**s3_config)

#     context.migration.load_archive_from_s3(bucket, prefix, validate = not no_validate)


@common.data.command()
@click.argument("bucket_name", type=click.STRING)
@click.argument("remote_path", type=click.STRING)
@click.option("--doc-type", type=click.STRING, default="*")
@click.option("--query", type=click.STRING, default='{"query":{"match_all":{}}}')
@click.option("--scroll", type=click.STRING, default="24h")
@click.option("--scroll-size", type=click.INT, default=100)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def s3_save_ldjson(bucket_name, remote_path, doc_type, query, scroll, scroll_size, env):
    """Export documents to an ldjson file"""
    project = Project(env=env)
    s3_config = project.get_s3_bucket_config(bucket_name)
    from yaada.core.analytic.context import make_analytic_context

    q = json.loads(query)
    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    bucket = context.migration.make_s3_bucket(**s3_config)

    context.migration.save_ldjson_to_s3(
        bucket,
        remote_path,
        doc_type=doc_type,
        query=q,
        scroll=scroll,
        scroll_size=scroll_size,
    )


@common.data.command()
@click.argument("bucket_name", type=click.STRING)
@click.argument("remote_path", type=click.STRING)
@click.option(
    "--process",
    is_flag=True,
    default=False,
    help="Run data through ingest pipelines while loading.",
)
@click.option(
    "--async",
    "not_sync",
    is_flag=True,
    default=False,
    help="Load data through asynchronous ingest pipeline rather than in local cli process.",
)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option(
    "--batch-size",
    required=False,
    type=int,
    default=10,
    show_default=True,
    help="Used for optimizing synchronous ingest speed.",
)
@click.option(
    "--no-validate",
    is_flag=True,
    default=False,
    help="Disable schema validation during ingest.",
)
@click.option(
    "--lazy-load",
    is_flag=True,
    default=False,
    help="Don't read whole file into memory. Will not see progress bar at ingest time.",
)
def s3_load_ldjson(
    bucket_name, remote_path, process, not_sync, env, batch_size, no_validate, lazy_load
):
    """Load data from line-delimited json"""
    project = Project(env=env)
    s3_config = project.get_s3_bucket_config(bucket_name)
    from yaada.core.analytic.context import make_analytic_context

    context = make_analytic_context(
        "CLI", init_pipelines=False, overrides=project.config
    )
    bucket = context.migration.make_s3_bucket(**s3_config)
    context.migration.load_ldjson_from_s3(
        bucket,
        remote_path,
        process=process,
        sync=not not_sync,
        batch_size=batch_size,
        validate=not no_validate,
        realize=not lazy_load,
    )
