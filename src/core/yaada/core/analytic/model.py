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

import inspect
import json
import logging
import os
from abc import ABC, abstractmethod

from yaada.core.infrastructure.event import Event, event_registry
from yaada.core.utility import default_log_level

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class ModelBase(ABC):
    def __init__(self, instance_id, subscribe_events=[]):
        self.instance_id = instance_id
        self.name = self.__class__.__name__
        self.full_name = (
            f"{inspect.getmodule(self.__class__).__name__}.{self.__class__.__name__}"
        )
        self.artifacts = (
            {}
        )  # key: artifact type, value: relative or absolute path to artifact dir or file
        self.artifacts["SubscribedEvents"] = "SubscribedEvents/subscribed_events.json"
        self.artifacts["Manifest"] = "Manifest/manifest.json"
        self.subscribed_events = []
        self.subscribe_events(subscribe_events)

    @abstractmethod
    def save_artifacts(self, path):
        pass

    @abstractmethod
    def load_artifacts(self, path):
        pass

    @classmethod
    def load(cls, path, instance_id):
        instance = cls(instance_id)
        path = os.path.join(path, f"{instance.name}/{instance.instance_id}")
        instance._load_manifest(path)
        instance._load_events(path)
        instance.load_artifacts(path)
        return instance

    def save(self, path):
        path = os.path.join(path, f"{self.name}/{self.instance_id}")
        os.makedirs(path, exist_ok=True)
        self.save_artifacts(path)
        self._save_events(path)
        self._save_manifest(path)
        return path

    def on_event(self, event: Event):
        logger.warning(
            f"Received event {event.name} in ModelBase. Implement the on_event() method in child class to handle events.",
            event,
        )

    def subscribe_events(self, events=[]):
        for event_name in events:
            if event_name not in self.subscribed_events:
                event_registry.add_event_handler(event_name, self.on_event)
                self.subscribed_events.append(event_name)

    def get_name(self):
        return self.name

    def get_full_name(self):
        return self.full_name

    def get_instance_id(self):
        return self.instance_id

    def get_subscribed_events(self):
        return self.subscribed_events

    def get_artifact_types(self):
        return self.artifacts.keys()

    def get_artifact_path(self, artifact_type):
        if artifact_type in self.artifacts:
            return self.artifacts[artifact_type]

    def set_artifact_path(self, artifact_type, path):
        self.artifacts[artifact_type] = path

    def unset_artifact_path(self, artifact_type):
        if artifact_type in self.artifacts:
            del self.artifacts[artifact_type]

    def make_artifact_dir(self, path, artifact_type, set_artifact_path=True):
        artifact_dir = os.path.join(path, artifact_type)
        os.makedirs(artifact_dir, exist_ok=True)
        if set_artifact_path:
            self.set_artifact_path(artifact_type, artifact_dir)
        return artifact_dir

    def get_artifact_dir(self, path, artifact_type):
        if artifact_type in self.artifacts:
            return os.path.join(path, artifact_type)
        return None

    def _save_manifest(self, path):
        manifest_dir = self.make_artifact_dir(path, "Manifest")
        with open(os.path.join(manifest_dir, "manifest.json"), "w") as f:
            json.dump(self.artifacts, f)

    def _load_manifest(self, path):
        manifest_dir = self.get_artifact_dir(path, "Manifest")
        with open(os.path.join(manifest_dir, "manifest.json"), "r") as f:
            self.artifacts = json.load(f)

    def _save_events(self, path):
        events_dir = self.make_artifact_dir(path, "SubscribedEvents")
        with open(os.path.join(events_dir, "subscribed_events.json"), "w") as f:
            json.dump(self.subscribed_events, f)

    def _load_events(self, path):
        events_dir = self.get_artifact_dir(path, "SubscribedEvents")
        with open(os.path.join(events_dir, "subscribed_events.json"), "r") as f:
            self.subscribe_events(json.load(f))
