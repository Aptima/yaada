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

import glob
import json
import logging
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

import boto3
import botocore
from tqdm import tqdm
from yaada.core import default_log_level, utility
from yaada.core.analytic.plugin import AnalyticContextPlugin

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class MigrationContextPlugin(AnalyticContextPlugin):
    def __init__(self):
        pass

    def register(self, context):
        self.context = context
        context.migration = self

    def export_to_ldjson_stream(
        self,
        outfile,
        doc_type="*",
        query={"query": {"match_all": {}}},
        scroll_size=100,
        scroll="24h",
        binary=False,
    ):
        doc_service = self.context.doc_service
        c = 0
        for doc in tqdm(
            doc_service.query(
                doc_type=doc_type, query=query, scroll_size=scroll_size, scroll=scroll
            )
        ):
            text = json.dumps(doc, cls=utility.DateTimeEncoder) + "\n"
            if binary:
                outfile.write(text.encode())
            else:
                outfile.write(text)
            c = c + 1
        logger.info(f"Wrote {c} documents")

    def save_ldjson_to_file(
        self,
        destination,
        doc_type="*",
        query={"query": {"match_all": {}}},
        scroll_size=100,
        scroll="24h",
        binary=False,
    ):
        if destination.endswith(".zip"):
            internal_name, ext = destination.rsplit(".", 1)
            basename = os.path.basename(internal_name)
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_BZIP2) as zf:
                with zf.open(basename, "w") as f:
                    self.export_to_ldjson_stream(
                        f,
                        doc_type=doc_type,
                        query=query,
                        scroll=scroll,
                        scroll_size=scroll_size,
                        binary=binary,
                    )

        else:
            with open(destination, "wb") as f:
                self.export_to_ldjson_stream(
                    f,
                    doc_type=doc_type,
                    query=query,
                    scroll=scroll,
                    scroll_size=scroll_size,
                    binary=binary,
                )

    def import_from_ldjson_stream(
        self,
        infile,
        process=True,
        sync=True,
        batch_size=10,
        validate=True,
        realize=False,
    ):
        # msg_service = self.context.msg_service
        lines = infile
        if realize:
            lines = infile.readlines()

        def doc_gen():
            for line in tqdm(lines):
                if line:
                    doc = json.loads(line.rstrip())
                    yield doc

        docs = doc_gen()
        for batch in utility.batched_generator(docs, batch_size):
            self.context.update(
                batch, process=process, sync=sync, archive=True, validate=validate
            )

    def load_ldjson_from_file(
        self,
        source,
        process=True,
        sync=True,
        batch_size=10,
        validate=True,
        realize=False,
    ):
        if source.endswith(".zip"):
            internal_name, ext = source.rsplit(".", 1)
            basename = os.path.basename(internal_name)
            with zipfile.ZipFile(source, "r", compression=zipfile.ZIP_BZIP2) as zf:
                with zf.open(basename, "r") as f:
                    self.import_from_ldjson_stream(
                        f,
                        process=process,
                        sync=sync,
                        batch_size=batch_size,
                        validate=validate,
                        realize=realize,
                    )
        else:
            with open(source) as f:
                self.import_from_ldjson_stream(
                    f,
                    process=process,
                    sync=sync,
                    batch_size=batch_size,
                    validate=validate,
                    realize=realize,
                )

    def save_archive_to_directory(
        self,
        directory_path,
        doc_type="*",
        query={"query": {"match_all": {}}},
        scroll_size=100,
        scroll="24h",
        include_artifacts=True,
        id_by_count=False,
        id_by_hash=True,
    ):
        c = 0
        for doc in tqdm(
            self.context.query(
                doc_type=doc_type, query=query, scroll_size=scroll_size, scroll=scroll
            ),
            desc=f"exporting to '{directory_path}'",
        ):
            id_str = utility.urlencode(doc["_id"])
            if id_by_hash:
                id_str = utility.hash_for_text([doc["_id"]])
            elif id_by_count:
                id_str = f"{c}"
            doc_dir_path = os.path.join(
                directory_path, utility.urlencode(doc["doc_type"]), id_str
            )
            if not os.path.isdir(doc_dir_path):
                os.makedirs(doc_dir_path)
            doc_json_path = os.path.join(doc_dir_path, "doc.json")
            with open(doc_json_path, "w") as jsonfile:
                json.dump(doc, jsonfile, indent=2)
            if "artifacts" in doc and include_artifacts:
                for artifact_type in doc.get("artifacts", {}):
                    for blob in doc["artifacts"][artifact_type]:
                        if blob and "remote_file_path" in blob and "filename" in blob:
                            doc_artifact_type_dir = os.path.join(
                                doc_dir_path, artifact_type
                            )
                            if not os.path.isdir(doc_artifact_type_dir):
                                os.makedirs(doc_artifact_type_dir)
                            self.context.fetch_file_to_directory(
                                blob["remote_file_path"],
                                doc_artifact_type_dir,
                                blob["filename"],
                            )
            logger.debug(f"saved {c} {doc['doc_type']}:{doc['_id']} to {doc_dir_path}")

            c = c + 1
        logger.info(f"done archiving {c} documents to {directory_path}")

    def load_archive_from_directory(
        self, directory_path, process=False, sync=True, validate=True
    ):
        c = 0

        def load_docs_gen():
            for doc_json_path in glob.iglob(
                f"{directory_path}/**/doc.json", recursive=True
            ):
                with open(doc_json_path, "r") as input:
                    doc = json.load(input)

                    doc_dir_path = os.path.dirname(doc_json_path)
                    if "artifacts" in doc:
                        for artifact_type in doc.get("artifacts", {}):
                            for blob in doc["artifacts"][artifact_type]:
                                if blob and "filename" in blob:
                                    doc_artifact_type_dir = os.path.join(
                                        doc_dir_path, artifact_type
                                    )
                                    if os.path.isdir(doc_artifact_type_dir):
                                        artifact_file_path = os.path.join(
                                            doc_artifact_type_dir, blob["filename"]
                                        )
                                        with open(
                                            artifact_file_path, "rb"
                                        ) as artifact_file:
                                            self.context.save_artifact(
                                                doc,
                                                artifact_type,
                                                blob["filename"],
                                                artifact_file,
                                            )
                    nonlocal c
                    c = c + 1
                    logger.debug(f"loaded {c} {doc['doc_type']}:{doc['_id']}")
                    yield doc

        docs = load_docs_gen()
        for batch in utility.batched_generator(
            tqdm(docs, desc="loading documents"), 10
        ):
            self.context.update(
                batch, process=process, sync=sync, archive=True, validate=validate
            )
        logger.info(f"done loading {c} documents from {directory_path}")

    def save_archive_to_tar(
        self,
        dest_path,
        doc_type="*",
        query={"query": {"match_all": {}}},
        scroll_size=100,
        scroll="24h",
        include_artifacts=True,
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            dest_basename = os.path.basename(dest_path)
            inner_dir = Path(dest_basename).stem
            download_dir = os.path.join(tempdir, inner_dir)
            mode = "w"
            if dest_path.endswith("tgz") or dest_path.endswith("tar.gz"):
                mode = "w:gz"
            logger.info(f"storing data in {download_dir}")
            self.save_archive_to_directory(
                download_dir,
                doc_type=doc_type,
                query=query,
                scroll_size=scroll_size,
                scroll=scroll,
                include_artifacts=include_artifacts,
            )
            temp_tar_path = os.path.join(tempdir, dest_basename)
            print(f"archiving to {temp_tar_path}")
            with tarfile.open(temp_tar_path, mode) as tar:
                tar.add(download_dir, arcname=inner_dir)
            print(f"moving {temp_tar_path} to {dest_path}")
            shutil.move(temp_tar_path, dest_path)

    def load_archive_from_tar(self, tar_path, process=False, sync=True, validate=True):
        with tempfile.TemporaryDirectory() as tempdir:
            basename = os.path.basename(tar_path)
            mode = "r"
            if basename.endswith("tgz") or basename.endswith("tar.gz"):
                mode = "r:gz"
            with tarfile.open(tar_path, mode) as tar:
                # tar.extractall(path=tempdir)
                for member in tqdm(
                    iterable=tar.getmembers(),
                    total=len(tar.getmembers()),
                    desc=f"extracting {tar_path}",
                ):
                    tar.extract(member=member, path=tempdir)

                archive_dir = os.path.join(tempdir)
                self.load_archive_from_directory(
                    archive_dir, process=process, sync=sync, validate=validate
                )

    def save_archive_to_s3_tar(
        self,
        bucket,
        remote_path,
        doc_type="*",
        query={"query": {"match_all": {}}},
        scroll_size=100,
        scroll="24h",
        include_artifacts=True,
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            basename = os.path.basename(remote_path)
            temp_tar_path = os.path.join(tempdir, basename)
            self.save_archive_to_tar(
                temp_tar_path,
                doc_type=doc_type,
                query=query,
                scroll_size=scroll_size,
                scroll=scroll,
                include_artifacts=include_artifacts,
            )
            with open(temp_tar_path, "rb") as f:
                bucket.put_file(remote_path, f)
                logger.debug(f"wrote file to {remote_path}")
                # print('cleaning up')

    def load_archive_from_s3_tar(
        self, bucket, remote_path, process=False, sync=True, validate=True
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            basename = os.path.basename(remote_path)
            temp_tar_path = os.path.join(tempdir, basename)
            bucket.fetch_file(remote_path, temp_tar_path)
            self.load_archive_from_tar(
                temp_tar_path, process=process, sync=sync, validate=validate
            )

    def save_archive_to_s3(
        self,
        bucket,
        prefix="archive",
        doc_type="*",
        query={"query": {"match_all": {}}},
        scroll_size=100,
        scroll="24h",
        include_artifacts=True,
    ):
        c = 0
        for doc in tqdm(
            self.context.query(
                doc_type=doc_type, query=query, scroll_size=scroll_size, scroll=scroll
            )
        ):
            s3_doc_dir_path = os.path.join(
                prefix,
                utility.urlencode(doc["doc_type"]),
                utility.hash_for_text([doc["id"]]),
            )
            doc_json_file_path = os.path.join(s3_doc_dir_path, "doc.json")
            with tempfile.NamedTemporaryFile() as tf:
                tf.write(json.dumps(doc, indent=2).encode("utf-8"))
                bucket.put_file(doc_json_file_path, tf)
                logger.debug(f"wrote {c} {doc_json_file_path}")

            if "artifacts" in doc and include_artifacts:
                for artifact_type in doc.get("artifacts", {}):
                    for blob in doc["artifacts"][artifact_type]:
                        if blob and "remote_file_path" in blob and "filename" in blob:
                            tf = self.context.fetch_file_to_temp(
                                blob["remote_file_path"]
                            )
                            s3_artifact_dir = os.path.join(
                                s3_doc_dir_path, utility.urlencode(artifact_type)
                            )
                            s3_artifact_file_path = os.path.join(
                                s3_artifact_dir, utility.urlencode(blob["filename"])
                            )
                            bucket.put_file(s3_artifact_file_path, tf)
                            tf.close()
                            logger.debug(f"wrote {c} {s3_artifact_file_path}")

            c = c + 1
        logger.info(f"done archiving {c} documents to '{bucket.bucket}/{prefix}'")

    def load_archive_from_s3(
        self, bucket, prefix, process=False, sync=True, validate=True
    ):
        c = 0

        def load_docs_gen():
            for doc_json_path in (
                p
                for p in bucket.list_filenames(prefix=prefix)
                if p.endswith("doc.json")
            ):
                json_file = bucket.fetch_file_to_temp(doc_json_path)
                doc = json.load(json_file)
                json_file.close()
                doc_dir_path = os.path.dirname(doc_json_path)
                if "artifacts" in doc:
                    for artifact_type in doc.get("artifacts", {}):
                        for blob in doc["artifacts"][artifact_type]:
                            if blob and "filename" in blob:
                                doc_artifact_type_dir = os.path.join(
                                    doc_dir_path, utility.urlencode(artifact_type)
                                )
                                artifact_file_path = os.path.join(
                                    doc_artifact_type_dir,
                                    utility.urlencode(blob["filename"]),
                                )
                                artifact_file = bucket.fetch_file_to_temp(
                                    artifact_file_path
                                )
                                self.context.save_artifact(
                                    doc, artifact_type, blob["filename"], artifact_file
                                )
                                artifact_file.close()
                nonlocal c
                c = c + 1

                logger.debug(f"loaded {c} {doc['doc_type']}:{doc['_id']}")

                yield doc

        docs = load_docs_gen()
        for batch in utility.batched_generator(tqdm(docs), 10):
            self.context.update(
                batch, process=process, sync=sync, archive=True, validate=validate
            )
        logger.info(f"done loading {c} documents from '{bucket.bucket}/{prefix}'")

    def save_ldjson_to_s3(
        self,
        bucket,
        remote_path,
        doc_type="*",
        query={"query": {"match_all": {}}},
        scroll_size=100,
        scroll="24h",
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            basename = os.path.basename(remote_path)
            temp_file_path = os.path.join(tempdir, basename)
            self.save_ldjson_to_file(
                temp_file_path,
                doc_type=doc_type,
                query=query,
                scroll=scroll,
                scroll_size=scroll_size,
                binary=True,
            )
            with open(temp_file_path, "rb") as f:
                bucket.put_file(remote_path, f)
                logger.debug(f"wrote file to {remote_path}")

    def load_ldjson_from_s3(
        self,
        bucket,
        remote_path,
        process=True,
        sync=True,
        batch_size=10,
        validate=True,
        realize=False,
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            basename = os.path.basename(remote_path)
            temp_file_path = os.path.join(tempdir, basename)
            bucket.fetch_file(remote_path, temp_file_path)
            self.load_ldjson_from_file(
                temp_file_path,
                process=process,
                sync=sync,
                batch_size=batch_size,
                validate=validate,
                realize=realize,
            )

    def to_context(
        self,
        to_context,
        doc_type="*",
        query={"query": {"match_all": {}}},
        scroll_size=100,
        scroll="24h",
        source=None,
        include_artifacts=True,
        process=False,
        sync=True,
        validate=True,
    ):
        c = 0
        for doc in tqdm(
            self.context.query(
                doc_type=doc_type,
                query=query,
                scroll_size=scroll_size,
                scroll=scroll,
                source=source,
            )
        ):
            if "artifacts" in doc and include_artifacts:
                for artifact_type in doc.get("artifacts", {}):
                    for blob in doc["artifacts"][artifact_type]:
                        if blob and "remote_file_path" in blob and "filename" in blob:
                            tf = self.context.fetch_file_to_temp(
                                blob["remote_file_path"]
                            )
                            to_context.save_artifact(
                                doc, artifact_type, blob["filename"], tf
                            )
                            tf.close()
            to_context.update(
                doc, process=process, sync=sync, archive=True, validate=validate
            )

            logger.debug(f"transferred {c} {doc['doc_type']}/{doc['_id']}")
            c = c + 1
        logger.info(f"transferred {c} documents")

    def make_s3_bucket(
        self,
        bucket,
        endpoint=None,
        access_key_id=None,
        secret_access_key=None,
        secure=None,
        region=None,
        http_client=None,
        prefix="",
    ):
        if endpoint is None:
            endpoint = self.context.ob_service.object_storage_url
        if access_key_id is None:
            access_key_id = self.context.ob_service.access_key_id
        if secret_access_key is None:
            secret_access_key = self.context.ob_service.secret_access_key
        if secure is None:
            secure = self.context.ob_service.secure
        if region is None:
            region = self.context.ob_service.location
        return S3Bucket(
            endpoint,
            bucket=bucket,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            secure=secure,
            region=region,
            http_client=http_client,
            prefix=prefix,
        )

    def list_buckets(self):
        endpoint = self.context.ob_service.object_storage_url
        access_key_id = self.context.ob_service.access_key_id
        secret_access_key = self.context.ob_service.secret_access_key
        secure = self.context.ob_service.secure

        client = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint,
            use_ssl=secure,
        )

        response = client.list_buckets()
        for bucket in response.get("Buckets", []):
            yield bucket


class S3Bucket:
    def __init__(
        self,
        endpoint,
        bucket,
        access_key_id=None,
        secret_access_key=None,
        secure=True,
        region="us-east-1",
        http_client=None,
        prefix="",
    ):
        self.bucket = bucket
        self.region = region
        self.prefix = prefix
        self.client = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint,
            use_ssl=secure,
        )
        try:
            self.client.head_bucket(Bucket=self.bucket)
            logger.info(f"s3 bucket exists: {self.bucket}")
        except botocore.exceptions.ClientError:
            r = self.client.create_bucket(
                Bucket=self.bucket,
                CreateBucketConfiguration={"LocationConstraint": self.region},
            )
            logger.info(f"created s3 bucket: {r}")

    def list_objects(self, prefix=None, max_count=None):
        i = 0
        paginator = self.client.get_paginator("list_objects")
        page_iterator = paginator.paginate(
            Bucket=self.bucket,
            PaginationConfig={"MaxItems": 10},
            Prefix=prefix or self.prefix,
        )
        for page in page_iterator:
            for ob in page.get("Contents", []):
                i += 1
                if max_count is not None:
                    if i > max_count:
                        return
                yield ob

    def list_filenames(self, prefix=None, max_count=None):
        return (
            ob["Key"]
            for ob in self.list_objects(
                prefix=prefix or self.prefix, max_count=max_count
            )
        )

    def fetch_file_to_temp(self, remote_file_path):
        meta_data = self.client.head_object(Bucket=self.bucket, Key=remote_file_path)
        total_length = int(meta_data.get("ContentLength", 0))
        tf = tempfile.NamedTemporaryFile()
        with tqdm(
            total=total_length,
            desc=f"fetching: s3://{self.bucket}/{remote_file_path}",
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            self.client.download_fileobj(
                Bucket=self.bucket,
                Key=remote_file_path,
                Fileobj=tf,
                Callback=pbar.update,
            )
        tf.seek(0)
        return tf

    def fetch_file(self, remote_file_path, local_file_path):
        meta_data = self.client.head_object(Bucket=self.bucket, Key=remote_file_path)
        total_length = int(meta_data.get("ContentLength", 0))

        with tqdm(
            total=total_length,
            desc=f"fetching: s3://{self.bucket}/{remote_file_path}",
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            with open(local_file_path, "wb") as f:
                self.client.download_fileobj(
                    Bucket=self.bucket,
                    Key=remote_file_path,
                    Fileobj=f,
                    Callback=pbar.update,
                )

        # self.client.download_file(
        #     Bucket=self.bucket, Key=remote_file_path, Filename=local_file_path
        # )

    def put_file(self, remote_file_path, file):
        file.seek(0, os.SEEK_END)
        total_length = file.tell()
        file.seek(0)

        with tqdm(
            total=total_length,
            desc=f"uploading: s3://{self.bucket}/{remote_file_path}",
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            self.client.upload_fileobj(
                Bucket=self.bucket,
                Key=remote_file_path,
                Fileobj=file,
                Callback=pbar.update,
            )
        # self.client.put_object(Bucket=self.bucket, Key=remote_file_path, Body=file)

    def delete_remote_file(self, remote_file_path):
        self.client.delete_object(Bucket=self.bucket, Key=remote_file_path)
        print(f"deleted 's3://{self.bucket}/{remote_file_path}'")
