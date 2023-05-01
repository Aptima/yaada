#!/bin/bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")") # get the parent directory of this script
YAADA_DIR="$(dirname "$SCRIPT_DIR")"
pip install -r ${YAADA_DIR}/docker/yaada/requirements.txt
pip install -e ${YAADA_DIR}/src/core
pip install -e ${YAADA_DIR}/src/dataset
pip install -e ${YAADA_DIR}/src/nlp
pip install -e ${YAADA_DIR}/src/openapi
pip install -e ${YAADA_DIR}/src/webscraping
