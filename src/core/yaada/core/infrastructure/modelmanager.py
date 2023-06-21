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

import os
import tarfile
import tempfile
import typing

from yaada.core import analytic
from yaada.core.infrastructure.modelcache import ModelCache


class ModelManager:
    def __init__(self, config, context):
        self.cache = ModelCache(config.yaada_model_cache_size)
        self.context = context

    def save_model_instance(
        self,
        model,
        local_path=None,
        archive=True,
        save_model_document=True,
        process_model_document=False,
    ):
        model_name = model.get_name()
        model_instance_id = model.get_instance_id()
        model_cache_key = f"{model_name}/{model_instance_id}"

        if local_path is None:
            local_path = tempfile.TemporaryDirectory().name
        save_path = model.save(local_path)

        if model_cache_key not in self.cache:
            self.cache[model_cache_key] = model

        doc = {
            "doc_type": model_name,
            "_id": model_instance_id,
            "id": model_instance_id,
            "model_full_name": model.get_full_name(),
        }

        if archive:
            temp_dir = tempfile.TemporaryDirectory()
            archive_name = f"{model_name}_{model_instance_id}.tar.gz"
            archive_path = os.path.join(temp_dir.name, archive_name)
            with tarfile.open(archive_path, "w:gz") as tgz:
                tgz.add(save_path, arcname="")
            with open(archive_path, "rb") as f:
                doc = self.context.ob_service.save_artifact(
                    doc, "archive", os.path.basename(f.name), f
                )
        else:
            for type in model.get_artifact_types():
                path = os.path.join(save_path, model.get_artifact_path(type))
                if os.path.isdir(path):
                    doc = self.context.ob_service.save_artifact_dir(doc, type, path)
                elif os.path.isfile(path):
                    with open(path, "rb") as f:
                        doc = self.context.ob_service.save_artifact(
                            doc, type, os.path.basename(f.name), f
                        )
        if save_model_document:
            self.context.update(doc, process=process_model_document)
        return doc

    def load_model_instance(
        self,
        model_clazz_or_full_name: typing.Union[type, str],
        model_instance_id,
        local_path=None,
        archive=True,
    ):
        if isinstance(model_clazz_or_full_name, type):
            model_clazz = model_clazz_or_full_name
        elif isinstance(model_clazz_or_full_name, str):
            model_clazz = analytic.get_model_class(model_clazz_or_full_name)
        else:
            raise TypeError(
                "model_clazz_or_full_name must be class or fully qualified class name"
            )

        model_name = model_clazz.__name__
        model_cache_key = f"{model_name}/{model_instance_id}"

        if model_cache_key in self.cache:
            return self.cache[model_cache_key]
        else:
            if local_path is None:
                local_path = tempfile.TemporaryDirectory().name

            doc = self.context.get(model_name, model_instance_id)
            if doc is not None:
                if archive:
                    temp_dir = tempfile.TemporaryDirectory()
                    archive_name = f"{model_name}_{model_instance_id}.tar.gz"
                    archive_path = self.context.ob_service.fetch_artifact_to_directory(
                        doc, "archive", temp_dir.name
                    )
                    if archive_path is None:
                        return None
                    with tarfile.open(
                        os.path.join(archive_path, archive_name), "r:gz"
                    ) as tgz:
                        tgz.extractall(
                            path=os.path.join(local_path, model_name, model_instance_id)
                        )
                else:
                    self.context.ob_service.fetch_artifacts_to_directory(
                        doc, local_path
                    )

                model = model_clazz.load(local_path, model_instance_id)
                self.cache[model_cache_key] = model
                return model

        return None

    def invalidate_model_instance(self, model_clazz, model_instance_id):
        model_cache_key = f"{model_clazz.__name__}/{model_instance_id}"
        if model_cache_key in self.cache:
            self.cache.mark_evictable(model_cache_key)
            del self.cache[model_cache_key]

    def mark_model_unevictable(self, model_clazz, model_instance_id):
        model_cache_key = f"{model_clazz.__name__}/{model_instance_id}"
        if model_cache_key in self.cache:
            self.cache.mark_unevictable(model_cache_key)

    def mark_model_evictable(self, model_clazz, model_instance_id):
        model_cache_key = f"{model_clazz.__name__}/{model_instance_id}"
        if model_cache_key in self.cache:
            self.cache.mark_evictable(model_cache_key)

    def get_unevictable(self):
        return self.cache.unevictable_nodes()
