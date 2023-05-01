import jsonschema
import pytest

from yaada.core.analytic.context import make_analytic_context

context = make_analytic_context("test", "test")
context.wait_for_ready()


def test_clean_ingest():
    articles = {"1": "foo.com", "2": "foo.com", "3": "bar.com"}
    counts = context.document_counts()
    if "NewsArticle" in counts:
        context.delete_index("NewsArticle")

    docs = [
        dict(doc_type="NewsArticle", id=id, url=url) for id, url in articles.items()
    ]

    context.update(docs, barrier=True, raise_ingest_error=True)

    assert context.document_counts()["NewsArticle"] == 3
    for v in ["1", "2", "3"]:
        result = context.get("NewsArticle", v)
        assert result is not None

    context.delete_index("NewsArticle")


def test_raise_error():
    articles = {"1": "foo.com", "2": None, "3": "bar.com"}
    counts = context.document_counts()
    if "NewsArticle" in counts:
        context.delete_index("NewsArticle")

    docs = [
        dict(doc_type="NewsArticle", id=id, url=url) for id, url in articles.items()
    ]

    # expecting documents 2 and 3 to trigger mapper_parsing_exception errors in elasticsearch. We'd like documents 1 and 4 to be persisted and available though.
    with pytest.raises(jsonschema.exceptions.ValidationError):
        context.update(docs, barrier=True, raise_ingest_error=True)


def test_dont_raise_error():
    articles = {"1": "foo.com", "2": None, "3": "bar.com"}
    counts = context.document_counts()
    if "NewsArticle" in counts:
        context.delete_index("NewsArticle")

    docs = [
        dict(doc_type="NewsArticle", id=id, url=url) for id, url in articles.items()
    ]

    context.update(docs, barrier=True, raise_ingest_error=False)

    assert context.document_counts()["NewsArticle"] == 2
    for v in ["1", "3"]:
        result = context.get("NewsArticle", v)
        assert result is not None

    for v in ["2"]:
        result = context.get("NewsArticle", v)
        assert result is None

    context.delete_index("NewsArticle")
