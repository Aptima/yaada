# Yet Another Analytic Dataflow Architecture

YAADA is a data architecture and analytics platform developed to support the full analytics development lifecycle, from prototyping in local Python to operational deployment as containerized microservices. YAADA’s primary focus is ingesting, storing, and analyzing semi-structured document-oriented data and training, persisting, and applying analytic models. It leverages industry hardened cloud technologies such as Elasticsearch and Kibana for document storage and visualization and Jupyter Notebook for exploratory data analysis and analytic prototyping. It provides an analytic plugin API that allow analytic developers to focus on the algorithms, while handling all the details of data management and analytic invocation through REST and message-based APIs. In addition, YAADA includes pre-built analytic wrappers for popular open source libraries for NLP and web scraping.

## Getting started

This README has contains instructions for developing the core YAADA project. For instructions on using YAADA for your project, consult the [Getting Started documentation](https://aptima.github.io/yaada/getting-started/).

### Prerequisites
* Docker
* docker-compose (isn't always installed with Docker under Linux, so may need to install seperately)
* On Windows, make sure Microsoft Visual C++ Build Tools are installed (requires Admin rights) and on the System PATH. (current download location: https://visualstudio.microsoft.com/downloads/ under `Tools for Visual Studio 2017` ... `Build Tools for Visual Studio 2017`)
* Python 3.8
* [PIP](https://pip.pypa.io/en/stable/)
* [`pipenv`](https://pipenv.pypa.io/en/latest/)
* Optional but recommended [`cookiecutter`](https://cookiecutter.readthedocs.io/en/stable/) -- if you would like to create your project from a template

If you run into pip version issues when installing `pipenv`, consider installing `pipenv` through [pipx](https://pipenv.pypa.io/en/latest/install/#isolated-installation-of-pipenv-with-pipx).

### Docker Setup

* On Mac, use Docker for Mac
* On Linux, use Docker for Linux
* On Windows 10, use Docker for Windows (WSL2 install preferred)
    * Note: Windows 11 is currently untested

#### YAADA memory requirements

A full YAADA-based system running infrastructure and YAADA services in development mode should ideally be allocated at least 8GB of memory. If using Docker for Mac, the default virtual machine has 2GB allocated, so this will need to be adjusted.

### Installing and running

To install and run the stock YAADA system from this repo, follow the instruction in this section. If you want to create your own project that uses YAADA, consult the [Getting Started documentation](https://aptima.github.io/yaada/getting-started/).

Activate virtual environment with:

```
pipenv shell
```

Install yaada packages with:

```
pipenv install
```

### Downloading NLP resources

```
yda run download-nlp-resources
```

### Building and running through Docker

```
$ yda build
```

#### Launching

Bring up services and infrastructure:

```
$ yda up
```

You can now access the services provided in YAADA. Here is a table of the services and how to access them locally

| Server Access Points                        |
| ------------------------------------------- |
| [OpenAPI REST UI](http://localhost:5000/ui) |
| [Jupyter Lab](http://localhost:8888/)       |
| [Kibana](http://localhost:5601)             |
| [MinIO](http://localhost:9000/)             |

Bring down services and infrastructure:

```
$ yda down
```

### Useful CLI Commands

This section will cover some useful builtin commands and tools for local development.

To see what docker containers are running, run:

```
$ yda ps 
```

When having difficulty with a service, to see the logs of that service, run::

```
$ yda logs <service_name>
```

The following command is commonly used to check what documents are currently in Elasticsearch:

```
$ yda data counts
```

Launch an IPython shell with a YAADA `context` already constructed and available and live reload setup:

```
$ yda run ipython
```

Launch Jupyter Lab locally (stopping the Docker-based instance that gets launched automatically):

```
$ yda run jupyter
```


## Contributing

Please see [Contributing Guide](CONTRIBUTING.md) for details.


## Developing YAADA

Install yaada packages with:

```
pipenv install --dev
```

Update dependencies after modifying a package's `install_requires`.

```
pipenv update
```

Updating package lock:

```
pipenv lock
```

### Linting

YAADA uses [black](https://black.readthedocs.io/en/stable/) and [isort](https://pycqa.github.io/isort/) for code reformatting and [flake8](https://flake8.pycqa.org/en/latest/) for linting. Before committing any code to the YAADA repo, you should make sure that the code is formatted and passes the linting check:

```
make lint
```

### Troubleshooting zscaler issues

Add zscaler root cert
See: https://community.zscaler.com/t/installing-tls-ssl-root-certificates-to-non-standard-environments/7261

#### Mac/Linux

```
cat cert/ZscalerRootCertificate-2048-SHA256.crt >> $(python -m certifi)
```

## Release Notes

### 6.0.3 --> 6.1.0
Due to current versions of Elasticsearch and MinIO incompatibility with M1 Macs, and due to both products having recent license changes,
YAADA has replaced Elasticsearch with OpenSearch, and replaced MinIO with Zenko CloudServer. Additionally, all use of the minio python 
client has been replaced with use of the boto3 AWS client.

OpenSearch and Zenko CloudServer both have Apache 2.0 licenses.

This will affect all project docker-compose.yml configurations, but the Python API is unchanged.

