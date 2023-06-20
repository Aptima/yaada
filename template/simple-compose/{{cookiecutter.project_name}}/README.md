# {{cookiecutter.project_name}}

## Getting started

### Docker Setup

* On Mac, use Docker for Mac
* On Linux, use Docker for Linux
* On Windows 10, use Docker for Windows (WSL2 install preferred)

### Prerequisites
* Docker
* docker-compose (isn't always installed with Docker under Linux, sp may need to install seperately)
* Python 3.8 installed locally and runnable with name `python`
* On Windows, make sure Microsoft Visual C++ Build Tools are installed (requires Admin rights) and on the System PATH. (current download location: https://visualstudio.microsoft.com/downloads/ under `Tools for Visual Studio 2017` ... `Build Tools for Visual Studio 2017`)
* [PIP](https://pip.pypa.io/en/stable/)
* [`pipenv`](https://pipenv.pypa.io/en/latest/)

If you run into pip version issues when installing `pipenv`, consider installing `pipenv` through pipx: https://pipenv.pypa.io/en/latest/install/#isolated-installation-of-pipenv-with-pipx

#### YAADA memory requirements

A full YAADA-based system running infrastructure and YAADA services in development mode should ideally be allocated at least 8GB of memory. If using Docker for Mac, the default virtual machine has 2GB allocated, so this will need to be adjusted.

### Installing and running

Install yaada packages with:

```
pipenv install
```

Activate virtual environment with:

```
pipenv shell
```

## Development Instructions

Install project packages with:

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
