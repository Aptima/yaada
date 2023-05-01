import pytest
from elasticsearch.helpers.errors import BulkIndexError

from yaada.core.analytic.context import make_analytic_context

context = make_analytic_context("test", "test")
context.wait_for_ready()


def test_dont_raise_error():
    counts = context.document_counts()
    if "TestDocument" in counts:
        context.delete_index("TestDocument")

    docs = [
        dict(doc_type="TestDocument", id=v[0], value=v[1])
        for v in [("1", 1), ("2", dict(x=2)), ("3", "3"), ("4", dict(x=4))]
    ]

    # expecting documents 2 and 3 to trigger mapper_parsing_exception errors in elasticsearch. We'd like documents 1 and 4 to be persisted and available though.
    context.update(docs, barrier=True, raise_ingest_error=False)

    assert context.document_counts()["TestDocument"] == 2
    for v in ["1", "3"]:
        result = context.get("TestDocument", v)
        assert result is not None

    for v in ["2", "4"]:
        result = context.get("TestDocument", v)
        assert result is None

    context.delete_index("TestDocument")


def test_raise_error():
    counts = context.document_counts()
    if "TestDocument" in counts:
        context.delete_index("TestDocument")

    docs = [
        dict(doc_type="TestDocument", id=v[0], value=v[1])
        for v in [("1", 1), ("2", dict(x=2)), ("3", "3"), ("4", dict(x=4))]
    ]

    with pytest.raises(BulkIndexError):
        context.update(docs, barrier=True, raise_ingest_error=True)
