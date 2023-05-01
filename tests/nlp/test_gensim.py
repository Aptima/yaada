import pytest


def test_gensim():
    import gensim.downloader as api
    model = api.load("glove-wiki-gigaword-50")
    sims = model.most_similar("cat")
    assert len(sims) > 0
    assert sims[0][0] == 'dog'