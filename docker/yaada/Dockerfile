ARG YAADA_BASE_IMAGE=python:3.10
ARG PLATFORM=amd64
FROM --platform=linux/${PLATFORM} ${YAADA_BASE_IMAGE}
ARG PLATFORM=amd64

RUN echo "building for platform: linux/${PLATFORM}"
RUN apt-get update && apt-get install -y dos2unix

RUN groupadd -r yaada && useradd -d /home/yaada -m -s/bin/bash --no-log-init -r -g yaada yaada

RUN mkdir /notebooks && chown -R yaada:yaada /notebooks

VOLUME ["/notebooks"]

USER yaada

ENV VIRTUAL_ENV=/home/yaada/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN mkdir -p /home/yaada/modelcache
RUN mkdir -p /home/yaada/modelcache/transformers
RUN mkdir -p /home/yaada/modelcache/sentence_transformers
RUN mkdir -p /home/yaada/modelcache/torch
RUN mkdir -p /home/yaada/modelcache/nltk_data

ENV TRANSFORMERS_CACHE=/home/yaada/modelcache/transformers
ENV SENTENCE_TRANSFORMERS_HOME=/home/yaada/modelcache/sentence_transformers
ENV TORCH_HOME=/home/yaada/modelcache/torch
ENV NLTK_DATA=/home/yaada/modelcache/nltk_data



RUN python -m pip install --upgrade pip

# cache the external requirements into a layer
COPY --chown=yaada:yaada docker/yaada/requirements-${PLATFORM}.txt /usr/src/yaada/requirements-${PLATFORM}.txt
RUN pip install --no-cache-dir -r /usr/src/yaada/requirements-${PLATFORM}.txt
RUN pip install pytest

COPY ./cert/ZscalerRootCertificate-2048-SHA256.crt /ZscalerRootCertificate-2048-SHA256.crt
RUN cat /ZscalerRootCertificate-2048-SHA256.crt >> $(python -m certifi)

WORKDIR /usr/src/yaada

ENV YAADA_CONFIG default.conf

VOLUME ["/root/.newspaper_scraper"]

COPY --chown=yaada:yaada . /usr/src/yaada

RUN pip install -e /usr/src/yaada/src/core
RUN pip install -e /usr/src/yaada/src/webscraping
RUN pip install -e /usr/src/yaada/src/nlp
RUN pip install -e /usr/src/yaada/src/openapi

RUN yaada-download-default-nlp-resources.py

USER yaada


