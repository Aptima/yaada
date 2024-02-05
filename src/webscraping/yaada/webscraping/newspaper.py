# Copyright (c) 2023 Aptima, Inc.
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

import datetime
import logging
import random
import re
import tempfile
import traceback
from urllib.parse import urlparse

import newspaper
import requests
from newspaper import Article
from pyquery import PyQuery

from yaada.core import default_log_level, schema, utility
from yaada.core.analytic import YAADAAnalytic, YAADAPipelineProcessor

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)

newspaper_network_logger = logging.getLogger("newspaper.network")
newspaper_network_logger.disabled = True

newspaper_source_logger = logging.getLogger("newspaper.source")
newspaper_source_logger.disabled = True


def id_from_url(url: str):
    return utility.hash_for_text([url])


def article_exists(context, url):
    results = list(
        context.query(
            "NewsArticle",
            {"query": {"term": {"url.keyword": url}}},
            source=dict(include=["doc_type", "_id"]),
        )
    )
    if len(results) > 0:
        return True
    else:
        return False


def get_filename_from_cd(cd):
    """
    Get filename from content-disposition
    """
    if not cd:
        return None
    fname = re.findall("filename=(.+)", cd)
    if len(fname) == 0:
        return None
    return fname[0]


def prepare_url(url):
    o = urlparse(url)
    if not o.scheme:
        url = f"http://{url}"
    return url


def _resolve_redirect(article_doc, analyze_feature="url"):
    url = article_doc[analyze_feature]
    try:
        r = requests.head(prepare_url(url), allow_redirects=True)
        newurl = r.url
        if newurl != url:
            print(f"redirected '{url}' to '{newurl}'")
            article_doc[analyze_feature] = newurl
            article_doc["_id"] = id_from_url(newurl)
            article_doc["id"] = article_doc["_id"]
    except Exception as e:
        print(f"error following redirect {article_doc}: {e}")
        article_doc["scrape_status"] = False
        article_doc["scrape_error"] = True
        article_doc["scrape_error_message"] = str(e)
    return article_doc


def XPathToSelector(xpath):
    _xp = xpath.replace("/", " ")
    if re.search(r"\[[\d]*\]", _xp):
        _xp = re.sub(r"\[([\d]*)\]", r":nth-child(\1)", _xp)

    return _xp


def xpath_content_extraction(xpaths, article, article_doc):
    d = PyQuery(article.html)
    content = ""
    for xpath in xpaths:
        selector = XPathToSelector(xpath)
        temp_content_html = d(selector)
        temp_content = ""

        # Formatting
        for temp_tag in temp_content_html.items():
            if not temp_content:
                temp_content = temp_tag.text()
            else:
                temp_content = temp_content + "\n\n" + temp_tag.text()

        # If multiple xpaths given, keep the one that gets the most content
        content = temp_content.strip() if len(temp_content) > len(content) else content

    # If newspaper got no content OR the content it got is less than 75% of the length of the xpath content, use the xpath content
    if not article_doc["content"] or len(article_doc["content"]) / len(content) <= 0.75:
        article_doc["content"] = content


def scrape_article_content(
    context,
    article_doc,
    scrape_top_image=False,
    resolve_redirect=False,
    save_html=False,
    analyze_feature="url",
    rescrape=True,
    use_xpath=False,
    xpaths=list(),
):
    if resolve_redirect:
        article_doc = _resolve_redirect(article_doc, analyze_feature=analyze_feature)

    url = article_doc[analyze_feature]

    if not rescrape:
        if context.exists(article_doc["doc_type"], article_doc["_id"]):
            return context.get(article_doc["doc_type"], article_doc["_id"])
    try:
        context.report_status(message=f"scraping:{url}")
        article = Article(url)
        article.download()
        article.parse()
        article.nlp()

        publish_date = article.publish_date
        if isinstance(publish_date, datetime.datetime):
            publish_date = publish_date.isoformat()

        article_doc["authors"] = article.authors
        if publish_date is not None:
            article_doc["publish_date"] = publish_date
        article_doc["content"] = article.text
        if save_html:
            article_doc["html"] = article.html
        article_doc["title"] = article.title or url
        article_doc["keywords"] = article.keywords
        article_doc["summary"] = article.summary
        article_doc["source_url"] = article.source_url
        article_doc["meta_lang"] = article.meta_lang
        article_doc["authors"] = article.authors
        article_doc["top_image"] = article.top_image
        article_doc["scrape_status"] = True
        if scrape_top_image and article_doc["top_image"]:
            try:
                with tempfile.NamedTemporaryFile() as tf:
                    with requests.get(
                        article_doc["top_image"], allow_redirects=True, stream=True
                    ) as r:
                        filename = None
                        if article_doc["top_image"].find("/"):
                            filename = article_doc["top_image"].rsplit("/", 1)[1]
                        if not filename:
                            filename = get_filename_from_cd(
                                r.headers.get("content-disposition")
                            )
                        tf.write(r.content)
                        tf.seek(0)
                        context.ob_service.save_artifact(
                            article_doc, "top_image", filename, tf
                        )
                        article_doc["top_image_download"] = True
            except Exception as e:
                traceback.print_exc()
                context.report_status(
                    message=f"error scraping top_image {article_doc['top_image']}: {e}"
                )
                article_doc["top_image_download"] = False
                article_doc["top_image_download_error"] = True
                article_doc["top_image_download_error_message"] = str(e)

        if (
            use_xpath and len(xpaths) >= 1
        ):  # if we want to use xpaths and at least one is given
            xpath_content_extraction(xpaths, article, article_doc)

    except newspaper.article.ArticleException as e:
        context.report_status(message=f"error scraping {article_doc}: {e}")
        article_doc["scrape_status"] = False
        article_doc["scrape_error"] = True
        article_doc["scrape_error_message"] = str(e)
    return article_doc


class NewspaperScrapeSingleArticle(YAADAAnalytic):
    """
    This analytic scrapes a single source for articles and stores them in opensearch with the doc_type ``NewsArticle``.

    .. code-block:: python

      name=yaada.analytic.builtin.newspaper.NewspaperScrapeSingleArticle
      parameters {
          "description":"url of a news article",
          "type":"object",
          "properties": {
            "url": {
              "description": "A web page url",
              "type": "string"
            },
            "corpus": {
              "description": "Corpus to tag article with",
              "type": "string"
            },
            "scrape_top_image": {
              "description": "download the article top image",
              "type": "boolean"
            },
            "resolve_redirect": {
              "description": "follow redirects to get the actual url. adds processing time, so defaults to False",
              "type": "boolean"
            },
            "save_html": {
              "description": "keep the raw html",
              "type": "boolean"
            }
          },
          "required": [ "url" ]
        }

    """

    DESCRIPTION = (
        "Scrape a single article based on url passed through analytic parameters."
    )
    PARAMETERS_SCHEMA = {
        "description": "url of a news article",
        "type": "object",
        "properties": {
            "url": {"description": "A web page url", "type": "string"},
            "corpus": {"description": "Corpus to tag article with", "type": "string"},
            "scrape_top_image": {
                "description": "download the article top image",
                "type": "boolean",
            },
            "resolve_redirect": {
                "description": "follow redirects to get the actual url. adds processing time, so defaults to False",
                "type": "boolean",
            },
            "save_html": {"description": "keep the raw html", "type": "boolean"},
            "rescrape": {
                "description": "redownload the article if already have it. defaults to false",
                "type": "boolean",
            },
            "use_xpath": {
                "description": "flag to determine if xpaths should be used for scraping",
                "type": "boolean",
            },
            "xpaths": {
                "description": "list of xpaths (relative or absolute) that will be used to scrape content",
                "type": "array",
            },
        },
        "required": ["url"],
    }
    REQUEST_SCHEMA = schema.make_request_schema(PARAMETERS_SCHEMA)

    def __init__(self):
        pass

    def run(self, context, request):
        scrape_top_image = request["parameters"].get("scrape_top_image", False)
        resolve_redirect = request["parameters"].get("resolve_redirect", False)
        save_html = request["parameters"].get("save_html", False)
        corpus = request["parameters"].get("corpus", None)
        rescrape = request["parameters"].get("rescrape", False)
        use_xpath = request["parameters"].get("use_xpath", False)
        xpaths = request["parameters"].get("xpaths", list())

        url = request["parameters"]["url"]

        doc = dict(doc_type="NewsArticle", _id=id_from_url(url), url=url, title=url)
        if corpus:
            doc["corpus"] = corpus
        doc = scrape_article_content(
            context,
            doc,
            scrape_top_image=scrape_top_image,
            resolve_redirect=resolve_redirect,
            save_html=save_html,
            rescrape=rescrape,
            use_xpath=use_xpath,
            xpaths=xpaths,
        )
        context.update(doc, sync=True)
        return doc


class NewspaperScrapeSources(YAADAAnalytic):
    """
    This analytic collects urls to later have their contents scraped.

    .. code-block:: python

      name=yaada.analytic.buitin.newspaper.NewspaperScrapeSources
      parameters = {
        "description":"Scrape article header information from news sources.",
        "type":"object",
        "properties": {
          "memoize": {
            "description": "Should we only return new articles or should we return all",
            "type": "boolean"
          },
          "content": {
            "description": "Should we download the article content too?",
            "type": "boolean"
          },
          "source_urls": {
            "description": "Should we download the article content too?",
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "corpus": {
            "description": "corpus to assign scraped articles to",
            "type": "string"
          },
          "scrape_top_image": {
            "description": "download the article top image",
            "type": "boolean"
          },
          "resolve_redirect": {
            "description": "follow redirects to get the actual url. adds processing time, so defaults to False",
            "type": "boolean"
          },
          "save_html": {
            "description": "keep the raw html",
            "type": "boolean"
          }
        },
      }
    """

    DESCRIPTION = "Scrape all urls from a set of sites"
    PARAMETERS_SCHEMA = {
        "description": "Scrape article header information from news sources.",
        "type": "object",
        "properties": {
            "memoize": {
                "description": "Should we only return new articles or should we return all",
                "type": "boolean",
            },
            "content": {
                "description": "Should we download the article content too?",
                "type": "boolean",
            },
            "source_urls": {
                "description": "Urls to scrape.",
                "type": "array",
                "items": {"type": "string"},
            },
            "corpus": {
                "description": "corpus to assign scraped articles to",
                "type": "string",
            },
            "scrape_top_image": {
                "description": "download the article top image",
                "type": "boolean",
            },
            "resolve_redirect": {
                "description": "follow redirects to get the actual url. adds processing time, so defaults to False",
                "type": "boolean",
            },
            "save_html": {"description": "keep the raw html", "type": "boolean"},
            "accept_meta_langs": {
                "description": "list of acceptable meta langs",
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }
    REQUEST_SCHEMA = schema.make_request_schema(PARAMETERS_SCHEMA)

    def __init__(self):
        pass

    def run(self, context, request):
        memoize_articles = request.get("parameters", {}).get(
            "memoize_articles", False
        )  # maintaining backwards compatibility with old api
        memoize_articles = request.get("parameters", {}).get(
            "memoize", memoize_articles
        )
        scrape_content = request.get("parameters", {}).get("content", True)
        source_urls = request.get("parameters", {}).get("source_urls", [])
        source_corpus = request.get("parameters", {}).get("corpus", None)
        scrape_top_image = request["parameters"].get("scrape_top_image", False)
        resolve_redirect = request["parameters"].get("resolve_redirect", False)
        save_html = request["parameters"].get("save_html", False)

        accept_meta_langs = request["parameters"].get("accept_meta_langs", [])

        source_docs = [
            dict(doc_type="SourceUrl", url=url, id=id_from_url(url))
            for url in source_urls
        ]
        context.update(source_docs)

        if len(source_docs) == 0:
            source_docs = list(context.query("SourceUrl"))

        for source in source_docs:
            source_url = source["url"]
            context.report_status(message=f"Looking at source: {source_url}")
            corpus = source.get("corpus", source_corpus)
            use_xpath = source.get("use_xpath", False)
            xpaths = source.get("xpaths", list())

            source["last_scrape_count"] = 0
            try:
                site = newspaper.build(source_url, memoize_articles=memoize_articles)

                for article in site.articles:
                    url = article.url.strip()
                    if article_exists(
                        context, url
                    ):  # if we've already scraped this url, skip the download.
                        logger.info(f"skipping existing article: {url}")
                        continue
                    hashed_url = id_from_url(url)
                    r = {
                        "doc_type": "NewsArticle",
                        "url": url,
                        "id": hashed_url,
                        "_id": hashed_url,
                        "original_source_url": source_url,
                        "title": url,
                        "has_source": {"doc_type": "SourceUrl", "id": source["id"]},
                    }
                    if resolve_redirect:
                        r = _resolve_redirect(r)

                    if corpus:
                        r["corpus"] = corpus

                    if scrape_content:
                        r = scrape_article_content(
                            context,
                            r,
                            scrape_top_image=scrape_top_image,
                            save_html=save_html,
                            use_xpath=use_xpath,
                            xpaths=xpaths,
                        )
                    if "meta_lang" in r and len(accept_meta_langs) > 0:
                        if r["meta_lang"] not in accept_meta_langs:
                            logger.info(
                                f"article meta_lang not in {accept_meta_langs}, skipping: {url}"
                            )
                            continue
                    context.update(r)
                    source["last_scrape_count"] += 1
                context.update(source)
            except Exception as e:
                logger.error(f"error scraping {source_url}", e)
                context.report_status(message=f"error scraping {source_url} {e}")
        context.report_status(message="Done!")


class ScrapeSourceProcessor(YAADAPipelineProcessor):
    def process(self, context, parameters, doc):
        context.async_exec_analytic(
            "yaada.analytic.builtin.newspaper.NewspaperScrapeSources",
            parameters=dict(
                source_urls=[doc["url"]],
                memoize=parameters.get("memoize", False),
                corpus=parameters.get("corpus", doc.get("corpus", None)),
                scrape_top_image=parameters.get("scrape_top_image", False),
                resolve_redirect=parameters.get("resolve_redirect", False),
                save_html=parameters.get("save_html", False),
                content=parameters.get("content", True),
            ),
        )
        return doc


class NewspaperScrapeContent(YAADAAnalytic):
    DESCRIPTION = "Scrape page content for url in arbitrary document."
    PARAMETERS_SCHEMA = {
        "description": "scrape articles",
        "type": "object",
        "properties": {
            "analyze_query": {
                "description": "the opensearch query for fetching documents to analyze",
                "type": "object",
            },
            "analyze_doc_type": {
                "description": "the opensearch query for fetching documents to analyze",
                "type": "object",
            },
            "analyze_feature": {
                "description": "the field containing url to scrape",
                "type": "object",
            },
            "scrape_top_image": {
                "description": "download the article top image",
                "type": "boolean",
            },
            "resolve_redirect": {
                "description": "follow redirects to get the actual url. adds processing time, so defaults to False",
                "type": "boolean",
            },
            "save_html": {"description": "keep the raw html", "type": "boolean"},
            "shuffle": {
                "description": "shuffle order of urls to scrape",
                "type": "boolean",
            },
        },
        "required": ["analyze_doc_type", "analyze_feature"],
    }
    REQUEST_SCHEMA = schema.make_request_schema(PARAMETERS_SCHEMA)

    def __init__(self):
        pass

    def run(self, context, request):
        analyze_feature = request.get("parameters", {}).get("analyze_feature")
        analyze_doc_type = request.get("parameters", {}).get(
            "analyze_doc_type", "NewsArticle"
        )
        q = {"query": {"bool": {"must": {"exists": {"field": analyze_feature}}}}}
        analyze_query = request.get("parameters", {}).get("analyze_query", q)

        scrape_top_image = request["parameters"].get("scrape_top_image", False)
        resolve_redirect = request["parameters"].get("resolve_redirect", False)
        save_html = request["parameters"].get("save_html", False)
        shuffle = request["parameters"].get("shuffle", False)

        urls = list(
            context.query(
                analyze_doc_type,
                analyze_query,
                source=dict(include=["doc_type", "_id", analyze_feature]),
            )
        )
        if shuffle:
            random.shuffle(urls)
        for doc in urls:
            doc = scrape_article_content(
                context,
                doc,
                scrape_top_image=scrape_top_image,
                resolve_redirect=resolve_redirect,
                save_html=save_html,
                analyze_feature=analyze_feature,
            )
            context.update(doc)
