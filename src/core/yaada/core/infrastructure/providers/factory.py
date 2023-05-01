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

from yaada.core.infrastructure.modelmanager import ModelManager
from yaada.core.infrastructure.providers.elasticsearch import ElasticsearchProvider
from yaada.core.infrastructure.providers.mqtt import ExternalMQTTProvider, MQTTProvider
from yaada.core.infrastructure.providers.objectstorage import ObjectStorageProvider
from yaada.core.utility import create_service_overrides


def make_message_service(config, overrides={}):
    if config.message_provider == "mqtt":
        _message_service = MQTTProvider(
            config, overrides=create_service_overrides("mqtt", overrides)
        )
        return _message_service


def make_document_service(config, overrides={}):
    _document_service = ElasticsearchProvider(
        config, overrides=create_service_overrides("elasticsearch", overrides)
    )
    return _document_service


def make_objectstorage_service(config, overrides={}):
    _objectstorage_service = ObjectStorageProvider(
        config, overrides=create_service_overrides("objectstorage", overrides)
    )
    return _objectstorage_service


def make_external_mqtt_service(config, overrides={}):
    _external_mqtt_service = ExternalMQTTProvider(
        config, overrides=create_service_overrides("external_mqtt", overrides)
    )
    return _external_mqtt_service


def make_model_manager(config, context):
    _model_manager = ModelManager(config, context)
    return _model_manager
