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

import copy
import json
import logging
import time
import warnings
from datetime import datetime, timedelta

from deepmerge import always_merger
from elasticsearch import Elasticsearch, helpers
from elasticsearch.client import ClusterClient, IndicesClient
from elasticsearch.exceptions import NotFoundError
from elasticsearch.helpers.errors import BulkIndexError
from yaada.core import default_log_level, utility

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class ElasticsearchProvider:
    def __init__(self, config, overrides={}):
        self.config = config
        logger.debug(f"overrides {overrides}")
        elasticsearch_url = self.config.elasticsearch_url

        if any([x in overrides for x in ["hostname", "port", "protocol"]]):
            elasticsearch_url = f"{overrides.get('protocol','http')}://{overrides.get('hostname')}:{overrides.get('port','9200')}"
        utility.wait_net_service(
            "elasticsearch", elasticsearch_url, 5.0, config.connection_timeout
        )
        elasticsearch_logger = logging.getLogger("elasticsearch")
        elasticsearch_logger.disabled = True
        self.username = overrides.get("username", config.elasticsearch_username)
        self.password = overrides.get("password", config.elasticsearch_password)
        http_auth = None

        if self.username and self.password:
            http_auth = (self.username, self.password)

        logger.info(
            f"connecting to elasticsearch elasticsearch_url={elasticsearch_url}"
        )
        self.es = Elasticsearch(
            elasticsearch_url, timeout=60, max_retries=2, http_auth=http_auth
        )

        self.wait_for_es()
        elasticsearch_logger.disabled = False
        self.tenant = overrides.get("tenant", config.tenant)
        self.prefix = overrides.get("prefix", config.data_prefix)
        self.document_buffer = []
        self.result_buffer = []
        self.last_result_flush = datetime.utcnow()
        self.last_document_flush = datetime.utcnow()
        self.index_cache = set()
        self.index_has_ts = self.config.elasticsearch_index_has_ts

    @staticmethod
    def clean_fields(doc):
        return {k: v for k, v in doc.items() if k not in {"_id", "_op_type"}}

    def wait_for_es(self, timeout=30):
        cluster = ClusterClient(self.es)
        start_time = time.time()
        while True:
            try:
                if self.es.ping():
                    health = cluster.health()

                    if health["status"] in ["yellow", "green"]:
                        return True
            except Exception:
                time.sleep(1)
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout:
                raise TimeoutError("waited too long for analytic context")

    def reset_index_cache(self):
        self.index_cache = set()

    def set_tenant(self, tenant):
        self.tenant = tenant

    def init_indexes(self):
        for doc_type in self.config.elasticsearch_index_config:
            self.init_index(doc_type)

    def index_str(self, base, name, tenant=None):
        prefix = self.prefix
        mytenant = self.tenant
        if tenant is not None:
            mytenant = tenant

        if self.index_has_ts:
            ts = datetime.utcnow().strftime("%Y%m%d")
            return f"{prefix}-{mytenant}-{base}-{name.lower()}-{ts}"
        else:
            return f"{prefix}-{mytenant}-{base}-{name.lower()}"

    def all_docs_i_pattern(self, tenant=None):
        prefix = self.prefix
        mytenant = self.tenant
        if tenant is not None:
            mytenant = tenant
        return f"{prefix}-{mytenant}-document-*"

    def i_pattern(self, doc_type, tenant=None):
        prefix = self.prefix
        mytenant = self.tenant
        if tenant is not None:
            mytenant = tenant
        if self.index_has_ts:
            return f"{prefix}-{mytenant}-document-{doc_type.lower()}-*"
        else:
            return f"{prefix}-{mytenant}-document-{doc_type.lower()}"

    def document_mappings(self, doc_type, *fields):
        return self.index_field_mappings(doc_type, *fields)

    def index_field_mappings(self, doc_type, *fields):
        x = ",".join(fields)
        if x == "":
            x = "*"
        index = self.index_str("document", doc_type)
        if self.es.indices.exists(index=index):
            m = self.es.indices.get_field_mapping(index=index, fields=x)
            return m
        else:
            return None

    def index_settings(self, doc_type):
        index = self.index_str("document", doc_type)
        if self.es.indices.exists(index=index):
            m = self.es.indices.get_settings(index=index, flat_settings=True)
            return m
        else:
            return None

    def index_mappings(self, doc_type):
        index = self.index_str("document", doc_type)
        if self.es.indices.exists(index=index):
            m = self.es.indices.get_mapping(index=index)
            return m
        else:
            return None

    def init_index(self, doc_type, settings={}, mappings={}, aliases={}):
        _index = self.index_str("document", doc_type)
        _mappings = {
            "properties": {"doc_type": {"type": "keyword"}, "id": {"type": "keyword"}},
            "dynamic_templates": [
                {
                    "geopoint_strings": {
                        "match_mapping_type": "string",
                        "match": "*_geopoint",
                        "mapping": {"type": "geo_point"},
                    }
                },
                {
                    "geopoint_objects": {
                        "match_mapping_type": "object",
                        "match": "*_geopoint",
                        "mapping": {"type": "geo_point"},
                    }
                },
                {
                    "geoshape_strings": {
                        "match_mapping_type": "string",
                        "match": "*_geoshape",
                        "mapping": {"type": "geo_shape"},
                    }
                },
                {
                    "geoshape_objects": {
                        "match_mapping_type": "object",
                        "match": "*_geoshape",
                        "mapping": {"type": "geo_shape"},
                    }
                },
            ],
        }
        _settings = utility.nestify_dict(
            {
                "number_of_shards": 1,
                "index.mapping.total_fields.limit": self.config.elasticsearch_field_limit,
            }
        )
        _aliases = {}
        if (
            self.config.elasticsearch_index_config
            and doc_type in self.config.elasticsearch_index_config
        ):
            _mappings = always_merger.merge(
                _mappings,
                utility.nestify_dict(
                    self.config.elasticsearch_index_config.get(doc_type).get(
                        "mappings", {}
                    )
                ),
            )
            _settings = always_merger.merge(
                _settings,
                utility.nestify_dict(
                    self.config.elasticsearch_index_config.get(doc_type).get(
                        "settings", {}
                    )
                ),
            )
            _aliases = always_merger.merge(
                _aliases,
                utility.nestify_dict(
                    self.config.elasticsearch_index_config.get(doc_type).get(
                        "aliases", {}
                    )
                ),
            )

        _mappings = always_merger.merge(_mappings, utility.nestify_dict(mappings))
        _settings = always_merger.merge(_settings, utility.nestify_dict(settings))
        _aliases = always_merger.merge(_aliases, utility.nestify_dict(aliases))
        if _index not in self.index_cache:
            if self.es.indices.exists(index=_index):
                self.index_cache.add(_index)
            else:
                body = {
                    "settings": _settings,
                    "mappings": _mappings,
                    "aliases": _aliases,
                }
                logger.info(f"{_index} body {json.dumps(body,indent=2)}")
                ic = IndicesClient(self.es)
                ic.create(index=_index, body=body)
                self.index_cache.add(_index)

    def is_time_to_flush(self):
        return len(
            self.document_buffer
        ) > self.config.ingest_buff_size or datetime.utcnow() - self.last_document_flush > timedelta(
            seconds=2
        )

    def enqueue_document(self, doc):
        self.document_buffer.append(doc)

    def write_analytic_status(self, analytic_name, analytic_session_id, status):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.es.index(
                index=self.index_str("analytic", analytic_name),
                doc_type="status",
                id=analytic_session_id,
                body=status,
            )

    def write_ingest_error(self, error_type, data):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.es.index(
                index=self.index_str("error", error_type),
                body={
                    "@timestamp": datetime.utcnow(),
                    "data": json.dumps(utility.jsonify(data), indent=2),
                },
            )

    # def send_ingest_status(self, status):
    #
    #   self.es.index(
    #     index='ingest',
    #     doc_type='status',
    #     body=status
    #   )

    def doc_is_valid(self, doc):
        if "_id" not in doc or not doc["_id"]:
            return False
        if "id" not in doc or not doc["id"]:
            return False
        if "doc_type" not in doc or not doc["doc_type"]:
            return False

        return True

    def create_bulk_action(self, doc):
        action = {
            "_index": self.index_str("document", doc["doc_type"]),
            "_id": doc["_id"],
        }
        self.init_index(doc["doc_type"])
        if "_op_type" not in doc or doc["_op_type"] == "index":
            action["_source"] = self.clean_fields(doc)
        elif doc["_op_type"] == "update":
            action["_op_type"] = doc.get("_op_type", "index")
            action["doc"] = self.clean_fields(doc)
            action["doc_as_upsert"] = True
        return action

    def flush_documents(self, raise_ingest_error=False):
        flushed_docs = set()
        if len(self.document_buffer) > 0:
            actions = []
            for doc in self.document_buffer:
                if not self.doc_is_valid(doc):
                    # if the document isn't valid, don't ingest and instead put into a penalty index
                    self.write_ingest_error("missing_fields", doc)
                else:
                    # if the document is valid, create a bulk action and store the identifier into the result set
                    actions.append(self.create_bulk_action(doc))
                    flushed_docs.add((doc["doc_type"], doc["_id"]))
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    helpers.bulk(
                        self.es, actions, raise_on_error=True, raise_on_exception=False
                    )
            except BulkIndexError as e:
                for error in e.errors:
                    # if there is an indexing error, put the data into a penalty index and only raise exception of requested to.
                    for action_type, error_data in error.items():
                        self.write_ingest_error("BulkIndexError", error_data)
                        # since the document actually wasn't flushed to elasticsearch, remove from the result set
                        error_id = error_data.get("_id")
                        error_doc_type = (
                            error_data.get("data", {})
                            .get("doc", {})
                            .get("doc_type", None)
                        )
                        if error_id is not None and error_doc_type is not None:
                            flushed_docs.remove((error_doc_type, error_id))
                if raise_ingest_error:
                    raise e
            self.document_buffer.clear()
        self.last_document_flush = datetime.utcnow()
        return flushed_docs

    def store_batch(self, batch, raise_ingest_error=False, refresh=False):
        flushed_docs = set()
        if len(batch) > 0:
            actions = []
            for doc in batch:
                if not self.doc_is_valid(doc):
                    # if the document isn't valid, don't ingest and instead put into a penalty index
                    self.write_ingest_error("missing_fields", doc)
                else:
                    # if the document is valid, create a bulk action and store the identifier into the result set
                    actions.append(self.create_bulk_action(doc))
                    flushed_docs.add((doc["doc_type"], doc["_id"]))
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    helpers.bulk(
                        self.es,
                        actions,
                        raise_on_error=True,
                        raise_on_exception=False,
                        refresh=refresh,
                    )
            except BulkIndexError as e:
                for error in e.errors:
                    # if there is an indexing error, put the data into a penalty index and only raise exception of requested to.
                    for action_type, error_data in error.items():
                        self.write_ingest_error("BulkIndexError", error_data)
                        # since the document actually wasn't flushed to elasticsearch, remove from the result set
                        error_id = error_data.get("_id")
                        error_doc_type = (
                            error_data.get("data", {})
                            .get("doc", {})
                            .get("doc_type", None)
                        )
                        if error_id is not None and error_doc_type is not None:
                            flushed_docs.remove((error_doc_type, error_id))
                if raise_ingest_error:
                    raise e
        return flushed_docs

    def document_type_exists(self, doc_type, tenant=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.i_pattern(doc_type, tenant=tenant)
            return self.es.indices.exists(index=i)

    def query(
        self,
        doc_type,
        query={"query": {"match_all": {}}},
        size=None,
        scroll_size=1000,
        scroll="2m",
        tenant=None,
        raw=False,
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                i = self.i_pattern(doc_type, tenant=tenant)
                c = 0
                for d in helpers.scan(
                    self.es, query=query, index=i, size=scroll_size, scroll=scroll
                ):
                    if not raw:
                        doc = d["_source"]
                        doc["_id"] = d.get("_id", {})
                    else:
                        doc = d
                    c = c + 1

                    if size is not None and c > size:
                        return
                    yield doc
            except NotFoundError:
                pass

    def query_count(self, doc_type, query={"query": {"match_all": {}}}, tenant=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                i = self.i_pattern(doc_type, tenant=tenant)
                r = self.es.count(index=i, body=query)
                return r["count"]
            except NotFoundError:
                pass

    def paged_query(
        self,
        doc_type,
        query={"query": {"match_all": {}}},
        page_from=0,
        page_size=10,
        _source=None,
        _source_exclude=None,
        _source_include=None,
        raw=False,
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = dict(
                total_result=0,
                took=0,
                timed_out=False,
                page_from=0,
                page_size=0,
                documents=[],
            )
            try:
                i = self.i_pattern(doc_type)
                r = self.es.search(
                    index=i,
                    body=query,
                    from_=page_from,
                    size=page_size,
                    _source=_source,
                    _source_excludes=_source_exclude,
                    _source_includes=_source_include,
                )
                result["total_result"] = r["hits"]["total"]["value"]
                result["took"] = r["took"]
                result["timed_out"] = r["timed_out"]
                result["page_from"] = page_from
                result["page_size"] = page_size
                result["documents"] = []
                for hit in r["hits"].get("hits", []):
                    if not raw:
                        d = hit.get("_source", {})
                        d["_id"] = hit["_id"]
                    else:
                        d = hit

                    result["documents"].append(d)
            except NotFoundError:
                pass
            #   traceback.print_exc(limit=2)
            return result

    def exists(self, doc_type, id):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.i_pattern(doc_type)
            return self.es.exists(index=i, id=id)

    def get(
        self, doc_type, id, _source=None, _source_exclude=None, _source_include=None
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                i = self.i_pattern(doc_type)
                r = self.es.get(
                    index=i,
                    id=id,
                    _source=_source,
                    _source_excludes=_source_exclude,
                    _source_includes=_source_include,
                ).get("_source", None)
                r["_id"] = id
                return r
            except NotFoundError:
                return None

    def mget(
        self, doc_type, ids, _source=None, _source_exclude=None, _source_include=None
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                i = self.i_pattern(doc_type)
                docs = [dict(_index=i, _id=id) for id in ids]
                results = self.es.mget(
                    dict(docs=docs),
                    _source=_source,
                    _source_excludes=_source_exclude,
                    _source_includes=_source_include,
                )
                return [
                    dict(_id=r["_id"], **r["_source"])
                    for r in results["docs"]
                    if r["found"]
                ]
            except NotFoundError:
                return []

    def delete_by_query(self, doc_type, query, tenant=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.i_pattern(doc_type, tenant=tenant)
            self.es.delete_by_query(body=query, index=i)

    def delete(self, doc_type, id):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.i_pattern(doc_type)
            self.es.delete(index=i, id=id)

    def delete_index(self, doc_type, tenant=None, initialize_index=True):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.i_pattern(doc_type, tenant=tenant)
            if self.es.indices.exists(index=i):
                self.es.indices.delete(index=i)
                self.reset_index_cache()
            if initialize_index:
                self.init_index(doc_type)

    def document_counts(self, tenant=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.all_docs_i_pattern(tenant=tenant)
            query = {
                "aggregations": {
                    "count_by_type": {"terms": {"field": "doc_type", "size": 10000}}
                },
                "size": 0,
            }
            buckets = (
                self.es.search(body=query, index=i)
                .get("aggregations", {})
                .get("count_by_type", {})
                .get("buckets", [])
            )
            r = {}
            for b in buckets:
                r[b["key"]] = b["doc_count"]
            return r

    def aggregation(self, doc_type, query, tenant=None):
        return self.rawquery(doc_type, query, tenant)

    def rawquery(self, doc_type, query, tenant=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.i_pattern(doc_type, tenant=tenant)
            return self.es.search(body=query, index=i)

    def term_counts(
        self, doc_type, term, query={"query": {"match_all": {}}}, tenant=None
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                q = copy.deepcopy(query)
                q["aggregations"] = {
                    "count_by_term": {"terms": {"field": term, "size": 10000}}
                }
                q["size"] = 0
                buckets = (
                    self.rawquery(doc_type, q)
                    .get("aggregations", {})
                    .get("count_by_term", {})
                    .get("buckets", [])
                )
                r = {}
                for b in buckets:
                    r[b["key"]] = b["doc_count"]
                return r
            except NotFoundError:
                return {}

    def get_analytic_session_status(self, analytic_name, analytic_session_id):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.index_str("analytic", analytic_name)
            q = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "analytic_session_id.keyword": analytic_session_id
                                }
                            }
                        ]
                    }
                }
            }
            r = [
                h.get("_source")
                for h in self.es.search(body=q, index=i)["hits"]["hits"]
            ]
            if len(r) > 0:
                return {
                    k: v
                    for k, v in r[-1].items()
                    if k
                    in [
                        "started",
                        "finished",
                        "error",
                        "input_stats",
                        "output_stats",
                        "message",
                        "analytic_compute_duration_seconds",
                    ]
                }
            else:
                return {}

    def get_analytic_session_counts(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.index_str("analytic", "*")
            if not self.es.indices.exists(index=i):
                return []
            q = {
                "query": {"match_all": {}},
                "aggs": {
                    "count": {
                        "terms": {"field": "analytic_name.keyword", "size": 100000}
                    }
                },
                "size": 0,
            }
            buckets = (
                self.es.search(body=q, index=i)
                .get("aggregations", {})
                .get("count", {})
                .get("buckets", [])
            )
            r = {}
            for b in buckets:
                r[b["key"]] = b["doc_count"]
            return r

    def get_active_analytic_session_counts(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.index_str("analytic", "*")
            if not self.es.indices.exists(index=i):
                return []
            q = {
                "query": {
                    "bool": {
                        "must_not": [
                            {"term": {"finished": True}},
                            {"term": {"error": True}},
                        ]
                    }
                },
                "aggs": {
                    "count": {
                        "terms": {"field": "analytic_name.keyword", "size": 100000}
                    }
                },
                "size": 0,
            }
            buckets = (
                self.es.search(body=q, index=i)
                .get("aggregations", {})
                .get("count", {})
                .get("buckets", [])
            )
            r = {}
            for b in buckets:
                r[b["key"]] = b["doc_count"]
            return r

    def get_active_analytic_sessions(self, analytic_name):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.index_str("analytic", analytic_name)
            if not self.es.indices.exists(index=i):
                return []
            q = {
                "query": {
                    "bool": {
                        "must_not": [
                            {"term": {"finished": True}},
                            {"term": {"error": True}},
                        ]
                    }
                },
                "aggs": {
                    "count": {
                        "terms": {
                            "field": "analytic_session_id.keyword",
                            "size": 100000,
                        }
                    }
                },
                "size": 0,
            }
            buckets = (
                self.es.search(body=q, index=i)
                .get("aggregations", {})
                .get("count", {})
                .get("buckets", [])
            )
            r = []
            for b in buckets:
                r.append(b["key"])
                # r[b['key']] = b['doc_count']
            return r

    def get_error_analytic_sessions(self, analytic_name):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.index_str("analytic", analytic_name)
            if not self.es.indices.exists(index=i):
                return []
            q = {
                "query": {"bool": {"must": [{"term": {"error": True}}]}},
                "aggs": {
                    "count": {
                        "terms": {
                            "field": "analytic_session_id.keyword",
                            "size": 100000,
                        }
                    }
                },
                "size": 0,
            }
            buckets = (
                self.es.search(body=q, index=i)
                .get("aggregations", {})
                .get("count", {})
                .get("buckets", [])
            )
            r = []
            for b in buckets:
                r.append(b["key"])
                # r[b['key']] = b['doc_count']
            return r

    def get_finished_analytic_sessions(self, analytic_name):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.index_str("analytic", analytic_name)
            if not self.es.indices.exists(index=i):
                return []
            q = {
                "query": {"bool": {"must": [{"term": {"finished": True}}]}},
                "aggs": {
                    "count": {
                        "terms": {
                            "field": "analytic_session_id.keyword",
                            "size": 100000,
                        }
                    }
                },
                "size": 0,
            }
            buckets = (
                self.es.search(body=q, index=i)
                .get("aggregations", {})
                .get("count", {})
                .get("buckets", [])
            )
            r = []
            for b in buckets:
                r.append(b["key"])
                # r[b['key']] = b['doc_count']
            return r

    def delete_analytic_session(self, analytic_name, analytic_session_id):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            i = self.index_str("analytic", analytic_name)
            self.es.delete(index=i, id=analytic_session_id)

    def delete_analytic_sessions(self, analytic_name=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if analytic_name is None:
                i = self.index_str("analytic", "*")
                self.es.indices.delete(index=i)
            else:
                i = self.index_str("analytic", analytic_name)
                self.es.indices.delete(index=i)
