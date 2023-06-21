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

import base64
import datetime
import io
import json
import logging
import os
import sys
import time
import uuid as _uuid
import zipfile
from typing import List, Optional

import boto3
import botocore.exceptions
import click
from tqdm import tqdm

import docker
from yaada.core import utility
from yaada.core.cli import common
from yaada.core.cli.project import Project

logging.Logger.manager.loggerDict["boto3"].setLevel(logging.CRITICAL)
logging.Logger.manager.loggerDict["botocore"].setLevel(logging.CRITICAL)


def get_cf_value(project, name):
    if "cf" not in project.config:
        common.fatal_error("Project has not cloud formation ('cf') configuration.")
    val = project.config.get("cf").get(name, None)
    if val is None:
        common.fatal_error(f"'{name}' must be configured")
    return val


def copy_resource_to_s3(project, s3, stack_name, s3_bucket_name, package):
    archive_name = f"{stack_name}.zip"

    remote_object_path = f"stack-resource/{archive_name}"

    def file_list(package):
        for p in package:
            if os.path.isfile(p):
                yield p
            elif os.path.isdir(p):
                for root, dirs, files in os.walk(p):
                    for f in files:
                        yield os.path.join(root, f)

    def zip_files(file_list, zip_file):
        for f in file_list:
            zip_file.write(f)
            print(f"adding: {f}")

    b = s3.Bucket(s3_bucket_name)

    with io.BytesIO() as vfile:
        with zipfile.ZipFile(vfile, "w") as zipf:
            zip_files(file_list(package), zipf)
        vfile.seek(0)
        b.upload_fileobj(vfile, remote_object_path)

    print(f"Uploaded {s3_bucket_name}/{remote_object_path}")
    return remote_object_path


def get_ecr_base_url(uri):
    return uri.split("/yaada/", 1)[0]


def ecr_docker_login(ecr, docker_client, uri):
    base_uri = get_ecr_base_url(uri)
    tokens = ecr.get_authorization_token()["authorizationData"]
    for t in tokens:
        if t["proxyEndpoint"].find(base_uri) != -1:
            username, password = (
                base64.b64decode(t["authorizationToken"]).decode("ascii").split(":", 1)
            )
            docker_client.login(username=username, password=password, registry=base_uri)
            print(f"logged into {base_uri}")


def ensure_ecr_repository(ecr, repository_name):
    if not ecr_repositiry_exists(ecr, repository_name):
        uri = ecr.create_repository(
            repositoryName=repository_name, imageTagMutability="MUTABLE"
        )["repository"]["repositoryUri"]
        print(f"created ecr repository {uri}")
        return uri
    else:
        uri = ecr.describe_repositories(repositoryNames=[repository_name])[
            "repositories"
        ][0]["repositoryUri"]
        print(f"found ecr repository {uri}")
        return uri


def report_push_progress(progress):
    position = 0
    pbars = {}
    current = {}
    for doc in progress:
        if "status" in doc:
            if doc["status"] == "Pushing":
                i = doc.get("id", None)
                c = doc.get("progressDetail", {}).get("current", None)
                t = doc.get("progressDetail", {}).get("total", None)
                if i is not None and c is not None and t is not None:
                    if i in pbars:
                        pbars[i].total = t
                        pbars[i].update(c - current[i])
                        current[i] = c
                    else:
                        pbars[i] = tqdm(
                            total=t,
                            desc=i,
                            position=position,
                            unit_scale=True,
                            initial=c,
                            unit="b",
                        )
                        position += 1
                        current[i] = c
                # print(doc)
            else:
                pass
                # print(doc)
        else:
            if "errorDetail" in doc:
                common.fatal_error(f"error: {doc['errorDetail']['message']}")
            else:
                print(doc)
    for pbar in pbars.values():
        pbar.close()


def push_core_images(project, ecr, docker_client):
    images = project.get_core_images()
    tag = project.config.get("yaada_core_version")
    for img_name in images:
        uri = ensure_ecr_repository(ecr, img_name)
        ecr_docker_login(ecr, docker_client, uri)
        print(f"tagging: {img_name}:{tag} to {uri}:{tag}")
        docker_client.api.tag(f"{img_name}:{tag}", f"{uri}:{tag}")
        print(f"pushing image: {uri}:{tag}")
        report_push_progress(
            docker_client.images.push(uri, tag=tag, stream=True, decode=True)
        )


def pull_core_images(project, ecr, docker_client):
    images = project.get_core_images()
    tag = project.config.get("yaada_core_version")
    for img_name in images:
        uri = ensure_ecr_repository(ecr, img_name)
        ecr_docker_login(ecr, docker_client, uri)

        print(f"pulling image: {uri}:{tag}")
        docker_client.images.pull(uri, tag=tag)

        print(f"tagging: {uri}:{tag} to {img_name}:{tag} ")
        docker_client.api.tag(f"{uri}:{tag}", f"{img_name}:{tag}")


def push_image(project, ecr, docker_client, img_name, tag):
    uri = ensure_ecr_repository(ecr, img_name)
    ecr_docker_login(ecr, docker_client, uri)
    print(f"tagging: {img_name}:{tag} to {uri}:{tag}")
    docker_client.api.tag(f"{img_name}:{tag}", f"{uri}:{tag}")
    print(f"pushing image: {uri}:{tag}")
    report_push_progress(
        docker_client.images.push(uri, tag=tag, stream=True, decode=True)
    )
    return f"{uri}:{tag}"


def push_image_hash(project, ecr, docker_client, img_name, imghash):
    uri = ensure_ecr_repository(ecr, img_name)
    ecr_docker_login(ecr, docker_client, uri)
    print(f"pushing image: {uri}@{imghash}")
    report_push_progress(
        docker_client.images.push(f"{uri}@{imghash}", stream=True, decode=True)
    )


def push_project_images(project, ecr, docker_client):
    images = project.get_project_images()
    tags = project.get_project_tags()
    for img_name in images:
        for tag in tags:
            uri = ensure_ecr_repository(ecr, img_name)
            ecr_docker_login(ecr, docker_client, uri)
            print(f"tagging: {img_name}:{tag} to {uri}:{tag}")
            docker_client.api.tag(f"{img_name}:{tag}", f"{uri}:{tag}")
            print(f"pushing image: {uri}:{tag}")
            report_push_progress(
                docker_client.images.push(uri, tag=tag, stream=True, decode=True)
            )


def pull_project_images(project, ecr, docker_client):
    images = project.get_project_images()
    tags = project.get_project_tags()
    for img_name in images:
        for tag in tags:
            uri = ensure_ecr_repository(ecr, img_name)
            ecr_docker_login(ecr, docker_client, uri)
            print(f"pulling image: {uri}:{tag}")
            docker_client.images.pull(uri, tag=tag)

            print(f"tagging: {uri}:{tag} to {img_name}:{tag} ")
            docker_client.api.tag(f"{uri}:{tag}", f"{img_name}:{tag}")


def wait_for_deploy(project, stack_name):
    cf_client = boto3.client("cloudformation")
    while True:
        if stack_exists(cf_client, stack_name):
            stacks = cf_client.describe_stacks(StackName=stack_name)
            ip = None
            for stack in stacks.get("Stacks", []):
                if stack["StackName"] == stack_name:
                    print(
                        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {stack['StackStatus']}"
                    )
                    for output in stack.get("Outputs", []):
                        if output["OutputKey"] == "EC2InstancePrivateIp":
                            ip = output["OutputValue"]
            if ip is not None:
                write_cf_config(project, stack_name)
                newproject = Project(env=[stack_name])
                from yaada.core.analytic.context import make_analytic_context

                print("Waiting for backend services...", file=sys.stderr)
                context = make_analytic_context(  # noqa: F841
                    "CLI", init_pipelines=False, overrides=newproject.config
                )
                return
        time.sleep(15.0)


def wait_for_delete(project, stack_name):
    cf_client = boto3.client("cloudformation")
    while True:
        if stack_exists(cf_client, stack_name):
            stacks = cf_client.describe_stacks(StackName=stack_name)
            for stack in stacks.get("Stacks", []):
                if stack["StackName"] == stack_name:
                    print(
                        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {stack['StackStatus']}"
                    )
        else:
            return
        time.sleep(15.0)


def wait_for_instance_state(project, stack_name, instance_ids, state):
    client = boto3.client("ec2")
    instance_states = {instance_id: "unknown" for instance_id in instance_ids}
    while True:
        response = client.describe_instances(InstanceIds=instance_ids)
        for container in ["Reservations"]:
            for r in response.get(container, []):
                for instance in r.get("Instances", []):
                    instance_states[instance["InstanceId"]] = instance["State"]["Name"]
        print(instance_states)
        if all([val == state for val in instance_states.values()]):
            return
        time.sleep(15.0)


def write_cf_config(project, stack_name):
    cf_client = boto3.client("cloudformation")
    if stack_exists(cf_client, stack_name):
        stacks = cf_client.describe_stacks(StackName=stack_name)
        for stack in stacks.get("Stacks", []):
            ip = None
            instance_ids = []
            if stack["StackName"] == stack_name:
                for output in stack.get("Outputs", []):
                    if output["OutputKey"] == "EC2InstancePrivateIp":
                        ip = output["OutputValue"]
                    elif output["OutputKey"] == "EC2InstanceID":
                        instance_ids.append(output["OutputValue"])
            newconf = dict()
            newconf["cf"] = {}
            newconf["cf"]["ec2_instance_ids"] = instance_ids

            if ip is not None:
                newconf["environments"] = {}
                newconf["environments"][stack_name] = dict(hostname=ip)

            if len(newconf) > 0:
                project.write_side_config("cf", newconf)
    else:
        common.fatal_error(f"Stack {stack_name} doesn't exist. Can't write config")


def stack_exists(client, stack_name):
    try:
        stacks = client.describe_stacks(StackName=stack_name)
        if len(stacks["Stacks"]) > 0:
            return True
    except botocore.exceptions.ClientError:
        pass

    return False


def ecr_repositiry_exists(ecr, repository_name):
    try:
        repositories = ecr.describe_repositories(repositoryNames=[repository_name])
        if len(repositories["repositories"]) > 0:
            return True
    except botocore.exceptions.ClientError:
        pass

    return False


class CloudFormationExecutor:
    def __init__(self, env: Optional[List[str]] = None):
        self.ecr = boto3.client("ecr")
        self.docker_client = docker.from_env()
        self.s3 = boto3.resource("s3")
        self.env = env
        self._remote_context = None

    def remote_context(self, force=False):
        if self._remote_context is None or force:
            from yaada.core.analytic.context import make_analytic_context

            # project = Project(env=self.env)
            # stack_name = get_cf_value(project,"stack_name")
            remoteproject = Project(env=self.env)
            self._remote_context = make_analytic_context(
                "CLI", init_pipelines=False, overrides=remoteproject.config
            )
        return self._remote_context

    def stack_name(self):
        project = Project(env=self.env)
        return get_cf_value(project, "stack_name")

    def set_env(self, envs: List[str]):
        self.env = envs

    def add_env(self, env: str):
        if self.env is None:
            self.env = []
        if env not in self.env:
            self.env.append(env)

    def package(self):
        project = Project(env=self.env)
        stack_name = get_cf_value(project, "stack_name")
        deployment_s3_bucket = get_cf_value(project, "deployment_s3_bucket")
        package_paths = get_cf_value(project, "package")
        copy_resource_to_s3(
            project, self.s3, stack_name, deployment_s3_bucket, package_paths
        )

    def ecr_login(self):
        repositories = self.ecr.describe_repositories(
            repositoryNames=["yaada/yaada-core"]
        ).get("repositories", [])
        if len(repositories) == 0:
            common.fatal_error("No repositories available. Have you pushed?")
        uri = repositories[0]["repositoryUri"]
        base_uri = get_ecr_base_url(uri)
        tokens = self.ecr.get_authorization_token()["authorizationData"]
        for t in tokens:
            if t["proxyEndpoint"].find(base_uri) != -1:
                username, password = (
                    base64.b64decode(t["authorizationToken"])
                    .decode("ascii")
                    .split(":", 1)
                )
                login = dict(registry=base_uri, username=username, password=password)
                self.docker_client.login(**login)
                return login

    def push(self):
        project = Project(env=self.env)
        push_core_images(project, self.ecr, self.docker_client)
        push_project_images(project, self.ecr, self.docker_client)

    def pull(self):
        project = Project(env=self.env)
        pull_core_images(project, self.ecr, self.docker_client)
        pull_project_images(project, self.ecr, self.docker_client)

    def build_image(self, image, tag):
        project = Project(env=self.env)
        build = project.get_image_build(image)
        print(f"building {build}")

        img, output = self.docker_client.images.build(
            path=build["context"],
            dockerfile=build["dockerfile"],
            buildargs=build["build_args"],
            tag=build["image"] + ":" + tag,
        )
        # for o in output:
        #   print(o)

        return img.id

    def push_image(self, image, tag):
        project = Project(env=self.env)
        print(f"pushing {image}:{tag}")
        return push_image(project, self.ecr, self.docker_client, image, tag)

    # def push_image_hash(self,image,imghash):
    #   project = Project(env=self.env)
    #   print(f"pushing {image}@{hash}")
    #   push_image_hash(project,self.ecr,self.docker_client,image,imghash)

    def build(self):
        project = Project(env=self.env)
        for build in project.get_image_builds([]):
            print(build)
            img, output = self.docker_client.images.build(
                path=build["context"],
                dockerfile=build["dockerfile"],
                buildargs=build["build_args"],
                tag=build["image"] + ":latest",
            )
            for o in output:
                print(o)

    def instance_status(self):
        project = Project(env=self.env)
        # stack_name = get_cf_value(project, "stack_name")
        ec2_instance_ids = get_cf_value(project, "ec2_instance_ids")
        client = boto3.client("ec2")
        response = client.describe_instances(InstanceIds=ec2_instance_ids)
        return response

    def instance_started(self):
        # project = Project(env=self.env)
        # stack_name = get_cf_value(project, "stack_name")
        # ec2_instance_ids = get_cf_value(project, "ec2_instance_ids")
        s = self.instance_status()

        for r in s.get("Reservations", []):
            for instance in r.get("Instances", []):
                if instance["State"]["Name"] == "running":
                    return True
        return False

    def instance_stop(self, wait=True):
        project = Project(env=self.env)
        stack_name = get_cf_value(project, "stack_name")
        ec2_instance_ids = get_cf_value(project, "ec2_instance_ids")
        client = boto3.client("ec2")
        print(f"stopping {ec2_instance_ids}")
        client.stop_instances(InstanceIds=ec2_instance_ids)
        client.describe_instances(InstanceIds=ec2_instance_ids)
        if wait:
            wait_for_instance_state(project, stack_name, ec2_instance_ids, "stopped")

    def instance_start(self, wait=True):
        project = Project(env=self.env)
        stack_name = get_cf_value(project, "stack_name")
        ec2_instance_ids = get_cf_value(project, "ec2_instance_ids")
        client = boto3.client("ec2")
        print(f"starting {ec2_instance_ids}")
        client.start_instances(InstanceIds=ec2_instance_ids)
        if wait:
            wait_for_instance_state(project, stack_name, ec2_instance_ids, "running")

    def exec_analytic(
        self,
        analytic_name,
        analytic_session_id=None,
        parameters={},
        gpu=False,
        stream_status=False,
    ):
        project = Project(env=self.env)
        image = project.get_project_image()
        tag = "latest"
        print(f"using image:{image}:{tag}")
        print(f"gpu enabled: {gpu}")
        if analytic_session_id is None:
            analytic_session_id = str(_uuid.uuid4())

        self.build_image(image, tag)
        pushed_image_tag = self.push_image(image, tag)
        context = self.remote_context()
        status = context.async_exec_analytic(
            analytic_name,
            analytic_session_id=analytic_session_id,
            parameters=parameters,
            worker="docker",
            gpu=gpu,
            image=pushed_image_tag,
            login=self.ecr_login(),
            stream_status=stream_status,
        )
        return status
        # context.msg_service.subscribe_analytic_status(analytic_name,analytic_session_id)
        # while True:
        #   r = context.msg_service.fetch()
        #   for doc in r:
        #     yield doc
        #     if doc.get('finished',False) or doc.get('error',False):
        #       break
        # context.msg_service.unsubscribe_analytic_status(analytic_name,analytic_session_id)
        # context.msg_service.fetch()


@common.cf.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def package(env):
    cfe = CloudFormationExecutor(env=env)
    cfe.package()


@common.cf.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def push(env):
    cfe = CloudFormationExecutor(env=env)
    cfe.push()


@common.cf.command()
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def pull(env):
    cfe = CloudFormationExecutor(env=env)
    cfe.pull()


@common.cf.command()
@click.option("--verbose", "-v", is_flag=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--wait", "-w", is_flag=True)
def stack_deploy(verbose, env, wait):
    """Deploy a cloud formation template"""
    project = Project(env=env)
    if "cf" not in project.config:
        common.fatal_error("Project has not cloud formation ('cf') configuration.")

    # load the template from disk

    # template_file = get_cf_value(project, "template_file")

    # template_body = None
    # with open(template_file) as f:
    #     template_body = f.read()

    stack_name = get_cf_value(project, "stack_name")
    # service_role = get_cf_value(project, "service_role")

    cf_client = boto3.client("cloudformation")

    # stack_details = dict(
    #     StackName=stack_name,
    #     TemplateBody=template_body,
    #     RoleARN=service_role,
    #     Parameters=[
    #         {
    #             "ParameterKey": "AmiId",
    #             "ParameterValue": get_cf_value(project, "ami_id"),
    #         },
    #         {
    #             "ParameterKey": "SubnetId",
    #             "ParameterValue": get_cf_value(project, "subnet_id"),
    #         },
    #         {
    #             "ParameterKey": "VpcId",
    #             "ParameterValue": get_cf_value(project, "vpc_id"),
    #         },
    #         {
    #             "ParameterKey": "InstanceType",
    #             "ParameterValue": get_cf_value(project, "instance_type"),
    #         },
    #         {
    #             "ParameterKey": "EC2KeyName",
    #             "ParameterValue": get_cf_value(project, "ec2_key_name"),
    #         },
    #     ],
    #     Capabilities=[
    #         "CAPABILITY_IAM",
    #         "CAPABILITY_NAMED_IAM",
    #         "CAPABILITY_AUTO_EXPAND",
    #     ],
    # )

    if stack_exists(cf_client, stack_name):
        print(f"Stack {stack_name} already exists. Update not supported:")
        # response = cf_client.update_stack(
        #   **stack_details
        # )
    else:
        if wait:
            wait_for_deploy(project, stack_name)
        else:
            print(
                "Wait for stack to be created and an IP to be assigned and then run 'yda cf config' to create the yaada.cf.yml project file."
            )

    # cf_client = boto3.client('cloudformation')


@common.cf.command()
@click.option("--verbose", "-v", is_flag=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--wait", "-w", is_flag=True)
def stack_delete(verbose, env, wait):
    """Delete the configured cloud formation stack"""
    project = Project(env=env)

    stack_name = get_cf_value(project, "stack_name")

    cf_client = boto3.client("cloudformation")

    if stack_exists(cf_client, stack_name):
        print(f"Deleting stack {stack_name}")
        cf_client.delete_stack(StackName=stack_name)
        if wait:
            wait_for_delete(project, stack_name)
    else:
        print(f"Stack {stack_name} doesn't exist")


@common.cf.command()
@click.option("--verbose", "-v", is_flag=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
@click.option("--json", "is_json", is_flag=True, default=False)
def stack_status(verbose, env, is_json):
    """Status of the configured cloud formation stack"""
    project = Project(env=env)
    stack_name = get_cf_value(project, "stack_name")

    cf_client = boto3.client("cloudformation")
    if stack_exists(cf_client, stack_name):
        stacks = cf_client.describe_stacks(StackName=stack_name)
        if is_json:
            print(json.dumps(utility.jsonify(stacks), indent=2))
        else:
            for s in stacks.get("Stacks", []):
                print(f"{s['StackName']} -- {s['StackStatus']}")
                for o in s.get("Outputs", []):
                    print(f"   {o['OutputKey']}={o['OutputValue']}")
    else:
        print(f"Stack {stack_name} doesn't exist")


@common.cf.command()
def stack_wait_deploy():
    """Wait for a stack to be done deploying"""
    project = Project()
    stack_name = get_cf_value(project, "stack_name")

    wait_for_deploy(project, stack_name)
    print("READY")


@common.cf.command()
def stack_wait_delete():
    """Wait for a stack to be done deleting"""
    project = Project()
    stack_name = get_cf_value(project, "stack_name")

    wait_for_delete(project, stack_name)
    print("READY")


@common.cf.command()
@click.option("--verbose", "-v", is_flag=True)
@click.option(
    "--env", "-e", type=common.EnvironmentsType(), default=None, multiple=True
)
def config(verbose, env):
    """Write a stack project config file"""
    project = Project(env=env)
    stack_name = get_cf_value(project, "stack_name")

    write_cf_config(project, stack_name)


@common.cf.command()
@click.option("--wait", "-w", is_flag=True)
def instance_stop(wait):
    """Stop instances in current stack"""
    cfe = CloudFormationExecutor()
    cfe.instance_stop(wait)


@common.cf.command()
@click.option("--json", "is_json", is_flag=True, default=False)
def instance_status(is_json):
    """Status of ec2 instances"""
    cfe = CloudFormationExecutor()
    response = cfe.instance_status()
    if is_json:
        print(json.dumps(utility.jsonify(response), indent=2))
    else:
        for container in ["Reservations"]:
            for r in response.get(container, []):
                for instance in r.get("Instances", []):
                    print(
                        f"{container} id: {instance['InstanceId']} ip:{instance['PrivateIpAddress']} state: {instance['State']['Name']}"
                    )


@common.cf.command()
@click.option("--wait", "-w", is_flag=True)
def instance_start(wait):
    """Start instances in current stack"""
    cfe = CloudFormationExecutor()
    cfe.instance_start(wait)


@common.cf.command()
def ecr_login():
    """Get ECR login credentials"""
    cfe = CloudFormationExecutor()
    creds = cfe.ecr_login()
    if creds is not None:
        print(repr(creds))
    else:
        common.fatal_error("couldn't create ecr login credentials.")
