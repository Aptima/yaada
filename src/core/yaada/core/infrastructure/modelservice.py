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
import logging
import os.path
import tempfile
from os import listdir
from os.path import isfile, join

from yaada.core import default_log_level

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


def get_temp_dir():
    return tempfile.TemporaryDirectory()


def save_manifest(ob, model_name, model_instance_id, resource_dir, files):
    data = dict(files=files)
    with open(os.path.join(resource_dir.name, "manifest.json"), "w") as f:
        json.dump(data, f)
    with open(os.path.join(resource_dir.name, "manifest.json"), "rb") as f:
        ob.save_file(
            f"{ob.tenant}-models/{model_name}/{model_instance_id}", "manifest.json", f
        )
    logger.info(f"wrote manifest for {model_name}:{model_instance_id}--{data}")


def save_model_resources(ob, resource_dir, model_name, model_instance_id):
    files = [
        f for f in listdir(resource_dir.name) if isfile(join(resource_dir.name, f))
    ]
    save_manifest(ob, model_name, model_instance_id, resource_dir, files)
    for filename in files:
        with open(join(resource_dir.name, filename), "rb") as f:
            ob.save_file(
                f"{ob.tenant}-models/{model_name}/{model_instance_id}", filename, f
            )
            logger.info(
                f"wrote file 'models/{model_name}/{model_instance_id}/{filename}'"
            )


def load_manifest(ob, model_name, model_instance_id):
    tf = ob.fetch_file_to_temp(
        f"{ob.tenant}-models/{model_name}/{model_instance_id}/manifest.json"
    )
    data = json.load(tf)
    tf.close()
    return data


def load_model_resources(ob, resource_dir, model_name, model_instance_id):
    manifest = load_manifest(ob, model_name, model_instance_id)
    logger.info(f"loaded manifest for {model_name}:{model_instance_id}--{manifest}")
    for filename in manifest["files"]:
        ob.fetch_file_to_directory(
            f"{ob.tenant}-models/{model_name}/{model_instance_id}/{filename}",
            resource_dir.name,
            filename,
        )
        logger.info(
            f"read file '{ob.tenant}-models/{model_name}/{model_instance_id}/{filename}'"
        )


model_classes = {}


def register_model(clazz):
    model_name = clazz.__name__

    if model_name in model_classes:
        raise Exception(
            f"Can't register model '{model_name}'. A model of the same name already exists."
        )
    model_classes[model_name] = clazz

    logger.info(f"----- registered model {model_name}")


models = {}


def save_model_instance(ob, m):
    if m.model_name not in models:
        models[m.model_name] = {}
    models[m.model_name][m.model_instance_id] = m
    resource_dir = get_temp_dir()
    m.save_resources(resource_dir.name)
    save_model_resources(ob, resource_dir, m.model_name, m.model_instance_id)
    resource_dir.cleanup()
    logger.info(f"----- saved model instance {m.model_name}:{m.model_instance_id}")


def load_model_instance(ob, model_name, model_instance_id):
    if model_name in models and model_instance_id in models[model_name]:
        logger.info(
            f"----- loaded model instance {model_name}:{model_instance_id} from memory cache"
        )
        return models[model_name][model_instance_id]
    else:
        m = model_classes[model_name](model_instance_id)
        resource_dir = get_temp_dir()
        load_model_resources(ob, resource_dir, m.model_name, m.model_instance_id)
        m.load_resources(resource_dir.name)
        logger.info(
            f"----- loaded model instance {model_name}:{model_instance_id} from blobstore"
        )
        resource_dir.cleanup()
        if model_name not in models:
            models[model_name] = dict()
        models[model_name][model_instance_id] = m
        return m


def invalidate_model_instance(model_name, model_instance_id):
    if model_name in models and model_instance_id in models[model_name]:
        del models[model_name][model_instance_id]
