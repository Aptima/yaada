import requests

from yaada.core import utility
from yaada.core.analytic.context import make_analytic_context
import os
context = make_analytic_context("test", "test")
context.wait_for_ready()
headers = {"Content-Type": "application/json", "Accept": "application/json"}

counts = context.document_counts()

if "TestDocument" in counts:
    context.delete_index("TestDocument")

yaada_hostname = os.environ.get('YAADA_HOSTNAME','localhost')

def test_file_upload():
    # utility.wait_net_service("flask", 'http://localhost:5000', 10.0)
    doc = dict(doc_type="TestDocument")
    utility.assign_document_id(doc)

    files = {"file": open("testdata/test.txt", "rb")}
    r = requests.post(
        f"http://{yaada_hostname}:5000/artifact/{doc['doc_type']}/{doc['id']}?artifact_type=file&barrier=true",
        files=files,
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
    assert "artifacts" in result
    assert "file" in result["artifacts"]
    assert result["artifacts"]["file"][0]["content_type"] == "text/plain"
    assert result["artifacts"]["file"][0]["filename"] == "test.txt"
    assert (
        result["artifacts"]["file"][0]["remote_path"]
        == f"default/artifacts/{doc['doc_type']}/{doc['id']}/file"
    )
    assert (
        result["artifacts"]["file"][0]["remote_file_path"]
        == f"default/artifacts/{doc['doc_type']}/{doc['id']}/file/test.txt"
    )

    context.delete_by_query("TestDocument", {"query": {"match": {"id": doc["id"]}}})
