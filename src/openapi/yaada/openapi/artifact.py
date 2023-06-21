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

import connexion
from flask import send_file

from yaada.core import utility


def upload_artifact(body, doc_type, id, sync, process, barrier, artifact_type, file):
    doc = connexion.request.context.doc_service.get(
        doc_type, id, _source_include=["doc_type", "_id", "artifacts"]
    )
    if doc is None:
        doc = dict(doc_type=doc_type, _id=id)
    doc = connexion.request.context.ob_service.receive_blob_upload(
        doc, artifact_type, file
    )
    connexion.request.context.update(doc, sync=sync, process=process, barrier=barrier)

    return utility.jsonify(doc), 200


def get_artifact(artifact_type, doc_type, id, filename):
    doc = connexion.request.context.doc_service.get(doc_type, id)

    for blob in doc["artifacts"][artifact_type]:
        if filename == blob["filename"]:
            tf = connexion.request.context.ob_service.fetch_file_to_temp(
                blob["remote_file_path"]
            )
            return send_file(
                tf, mimetype=blob["content_type"], attachment_filename=filename
            )

    return None
