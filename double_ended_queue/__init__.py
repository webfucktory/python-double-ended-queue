# flake8: noqa

# PEP0440 compatible formatted version, see:
# https://www.python.org/dev/peps/pep-0440/
#
# Generic release markers:
#   X.Y.0   # For first release after an increment in Y
#   X.Y.Z   # For bugfix releases
__version__ = '0.1.1'

import collections
from asyncio import events, locks
from typing import Any


class DequeEmpty(Exception):
    """Raised when Deque.get_left_nowait() or Deque.get_right_nowait() methods are called on an empty Deque."""

    pass


class DequeFull(Exception):
    """Raised when the Deque.put_left_nowait() or Deque.put_right_nowait() methods are called on a full Deque."""

    pass


class Deque:
    def __init__(self, maxsize=0):
        self.__loop = events.get_event_loop()

        self.__maxsize = maxsize

        # Futures.
        self.__getters = collections.deque()

        # Futures.
        self.__putters = collections.deque()

        self.__unfinished_tasks = 0

        self.__finished = locks.Event()

        self.__finished.set()

        self.__deque = collections.deque()

    @staticmethod
    def __wakeup_next(waiters):
        # Wake up the next waiter (if any) that isn't cancelled.
        while waiters:
            waiter = waiters.popleft()

            if not waiter.done():
                waiter.set_result(None)

                break

    def __repr__(self):
        return f'<{type(self).__name__} at {id(self):#x} {self.__format()}>'

    def __str__(self):
        return f'<{type(self).__name__} {self.__format()}>'

    def __format(self):
        result = f'maxsize={self.__maxsize!r}'

        if getattr(self, '_deque', None):
            result += f' _deque={list(self.__deque)!r}'

        if self.__getters:
            result += f' _getters[{len(self.__getters)}]'

        if self.__putters:
            result += f' _putters[{len(self.__putters)}]'

        if self.__unfinished_tasks:
            result += f' tasks={self.__unfinished_tasks}'

        return result

    def size(self):
        """Number of items in the Deque."""

        return len(self.__deque)

    @property
    def maxsize(self):
        """Number of items allowed in the Deque."""

        return self.__maxsize

    def empty(self):
        """Return True if the Deque is empty, False otherwise."""

        return not self.__deque

    def full(self):
        """
        Return True if there are maxsize items in the Deque.

        Note: if the Deque was initialized with maxsize=0 (the default), then full() is never True.
        """

        if self.__maxsize <= 0:
            return False

        else:
            return self.size() >= self.__maxsize

    async def __wake_up_on_free_slot(self) -> None:
        while self.full():
            putter = self.__loop.create_future()

            self.__putters.append(putter)

            try:
                await putter

            except Exception:
                putter.cancel()  # Just in case putter is not done yet.

                try:
                    # Clean self._putters from canceled putters.
                    self.__putters.remove(putter)

                except ValueError:
                    # The putter could be removed from self._putters by a
                    # previous get_nowait call.
                    pass

                if not self.full() and not putter.cancelled():
                    # We were woken up by get_nowait(), but can't take
                    # the call.  Wake up the next in line.
                    self.__wakeup_next(self.__putters)

                raise

    async def __wake_up_on_available_item(self) -> Any:
        while self.empty():
            getter = self.__loop.create_future()

            self.__getters.append(getter)

            try:
                await getter

            except Exception:
                getter.cancel()  # Just in case getter is not done yet.

                try:
                    # Clean self._getters from canceled getters.
                    self.__getters.remove(getter)

                except ValueError:
                    # The getter could be removed from self._getters by a
                    # previous put_nowait call.
                    pass

                if not self.empty() and not getter.cancelled():
                    # We were woken up by put_nowait(), but can't take
                    # the call.  Wake up the next in line.
                    self.__wakeup_next(self.__getters)

                raise

    def __check_full(self) -> None:
        if self.full():
            raise DequeFull

    def __check_empty(self) -> None:
        if self.empty():
            raise DequeEmpty

    async def put(self, item):
        """
        Put an item at the back of the Deque.

        If the Deque is full, wait until a free slot is available before adding item.
        """

        await self.__wake_up_on_free_slot()

        return self.put_nowait(item)

    def put_nowait(self, item):
        """
        Put an item at the back of the Deque without blocking.

        If no free slot is immediately available, raise DequeFull.
        """

        self.__check_full()

        self.__deque.append(item)

        self.__unfinished_tasks += 1

        self.__finished.clear()

        self.__wakeup_next(self.__getters)

    async def get(self):
        """
        Remove and return an item from the front of the Deque.

        If Deque is empty, wait until an item is available.
        """

        await self.__wake_up_on_available_item()

        return self.get_nowait()

    def get_nowait(self):
        """
        Remove and return an item from the front of the Deque.

        Return an item if one is immediately available, else raise DequeEmpty.
        """

        self.__check_empty()

        item = self.__deque.popleft()

        self.__wakeup_next(self.__putters)

        return item

    async def put_left(self, item):
        """
        Put an item at the front of the Deque.

        If the Deque is full, wait until a free slot is available before adding item.
        """

        await self.__wake_up_on_free_slot()

        return self.put_left_nowait(item)

    def put_left_nowait(self, item):
        """
        Put an item at the front of the Deque without blocking.

        If no free slot is immediately available, raise DequeFull.
        """

        self.__check_full()

        self.__deque.appendleft(item)

        self.__unfinished_tasks += 1

        self.__finished.clear()

        self.__wakeup_next(self.__getters)

    async def get_right(self):
        """
        Remove and return an item from the back of the Deque.

        If Deque is empty, wait until an item is available.
        """

        await self.__wake_up_on_available_item()

        return self.get_right_nowait()

    def get_right_nowait(self):
        """
        Remove and return an item from the back of the Deque.

        Return an item if one is immediately available, else raise DequeEmpty.
        """
        self.__check_empty()

        item = self.__deque.pop()

        self.__wakeup_next(self.__putters)

        return item

    def task_done(self):
        """
        Indicate that a formerly enqueued task is complete.

        Used by queue consumers. For each get() used to fetch a task, a subsequent call to task_done() tells the queue
        that the processing on the task is complete.

        If a join() is currently blocking, it will resume when all items have been processed (meaning that a task_done()
        call was received for every item that had been put() into the queue).

        Raises ValueError if called more times than there were items placed in the queue.
        """

        if self.__unfinished_tasks <= 0:
            raise ValueError('task_done() called too many times')

        self.__unfinished_tasks -= 1

        if self.__unfinished_tasks == 0:
            self.__finished.set()

    async def join(self):
        """
        Block until all items in the queue have been gotten and processed.

        The count of unfinished tasks goes up whenever an item is added to the Deque. The count goes down whenever a
        consumer calls task_done() to indicate that the item was retrieved and all work on it is complete. When the
        count of unfinished tasks drops to zero, join() unblocks.
        """

        if self.__unfinished_tasks > 0:
            await self.__finished.wait()

