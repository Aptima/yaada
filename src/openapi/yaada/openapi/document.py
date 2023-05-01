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
from jsonschema.exceptions import ValidationError

from yaada.core import utility


def document_counts():
    return connexion.request.context.document_counts()


def search_post(body):

    result = connexion.request.context.doc_service.paged_query(
        body["doc_type"],
        body.get("query_body", {"query": {"match_all": {}}}),
        page_from=body.get("page_from", 0),
        page_size=body.get("page_size", 10),
        raw=body.get("raw", False),
        _source=body.get("_source", None),
        _source_include=body.get("_source_include", None),
        _source_exclude=body.get("_source_exclude", None),
    )
    return result


def search(
    doc_type,
    source_include=None,
    source_exclude=None,
    page_from=0,
    page_size=10,
    raw=False,
    query={"query": {"match_all": {}}},
):

    result = connexion.request.context.doc_service.paged_query(
        doc_type,
        query,
        page_from=page_from,
        page_size=page_size,
        raw=raw,
        _source_include=source_include,
        _source_exclude=source_exclude,
    )
    return result


def rawquery(body):

    result = connexion.request.context.doc_service.rawquery(
        body["doc_type"], body["query_body"]
    )
    return result


def term_counts(body):
    return connexion.request.context.doc_service.term_counts(
        body["doc_type"],
        body["term"],
        query=body.get("query_body", {"query": {"match_all": {}}}),
    )


def get_post(body):
    r = connexion.request.context.doc_service.get(
        body["doc_type"],
        body["id"],
        _source=body.get("_source", None),
        _source_include=body.get("_source_include", None),
        _source_exclude=body.get("_source_exclude", None),
    )
    if r is None:
        return None, 404
    return r


def get(doc_type, id, source_include=None, source_exclude=None):
    r = connexion.request.context.doc_service.get(
        doc_type,
        id,
        _source_include=source_include,
        _source_exclude=source_exclude,
    )
    if r is None:
        return None, 404
    return r


def mget_post(body):
    return connexion.request.context.doc_service.mget(
        body["doc_type"],
        body["ids"],
        _source=body.get("_source", None),
        _source_include=body.get("_source_include", None),
        _source_exclude=body.get("_source_exclude", None),
    )


def mget(doc_type, ids, source_include=None, source_exclude=None):
    return connexion.request.context.doc_service.mget(
        doc_type,
        ids,
        _source_include=source_include,
        _source_exclude=source_exclude,
    )


def ingest(body, sync=True, process=True, barrier=False):
    utility.assign_document_id(body)
    try:
        connexion.request.context.schema_manager.validate_document(body)
    except ValidationError as e:
        return str(e), 400

    connexion.request.context.update(body, sync=sync, process=process, barrier=barrier)

    return utility.jsonify(body)
