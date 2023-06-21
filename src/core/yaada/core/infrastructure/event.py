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

from abc import ABC, abstractmethod


class Event(ABC):
    """Base event class"""

    def __init__(self, data=None, handlers=[]):
        self.data = data
        self.name = self.__class__.__name__
        self.handlers = handlers

    def __eq__(self, other):
        if isinstance(self, other.__class__):
            return self.__dict__ == other.__dict__
        return False

    def get_name(self):
        return self.name

    def trigger(self):
        self.on_trigger()
        for handler in self.handlers:
            handler(self)

    @abstractmethod
    def on_trigger(self):
        pass


class EventRegistry:
    """Handles event class registration"""

    def __init__(self):
        self.event_classes = {}
        self.handlers = {}

    def register(self, event_clazz: Event):
        if event_clazz.__name__ not in self.event_classes.keys():
            self.event_classes[event_clazz.__name__] = event_clazz
            self.handlers[event_clazz.__name__] = []

    def get_event_class(self, event_name: str):
        if event_name in self.event_classes:
            return self.event_classes[event_name]
        return None

    def get_registered_event_names(self):
        return self.event_classes.keys()

    def make_event_obj(self, event_name: str, data=None):
        if event_name in self.event_classes:
            handlers = self.handlers[event_name]
            return self.event_classes[event_name](data, handlers)
        return None

    def add_event_handler(self, event_name: str, handler):
        if event_name in self.handlers:
            self.handlers[event_name].append(handler)


event_registry = EventRegistry()
