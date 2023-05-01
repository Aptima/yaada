import pytest

text="""
This is a test title.
This is some content.
and so is this.
Written by Gabe.
"""

def test_transformers():
    from transformers import pipeline
    classifier = pipeline("sentiment-analysis")
    scores = classifier('Transformers sentiment analysis is working great!')
    assert len(scores) > 0
    assert scores[0]['label'] == 'POSITIVE'


def test_sentence_transformers():
    from sentence_transformers import SentenceTransformer, util
    model = SentenceTransformer('all-MiniLM-L6-v2')
    sentences = text.strip().split("\n")
    embeddings = model.encode(sentences)
    cos_sim = util.cos_sim(embeddings, embeddings)
    assert float(cos_sim[0][1]) <1.0 and float(cos_sim[0][1]) > 0.0