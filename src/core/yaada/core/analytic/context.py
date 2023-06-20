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
import time
import uuid as _uuid
from datetime import datetime

import jsonschema
from yaada.core import analytic, default_log_level, utility
from yaada.core.analytic.execution import async_exec_analytic, sync_exec_analytic
from yaada.core.analytic.pipeline import make_pipeline
from yaada.core.analytic.plugin import register_context_plugins
from yaada.core.config import YAADAConfig
from yaada.core.infrastructure import modelservice
from yaada.core.infrastructure.providers import (
    make_document_service,
    make_external_mqtt_service,
    make_message_service,
    make_model_manager,
    make_objectstorage_service,
)
from yaada.core.infrastructure.providers.mqtt import BufferedStream
from yaada.core.schema import SchemaManager
from yaada.core.utility import prepare_doc_for_insert

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


def apply_barrier_sentinel_generator(docs, sentinel_key, sentinel_value):
    for doc in docs:
        if doc and sentinel_key and sentinel_value:
            doc[sentinel_key] = sentinel_value
        yield doc


class IngestBarrierTimeout(Exception):
    pass


class AnalyticContext:
    def __init__(
        self,
        analytic_name,
        analytic_session_id,
        parameters,
        msg_service=None,
        doc_service=None,
        ob_service=None,
        model_manager=None,
        config=None,
        schema_manager=None,
        connect_to_services=True,
        overrides={},
    ):
        self.config = config
        if self.config is None:
            if "config" in overrides:
                self.config = YAADAConfig(overrides["config"], overrides=overrides)
            else:
                self.config = YAADAConfig(overrides=overrides)
        self.schema_manager = schema_manager
        if self.schema_manager is None:
            self.schema_manager = SchemaManager(self.config)

        self.analytic_name = analytic_name
        self.analytic_session_id = analytic_session_id
        self.parameters = parameters
        self.status = dict(
            analytic_name=self.analytic_name,
            analytic_session_id=self.analytic_session_id,
            started=False,
            finished=False,
            input_stats={},
            output_stats={},
            error=False,
            message=None,
            parameters=self.parameters,
        )
        self._results = []
        self._document_pipeline = None
        self.last_flush = datetime.utcnow()
        self._printer = None
        self.overrides = overrides
        self._start_time = datetime.utcnow()
        self.msg_service = msg_service
        self.doc_service = doc_service
        self.ob_service = ob_service
        self.model_manager = model_manager
        self.results_in_status = False
        self.migration = None
        self._connect_to_services = connect_to_services

        if self._connect_to_services:
            if self.msg_service is None:
                self.msg_service = make_message_service(
                    self.config, overrides=overrides
                )
                self.msg_service.connect(
                    f"analytic-context-{analytic_name}-{analytic_session_id}"
                )

            if self.doc_service is None:
                self.doc_service = make_document_service(
                    self.config, overrides=overrides
                )

            if self.ob_service is None:
                self.ob_service = make_objectstorage_service(
                    self.config, overrides=overrides
                )

            if self.model_manager is None:
                self.model_manager = make_model_manager(self.config, self)

            self.msg_service.set_analytic(analytic_name, analytic_session_id)

        register_context_plugins(self)

    def wait_for_ready(self, timeout=30):
        start_time = time.time()
        while True:
            try:
                self.document_counts()
                return True
            except Exception:
                elapsed_time = time.time() - start_time
                time.sleep(0.5)
                if elapsed_time >= timeout:
                    raise TimeoutError("waited too long for analytic context")

    def set_analytic_name(self, analytic_name):
        """
        Assigns an ``analytic_name`` value of a context object.

        Parameters:

        * **analytic_name: str**

          A description of the analytic's purpose

        Example:

        .. code-block:: python

            context.set_analytic_name("jupyter")
        """
        self.analytic_name = analytic_name
        # self.status['analytic_name'] = analytic_name

    def set_analytic_session_id(self, analytic_session_id):
        """
        Assigns an ``analytic_session_id`` value of a context object.

        Parameters:

          * **analytic_session_id: str**

            An identifier for this analytic object

        Example:

        .. code-block:: python

            context.set_analytic_session_id("Query Data")
        """
        self.analytic_session_id = analytic_session_id
        # self.status['analytic_session_id'] = analytic_session_id

    def create_derived_context(self, analytic_name, analytic_session_id, parameters):
        c = AnalyticContext(
            analytic_name=analytic_name,
            analytic_session_id=analytic_session_id,
            parameters=parameters,
            msg_service=self.msg_service,
            doc_service=self.doc_service,
            ob_service=self.ob_service,
            model_manager=self.model_manager,
            config=self.config,
            schema_manager=self.schema_manager,
            connect_to_services=self._connect_to_services,
            overrides=self.overrides,
        )
        c.status["parent"] = dict(
            analytic_name=self.analytic_name,
            analytic_session_id=self.analytic_session_id,
        )
        return c

    def include_results_in_status(self, results_in_status):
        self.results_in_status = results_in_status
        self._results = []
        # self.status['results'] = list()

    def init_pipeline(self):
        self._document_pipeline = make_pipeline(
            self.create_derived_context("pipeline", "0", {})
        )

    @property
    def document_pipeline(self):
        if self._document_pipeline is None:
            analytic.find_and_register(self.config, pipelines=True)
            self.init_pipeline()
        return self._document_pipeline

    def result_sync(
        self,
        docs,
        process=True,
        upsert=False,
        archive=False,
        barrier=False,
        barrier_timeout=600,
        raise_ingest_error=True,
        validate=True,
        refresh=False,
    ):
        if barrier:
            sentinel_value = str(_uuid.uuid4())
        else:
            sentinel_value = None
        for batch in utility.batched_generator(
            apply_barrier_sentinel_generator(docs, "_ingest_sentinel", sentinel_value),
            1000,
        ):
            # each batch is fully realized and has sentinel applied if necessary
            doc_dict = {}
            batch_to_store = []
            for doc in batch:
                doc = prepare_doc_for_insert(
                    doc,
                    self.analytic_name,
                    self.analytic_session_id,
                    upsert,
                    archive=archive,
                )
                if process:
                    doc = self.document_pipeline.process_document(doc)
                if validate:
                    try:
                        self.schema_manager.validate_document(doc)
                    except jsonschema.exceptions.ValidationError as e:
                        self.doc_service.write_ingest_error(
                            "jsonschema", dict(doc=doc, error=str(e))
                        )
                        if raise_ingest_error:
                            raise e
                        continue

                batch_to_store.append(doc)
                doc_dict[(doc["doc_type"], doc["_id"])] = doc
                self._count_result(doc["doc_type"])
                if self.results_in_status:
                    self._results.append(doc)
            docs_flushed = self.doc_service.store_batch(
                batch_to_store, raise_ingest_error=raise_ingest_error, refresh=refresh
            )
            for doc_type, _id in docs_flushed:
                if (doc_type, _id) in doc_dict:
                    self.msg_service.publish_sinklog(doc_dict[(doc_type, _id)])
                else:
                    logger.error(
                        f"{(doc_type,_id)} not found in doc_dict {doc_dict.keys()}"
                    )

            if barrier:
                for doc_type, _id in docs_flushed:
                    self.ingest_barrier(
                        doc_type,
                        _id,
                        barrier_timeout,
                        "_ingest_sentinel",
                        sentinel_value,
                    )

    def result_async(
        self,
        docs,
        process=True,
        upsert=False,
        archive=False,
        barrier=False,
        barrier_timeout=600,
        raise_ingest_error=True,
        validate=True,
    ):
        docs_to_wait_for = []
        if barrier:
            sentinel_value = str(_uuid.uuid4())
        else:
            sentinel_value = None

        for doc in apply_barrier_sentinel_generator(
            docs, "_ingest_sentinel", sentinel_value
        ):  # sentinel value is only applied if sentinel_value is non-None
            doc = prepare_doc_for_insert(
                doc, self.analytic_name, self.analytic_session_id, upsert
            )
            if validate:
                self.schema_manager.validate_document(doc)
                try:
                    self.schema_manager.validate_document(doc)
                except jsonschema.exceptions.ValidationError as e:
                    self.doc_service.write_ingest_error(
                        "jsonschema", dict(doc=doc, error=str(e))
                    )
                    if raise_ingest_error:
                        raise e
            if barrier:
                docs_to_wait_for.append((doc["doc_type"], doc["_id"]))
            if process:
                self.msg_service.publish_ingest(doc)
            else:
                self.msg_service.publish_sink(doc)
            self._count_result(doc["doc_type"])
            if self.results_in_status:
                self._results.append(doc)

        if barrier:
            for doc_type, _id in docs_to_wait_for:
                self.ingest_barrier(
                    doc_type, _id, barrier_timeout, "_ingest_sentinel", sentinel_value
                )

    def result(
        self,
        docs,
        process=True,
        sync=True,
        upsert=False,
        archive=False,
        barrier=False,
        barrier_timeout=600,
        raise_ingest_error=True,
        validate=True,
    ):
        if docs is None:
            return
        if utility.isiterable(docs):
            _docs = docs
        else:
            _docs = [docs]
        if sync:
            self.result_sync(
                docs=_docs,
                process=process,
                upsert=upsert,
                archive=archive,
                raise_ingest_error=raise_ingest_error,
                validate=validate,
                refresh=barrier,
            )
        else:
            self.result_async(
                docs=_docs,
                process=process,
                upsert=upsert,
                archive=archive,
                barrier=barrier,
                barrier_timeout=barrier_timeout,
                raise_ingest_error=raise_ingest_error,
                validate=validate,
            )
        self.report_status()

    def update(
        self,
        doc,
        process=True,
        sync=True,
        archive=False,
        barrier=False,
        barrier_timeout=600,
        raise_ingest_error=True,
        validate=True,
    ):
        """

        Stores the document given by the ``doc`` parameter in Elasticsearch.

          Parameters:

          * **doc: dict, list[dict]**

            The ``doc`` parameter, represents an Elasticsearch document to be ingested. The schema and details of a document can be found in :ref:`Documents`.

            This parameter can be given as a dictionary representation of an Elasticsearch document, or a list of ``doc``'s which will result in a batch-ingest.

          * **process: bool, default = True**

            optional

            If ``True``, the update process with run through the ingest pipeline

          * **sync: bool, default = True**

            optional

            If value is set to ``True``, the process will be run synchronously, if set to ``False``, it will run asynchronously.

          * **archive: bool, default = False**

            optional

            If the document or documents being ingested are from an archive, this parameter's value should be set
            to ``True``. Otherwise, it will default to ``False``.

            When ``False``, a document being ingested through the ``update`` function will be automtically set a timestamp value
            to the field ``@timestamp`` to the same time that it was ingested. When ``True``, because the document is from an archive,
            the ``@timestamp`` field will already exists and will not be reassigned. Therefore, it will keep it's value representing the time
            when it was originally ingested.

          * **barrier: bool, default=False**

            optional

            Setting ``barrier`` to ``True`` ensures that the document is indexed Elasticsearch
            and searchable before the the update function finishes running.

            Enabling ``barrier`` will dractically reduce throughput performace especially if ``update``
            is being called repeatedly by updating one document at a time. The process will not be slowed
            drastically if the ``update`` is run as a batch-ingest.

          * **barrier_timeout: int, default=600**

            optional

            This value is the maximum amount of time in seconds that the function will wait
            for the document to appear in Elasticsearch before finishing. If this maximum value
            is reached and the document is not in elastic search, it will return an
            ``IngestBarrierTimeout`` error. This only applies if the ``barrier`` parameter is set
            to ``True``.

          * **raise_ingest_error: bool, default=True**

            optional


        Short example:

        .. code-block:: python

          doc = {
              _id = "123",
              doc_type = "EmployeeSurvey",
              favorite_color = "red",
              favoite_number = 4
          }
          context.update(doc)


        """
        self.result(
            doc,
            process=process,
            sync=sync,
            upsert=True,
            archive=archive,
            barrier=barrier,
            barrier_timeout=barrier_timeout,
            raise_ingest_error=raise_ingest_error,
            validate=validate,
        )

    def _count_result(self, doc_type):
        if doc_type not in self.status["output_stats"]:
            self.status["output_stats"][doc_type] = 0
        self.status["output_stats"][doc_type] += 1

    def _count_input(self, doc_type):
        if doc_type not in self.status["input_stats"]:
            self.status["input_stats"][doc_type] = 0
        self.status["input_stats"][doc_type] += 1

    def report_status(self, write_es=False, message=None):
        """
        Called automatically when analytics are started and finishing. Available to be called by Anaytic developers
        to show intermediate status of a an analytic. To do this, call it in the ``run`` function of an Analytic.

          Parameters:

          * **write_es:bool, default=False**



          * **message:str, default=None**

            A string value containing the message to display.

        """
        self.status["@timestamp"] = datetime.utcnow()
        self.status["analytic_compute_duration_seconds"] = (
            datetime.utcnow() - self._start_time
        ).total_seconds()
        if message is not None:
            self.status["message"] = message
            if self._printer is not None:
                self._printer(message)
        self.msg_service.publish_analytic_status(
            self.analytic_name, self.analytic_session_id, self.status
        )
        if write_es:
            self.doc_service.write_analytic_status(
                self.analytic_name, self.analytic_session_id, self.status
            )

    def _started(self):
        self._start_time = datetime.utcnow()
        self.status["input_stats"] = {}
        self.status["output_stats"] = {}
        self.status["error"] = False
        self.status["message"] = None
        self.status["analytic_finish_time"] = None
        self.status["finished"] = False
        self.status["analytic_compute_duration_seconds"] = None
        self.status["started"] = True
        self.status["analytic_start_time"] = self._start_time.isoformat()
        self.report_status(write_es=True)

    def _finished(self):
        self._finish_time = datetime.utcnow()
        self.status["analytic_finish_time"] = self._finish_time.isoformat()
        self.status["finished"] = True
        self.status["analytic_compute_duration_seconds"] = (
            self._finish_time - self._start_time
        ).total_seconds()
        self.report_status(write_es=True)

    def error(self, message):
        self.status["error"] = True
        self.status["message"] = message
        self.report_status(write_es=True)

    def query(
        self,
        doc_type,
        query={"query": {"match_all": {}}},
        size=None,
        scroll_size=1000,
        scroll="2m",
        raw=False,
        source=None,
    ):
        """
        Returns results of a query to Elasticsearch as a generator object. It uses an abstraction of the `scroll API <https://www.elastic.co/guide/en/elasticsearch/reference/7.9/scroll-api.html>`_.

        Parameters:

          * **doc_type: str**

            This represents an Elasticsearch index. The query will search the index.

            Every document in Elasticsearch has a required ``doc_type`` field as described in the :ref:`Documents` section.

          * **query: dict, default={"query": {"match_all": {}}}**

            optional

            An Elasticsearch query. More info can be found in `Elasticsearch documentation.
            <https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html>`_
          * **size:int, default=None**

            optional

            Specifies number of documents to be returned. If the value is greater than the
            resulting number of documents, the resulting documents will all be returned.
          * **scroll_size:int, defaults=1000**

            optional

          * **scroll:str, default='2m'**

            optional

          * **raw:bool, default=False**

            optional

          * **source:list, default=None**

            optional

            A list of fields that will be shown for each document returned by the query. Used to limit the fields that each document will return.
            Must include ``_id`` and ``doc_type``.

        """

        if query is None:
            query = {"query": {"match_all": {}}}
        if source is not None:
            query["_source"] = source
        for d in self.doc_service.query(
            doc_type, query, size=size, scroll_size=scroll_size, scroll=scroll, raw=raw
        ):
            if not raw:
                self._count_input(d["doc_type"])
            yield d
        self.report_status()

    def paged_query(
        self,
        doc_type,
        query={"query": {"match_all": {}}},
        page_from=0,
        page_size=10,
        source=None,
        source_exclude=None,
        source_include=None,
        raw=False,
    ):
        return self.doc_service.paged_query(
            doc_type=doc_type,
            query=query,
            page_from=page_from,
            page_size=page_size,
            _source=source,
            _source_exclude=source_exclude,
            _source_include=source_include,
            raw=raw,
        )

    def query_count(self, doc_type, query={"query": {"match_all": {}}}):
        if query is None:
            query = {"query": {"match_all": {}}}

        return self.doc_service.query_count(doc_type, query)

    def get(
        self,
        doc_type,
        id,
        source=None,
        source_exclude=None,
        source_include=None,
        wait=False,
        timeout=60,
        sentinel_key="_ingest_sentinel",
        sentinel_value=None,
    ):
        """
        Returns a document from Elasticsearch.

        Parameters:

          * **doc_type: str**

            The document type of the desired document.

          * **id: str**

            The identifier of a single document.

          * **source: list, defult=None**

            optional

            A list containing the fields that will be returned for the document. Must include ``_id`` and ``doc_type``.

          * **source_exclude:list, default=None**

            optional

            A list containing the fields that will be excluded from what is returned for the document.

          * **source_include:list, default=None**

            optional

            A list containing the fields that will returned for the document.

          * **wait:bool, default=False**

            optional


            If True, this function will wait to return until the document is searchable in Elasticsearch.

          * **timeout:int, default=60**

            optional

            This specifies the maximum time to wait for the document to be searchable in Elasticsearch if the ``wait`` parameter is set to ``True``.

          * **sentinel_key:str, default='_ingest_sentinel'**

            optional

            Advance Usage

            Elasticsearch field that contains the ``sentinel_value``. By default, there will be an ``_ingest_sentinal`` Elasticsearch field.


            This parameter relates to the ``barrier`` concept used as a parameter in the :py:meth:`yaada.analytic.context.AnalyticContext.update` method.
            If this ``get`` method is being used to retrieve a document in Elasticsearch soon after it has been ingested, this can be used to wait until
            that value is searchable in Elasticsearch before it is retrieved. This parameter will only be applied if the ``wait`` parameter
            is set to ``True``.

          * **sentinel_value:str, default=None**

            optional

            Advance Usage

            This parameter is used to ensure that an updated document has fully updated in Elasticsearch before it is retrieved by the ``get`` method. Because a
            document that is being updated may already exist, YAADA needs a way to know that it has been updated before retrieving the document.
            This is done by introducing a new value to the document, called a sentinal value. If a value is specified for this parameter, YAADA will
            check that this value matches up with the value in the ``sentinel_key`` field for the document before retrieving it, to know that it has been updated.

        .. code-block:: python

          context.get("Publication", "2cf0d07c-cba9-47e3-9063-5d6265e26089")

        """
        if wait:
            self.ingest_barrier(
                doc_type,
                id,
                timeout=timeout,
                sentinel_key=sentinel_key,
                sentinel_value=sentinel_value,
            )
        return self.doc_service.get(
            doc_type,
            id,
            _source=source,
            _source_exclude=source_exclude,
            _source_include=source_include,
        )

    def exists(self, doc_type, id):
        """
        Returns a bool value describing whether or not a document exists.

        Parameters:

          * **doc_type: str**

              The document type.
          * **id: str**

              The unique id of the document


        Example

        .. code-block:: python

          context.exists("Publication", "f33bca95-3caa-46ac-8667-448ba4973190")
        """
        return self.doc_service.exists(doc_type, id)

    def mget(
        self, doc_type, ids, source=None, source_exclude=None, source_include=None
    ):
        """
        Returns multiple documents from Elasticsearch.

        Parameters:

          * **doc_type: str**

            The document type of the documents to be returned.

          * **ids: list**

            List of unique identifiers of documents in Elasticsearch

          * **source: list, defult=None**

            optional

            A list containing the fields that will be returned for the document.

          * **source_exclude, default=None**

            optional

            A list containing the fields that will be excluded from what is returned for the document.

          * **source_include, default=None**

            optional

            A list containing the fields that will returned for the document.


        Example:

        .. code-block:: python

          context.mget("Publication", ["2cf0d07c-cba9-47e3-9063-5d6265e26089", "b0e062ac-0e84-40db-8ecd-36e1aa0e264b"])
        """
        return self.doc_service.mget(
            doc_type,
            ids,
            _source=source,
            _source_exclude=source_exclude,
            _source_include=source_include,
        )

    def delete_by_query(self, doc_type, query={"query": {"match_all": {}}}):
        """
        Delete all documents that result from the a given query.

        Parameters:

          * **doc_type: str**

            The document type.

          * **query: dict**

            And Elasticsearch query. Elasticsearch's documentation on querying can be found `here
            <https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html>`_.

        Example:

        .. code-block:: python

          context.delete_by_query("Publication", {
              'query': {
                  'match': {
                      '_id': '2cf0d07c-cba9-47e3-9063-5d6265e26089'
                  }
              }
          })
        """
        if query is None:
            query = {"query": {"match_all": {}}}
        self.doc_service.delete_by_query(doc_type, query)

    def delete(self, doc_type, id):
        """
        Delete a single document in Elasticsearch.

        Parameters:

          * **doc_type: str**

            The document type of the documents to be returned.

          * **id: str**

            Identifier of document in Elasticsearch.

        Example:

        .. code-block:: python

            context.delete("Publication", "b0e062ac-0e84-40db-8ecd-36e1aa0e264b")

        """
        self.doc_service.delete(doc_type, id)

    def delete_index(self, doc_type, initialize_index=True):
        """
        Deletes an index in Elasticsearch.

        Parameters:

          * **doc_type: str**

            Documents with this ``doc_type`` will all be deleted.

        Example:

        .. code-block:: python

          context.delete_index("Publication")
        """
        self.doc_service.delete_index(doc_type, initialize_index=initialize_index)

    def save_model_instance(self, model):
        modelservice.save_model_instance(self.ob_service, model)
        self.status["model_name"] = model.model_name
        self.status["model_instance_id"] = model.model_instance_id

    def load_model_instance(self, model_name, model_instance_id):
        model = modelservice.load_model_instance(
            self.ob_service, model_name, model_instance_id
        )
        self.status["model_name"] = model.model_name
        self.status["model_instance_id"] = model.model_instance_id
        return model

    def sentinel_present(self, doc_type, id, sentinel_key, sentinel_value):
        """check if a document is searchable with a given sentinel value."""
        docs = list(
            self.query(
                doc_type,
                {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"_id": id}},
                                {"term": {f"{sentinel_key}.keyword": sentinel_value}},
                            ]
                        }
                    }
                },
            )
        )
        if len(docs) > 0:
            doc = docs[0]
            if sentinel_key in doc:
                return doc[sentinel_key] == sentinel_value

        return False

    def ingest_barrier(
        self,
        doc_type,
        id,
        timeout=60,
        sentinel_key="_ingest_sentinel",
        sentinel_value=None,
    ):
        """
        Describe sentinal key and value here so that it can be refered to.

        Args:
            doc_type ([type]): [description]
            id ([type]): [description]
            timeout (int, optional): [description]. Defaults to 60.
            sentinel_key (str, optional): [description]. Defaults to '_ingest_sentinel'.
            sentinel_value ([type], optional): [description]. Defaults to None.

        Raises:
            IngestBarrierTimeout: [description]
        """
        delays = [0, 1, 5, 10, 30]
        delay = 0
        found = False
        start_time = time.time()
        while not found:
            elapsed = time.time() - start_time
            if timeout is not None and elapsed >= timeout:
                raise IngestBarrierTimeout(
                    f"timeout of {timeout} reached and {doc_type}:{id} not found in total of {elapsed} seconds"
                )

            if delays:
                delay = delays.pop(0)

            if timeout is not None and timeout - elapsed < delay:
                delay = timeout - elapsed
            if delay > 0:
                # print(f"trying in {delay} seconds")
                time.sleep(delay)
            if sentinel_value is None:
                found = self.exists(doc_type, id)
            else:
                found = self.exists(doc_type, id) and self.sentinel_present(
                    doc_type, id, sentinel_key, sentinel_value
                )

    def invalidate_model_instance(self, model_name, model_instance_id):
        modelservice.invalidate_model_instance(model_name, model_instance_id)

    def document_counts(self):
        """
        Returns an object with a breakdown of each index and the count of documents
        in each index. The keys are each ``doc_type``'s in Elasticsearch and the values are
        the number of documents currently stored.

        Example:

        .. code-block:: python

            context.document_counts()
        """
        return self.doc_service.document_counts()

    def term_counts(self, doc_type, term, query={"query": {"match_all": {}}}):
        """

        Returns an object describing the frequency of terms for a given field of an index by running an Elasticsearch terms aggregation.

        Parameters:

          * **doc_type: str**

            The document type, this represents an Elasticsearch index.

          * **term: str**

            The field that will be inspected.

          * **query: dict, default={"query":{"match_all":{}}}**

            optional

            Provides a filter for the documents that will be aggregated.

        """
        return self.doc_service.term_counts(doc_type, term, query)

    def document_mappings(self, doc_type, *fields):
        """
        This is a depricated method, use :py:meth:`yaada.analytic.context.AnalyticContext.index_field_mappings` instead.
        """
        return self.doc_service.index_field_mappings(doc_type, *fields)

    def index_field_mappings(self, doc_type, *fields):
        # Link out specific Elasticsearch call
        """
        Returns the Elasticsearch mapping for the given ``doc_type``. The Elasticsearch documentation
        has a section on `mappings. <https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping.html>`_

        Parameters:

          * **doc_type: str**

            The document type, this represents an Elasticsearch index.

          * **fields: str **

            optional

            Limits the mapping to fields given for this parameter. Wildcards can be used.
        """
        return self.doc_service.index_field_mappings(doc_type, *fields)

    def index_mappings(self, doc_type):
        """
        Returns raw index mapping for an Elasticsearch index. Includes Elasticsearch metadata that :py:meth:`yaada.analytic.context.AnalyticContext.index_field_mappings` does not.

        Parameters:

          * **doc_type: str**

            The document type, this represents an Elasticsearch index.

        """
        return self.doc_service.index_mappings(doc_type)

    def index_settings(self, doc_type):
        """
        Returns an object with an index's Elasticsearch settings. `Documentation on Elasticsearch's settings <https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules.html#index-modules-settings>`_

        Parameters:

          * **doc_type: str**

            The document type, this represents an Elasticsearch index.


        """
        return self.doc_service.index_settings(doc_type)

    def init_index(self, doc_type, settings={}, mappings={}, aliases={}):
        self.doc_service.init_index(
            doc_type, settings=settings, mappings=mappings, aliases=aliases
        )

    def aggregation(self, doc_type, query):
        """
        Depricated, use :py:meth:`yaada.analytic.context.AnalyticContext.rawquery` instead.
        """
        return self.doc_service.rawquery(doc_type, query)

    def rawquery(self, doc_type, query):
        """
        Returns results to a query.

        This returns the bare elasticsearch results. Use this to access to the scoring information or aggregations.

        Parameters:

          * **doc_type: str**

            The document type, this represents an Elasticsearch index.

          * **query: dict**

            Elasticsearch query, more documentation can be found `here <https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html>`_.

        """
        return self.doc_service.rawquery(doc_type, query)

    def document_type_exists(self, doc_type):
        """
        Returns a bool value describing whether a ``doc_type``
        exists.

        Parameters:

          * **doc_type:str**

            The document type, this represents an Elasticsearch index.

        Example:

         .. code-block:: python

            context.document_type_exists("Publication")
        """
        return self.doc_service.document_type_exists(doc_type)

    def query_hit_count(self, doc_type, query):
        q = query.copy()
        q["size"] = 0
        return (
            self.doc_service.aggregation(doc_type, q).get("hits", {}).get("total", None)
        )

    def sync_exec_analytic(
        self,
        analytic_name,
        analytic_session_id=None,
        parameters={},
        include_results=False,
        printer=print,
    ):
        """
        Synchronously run an analytic. A tutorial on writing and running yaada analytics can be found in the :ref:`Writing an Analytic<Writing an Analytic>` section.

        Parameters:

          * **analytic_name: str**

            The full analytic class name.

          * **analytic_session_id: str, default=None**

            optional

            This value will be stored in Elasticsearch to mark the documents changed by this analytic session.
            If a value is not defined, the context object's ``analytic_session_id`` value will be automatically assigned.

          * **parameters: dict, default={}**

            optional

            This value corresponds to the parameters of the yaada analytic being run.

            The parameters are assigned by setting each key in this dict to a string
            of the name of a parameter. The parameter will be assinged to the value given in the key-value pair.

          * **include_results: bool, default=False**

            If running an analytic synchronously, setting this to  ``True`` will return the produced documents from the analytic.

            Warning - Will Produce a Large Output

            optional

          * **printer: function, default=print**

            optional

            Advanced Usage, Experimental API subject to change, not recommended for users

        Example:

        .. code-block:: python

          context.sync_exec_analytic(
              analytic_name="yaada.analytic.builtin.newspaper.NewspaperScrapeSources",
              parameters={"content":True,"scrape_top_image":False,"memoize":True})

        """
        if analytic_session_id is None:
            analytic_session_id = str(_uuid.uuid4())
        c = self.create_derived_context(analytic_name, analytic_session_id, parameters)
        return sync_exec_analytic(
            c,
            analytic_name,
            analytic_session_id,
            parameters,
            include_results=include_results,
            printer=printer,
        )

    def async_exec_analytic(
        self,
        analytic_name,
        analytic_session_id=None,
        parameters={},
        worker="default",
        image=None,
        gpu=False,
        login=None,
        watch=False,
        stream_status=False,
    ):
        """
        Asynchronously run an analytic.

        Parameters:

          * **analytic_name: str**

            The full analytic class name.

          * **analytic_session_id: str, default=None**

            optional

            This value will be stored in Elasticsearch to mark the documents changed by this analytic session.
            If a value is not defined, the context object's ``analytic_session_id`` value will be automatically assigned.

          * **parameters: dict, default={}**

            optional

            This value corresponds to the parameters of the yaada analytic being run.

            The parameters are assigned by setting each key in this dict to a string
            of the name of a parameter. The parameter will be assinged to the value given in the key-value pair.

          * **worker:str, default='default**

            optional

            Use for selecting which analytic worker to use for execution

            Advanced Usage, Experimental API subject to change, not recommended for users

          * **watch:bool, default=False**

            optional

            Advanced Usage, Experimental API subject to change, not recommended for users

        """
        if analytic_session_id is None:
            analytic_session_id = str(_uuid.uuid4())
        if stream_status:
            self.msg_service.subscribe_analytic_status(
                analytic_name, analytic_session_id
            )
        status = async_exec_analytic(
            self.msg_service,
            analytic_name,
            analytic_session_id,
            parameters,
            worker=worker,
            image=image,
            gpu=gpu,
            login=login,
        )

        def gen(context, analytic_name, analytic_session_id):
            while True:
                r = context.msg_service.fetch()
                for doc in r:
                    yield doc
                    if doc.get("finished", False) or doc.get("error", False):
                        context.msg_service.unsubscribe_analytic_status(
                            analytic_name, analytic_session_id
                        )
                        context.msg_service.fetch()
                        return

        if stream_status:
            return gen(self, analytic_name, analytic_session_id)
        else:
            return status

    def fetch_file_to_temp(self, remote_file_path):
        return self.ob_service.fetch_file_to_temp(remote_file_path)

    def fetch_file_to_directory(self, remote_file_path, local_dir, filename):
        return self.ob_service.fetch_file_to_directory(
            remote_file_path, local_dir, filename
        )

    def fetch_artifact_to_directory(
        self, doc, artifact_type, cache_dir="/tmp/yaada/artifacts-cache"
    ):
        return self.ob_service.fetch_artifact_to_directory(
            doc, artifact_type, cache_dir
        )

    def save_artifact(self, doc, artifact_type, filename, file):
        return self.ob_service.save_artifact(doc, artifact_type, filename, file)

    def save_artifact_dir(self, doc, artifact_type, local_dir, re_skip_matches=None):
        return self.ob_service.save_artifact_dir(
            doc, artifact_type, local_dir, re_skip_matches
        )

    def finalize(self):
        self.msg_service.disconnect()

    def get_external_mqtt_service(self):
        return make_external_mqtt_service(self.config)

    def get_model_manager(self):
        return self.model_manager

    def analytic_description(self, name=None):
        if name is None:
            return analytic.get_analytics()
        else:
            return analytic.analytic_description(name)

    def publish_event(self, topic, data):
        self.msg_service.publish_event(topic, data)

    def subscribe_event(self, sub, dest=None):
        def remove_topic_prefix(doc):
            newdoc = dict(**doc)
            prefix = f"{self.msg_service._event_topic_base}/"
            if newdoc["_topic"].startswith(prefix):
                newdoc["_topic"] = newdoc["_topic"][len(prefix) :]
            return newdoc

        if dest is None:
            s = BufferedStream(transform=remove_topic_prefix)
        else:
            s = dest
        self.msg_service.subscribe_event(sub, dest=s)
        return s

    def unsubscribe_event(self, sub):
        self.msg_service.unsubscribe_event(sub)


def make_analytic_context(
    analytic_name="anonymous",
    analytic_session_id=None,
    parameters={},
    msg_service=None,
    doc_service=None,
    ob_service=None,
    model_manager=None,
    init_pipelines=True,
    init_analytics=True,
    init_models=True,
    config=None,
    schema_manager=None,
    connect_to_services=True,
    overrides={},
):
    """
    Return an instance of the context object. A context object is needed to
    interact with the Elasticsearch database using python. A detailed description of the
    context object can be found in the :ref:`Context Object<Context Object>` section.

    Parameters:

    * **analytic_name: str, default='anonymous'**

      A string describing the reason for this context object's instantiation.
      This value will mark documents created and edited by this instance of the context object

      When running an analytic, this value will automatically get set to the analytic's class name.

      This value will be stored in a document's ``analytic_name`` field.

    * **analytic_session_id: str, default=None**

      optional

      This value will be saved in Elasticsearch. It will mark which documents are edited by this specific instance of the
      context object.
      Documents added or edited by a context, will inherit that context's ``analytic_session_id`` in a ``analytic_session_id`` field.

      If no value is given, a universally unique identifier will be automatically assigned.

    * **parameters:dict, default={}**

      private
    * **msg_service=None**

      private
    * **doc_service=None**

      private
    * **ob_service=None**

      private
    * **model_manager=None**

    * **init_pipelines=True**

      optional

      When ``True``, the creation of the context object will initialize the pipelines. The pipeline needs to be initialized for
      asynchronous processes.

      The only downside to initializing the pipeline when it is not necessary is that it will take a little longer to create the context object.
    * **config=None**

      private
    * **schema_manager=None**

      private
    * **overrides={}**

      optional

      Allows an override to environment variables and settings in a service.

    Here is an example of what is needed to get started using the ``context object``

    .. code-block:: python

      from yaada.analytic.context import make_analytic_context
      context = make_analytic_context()


    """
    start_t = time.time()
    if analytic_session_id is None:
        analytic_session_id = str(_uuid.uuid4())

    context = AnalyticContext(
        analytic_name,
        analytic_session_id,
        parameters,
        msg_service=msg_service,
        doc_service=doc_service,
        ob_service=ob_service,
        model_manager=model_manager,
        config=config,
        schema_manager=schema_manager,
        connect_to_services=connect_to_services,
        overrides=overrides,
    )
    analytic.find_and_register(
        context.config, init_analytics, init_pipelines, init_models
    )

    if init_pipelines:
        context.init_pipeline()

    end_t = time.time()
    logger.info(f"##context creation took {end_t-start_t} seconds")
    return context
