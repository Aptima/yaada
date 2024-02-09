# yaada-weaviate

This module provides a plugin to YAADA that extends the YAADA context with a weaviate API.


## Docker Configuration

```yaml
version: '3.4'
volumes:
  weaviate-volume:
services:
  weaviate:
    image: semitechnologies/weaviate:1.18.3
    restart: on-failure:0
    ports:
     - "18080:8080"
    volumes:
      - dgraph-volume:/var/lib/weaviate
    environment:
      QUERY_DEFAULTS_LIMIT: 20
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: text2vec-transformers
      ENABLE_MODULES: text2vec-transformers
      TRANSFORMERS_INFERENCE_API: http://t2v-transformers:8080
      CLUSTER_HOSTNAME: 'node1'
  t2v-transformers:
    image: semitechnologies/transformers-inference:sentence-transformers-msmarco-distilroberta-base-v2
    environment:
      ENABLE_CUDA: 0 # set to 1 to enable
      # NVIDIA_VISIBLE_DEVICES: all # enable if running with CUDA
```

## YAADA Configuration
In order to load the weaviate plugin, add `yaada.weaviate.plugin.WeaviatePlugin` to the the `yaada.context.plugins` list in your project's conf file.

Assuming no other plugins, it could look like this:
```
yaada.context.plugins = ["yaada.weaviate.plugin.WeaviatePlugin"]
```

You can then configure the plugin by adding a `yaada.context.plugin.weaviate` section to the config like:

```
yaada.context.plugin.weaviate {
    url = "http://localhost:18080"
    url = ${?WEAVIATE_URL}
    doc_types {
        NewsArticle {
            schema { # weaviate schema. See https://weaviate.io/developers/weaviate/configuration/schema-configuration
                "vectorizer":"text2vec-transformers", # if using vectorizer module, must be enabled through Docker configuration. 
                "properties": [
                    {
                        "dataType": ["text"],
                        "description": "article title",
                        "name": "title",
                    },
                    {
                        "dataType": ["text"],
                        "description": "article body",
                        "name": "content",
                    },    
                    {
                        "dataType": ["string[]"],
                        "description": "article keywords",
                        "name": "keywords",
                    }
                ]
            }
            fields = [ # paths to extract value from json are defined using https://github.com/jmespath/jmespath.py
                {
                    "name":"title",
                    "path":"title"
                },
                {
                    "name":"content",
                    "path":"content"
                },
                {
                    "name":"keywords",
                    "path":"keywords"
                }
            ]

        }
    }
}
```