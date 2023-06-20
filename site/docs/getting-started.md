# Getting Started

## Prerequisites
* Docker
* docker-compose (isn't always installed with Docker under Linux, so may need to install seperately)
* Python 3.8 installed locally and runnable with name `python`
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

#### YAADA memory requirements

A full YAADA-based system running infrastructure and YAADA services in development mode should ideally be allocated at least 8GB of memory. If using Docker for Mac, the default virtual machine has 2GB allocated, so this will need to be adjusted.

## Create new project:
First, you will need to install `cookiecutter`:

```
$ pip install cookiecutter
```

Next, navigate to the parent directory of where you would like your new project to go, and invoke cookiecutter with the template you want to use:

```
$ cookiecutter https://github.com/Aptima/yaada.git --checkout=v6.2.0 --directory=template/simple-compose
```

Follow the prompts, and if successful, you will have a new yaada project directory. All remaining commands will happen from within the project directory

## Python environment setup

### Create virtual environment

Open a virtual environment shell:

```
$ pipenv shell
```

### Install the current project into virtual environment

This will install the current project's package, as well as the main YAADA packages. This will take a while the first time you to it because of the number of dependencies and the locking process.

```
$ pipenv install
```

## Building and running through Docker

### Build project images

```
$ yda build
```

### Launching

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
| [Zenko CloudServer](http://localhost:8000/)             |

Bring down services and infrastructure:

```
$ yda down
```

## Useful CLI Commands

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