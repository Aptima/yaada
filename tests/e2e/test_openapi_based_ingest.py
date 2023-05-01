import requests

from yaada.core import utility
from yaada.core.analytic.context import make_analytic_context
import os
context = make_analytic_context("test", "test")
context.wait_for_ready()
headers = {"Content-Type": "application/json", "Accept": "application/json"}

counts = context.document_counts()

yaada_hostname = os.environ.get('YAADA_HOSTNAME','localhost')
if "TestDocument" in counts:
    context.delete_index("TestDocument")


def test_single_document():

    doc = dict(doc_type="TestDocument", corpus="test")
    utility.assign_document_id(doc)

    r = requests.post(
        f"http://{yaada_hostname}:5000/document/?sync=true&process=true&barrier=true",
        headers=headers,
        json=doc,
    )
    assert r.status_code == 200

    r = requests.post(
        f"http://{yaada_hostname}:5000/document/get/",
        headers=headers,
        json=dict(doc_type="TestDocument", id=doc["id"]),
    )
    assert r.status_code == 200
    result = r.json()

    assert result["id"] == doc["id"]
    assert result["doc_type"] == doc["doc_type"]
    assert result["corpus"] == doc["corpus"]
    context.delete_by_query("TestDocument", {"query": {"match": {"id": doc["id"]}}})
