# Copyright (c) 2022 Aptima, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import fastentrypoints  # noqa
from setuptools import find_namespace_packages, setup

setup(
    name="yaada-core",
    version="6.2.0",
    packages=find_namespace_packages(),
    description="",
    long_description="",
    author="Gabriel Ganberg",
    author_email="ganberg@aptima.com",
    python_requires=">=3.8.0",
    zip_safe=False,
    licence="MIT License",
    scripts=[
        "yaada/core/entrypoints/yaada-ingest-pipeline.py",
        "yaada/core/entrypoints/yaada-single-job-executor.py",
        "yaada/core/entrypoints/yaada-sink.py",
        "yaada/core/entrypoints/yaada-sinklog-writer.py",
        "yaada/core/entrypoints/yaada-worker-docker.py",
        "yaada/core/entrypoints/yaada-worker.py",
    ],
    entry_points="""
        [console_scripts]
        yda=yaada.core.cli.yda:common.yaada
    """,
    install_requires=[
        "ipython",
        "click",
        "python-dateutil",
        "requests",
        "requests-file",
        "urllib3>=1.26,<2.1",  # elasticsearch usage of urllib3 will be deprecated as of urllib3 2.1.0. Will need to figure out elasticsearch upgrade path before relaxing this.
        "tqdm",
        "regex==2021.11.10",
        "paho-mqtt",
        "methodtools",
        "jmespath",
        "ruamel.yaml",
        "GitPython",
        "boto3",
        "docker",
        "elasticsearch==7.10.1",
        "schedule",
        "numpy",
        "networkx",
        "deepmerge",
        "pylru",  # for model cache
        "importlib-metadata",
        "chardet",  # for artifact file type inference
        "dateparser",
        "natsort",
        "genson",  # json schema generation
        "tika",  # for artifact extraction
        "pyhocon==0.3.59",  # 0.3.60 breaks things for some reason. Need to investigate before upgrading.
        "openapi-schema-validator",
        "jupyterlab",
        "pandas",
        "scikit-learn",
        "matplotlib",
        "pyLDAvis",
    ],
    include_package_data=True,
)
