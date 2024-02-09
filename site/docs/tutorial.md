# Tutorial

## Creating a project

In order to use YAADA, you first need to create a new project directory that will house your project metadata, Docker configuration for running the system, and any project specific source code or schemas. All of the tutorials in this section assume that you have read [Getting Started](getting-started.md) and followed the instructions to install prerequisites, create a project setting `yaada-tutorial` as the project_name (and accepting all defaults after that), run the system, and are running commands from the root of the project directory.

## Working with Jupyter or IPython

### Jupyter
Jupyter is helpful a developer tool. Many YAADA developers use it when writing the code of an analytic or processor before tying it into the rest of YAADA, or testing a query. To start up the dev Jupyter server, run the following command:

```
$ yda run jupyter
```

This will direct you to a new browser tab with the Jupyter interface and show logs in the terminal. If you’re unfamiliar with Jupyter, refer to the Jupyter Lab [documentation](https://jupyterlab.readthedocs.io/en/stable/).


Note that when using Jupyter, changes to code outside the notebook will not be picked up until the Jupyter Kernel is restarted.

In order to start interacting with YAADA data from a Jupyter noetbook, you will need to add the following as the first cell and execute it:

```python
from yaada,core.analytic.context import make_analytic_context
context = make_analytic_context()
```
### IPython
If you would prefer to experiment with YAADA from the command line, the IPython shell provides a REPL that can be used to experiment with the YAADA APIs.

Launch IPython with:

```
$ yda run ipython
```

Unlike with Jupyter, you don't need to construct the `context` manually. Once you are in the REPL, you will have a `context` already constructed for you and any code changes in your project will be automatically picked up through [IPython magic autoreload](https://ipython.org/ipython-doc/3/config/extensions/autoreload.html).

## Ingesting Data

This section will cover ingesting data into YAADA's OpenSearch. The tutorial will leverage a publically available csv containing avengers character data.
Content in this section assumes you have created an IPython shell with `yda run ipython` or using Jupyter Lab with `yda run jupyter` and have already constructed your YAADA `context`.

### Download csv data

Download the `avengers.csv`:

```python
import requests
response = requests.get("https://raw.githubusercontent.com/fivethirtyeight/data/master/avengers/avengers.csv")
open("avengers.csv", "wb").write(response.content)
```

### Load the csv

Read the CSV as dictionaries and write into YAADA.
```python
import csv
import re
from tqdm import tqdm
from yaada.core.utility import hash_for_text

with open('avengers.csv', 'r', encoding='latin-1') as csvfile:
  reader = csv.DictReader(csvfile)
  # Iterate through the csv, printing progress with tqdm
  for row in tqdm(reader): 
    # Create a dictionary containing all the values from the row, adding a `doc_type`
    # and normalizing the csv columns names to be better dictionary keys. Note that any 
    # fields that are an empty string are omitted to prevent OpenSearch from inferring 
    # the wrong schema type for the field.
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
    # Save into opensearch
    context.update(doc) 
```

Now verify that you have documents in OpenSearch using `context.document_counts()`:

```python
context.document_counts()
```

will result in:
```python
{'Avenger': 173}
```

Now to look at what the data looks like once ingested, fetch all the `Avenger` documents back from YAADA and inspect:

```python
avengers = list(context.query('Avenger'))
avengers[0]
```

should result in something like:

```python
{'doc_type': 'Avenger',
 'url': 'http://marvel.wikia.com/Henry_Pym_(Earth-616)',
 'name_alias': 'Henry Jonathan "Hank" Pym',
 'appearances': 1269,
 'current_': 'YES',
 'gender': 'MALE',
 'full_reserve_avengers_intro': 'Sep-63',
 'year': 1963,
 'years_since_joining': 52,
 'honorary': 'Full',
 'death1': 'YES',
 'return1': 'NO',
 'notes': 'Merged with Ultron in Rage of Ultron Vol. 1. A funeral was held. ',
 'id': '55f4787faa40baaf13540c4bf78509c976a5261050e400203355398209faa7ef',
 'analytic_session_id': ['fcd6d744-375e-4b34-8fb2-fdcaebc21440'],
 'analytic_name': ['IPython'],
 '@updated': '2022-08-22T21:40:12.600548',
 '@timestamp': '2022-08-22T21:40:12.600550',
 '_pipeline': [],
 '_id': '55f4787faa40baaf13540c4bf78509c976a5261050e400203355398209faa7ef'}
```
Note that several fields (i.e. `analytic_name`, `analytic_session_id`, `@updated`, `@timestamp`, `_pipeline`, `_id`) were autogenerated and can safely be ignored. The most useful of those is `@timestamp` which tracks the time that the document was first ingested.

### Defining a document schema

YAADA supports defining document schemas as json or yaml files following the [OpenAPI 3.0 json-schema variant](https://spec.openapis.org/oas/v3.0.0.html#schema-object).

To create a schema for our new `Avenger` document type, create a new file called `schema/Avenger.yaml` and put the following contents in it:

```yaml
type: object
properties:
  id:
    description: The index-unique id used for writing into opensearch -- will be autogenerated if omitted.
    type: string
  doc_type:
    type: string
  url:
    type: string
  name_alias:
    type: string
  appearances:
    type: integer
  current_:
    type: string
  gender:
    type: string
  full_reserve_avengers_intro:
    type: string
  year:
    type: integer
  years_since_joining:
    type: integer
  honorary:
    type: string
  death1:
    type: string
  return1:
    type: string
  notes:
    type: string
  death2:
    type: string
  return2:
    type: string
  probationary_introl:
    type: string
  death3:
    type: string
  return3:
    type: string
  death4:
    type: string
  return4:
    type: string
  death5:
    type: string
  return5:
    type: string
required:
  - doc_type
  - id
  - url
```
Note that the filename (minus the `.yaml`) must exactly match the `doc_type` field in the data being ingested.

After creating the schema file, you will need to exit your IPython session and relaunch, or restart your Jupyter kernel for the new schema to be picked up.

Now try to ingest an invalid document and watch an exception get thrown:

```python
context.update(dict(
    doc_type="Avenger",
    id='foo'
))
```

The above should result in a schema validation exception because we're missing the required `url` field.

```
ValidationError: 'url' is a required property

Failed validating 'required' in schema:
    {'definitions': {},
     'links': {},
     'nullable': False,
     'properties': {'_id': {'description': 'The index-unique id used for '
                                           'writing into opensearch -- '
                                           'will be autogenerated if '
                                           'omitted.',
                            'type': 'string'},
                    'appearances': {'type': 'integer'},
                    'current_': {'type': 'string'},
                    'death1': {'type': 'string'},
                    'death2': {'type': 'string'},
                    'death3': {'type': 'string'},
                    'death4': {'type': 'string'},
                    'death5': {'type': 'string'},
                    'doc_type': {'type': 'string'},
                    'full_reserve_avengers_intro': {'type': 'string'},
                    'gender': {'type': 'string'},
                    'honorary': {'type': 'string'},
                    'id': {'description': 'The index-unique id used for '
                                          'writing into opensearch -- '
                                          'will be autogenerated if '
                                          'omitted.',
                           'type': 'string'},
                    'name_alias': {'type': 'string'},
                    'notes': {'type': 'string'},
                    'probationary_introl': {'type': 'string'},
                    'return1': {'type': 'string'},
                    'return2': {'type': 'string'},
                    'return3': {'type': 'string'},
                    'return4': {'type': 'string'},
                    'return5': {'type': 'string'},
                    'url': {'type': 'string'},
                    'year': {'type': 'integer'},
                    'years_since_joining': {'type': 'integer'}},
     'required': ['id', 'doc_type', 'url'],
     'type': 'object'}

On instance:
    {'@timestamp': datetime.datetime(2022, 8, 22, 22, 44, 41, 55061),
     '@updated': datetime.datetime(2022, 8, 22, 22, 44, 41, 55056),
     '_id': 'foo',
     '_op_type': 'update',
     '_pipeline': [],
     'analytic_name': ['IPython'],
     'analytic_session_id': ['84244b01-daaa-4392-a11e-ca7ffcd79494'],
     'doc_type': 'Avenger',
     'id': 'foo'}
```

## Querying Data

This section will cover how to query data in YAADA. The methods that will be covered are `query`, `term_counts`, `exists`, `get`, and `rawquery` context methods.
Content in this section assumes you have created an IPython shell with `yda run ipython` or using Jupyter Lab with `yda run jupyter` and have already constructed your YAADA `context`, and have followed the previous tutorial to ingest `Avenger` documents.

### Fetch documents from an index with `context.query` method

This method uses the OpenSearch scroll api through the OpenSearch scan method and so can return extremely large numbers of documents if you are not careful.

Basic usage of `query` to retrieve all documents in index just requires passing the `doc_type` as a parameter:

```python
avengers = list(context.query('Avenger'))
print(len(avengers))
```
Which should print:

```
173
```

Note that `context.query('Avenger')` returns a python generator that will lazily scroll through the OpenSearch index, so we realize by wrapping with the `list` constructor.

Now let's query for a subset of avengers using an OpenSearch query. See [OpenSearch Query DSL documentation](https://opensearch.org/docs/latest/query-dsl/) for more details.

We are going to query for all avengers that have dies 3 times. Note that in the following query, we append a `.keyword` to the field we are querying on because by default, OpenSearch maps string to a fuzzy search index mapping, and provides a `.keyword` variant for exact matching with `term` queries.
```python
avengers = list(context.query('Avenger',{
    "query":{
        "term": {
            "death3.keyword":"YES"
        }
    }
}))
print(len(avengers))
```
Which should print:

```
2
```

To see the names of the two avengers returned, we can print with:

```python
print([a['name_alias'] for a in avengers])
```

and get:

```python
['Mar-Vell', 'Jocasta']
```

### Compute value counts with `context.term_counts` method
If we want to compute some high level summary statistics over some document field, we can use `context.term_counts`.

To see the counts of MALE vs FEMALE avengers, we can use the following:

```python
print(context.term_counts('Avenger','gender.keyword'))
```
which should print:
```python
{'MALE': 115, 'FEMALE': 58}
```

### Check if a document exists by id with `context.exists` method

If we want to see if an `id` exists in a specific document index, we can use `context.get`.

```python
print(context.exists('Avenger','e5d765e20f6e5e36f409a0cac8ff26bccc547a6316f4c5b5863ad360358cae89'))
```

should print:

```
True
```
### Fetch specific document with `context.get` method

To fetch a document from an index by id, we can:

```python
a = context.get('Avenger','e5d765e20f6e5e36f409a0cac8ff26bccc547a6316f4c5b5863ad360358cae89')
```

which when inspected should look like:

```
{'doc_type': 'Avenger',
 'url': 'http://marvel.wikia.com/Vision_(Earth-616)',
 'name_alias': 'Victor Shade (alias)',
 'appearances': 1036,
 'current_': 'YES',
 'gender': 'MALE',
 'full_reserve_avengers_intro': 'Nov-68',
 'year': 1968,
 'years_since_joining': 47,
 'honorary': 'Full',
 'death1': 'YES',
 'return1': 'YES',
 'notes': 'Dies in Avengers_Vol_1_500. Is eventually rebuilt. ',
 'id': 'e5d765e20f6e5e36f409a0cac8ff26bccc547a6316f4c5b5863ad360358cae89',
 'analytic_session_id': ['9d3e392b-f15e-4ac9-a24a-10b2c5145bf9'],
 'analytic_name': ['IPython'],
 '@updated': '2022-08-22T22:40:01.920328',
 '@timestamp': '2022-08-22T22:40:01.920330',
 '_pipeline': [],
 '_id': 'e5d765e20f6e5e36f409a0cac8ff26bccc547a6316f4c5b5863ad360358cae89'}
```

If I don't want to see all those fields returned, I can choose the just return certain fields by passing a `source` argument.

```python
a = context.get('Avenger','e5d765e20f6e5e36f409a0cac8ff26bccc547a6316f4c5b5863ad360358cae89',source=['doc_type','id','name_alias'])
```

which when inspected should look like:

```
{'name_alias': 'Victor Shade (alias)',
 'doc_type': 'Avenger',
 'id': 'e5d765e20f6e5e36f409a0cac8ff26bccc547a6316f4c5b5863ad360358cae89',
 '_id': 'e5d765e20f6e5e36f409a0cac8ff26bccc547a6316f4c5b5863ad360358cae89'}
```

### Raw OpenSearch query/aggregation with `context.rawquery` method

The `context.query` method mentioned above used the OpenSearch scroll API and only returns the source document, without any of the metadata from the Eleasticsearch query result envelope. If you want access to aggregations or query score data, you'll need to use `context.rawquery`.

If I want to run an OpenSearch aggregation to find out the range of `year` values in the `Avenger` index, I can run the following aggregation:

```python
r = context.rawquery('Avenger',{
    "query": {
        "match_all": {}
    },
    "aggs": {
      "earliest_year": {
        "min": {
          "field": "year"
        }
      },
      "latest_year": {
        "max": {
          "field": "year"
        }
      }
    },
    "size": 0
})
```

Inspecting the result should look like:

```
{'took': 3,
 'timed_out': False,
 '_shards': {'total': 1, 'successful': 1, 'skipped': 0, 'failed': 0},
 'hits': {'total': {'value': 173, 'relation': 'eq'},
  'max_score': None,
  'hits': []},
 'aggregations': {'earliest_year': {'value': 1900.0},
  'latest_year': {'value': 2015.0}}}
```

so we can see that the first year in the Avenger index is `1900.0` and the latest is `2015.0`.

## OpenSearch schema mapping

TODO

## Applying builtin analytics/pipelines

TODO

## Writing an Analytic

TODO

## Writing a Pipeline Processor

TODO

## Extending the REST API with custom endpoints

TODO