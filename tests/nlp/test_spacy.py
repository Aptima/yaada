import pytest

text="""
This is a test title.
This is some content.
and so is this.
Written by Gabe.
"""


def test_spacy():
    import spacy

        
    nlp = spacy.load("en_core_web_md")
    doc = nlp(text)
    ent = None
    for entity in doc.ents:
        if entity.text == 'Gabe':
            ent = entity
    assert ent is not None
    assert ent.label_ == 'PERSON'
