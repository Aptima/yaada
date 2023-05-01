from yaada.core import utility
from yaada.core.analytic.context import make_analytic_context

context = make_analytic_context("test", "test")
context.wait_for_ready()
counts = context.document_counts()

if "TestDocument" in counts:
    context.delete_index("TestDocument")


def test_single_document_sync():
    doc = dict(doc_type="TestDocument", corpus="test")
    utility.assign_document_id(doc)

    context.update(doc, barrier=True)

    result = context.get("TestDocument", doc["id"])
    assert result is not None

    assert result["id"] == doc["id"]
    assert result["doc_type"] == doc["doc_type"]
    assert result["corpus"] == doc["corpus"]
    context.delete_by_query("TestDocument", {"query": {"match": {"id": doc["id"]}}})


def test_single_document_async():
    doc = dict(doc_type="TestDocument", corpus="test")
    utility.assign_document_id(doc)

    context.update(doc, sync=False, barrier=True)

    result = context.get("TestDocument", doc["id"])
    assert result is not None

    assert result["id"] == doc["id"]
    assert result["doc_type"] == doc["doc_type"]
    assert result["corpus"] == doc["corpus"]
    context.delete_by_query("TestDocument", {"query": {"match": {"id": doc["id"]}}})
