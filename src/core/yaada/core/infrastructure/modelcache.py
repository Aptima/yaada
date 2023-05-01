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

from pylru import _dlnode, lrucache


class CacheFullError(Exception):
    pass


class UnevictableNodeError(Exception):
    pass


class DoublyLinkedListNode(_dlnode):
    __slots__ = ("evictable", "empty", "next", "prev", "key", "value")

    def __init__(self):
        self.empty = True
        self.evictable = True


class ModelCache(lrucache):
    def __init__(self, size, callback=None):
        self.callback = callback

        # Create an empty hash table.
        self.table = {}

        # Initialize the doubly linked list with one empty node. This is an
        # invariant. The cache size must always be greater than zero. Each
        # node has a 'prev' and 'next' variable to hold the node that comes
        # before it and after it respectively. Initially the two variables
        # each point to the head node itself, creating a circular doubly
        # linked list of size one.
        self.head = DoublyLinkedListNode()
        self.head.next = self.head
        self.head.prev = self.head

        self.listSize = 1

        # Now adjust the list to the desired size.
        self.size(size)

    def mark_unevictable(self, key):
        if key in self.table:
            self.table[key].evictable = False

    def mark_evictable(self, key):
        if key in self.table:
            self.table[key].evictable = True

    def unevictable_nodes(self):
        node = self.head.prev
        for i in range(len(self.table)):
            if not node.evictable:
                yield node.key
            node = node.prev

    def __setitem__(self, key, value):
        # If any value is stored under 'key' in the cache already, then replace
        # that value with the new one.
        if key in self.table:
            node = self.table[key]

            # Replace the value.
            node.value = value

            # Update the list ordering.
            self.mtf(node)
            self.head = node

            return

        # Ok, no value is currently stored under 'key' in the cache. We need
        # to choose a node to place the new item in. There are two cases. If
        # the cache is full some item will have to be pushed out of the
        # cache. We want to choose the node with the least recently used
        # item. This is the node at the tail of the list. If the cache is not
        # full we want to choose a node that is empty. Because of the way the
        # list is managed, the empty nodes are always together at the tail
        # end of the list. Thus, in either case, by chooseing the node at the
        # tail of the list our conditions are satisfied.

        # Since the list is circular, the tail node directly preceeds the
        # 'head' node.
        node = self.head.prev

        # If the node already contains something we need to remove the old
        # key from the dictionary.
        while not node.empty:
            if node.evictable:
                # Reorder the linked list in accordance with LRU.
                # Move evicted node to the tail and update the pointers
                self.mtf(node)
                if self.callback is not None:
                    self.callback(node.key, node.value)
                del self.table[node.key]
                break
            else:
                # Keep traversing until an evictable node is found
                node = node.prev
                if node == self.head.prev:
                    raise CacheFullError("Cache full and no evictable nodes found.")

        # Place the new key and value in the node
        node.empty = False
        node.key = key
        node.value = value
        node.evictable = True

        # Add the node to the dictionary under the new key and update head pointer.
        self.table[key] = node
        self.head = node

    def __delitem__(self, key):
        # Lookup the node, remove it from the hash table, and mark it as empty.
        node = self.table[key]
        if not node.evictable:
            raise UnevictableNodeError("Unable to delete unevictable node.")
        del self.table[key]
        node.empty = True
        node.evictable = True

        # Not strictly necessary.
        node.key = None
        node.value = None

        # Because this node is now empty we want to reuse it before any
        # non-empty node. To do that we want to move it to the tail of the
        # list. We move it so that it directly preceeds the 'head' node. This
        # makes it the tail node. The 'head' is then adjusted. This
        # adjustment ensures correctness even for the case where the 'node'
        # is the 'head' node.
        self.mtf(node)
        self.head = node.next

    def addTailNode(self, n):
        for i in range(n):
            node = DoublyLinkedListNode()
            node.next = self.head
            node.prev = self.head.prev

            self.head.prev.next = node
            self.head.prev = node

        self.listSize += n
