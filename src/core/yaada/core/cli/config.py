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

import click

from yaada.core.cli import common
from yaada.core.cli.project import Project


@common.config.command()
@click.argument("env", type=click.STRING)
@click.option("--config-file", type=click.STRING, default="override")
@click.option("--hostname", type=click.STRING, default=None)
@click.option("--tenant", type=click.STRING, default=None)
@click.option("--prefix", type=click.STRING, default=None)
@click.option(
    "--protocol", type=click.Choice(["http", "https"]), default=None, required=False
)
@click.option("--mqtt-port", type=int, default=None)
@click.option("--mqtt-hostname", type=click.STRING, default=None)
@click.option("--elasticsearch-port", type=int, default=None)
@click.option("--elasticsearch-hostname", type=click.STRING, default=None)
@click.option("--objectstorage-port", type=int, default=None)
@click.option("--objectstorage-hostname", type=click.STRING, default=None)
@click.option("--objectstorage-location", type=click.STRING, default=None)
@click.option("--objectstorage-bucket", type=click.STRING, default=None)
@click.option("--objectstorage-secure", type=bool, default=None)
@click.option("--objectstorage-access-key-id", type=click.STRING, default=None)
@click.option("--objectstorage-secret-access-key", type=click.STRING, default=None)
def env(
    env,
    config_file,
    hostname,
    tenant,
    prefix,
    protocol,
    mqtt_port,
    mqtt_hostname,
    elasticsearch_port,
    elasticsearch_hostname,
    objectstorage_port,
    objectstorage_hostname,
    objectstorage_location,
    objectstorage_bucket,
    objectstorage_secure,
    objectstorage_access_key_id,
    objectstorage_secret_access_key,
):
    project = Project()
    data = {}
    data["environments"] = {}
    data["environments"][env] = dict()
    data["environments"][env]["mqtt"] = {}
    data["environments"][env]["elasticsearch"] = {}
    data["environments"][env]["objectstorage"] = {}

    if hostname is not None:
        data["environments"][env]["hostame"] = hostname

    if tenant is not None:
        data["environments"][env]["tenant"] = tenant

    if prefix is not None:
        data["environments"][env]["prefix"] = prefix

    if protocol is not None:
        data["environments"][env]["protocol"] = protocol

    if mqtt_port is not None:
        data["environments"][env]["mqtt"]["port"] = mqtt_port
    if mqtt_hostname is not None:
        data["environments"][env]["mqtt"]["hostname"] = mqtt_hostname

    if elasticsearch_port is not None:
        data["environments"][env]["elasticsearch"]["port"] = elasticsearch_port
    if elasticsearch_hostname is not None:
        data["environments"][env]["elasticsearch"]["hostname"] = elasticsearch_hostname

    if objectstorage_port is not None:
        data["environments"][env]["objectstorage"]["port"] = objectstorage_port
    if objectstorage_hostname is not None:
        data["environments"][env]["objectstorage"]["hostname"] = objectstorage_hostname
    if objectstorage_location is not None:
        data["environments"][env]["objectstorage"]["location"] = objectstorage_location
    if objectstorage_bucket is not None:
        data["environments"][env]["objectstorage"]["bucket"] = objectstorage_bucket
    if objectstorage_access_key_id is not None:
        data["environments"][env]["objectstorage"][
            "access_key_id"
        ] = objectstorage_access_key_id
    if objectstorage_secret_access_key is not None:
        data["environments"][env]["objectstorage"][
            "secret_access_key"
        ] = objectstorage_secret_access_key
    if objectstorage_secure is not None:
        data["environments"][env]["objectstorage"]["secure"] = objectstorage_secure

    project.write_side_config(config_file, data)
