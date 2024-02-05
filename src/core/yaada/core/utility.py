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

import copy
import copyreg
import hashlib
import inspect
import json
import logging
import math
import os
import threading
import time
import traceback
import typing
import urllib.parse
import uuid
from collections.abc import Iterable
from datetime import datetime

import dateparser
import dateutil.parser
import numpy
from natsort import natsorted

global default_log_level
default_log_level = os.getenv("YAADA_LOGLEVEL", "ERROR")
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)
logger.info(f"DEFAULT Log Level: {default_log_level}")


def setLogLevel(level, prefix="yaada"):
    global default_log_level
    default_log_level = level
    loggers = [
        logging.getLogger(name)
        for name in logging.root.manager.loggerDict
        if name.startswith(prefix)
    ]
    for _logger in loggers:
        _logger.setLevel(level)


def method_deprecated():
    method = inspect.stack()[1]
    caller = inspect.stack()[2]
    logger.warning(
        f"'{method.function}' deprecated from '{method.filename}:{method.lineno}' called from '{caller.filename}:{caller.lineno}'"
    )


def isiterable(docs):
    if isinstance(docs, dict):
        return False
    return isinstance(docs, Iterable)


def extract_date_from_string(source, date_formats=[], fuzzy=True):
    if isinstance(source, datetime):
        return source
    if source is None:
        return None
    ts = None
    for f in date_formats:
        try:
            ts = datetime.strptime(source, f)
            if ts is not None:
                break
        except ValueError:
            pass
    if ts is None:
        try:
            ts = dateutil.parser.parse(source)
        except ValueError:
            pass
    if ts is None and fuzzy:
        ts = dateparser.parse(source)
    return ts


def urlencode(name):
    return urllib.parse.quote(name, safe="")


def traceback2str(ex):
    tb_lines = traceback.format_exception(ex.__class__, ex, ex.__traceback__)
    tb_text = "".join(tb_lines)
    return tb_text


def to_bool(bool_val):
    """Parse the string and return the boolean value encoded or raise an exception"""
    if isinstance(bool_val, str) and bool_val:
        if bool_val.lower() in ["true", "t", "1"]:
            return True
        elif bool_val.lower() in ["false", "f", "0"]:
            return False
    elif bool_val is True or bool_val is False:
        return bool_val
    # if here we couldn't parse it
    raise ValueError("%s is no recognized as a boolean value" % bool_val)


def nestify_dict(input, delimiter=".", prefix=None, strip_prefix=False):
    output = {}
    for k, v in input.items():
        if prefix is None or k.startswith(prefix):
            current = output
            if strip_prefix:
                k = k.replace(prefix, "", 1)
            *key_path, final_key = k.split(delimiter)

            # build out the dictionaries for the key path
            for key in key_path:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # assign the value to the last dictionary created from the path
            current[final_key] = v
    return output


def listify_parameter_values(in_value):
    if isinstance(in_value, dict):
        return [in_value[k] for k in natsorted(in_value.keys())]
    elif isinstance(in_value, list):
        return [v for v in in_value]
    else:
        return [in_value]


def listify_parameter_dicts(in_value, sentinel):
    if isinstance(in_value, dict):
        if sentinel in in_value:
            return [in_value]
        else:
            return [
                in_value[k]
                for k in natsorted(in_value.keys())
                if sentinel in in_value[k]
            ]
    elif isinstance(in_value, list):
        return [v for v in in_value if isinstance(v, dict) and sentinel in v]
    return []


connectivity_cache = {}


def wait_api(url, timeout):
    wait_net_service("API", url, 5.0, timeout)
    import requests

    start_time = time.time()
    while True:
        try:
            r = requests.get(f"{url}/document/")
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(1)
        elapsed_time = time.time() - start_time
        if elapsed_time >= timeout:
            raise TimeoutError("waited too long for flask to be ready")


def wait_net_service(service_name, url, interval, timeout=None):
    """Wait for network service to appear
    @param timeout: in seconds, if None or 0 wait forever
    @return: True of False, if timeout is None may return only True or
         throw unhandled network exception
    """
    global connectivity_cache

    if connectivity_cache.get("service_name", False):
        return True

    # print(f"wait_net_service:{service_name}:{url}")
    import socket
    from time import sleep
    from urllib.parse import urlparse

    parsed = urlparse(url)
    # print(f"wait_net_service.parsed {parsed}")
    port = None
    if parsed.scheme in ['http','https']:
        if parsed.scheme == "https":
            port = 443
        elif parsed.scheme == "http":
            port = 80
        if parsed.netloc != "":
            parts = parsed.netloc.split(":")
        elif parsed.path != "":
            parts = parsed.path.split(":")
    else:
        parts = url.split(":")
    server = parts[0]

    if len(parts) > 1:
        port = int(parts[1])

    s = None

    if timeout:
        from time import time as now

        # time module is needed to calc timeout shared between two exceptions
        end = now() + timeout

    while True:
        try:
            s = socket.socket()
            if timeout:
                next_timeout = end - now()
                if next_timeout < 0:
                    return False
                else:
                    s.settimeout(next_timeout)
            s.connect((server, port))
        except socket.timeout:
            # this exception occurs only if timeout is set
            if timeout:
                return False
        except ConnectionRefusedError:
            pass
        except OSError:
            pass
        else:
            if s is not None:
                s.close()
            connectivity_cache[service_name] = True
            logger.info(
                "*** connectivity to {} at {}:{} established".format(
                    service_name, server, port
                )
            )
            return True
        logger.warning(
            "*** waiting for availability of {} at {}:{}".format(
                service_name, server, port
            )
        )
        sleep(interval)


epoch = datetime.utcfromtimestamp(0)


def current_timestamp_millis():
    return int((datetime.now() - epoch).total_seconds() * 1000.0)


def get_threads_by_name(name):
    for t in threading.enumerate():
        if t.name == name:
            yield t


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            ds = None
            try:
                ds = o.isoformat()
            except Exception:
                pass
            return ds
        return json.JSONEncoder.default(self, o)


def tscopy(ts):
    return str, (ts.isoformat(),)


copyreg.pickle(datetime, tscopy)


def deepcopy_ts(o):
    return copy.deepcopy(o)


def jsonify(data):
    if isinstance(data, list):
        return [jsonify(item) for item in data]
    if isinstance(data, tuple):
        return [jsonify(item) for item in data]
    elif isinstance(data, dict):
        json_data = dict()
        for key, value in data.items():
            key = str(key)
            value = jsonify(value)
            json_data[key] = value
        return json_data
    elif isinstance(
        data,
        (
            numpy.int_,
            numpy.intc,
            numpy.intp,
            numpy.int8,
            numpy.int16,
            numpy.int32,
            numpy.int64,
            numpy.uint8,
            numpy.uint16,
            numpy.uint32,
            numpy.uint64,
        ),
    ):
        return int(data)
    elif isinstance(data, (numpy.float_, numpy.float16, numpy.float32, numpy.float64)):
        return float(data)
    elif isinstance(data, (numpy.ndarray,)):
        return jsonify(data.tolist())
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, float) and data != data:  # checking for nan
        return None
    elif data is numpy.nan or data is math.nan:  # if key is integer: > to string
        return None
    elif type(data).__module__ == "numpy":  # if data is numpy.*: > to python list
        return jsonify(data.tolist())
    else:
        return data


# `id`` and `_id`` should always be the same. If one is set, the other will be set the the same value, giving preference to `id`.
def assign_document_id(d):
    if "_id" in d and "id" not in d:
        d["id"] = d["_id"]
    if "id" not in d:
        d["id"] = str(uuid.uuid4())
    d["_id"] = d["id"]
    return d


def assign_analytic_session_id(d, analytic_session_id):
    ids = d.get("analytic_session_id", None)
    if ids is None:
        ids = set()
    else:
        ids = set(ids)
    ids.add(analytic_session_id)

    d["analytic_session_id"] = list(ids)
    return d


def assign_analytic_name(d, analytic_name):
    names = d.get("analytic_name", None)
    if names is None:
        names = set()
    else:
        names = set(names)
    names.add(analytic_name)

    d["analytic_name"] = list(names)
    return d


def prepare_doc_for_insert(
    doc, analytic_name, analytic_session_id, upsert=False, archive=False
):
    doc = assign_document_id(doc)
    if not archive:
        doc = assign_analytic_session_id(doc, analytic_session_id)
        doc = assign_analytic_name(doc, analytic_name)
    if upsert:
        doc["_op_type"] = "update"
    if not archive:
        doc["@updated"] = datetime.utcnow()
        if "@timestamp" not in doc:
            doc["@timestamp"] = datetime.utcnow()

    return doc


def doc_ref(doc, label_field="title"):
    ref = dict(
        _id=doc["_id"], doc_type=doc["doc_type"], label=doc.get(label_field, None)
    )
    ref[label_field] = doc.get(label_field, None)
    return ref


# take an iterable list or generator and turn into generator of realized batches
def batched_generator(elements, batch_size):
    batch = []
    i = 0
    for el in elements:
        batch.append(el)
        i += 1

        if i >= batch_size:
            i = 0
            yield batch[:]
            batch.clear()

    if i > 0:
        yield batch


def create_service_overrides(service_name, overrides, fields=None):
    # fields specifies which values from the outer override section are relevant to the service specific section
    if fields is None:
        if service_name == "mqtt":
            fields = ["hostname", "prefix", "tenant"]
        elif service_name == "opensearch":
            fields = ["hostname", "prefix", "tenant", "protocol"]
        elif service_name == "objectstorage":
            fields = ["hostname", "prefix", "tenant"]
        elif service_name == "external_mqtt":
            fields = ["hostname"]
        else:
            fields = []

    my_overrides = dict(
        **overrides.get(service_name, {})
    )  # make a copy of mqtt section
    for k in fields:
        if k not in my_overrides and k in overrides:
            my_overrides[k] = overrides[k]
    return my_overrides


def hash_for_text(data: typing.List[str]) -> str:
    m = hashlib.sha256()
    for d in data:
        m.update(d.encode())
    return m.hexdigest()


def hash_doc_fields(doc, fields: typing.List[str]):
    h = hash_for_text([str(doc[f]) for f in fields if doc.get(f, None) is not None])
    return h
