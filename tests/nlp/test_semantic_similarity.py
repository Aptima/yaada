import pytest

from yaada.core.utility import hash_for_text
from yaada.core.analytic.context import make_analytic_context
context = make_analytic_context("test", "test")
context.wait_for_ready()
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
counts = context.document_counts()
if "Avenger" in counts:
    context.delete_index("Avenger")
def load_avengers_data(context):
    import requests
    import csv
    import re
    response = requests.get("https://raw.githubusercontent.com/fivethirtyeight/data/master/avengers/avengers.csv")
    csv_text = response.content.decode('latin-1')
    reader = csv.DictReader(csv_text.split('\n'))
    for row in reader: 
        # print(row)
        doc = dict(doc_type="Avenger",**{re.sub(r"\W+",'_',k.lower()):v for k,v in row.items() if v != ''})
        # for fields that contain numeric values, coerce to number if non empty string, delete if
        if doc.get('appearances',''):
            doc['appearances'] = int(doc['appearances'])
        if doc.get('year',''):
            doc['year'] = int(doc['year'])
        if doc.get('years_since_joining',''):
            doc['years_since_joining'] = int(doc['years_since_joining'])

        # Create a unique id for this row by hashing the URL it came from.
        doc['id'] = hash_for_text([row['URL']])
        doc['embedding'] = model.encode(doc['notes']).tolist()
        # Save into elasticsearch
        context.update(doc)

def test_similarity_search():
    load_avengers_data(context)
    text = "died but lives again"
    embedding = model.encode(text).tolist()
    q = {
      "query":{
        "knn": {
          "embedding": {
            "vector":embedding,
            "k":10
          }
        }
      }
    }

    docs = list(context.query("Avenger",q,source=['id','doc_type','notes','name_alias'],size=10))
    returned_names = set()
    for d in docs:
        returned_names.add(d['name_alias'])
    assert len(docs) == 10
    assert 'Steven Rogers' in returned_names