#!/usr/bin/env python
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
import os
import sys
import traceback

import docker
from yaada.core import utility
from yaada.core.analytic.execution import get_worker_labels, match_request_worker_label
from yaada.core.config import YAADAConfig
from yaada.core.infrastructure.providers import make_message_service

ANALYTIC_NAME = "docker_worker"
ANALYTIC_SESSION_ID = "0"
config = YAADAConfig()
msg_service = make_message_service(config)
msg_service.set_analytic(ANALYTIC_NAME, ANALYTIC_SESSION_ID)
msg_service.connect("docker-analytic-worker-0")
msg_service.subscribe_analytic_request()

env_variables_to_copy = [
    "FLASK_SERVER_IP",
    "FLASK_SERVER_PORT",
    "OBJECT_STORAGE_URL",
    "MQTT_HOSTNAME",
    "MQTT_PORT",
    "ELASTICSEARCH_URL",
    "YAADA_LOGLEVEL",
    "ARANGO_SERVER_HOSTS",
    "YAADA_CONFIG",
    "TIKA_SERVER_ENDPOINT",
    "YAADA_SERVICES_GEOPARSE_URL",
]

docker_env = {var: os.environ.get(var) for var in env_variables_to_copy}

DEFAULT_YAADA_IMAGE = os.environ.get(
    "YAADA_IMAGE",
    os.environ.get("YAADA_PROJECT_IMAGE", os.environ.get("YAADA_CORE_IMAGE")),
)
if DEFAULT_YAADA_IMAGE is None:
    print(
        "Error: one of the following environment variables must be set: YAADA_IMAGE, YAADA_PROJECT_IMAGE, YAADA_CORE_IMAGE"
    )
    sys.exit(1)
print(f"DEFAULT_YAADA_IMAGE:{DEFAULT_YAADA_IMAGE}")


def execute_analytic(req, msg_service):
    try:
        image = req.get("image", DEFAULT_YAADA_IMAGE)
        print(f"using image: {image}")
        device_requests = []
        gpu = req.get("gpu", False)

        if gpu:
            device_requests.append(
                dict(
                    Driver="nvidia",
                    Capabilities=[
                        ["gpu"],
                        ["nvidia"],
                        ["compute"],
                        ["compat32"],
                        ["graphics"],
                        ["utility"],
                        ["video"],
                        ["display"],
                    ],  # not sure which capabilities are really needed
                    Count=-1,  # enable all gpus
                )
            )
        login = req.get("login", None)
        if login is not None:
            docker_client.login(**login)
        print(f"pulling: {image}")
        docker_client.images.pull(image)
        command = [
            "yaada-single-job-executor.py",
            f"-a={req['analytic_name']}",
            f"-i={req['analytic_session_id']}",
        ]
        print(f"running {command} in {image}")
        docker_client.containers.run(
            image=image,
            command=command,
            detach=True,
            auto_remove=True,
            environment=docker_env,
            network="yaada-shared-infrastructure",
            name=f"yaada-single-job-executor-{req['analytic_session_id']}",
            device_requests=device_requests,
        )

    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
        status = dict(
            analytic_name=req["analytic_name"],
            analytic_session_id=req["analytic_session_id"],
            error=True,
            message=traceback.format_exc(),
        )
        msg_service.publish_analytic_status(
            req["analytic_name"], req["analytic_session_id"], status
        )


if __name__ == "__main__":
    labels = get_worker_labels()
    print(f"worker labels: {labels}")
    docker_client = docker.from_env()
    print("Ready for analytic requests...")
    while True:
        fetched = msg_service.fetch(timeout_ms=1000, max_count=1)
        for req in fetched:
            worker = req.get("worker", "default")
            if match_request_worker_label(labels, worker):
                print(f"executing {json.dumps(utility.jsonify(req),indent=2)}")
                execute_analytic(req, msg_service)
