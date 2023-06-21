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

import datetime
import glob
import os
import platform

import click

from yaada.core.cli import common
from yaada.core.cli.docker import DockerHelper
from yaada.core.cli.project import Project


@common.volume.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def ls(env):
    """list current project volumes"""
    project = Project(env=env)
    docker = DockerHelper(project)
    for v in docker.get_project_volumes():
        print(v)


@common.volume.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def purge(env):
    """purge current project volumes"""
    project = Project(env=env)
    docker = DockerHelper(project)
    for v in docker.get_project_volumes():
        docker.run_docker_command("volume", command_args=["rm", v], verbose=True)


@common.volume.command()
@click.argument(
    "destination",
    type=click.Path(file_okay=False, dir_okay=True, writable=True, resolve_path=True),
    default=f"docker_volume_backups/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def backup(destination, env):
    """Backup docker volumes to directory"""
    project = Project(env=env)
    docker = DockerHelper(project)
    print(f"Writing backup to: {destination}")
    if os.path.exists(destination):
        if os.path.isfile(destination):
            print(
                f"Error: destination must be a directory but is a file: {destination}"
            )
            os.exit(1)

    volumes = docker.get_project_volumes()
    print(f"Volumes to backup: {volumes}")

    print("\nVerify information above is correct")
    print("Warning: Make sure all containers are stopped before proceding!")
    if os.path.exists(destination) and os.path.isdir(destination):
        print(
            "Warning: destination directory already exists, data will be overwritten!"
        )

    print("\n")
    input("Return to continue, Ctl-C to cancel")

    if not os.path.exists(destination):
        print(f"Creating {destination}")
        os.makedirs(destination, exist_ok=True)

    for vol_name in volumes:
        dest_file = os.path.join(destination, f"{vol_name}.tgz")
        print(f"Backing up '{vol_name}' to '{dest_file}'")

        if platform.system() == "Windows":
            docker.run_docker_command(
                "run",
                command_args=[
                    "--rm",
                    "-it",
                    "-v",
                    f"{vol_name}:/volume",
                    "-v",
                    f"/{destination}:/backup",  # Windows needs an extra leading / for some reason
                    "alpine",
                    "tar",
                    "cfvz",
                    f"/backup/{vol_name}.tgz",
                    "-C",
                    "/volume",
                    "./",
                ],
                verbose=True,
            )
        else:
            docker.run_docker_command(
                "run",
                command_args=[
                    "--rm",
                    "-it",
                    "-v",
                    f"{vol_name}:/volume",
                    "-v",
                    f"{destination}:/backup",
                    "alpine",
                    "tar",
                    "cfvz",
                    f"/backup/{vol_name}.tgz",
                    "-C",
                    "/volume",
                    "./",
                ],
                verbose=True,
            )


@common.volume.command()
@click.argument(
    "source",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, writable=True, resolve_path=True
    ),
)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def restore(source, env):
    """Restore docker volumes from directory"""
    project = Project(env=env)
    docker = DockerHelper(project)
    print(f"Restoring data from: {source}")
    archives = glob.glob(f"{source}/*.tgz")
    print("Found the following volume backups:")
    for archive in archives:
        volume_basefile = os.path.basename(archive)
        print("    " + volume_basefile)
    # print(archives)

    print("Warning: Restoring onto existing volumes will lead to undefined results.")
    print("Are you sure you're willing to overwrite your current volumes?")
    print(
        "Are you sure that these volumes aren't currently mounted to running containers?"
    )
    input("Return to continue, Ctl-C to cancel")

    for archive in archives:
        volume_basefile = os.path.basename(archive)
        volume_name = os.path.splitext(volume_basefile)[0]
        if platform.system() == "Windows":
            docker.run_docker_command(
                "run",
                command_args=[
                    "--rm",
                    "-it",
                    "-v",
                    f"{volume_name}:/volume",
                    "-v",
                    f"/{source}:/backup",  # Windows needs an extra leading / for some reason
                    "alpine",
                    "sh",
                    "-c",
                    f"rm -rf /volume/* /volume/..?* /volume/.[!.]* ; cd /volume/ && tar xvfz /backup/{volume_basefile}",
                ],
                verbose=True,
            )
        else:
            docker.run_docker_command(
                "run",
                command_args=[
                    "--rm",
                    "-it",
                    "-v",
                    f"{volume_name}:/volume",
                    "-v",
                    f"{source}:/backup",
                    "alpine",
                    "sh",
                    "-c",
                    f"rm -rf /volume/* /volume/..?* /volume/.[!.]* ; cd /volume/ && tar xvfz /backup/{volume_basefile}",
                ],
                verbose=True,
            )
