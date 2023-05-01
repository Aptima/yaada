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

import urllib.request

from bs4 import BeautifulSoup
from newspaper import Article
from tqdm import tqdm

from yaada.core import schema
from yaada.core.analytic import YAADAAnalytic


def get_bio_links():
    with urllib.request.urlopen(
        "https://www.aptima.com/about-aptima/aptima-team/"
    ) as f:
        soup = BeautifulSoup(f, "html.parser")
        x = soup.find("main", attrs={"id": "qodef-page-content"}).find_all(
            "a", attrs={"class": "qodef-e-title-link"}
        )
        for a in x:
            yield dict(name=a.get_text().strip(), link=a["href"])


def download_bio(link):
    a = Article(link)
    a.download()
    a.parse()
    return a.text


class DownloadAptimaBios(YAADAAnalytic):
    DESCRIPTION = "Scrape Aptima bios from public site."
    PARAMETERS_SCHEMA = {
        "description": "scrape articles",
        "type": "object",
        "properties": {},
        "required": [],
    }
    REQUEST_SCHEMA = schema.make_request_schema(PARAMETERS_SCHEMA)

    def __init__(self):
        pass

    def run(self, context, request):
        for doc in tqdm(list(get_bio_links())):
            doc["doc_type"] = "Bio"
            doc["content"] = download_bio(doc["link"])
            doc["id"] = "-".join([part.lower() for part in doc["name"].split()])
            context.update(doc)
