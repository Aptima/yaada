# Copyright (c) 2023 Aptima, Inc.
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

PACKAGE_DIRS = $(dir $(wildcard src/*/setup.py)) $(dir $(wildcard src/plugins/*/setup.py))
DIST_DIRS = $(patsubst %, %/dist, $(PACKAGE_DIRS))
BUILD_DIRS = $(patsubst %, %/build, $(PACKAGE_DIRS))



flake8:
	pipenv run flake8 $(PACKAGE_DIRS)
black:
	pipenv run black $(PACKAGE_DIRS)
isort:
	pipenv run isort $(PACKAGE_DIRS)
lint: black isort flake8

build-packages: $(DIST_DIRS)

install:
	pipenv install --dev
update:
	pipenv update
lock-requirements:
	pipenv lock
update-requirements-arm64:
	pipenv requirements --exclude-markers | grep "^[^-]" > docker/yaada/requirements-arm64.txt
	pipenv requirements --exclude-markers | grep "^[^-]" > template/simple-compose/{{cookiecutter.project_name}}/docker/yaada/requirements-arm64.txt
lock-arm64: lock-requirements update-requirements-arm64

lock-amd64:lock-requirements update-requirements-amd64

update-requirements-amd64:
	pipenv requirements --exclude-markers | grep "^[^-]" > docker/yaada/requirements-amd64.txt
	pipenv requirements --exclude-markers | grep "^[^-]" > template/simple-compose/{{cookiecutter.project_name}}/docker/yaada/requirements-amd64.txt
lock: lock-amd64
%/dist:
	cd $(dir $@) && python -m build

clean-packages:
	rm -rf $(DIST_DIRS)
	rm -rf $(BUILD_DIRS)

WHEELS = $(wildcard src/*/dist/*.whl)
publish-packages: build-packages
	twine upload --repository-url https://pypi.org/simple $(WHEELS)

purge:
	yda volume purge
build:
	yda build
down:
	yda down
up:
	yda up
test:
	yda run test
test-docker:
	yda shell openapi -- pytest tests/e2e/ --ignore tests/e2e/test_openapi_file_upload.py
test-nlp:
	yda run test-nlp
test-nlp-docker:
	yda shell openapi -- pytest tests/nlp

docs-openapi-spec:
	yda openapi-spec > site/docs/openapi.json
docs-dev: docs-openapi-spec
	yda run docs-serve
docs-build:
	cd site && mkdocs build --verbose
publish: clean-packages publish-packages
	yda build
	yda push