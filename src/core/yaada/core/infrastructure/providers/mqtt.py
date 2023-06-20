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

import json
import logging
import os
import queue
from datetime import datetime, timedelta
from uuid import uuid4

import paho.mqtt.packettypes as packettypes
from paho.mqtt import client as mqtt
from yaada.core import default_log_level, utility

broker = {
    "host": os.getenv("MQTT_BROKER_HOSTNAME", "localhost"),
    "port": int(os.getenv("MQTT_BROKER_PORT", "1883")),
    "keepalive": 60,
    "bind_address": os.getenv("MQTT_BROKER_BIND_ADDRESS", ""),
}


def default_props():
    props = mqtt.Properties(packettypes.PacketTypes.PUBLISH)
    msgProps = [
        # (
        #     "_padding",
        #     "x" * 128,
        # )  # remove once we upgrade past v1.5.1. see https://github.com/eclipse/paho.mqtt.python/issues/541
    ]
    props.UserProperty = msgProps
    return props


def extract_message_payload(msg):
    return msg.payload


class RawMessage(object):
    def __init__(
        self, key, payload=None, rawProps=None, jsondata=None, jsonencoder=None
    ):
        if rawProps is not None:
            self.rawProps = rawProps
        else:
            self.rawProps = default_props()

        self.key = key
        self.payload = payload

        if jsondata:
            self.payload = json.dumps(jsondata, cls=jsonencoder).encode("utf-8")

    @property
    def jsondata(self):
        return json.loads(self.payload.decode("utf-8"))

    def __repr__(self):
        return f"RawMessage(key='{self.key}',payload={self.payload})"


class RawConnection(object):
    def __init__(
        self,
        clientid,
        host=broker["host"],
        port=broker["port"],
        keepalive=broker["keepalive"],
        bind_address=broker["bind_address"],
    ):
        self.__logger = logging.getLogger(__name__)
        self.__client_id = clientid
        self.__host = host
        self.__port = port
        self.__keepalive = keepalive
        self.__bind_address = bind_address
        self.__background_loop = False
        self.__mqttc = mqtt.Client(clientid, protocol=mqtt.MQTTv5)
        self.__mqttc.on_message = self.__on_message
        self.__mqttc.on_connect = self.__on_connect
        self.__mqttc.on_disconnect = self.__on_disconnect
        self.__onConnectionStateChange = None
        self.__onMessage = None

    # Callbacks
    def __on_connect(self, client, userdata, flags, rc, properties):
        callback = self.onConnectionStateChange
        if callback:
            try:
                callback(True, rc)
            except Exception:
                self.__logger.error("Failed connect callback", exc_info=True)
        else:
            self.__logger.info("connect rc {0}".format(rc))

    def __on_disconnect(self, client, userdata, rc):
        callback = self.onConnectionStateChange
        if callback:
            try:
                callback(False, rc)
            except Exception:
                self.__logger.error("Failed disconnect callback", exc_info=True)
        else:
            self.__logger.info("disconnect rc {0}".format(rc))

    def __on_message(self, client, userdata, msg):
        callback = self.onMessage
        payload = extract_message_payload(msg)
        if callback:
            try:
                callback(RawMessage(msg.topic, payload, msg.properties))
            except Exception:
                self.__logger.error("Failed message callback", exc_info=True)
        else:
            self.__logger.info(msg.topic + " " + str(msg.qos) + " " + str(payload))

    @property
    def onConnectionStateChange(self):
        return self.__onConnectionStateChange

    @onConnectionStateChange.setter
    def onConnectionStateChange(self, value):
        """Define the connection callback implementation.

        Expected signature is:
            onConnectionStateChange(isConnected, rc)

        isConnected : the client instance for this callback
        rc          : the connection result

        The value of rc indicates success or not:
            0: Connection successful
            1-255: Connection unsuccessful.
        """
        self.__onConnectionStateChange = value

    @property
    def onMessage(self):
        return self.__onMessage

    @onMessage.setter
    def onMessage(self, value):
        """Define the message callback implementation.

        Expected signature is:
        onMessage(rawMessage)

        rawMessage : the raw message
        """
        self.__onMessage = value

    # Publish
    def publish(self, msg, qos=0, retain=False):
        self.__mqttc.publish(
            msg.key, msg.payload, qos=qos, retain=retain, properties=msg.rawProps
        )

    # Subscribe
    def subscribe(self, topic):
        self.__mqttc.subscribe(topic)

    # deliver messages that match subscription filter to callback.
    # only messages that don't match any callbacks will be delivered to onMessage callback.
    def message_callback_add(self, sub, callback):
        def my_callback(client, userdata, msg):
            try:
                payload = extract_message_payload(msg)
                callback(RawMessage(msg.topic, payload, msg.properties))
            except Exception:
                self.__logger.error("Failed message callback", exc_info=True)

        self.__mqttc.message_callback_add(sub, my_callback)

    # remove subscription callback
    def message_callback_remove(self, sub):
        self.__mqttc.message_callback_remove(sub)

    # Unsubscribe
    def unsubscribe(self, topic):
        self.__mqttc.unsubscribe(topic)

    # Connect
    def connect(self, start_loop=True):
        self.__mqttc.connect(
            self.__host,
            port=self.__port,
            keepalive=self.__keepalive,
            bind_address=self.__bind_address,
        )
        self.__background_loop = start_loop
        if start_loop:
            self.__mqttc.loop_start()

    def start_loop(self):
        self.__background_loop = True
        self.__mqttc.loop_start()

    def loop_forever(self):
        self.__mqttc.loop_forever()

    def loop(self):
        self.__mqttc.loop()

    # Disconnect
    def disconnect(self):
        if self.__background_loop:
            self.__mqttc.loop_stop()
            self.__background_loop = False
        self.__mqttc.disconnect()

    @property
    def clientId(self):
        return self.__client_id


class BufferedStream:
    def __init__(self, maxsize=0, transform=None):
        self._queue = queue.Queue(maxsize=maxsize)
        self._callback = None
        self._transform = transform

    def put(self, item):
        x = item
        if self._transform is not None:
            x = self._transform(item)
        if self._callback is not None:
            self._callback(x)
        else:
            self._queue.put(x)

    def fetch(self, timeout_ms=1000, max_count=1000):
        delta = timedelta(milliseconds=timeout_ms)
        start = datetime.utcnow()
        r = []
        while len(r) < max_count and datetime.utcnow() - start < delta:
            try:
                timeout = (delta - (datetime.utcnow() - start)).total_seconds()
                if timeout < 0:
                    timeout = 0.001
                r.append(self._queue.get(block=True, timeout=timeout))
            except queue.Empty:
                break
        return r

    def on(self, callback):
        self._callback = callback

    def off(self):
        self._callback = None


class SubscriptionManager:
    def __init__(self, connection, default_queue):
        self.connection = connection
        self.default_queue = default_queue
        self.subscriptions = {}

    def subscribe(self, sub, dest=None):
        if sub not in self.subscriptions:
            self.connection.subscribe(sub)
            self.subscriptions[sub] = []

        q = self.default_queue
        if dest is not None:
            q = dest
        if q not in self.subscriptions[sub]:
            self.subscriptions[sub].append(q)

    def unsubscribe(self, sub):
        del self.subscriptions[sub]
        self.connection.unsubscribe(sub)

    def put(self, doc):
        for sub, dests in self.subscriptions.items():
            if mqtt.topic_matches_sub(sub, doc["_topic"]):
                for d in dests:
                    d.put(doc)


logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


def onConnection(isConnected, rc):
    if isConnected:
        logger.info("**************** mqtt connected")
    else:
        logger.info("**************** mqtt disconnected")


class MQTTProvider:
    def __init__(self, config, overrides={}):
        self.overrides = overrides
        self._config = config
        self._client_id = f"yaada-{str(uuid4())}"
        self._tenant = self.overrides.get("tenant", config.tenant)
        self._prefix = self.overrides.get("prefix", config.data_prefix)
        ingest_topic = self.overrides.get("ingest", config.mqtt_ingest_topic)
        sink_topic = self.overrides.get("sink", config.mqtt_sink_topic)
        sinklog_topic = self.overrides.get("sinklog", config.mqtt_sinklog_topic)
        self._ingest_topic = f"{self._prefix}/{self._tenant}/{ingest_topic}"
        self._sink_topic = f"{self._prefix}/{self._tenant}/{sink_topic}"
        self._sinklog_topic = f"{self._prefix}/{self._tenant}/{sinklog_topic}"
        self._analytic_request_topic = f"{self._prefix}/{self._tenant}/analytic/request"
        self._analytic_status_topic = f"{self._prefix}/{self._tenant}/analytic/status"
        self._event_topic_base = f"{self._prefix}/{self._tenant}/event"
        self.receive_buffer = BufferedStream()
        self.subscriptions = None

    def connect(self, client_id):
        self._client_id = client_id

        hostname = self.overrides.get("hostname", self._config.mqtt_hostname)
        port = self.overrides.get("port", self._config.mqtt_port)

        utility.wait_net_service(
            "mqtt", f"{hostname}:{port}", 5.0, self._config.connection_timeout
        )
        self.connection = RawConnection(
            f"{self._client_id}-{str(uuid4())}", host=hostname, port=port
        )
        self.connection.onMessage = self._incoming_message
        self.connection.onConnectionStateChange = onConnection
        # Connect and subscribe to messages, installing filter-based callbacks
        self.connection.connect()
        self.subscriptions = SubscriptionManager(
            connection=self.connection, default_queue=self.receive_buffer
        )

    def disconnect(self):
        self.connection.disconnect()

    def set_analytic(self, analytic_name, analytic_session_id):
        self.analytic_name = analytic_name
        self.analytic_session_id = analytic_session_id

    def subscribe_ingest(self):
        ingest_subscription = f"{self._ingest_topic}/#"
        self.subscriptions.subscribe(ingest_subscription)
        logger.info(f"ingest_subscription: {ingest_subscription}")

    def subscribe_sink(self):
        sink_subscription = f"{self._sink_topic}/#"
        self.subscriptions.subscribe(sink_subscription)
        logger.info(f"sink_subscription: {sink_subscription}")

    def subscribe_sinklog(self):
        sinklog_subscription = f"{self._sinklog_topic}/#"
        self.subscriptions.subscribe(sinklog_subscription)
        logger.info(f"sinklog_subscription: {sinklog_subscription}")

    def subscribe_analytic_request(self, analytic_name=None, analytic_session_id=None):
        sub_base = self._analytic_request_topic
        if analytic_name is None and analytic_session_id is None:
            sub = f"{sub_base}/#"
        elif analytic_session_id is None:
            sub = f"{sub_base}/{analytic_name}/#"
        else:
            sub = f"{sub_base}/{analytic_name}/{analytic_session_id}"
        self.subscriptions.subscribe(sub)
        logger.info(f"analytic_request_subscription: {sub}")

    def subscribe_analytic_status(self, analytic_name, analytic_session_id):
        sub_base = self._analytic_status_topic
        sub = f"{sub_base}/{analytic_name}/{analytic_session_id}"
        self.subscriptions.subscribe(sub)
        logger.info(f"subscribe_analytic_status: {sub}")

    def unsubscribe_analytic_status(self, analytic_name, analytic_session_id):
        sub_base = self._analytic_status_topic
        sub = f"{sub_base}/{analytic_name}/{analytic_session_id}"
        self.subscriptions.unsubscribe(sub)
        logger.info(f"unsubscribe_analytic_status: {sub}")

    def subscribe_event(self, sub, dest):
        self.subscriptions.subscribe(f"{self._event_topic_base}/{sub}", dest=dest)

    def unsubscribe_event(self, sub):
        self.subscriptions.unsubscribe(f"{self._event_topic_base}/{sub}")

    def publish(self, topic: str, payload: dict, retain=False, qos=0):
        msg = RawMessage(topic, jsondata=payload, jsonencoder=utility.DateTimeEncoder)
        self._send_msg(msg, retain=retain, qos=qos)

    def publish_event(self, topic: str, payload: dict, retain=False, qos=0):
        msg = RawMessage(
            f"{self._event_topic_base}/{topic}",
            jsondata=payload,
            jsonencoder=utility.DateTimeEncoder,
        )
        self._send_msg(msg, retain=retain, qos=qos)

    def publish_ingest(self, doc):
        msg = RawMessage(
            f"{self._ingest_topic}/{doc['doc_type']}/{utility.urlencode(doc['_id'])}",
            jsondata=doc,
            jsonencoder=utility.DateTimeEncoder,
        )
        self._send_msg(msg, retain=True, qos=0)

    def publish_sink(self, doc):
        msg = RawMessage(
            f"{self._sink_topic}/{doc['doc_type']}/{utility.urlencode(doc['_id'])}",
            jsondata=doc,
            jsonencoder=utility.DateTimeEncoder,
        )
        self._send_msg(msg, retain=True, qos=0)

    def publish_sinklog(self, doc):
        msg = RawMessage(
            f"{self._sinklog_topic}/{doc['doc_type']}/{utility.urlencode(doc['_id'])}",
            jsondata=doc,
            jsonencoder=utility.DateTimeEncoder,
        )
        self._send_msg(msg, retain=False, qos=0)

    def analytic_request_topic(self, analytic_name, analytic_session_id):
        return f"{self._analytic_request_topic}/{analytic_name}/{analytic_session_id}"

    def publish_analytic_request(
        self, analytic_name, analytic_session_id, parameters, worker, image, gpu, login
    ):
        msg = RawMessage(
            self.analytic_request_topic(analytic_name, analytic_session_id),
            jsondata=dict(
                analytic_name=analytic_name,
                analytic_session_id=analytic_session_id,
                parameters=parameters,
                worker=worker,
                image=image,
                gpu=gpu,
                login=login,
            ),
            jsonencoder=utility.DateTimeEncoder,
        )
        self._send_msg(msg, retain=True, qos=0)

    def analytic_status_topic(self, analytic_name, analytic_session_id):
        return f"{self._analytic_status_topic}/{analytic_name}/{analytic_session_id}"

    def publish_analytic_status(self, analytic_name, analytic_session_id, status):
        msg = RawMessage(
            self.analytic_status_topic(analytic_name, analytic_session_id),
            jsondata=status,
            jsonencoder=utility.DateTimeEncoder,
        )
        self._send_msg(msg, retain=False, qos=0)

    def delete_retained_topic(self, topic):
        msg = RawMessage(topic, payload=None)
        self._send_msg(msg, retain=True)

    def fetch(self, timeout_ms=1000, max_count=1000):
        return self.receive_buffer.fetch(timeout_ms=timeout_ms, max_count=max_count)

    def _incoming_message(self, msg):
        if not msg.payload:
            return
        doc = msg.jsondata
        doc["_topic"] = msg.key
        if "@timestamp" not in doc:
            doc["@timestamp"] = datetime.utcnow()
        self.subscriptions.put(doc)
        logger.debug(f"mqtt received {msg.payload}")

    def _send_msg(self, rawmsg, qos=0, retain=False):
        self.connection.publish(rawmsg, qos=qos, retain=retain)


class ExternalMQTTProvider:
    def __init__(self, config, overrides={}):
        self._config = config
        self._client_id = None
        self._topics = []
        self.connection = None
        self.overrides = overrides
        self.hostname = self.overrides.get("hostname", self._config.mqtt_hostname)
        self.port = self.overrides.get("port", self._config.mqtt_port)

    def connect(self, client_id):
        self._client_id = client_id
        utility.wait_net_service("mqtt", f"{self.hostname}:{self.port}", 5.0)
        self.connection = RawConnection(
            f"{self._client_id}-{str(uuid4())}", host=self.hostname, port=int(self.port)
        )
        self.connection.onConnectionStateChange = onConnection
        self.connection.onMessage = self._incoming_message
        self.connection.connect()

    def _incoming_message(self, msg):
        if not msg.payload:
            return
        message = msg.jsondata
        if "_topic" not in message:
            message["_topic"] = msg.key
        if "@timestamp" not in message:
            message["@timestamp"] = datetime.utcnow()
        logger.debug("Got message: " + message)

    def subscribe_topic(self, topic):
        self._topics.append(topic)
        self.connection.subscribe(topic, qos=0)

    def publish_topic(self, topic, msg, retain=False):
        msg = RawMessage(topic, jsondata=msg, jsonencoder=utility.DateTimeEncoder)
        self._send_msg(msg, retain=retain)

    def delete_retained_topic(self, topic):
        msg = RawMessage(topic, payload=None)
        self._send_msg(msg, retain=True)

    def _send_msg(self, rawmsg, qos=0, retain=False):
        self.connection.publish(rawmsg, qos=qos, retain=retain)
