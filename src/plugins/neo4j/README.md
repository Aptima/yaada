# yaada-neo4j

This module provides a plugin to YAADA that extends the YAADA context with a neo4j API.


## Docker Configuration

```
version: '3.6'

volumes:
  neo4j-volume:


networks:
  default:
    name: ${YAADA_NETWORK_NAME:-yaada-shared-infrastructure}
    external: true
services:
  neo4j:
    image: neo4j:5.5.0-community
    volumes:
      - neo4j-volume:/data
    environment:
      NEO4J_AUTH: none
    ports:
      - 7474:7474
      - 7687:7687
```

## YAADA Configuration

In order to load the neo4j plugin, add `yaada.neo4j.plugin.Neo4jPlugin` to the the `yaada.context.plugins` list in your project's conf file.

Assuming no other plugins, it could look like this:
```
yaada.context.plugins = ["yaada.neo4j.plugin.Neo4jPlugin"]

Example configuration for mapping data scraped from github into a graph structure:

```
yaada.context.plugin.neo4j {
    uri = "bolt://localhost:7687"
    uri = ${?NEO4J_URI}
    database = "neo4j"
    doc_types {
        GithubPullRequest {
            vertex_label = "GithubPullRequest"
            fields = [
                {
                    "type": "property"
                    "name":"id",
                    "path":"id",
                    "index": true
                },
                {
                    "type": "property",
                    "name":"state",
                    "path":"state"
                },
                {
                    "type": "property",
                    "name":"locked",
                    "path":"locked"
                },
                {
                    "type": "property",
                    "name":"title",
                    "path":"title"
                },

                {
                    "type": "edge",
                    "edge_label":"HAS_USER",
                    "target_vertex_label":"GithubUser",
                    "target_id":"id",
                    "path":"user.login"
                },
                {
                    "type": "edge",
                    "edge_label":"CLOSED_BY",
                    "target_vertex_label":"GithubUser",
                    "target_id":"id",
                    "path":"closed_by.login"
                },
                {
                    "type": "edge",
                    "edge_label":"RELATED_PULL",
                    "target_vertex_label":"GithubPullRequest",
                    "target_id":"id",
                    "path":"pull_doc_id"
                },

            ]
        },
        GithubIssue {
            vertex_label = "GithubIssue"
            fields = [
                {
                    "type": "property"
                    "name":"id",
                    "path":"id",
                    "index": true
                },
                {
                    "type": "property",
                    "name":"state",
                    "path":"state"
                },
                {
                    "type": "property",
                    "name":"locked",
                    "path":"locked"
                },
                {
                    "type": "property",
                    "name":"title",
                    "path":"title"
                },
                {
                    "type": "edge",
                    "edge_label":"HAS_USER",
                    "target_vertex_label":"GithubUser",
                    "target_id":"id",
                    "path":"user.login"
                },
                {
                    "type": "edge",
                    "edge_label":"CLOSED_BY",
                    "target_vertex_label":"GithubUser",
                    "target_id":"id",
                    "path":"closed_by.login"
                },
                {
                    "type": "edge",
                    "edge_label":"RELATED_PULL",
                    "target_vertex_label":"GithubPullRequest",
                    "target_id":"id",
                    "path":"pull_doc_id"
                },
            ]
        },
        GithubCommit {
            vertex_label = "GithubCommit"
            fields = [
                {
                    "type": "property"
                    "name":"id",
                    "path":"id",
                    "index": true
                },
                {
                    "type": "edge",
                    "edge_label":"HAS_AUTHOR",
                    "target_vertex_label":"GithubUser",
                    "target_id":"id",
                    "path":"@",
                    "target_property_fields": [
                        {
                            "name":"id",
                            "path":"author.login"
                        },
                        {
                            "name":"name",
                            "path":"commit.author.name"
                        },
                        {
                            "name":"email",
                            "path":"commit.author.email"
                        },
                    ],
                },
                {
                    "type": "edge",
                    "edge_label":"HAS_COMMITTER",
                    "target_vertex_label":"GithubUser",
                    "target_id":"id",
                    "path":"committer.login"
                },
                {
                    "type": "edge",
                    "edge_label":"CHANGED_FILE",
                    "target_vertex_label":"SourceFile",
                    "target_id":"filename",
                    "path":"files[]",
                    "target_property_fields": [
                        {
                            "name":"filename",
                            "path":"filename"
                        }
                    ],
                    "edge_property_fields": [
                        {
                            "name":"sha",
                            "path":"sha"
                        },
                        {
                            "name":"additions",
                            "path":"additions"
                        },
                        {
                            "name":"deletions",
                            "path":"deletions"
                        },
                        {
                            "name":"changes",
                            "path":"changes"
                        },
                        {
                            "name":"status",
                            "path":"status"
                        },
                    ]
                },
                {
                    "type": "edge",
                    "edge_label":"RELATED_PULL",
                    "target_vertex_label":"GithubPullRequest",
                    "target_id":"id",
                    "path":"pull_doc_id"
                },
            ]
        },
    }
}
```