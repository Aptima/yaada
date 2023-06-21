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

import logging
import mimetypes
import os
import tempfile

import boto3
import botocore

from yaada.core import default_log_level, exceptions, utility

mimetypes.add_type("text/markdown", ".md")
logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class ObjectStorageProvider:
    def __init__(self, config, overrides={}):
        self.config = config

        self.tenant = overrides.get("tenant", config.tenant)

        self.secure = overrides.get("secure", self.config.object_storage_secure)

        protocol = "http://"
        if self.secure:
            protocol = "https://"
        self.object_storage_url = protocol + config.object_storage_url
        if any([x in overrides for x in ["hostname", "port"]]):
            self.object_storage_url = (
                protocol + f"{overrides.get('hostname')}:{overrides.get('port','8000')}"
            )

        self.enabled = overrides.get("enabled", self.config.object_storage_enabled)

        logger.info(f"object_storage_url: {self.object_storage_url}")

        self.access_key_id = overrides.get(
            "access_key_id", self.config.object_storage_access_key_id
        )
        self.secret_access_key = overrides.get(
            "secret_access_key", self.config.object_storage_secret_access_key
        )

        logger.info(f"access_key_id: {self.access_key_id}")
        logger.info(f"secret_access_key: {self.secret_access_key}")

        self.bucket = overrides.get("bucket", self.config.object_storage_bucket)
        self.location = overrides.get("location", self.config.object_storage_location)
        logger.info(f"bucket: {self.bucket}")
        logger.info(f"location: {self.location}")

        self.make_bucket = overrides.get(
            "make_bucket", self.config.object_storage_make_bucket
        )

        if self.enabled:
            utility.wait_net_service(
                "objectstorage", self.object_storage_url, 5.0, config.connection_timeout
            )

            self.client = boto3.client(
                "s3",
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                endpoint_url=self.object_storage_url,
                use_ssl=self.secure,
            )

            if self.make_bucket:
                try:
                    self.client.head_bucket(Bucket=self.bucket)
                    logger.info(f"s3 bucket exists: {self.bucket}")
                except botocore.exceptions.ClientError:
                    r = self.client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={"LocationConstraint": self.location},
                    )
                    logger.info(f"created s3 bucket: {r}")
        else:
            self.client = None

    def check_enabled(self):
        if not self.enabled:
            raise exceptions.ObjectStorageDisabled(
                "Object storage is disabled. Please enable object storage before calling any object storage methods."
            )

    def create_temp_dir(self):
        return tempfile.TemporaryDirectory()

    def get_content_type(self, filename):
        return mimetypes.guess_type(filename)

    def create_remote_path(self, artifact_type, doc):
        remote_path = "{}/artifacts/{}/{}/{}".format(
            self.tenant,
            utility.urlencode(doc["doc_type"]),
            utility.urlencode(doc["_id"]),
            utility.urlencode(artifact_type),
        )
        return remote_path

    def fetch_file_to_temp(self, remote_file_path):
        self.check_enabled()
        tf = tempfile.NamedTemporaryFile()
        self.client.download_fileobj(
            Bucket=self.bucket, Key=remote_file_path, Fileobj=tf
        )
        tf.seek(0)
        return tf

    def fetch_file_to_directory(self, remote_file_path, local_dir, filename):
        self.check_enabled()
        if not os.path.isdir(local_dir):
            os.makedirs(local_dir)
        local_file_path = f"{local_dir}/{filename}"
        self.client.download_file(
            Bucket=self.bucket, Key=remote_file_path, Filename=local_file_path
        )

    def fetch_artifact_to_directory(
        self, doc, artifact_type, cache_dir="/tmp/yaada/artifacts-cache"
    ):
        self.check_enabled()
        if "artifacts" not in doc or artifact_type not in doc["artifacts"]:
            return None

        remote_path = self.create_remote_path(artifact_type, doc)
        local_path = os.path.join(
            cache_dir,
            utility.urlencode(doc["doc_type"]),
            utility.urlencode(doc["_id"]),
            artifact_type,
        )
        for blob in doc["artifacts"][artifact_type]:
            remote_file_path = f"{remote_path}/{utility.urlencode(blob['filename'])}"
            if not os.path.isfile(os.path.join(local_path, blob["filename"])):
                self.fetch_file_to_directory(
                    remote_file_path, local_path, blob["filename"]
                )
        return local_path

    def fetch_artifacts_to_directory(self, doc, cache_dir="/tmp/yaada/artifacts-cache"):
        self.check_enabled()
        for artifact_type in doc["artifacts"].keys():
            self.fetch_artifact_to_directory(doc, artifact_type, cache_dir)

    def save_file(self, remote_path, filename, file):
        self.check_enabled()
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        remote_file_path = f"{remote_path}/{utility.urlencode(filename)}"

        self.client.put_object(Bucket=self.bucket, Key=remote_file_path, Body=file)
        file.close()
        return dict(
            remote_file_path=remote_file_path,
            file_size=file_size,
            remote_path=remote_path,
            filename=filename,
        )

    def find_artifact(self, doc, artifact_type, filename):
        if "artifacts" in doc and artifact_type in doc["artifacts"]:
            for blob in doc["artifacts"][artifact_type]:
                if blob.get("filename", None) == filename:
                    return blob

    def save_artifact(self, doc, artifact_type, filename, file):
        self.check_enabled()
        # file.seek(0, 2)  # go to end of file
        # file_size = file.tell()
        file.seek(0)

        cleaned_filename = filename.split("?")[
            0
        ]  # stripping off any querystring parameters on end of filename
        content_type, encoding = self.get_content_type(cleaned_filename)

        if "artifacts" not in doc:
            doc["artifacts"] = {}
        if artifact_type not in doc["artifacts"]:
            doc["artifacts"][artifact_type] = []

        blob = self.find_artifact(doc, artifact_type, filename)
        if blob is None:
            blob = dict(filename=filename)
            if content_type is not None:
                blob["content_type"] = content_type
            doc["artifacts"][artifact_type].append(blob)

        remote_path = self.create_remote_path(artifact_type, doc)

        blob.update(self.save_file(remote_path, filename, file))

        return doc

    def save_artifact_dir(self, doc, artifact_type, local_dir, re_skip_matches=None):
        self.check_enabled()
        dir_path = None
        if isinstance(local_dir, str):
            dir_path = local_dir
        else:
            try:
                dir_path = local_dir.name
            except Exception:
                pass

        files = [
            f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))
        ]

        for filename in files:
            if re_skip_matches is not None and any(
                [f.match(filename) for f in re_skip_matches]
            ):
                continue
            with open(os.path.join(dir_path, filename), "rb") as f:
                self.save_artifact(doc, artifact_type, filename, f)

        return doc

    def receive_blob_upload(self, doc, artifact_type, filestorage):
        self.check_enabled()
        tf = tempfile.TemporaryFile()
        filestorage.save(tf)
        filename = filestorage.filename

        return self.save_artifact(doc, artifact_type, filename, tf)
