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

import os


def ensure_spacy_model(model_name):
    import spacy

    if not spacy.util.is_package(model_name):
        spacy.cli.download(model_name)


nltk_search_path = dict(
    punkt="tokenizers/punkt",
    stopwords="corpora/stopwords",
    brown="corpora/brown",
    wordnet="corpora/wordnet",
    averaged_perceptron_tagger="taggers/averaged_perceptron_tagger",
    conll2000="corpora/conll2000",
    movie_reviews="corpora/movie_reviews",
)


def ensure_nltk_model(model_name):
    from nltk import data, download

    download_location = os.getenv("NLTK_DATA", None)

    name = nltk_search_path.get(model_name, model_name)
    print(f"nltk download '{name}' location {download_location}")
    try:
        x = data.find(name)
        print(f"found nltk {name} at {x}")
    except LookupError:
        download(model_name, download_dir=download_location)


def ensure_nltk_punkt():
    ensure_nltk_model("punkt")


def ensure_nltk_stopwords():
    ensure_nltk_model("stopwords")


def ensure_textblob_corpora():
    # see requirements from https://github.com/sloria/TextBlob/blob/dev/textblob/download_corpora.py
    ensure_nltk_model("punkt")
    ensure_nltk_model("brown")
    ensure_nltk_model("wordnet")
    ensure_nltk_model("averaged_perceptron_tagger")

    # if you want to use ConllExtractor, use `ensure_nltk_model('conll2000')` first
    # if you want to use NaiveBayesAnalyzer, use `ensure_nltk_model('movie_reviews')` first


# def ensure_transformer_pipeline(name):
#     from transformers import pipeline

#     pipeline(name)

# def ensure_transformer_autotokenizer(name):
#     from transformers import AutoTokenizer

#     AutoTokenizer.from_pretrained(name)


def download_nlp_resources():
    ensure_spacy_model("xx_ent_wiki_sm")
    ensure_spacy_model("en_core_web_sm")
    ensure_spacy_model("en_core_web_md")
    print("******************** downloaded spacy models")
    ensure_nltk_punkt()
    ensure_nltk_stopwords()
    print("******************** downloaded nltk data")
    ensure_textblob_corpora()
    print("******************** downloaded textblob data")
