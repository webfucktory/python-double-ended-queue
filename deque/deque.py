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

        self.__wakeup_next(self.__getters)

    async def put_right(self, item):
        """
        Put an item at the back of the Deque.

        If the Deque is full, wait until a free slot is available before adding item.
        """

        await self.__wake_up_on_free_slot()

        return self.put_right_nowait(item)

    def put_right_nowait(self, item):
        """
        Put an item at the back of the Deque without blocking.

        If no free slot is immediately available, raise DequeFull.
        """

        self.__check_full()

        self.__deque.append(item)

        self.__wakeup_next(self.__getters)

    async def get_left(self):
        """
        Remove and return an item from the front of the Deque.

        If Deque is empty, wait until an item is available.
        """

        await self.__wake_up_on_available_item()

        return self.get_left_nowait()

    def get_left_nowait(self):
        """
        Remove and return an item from the front of the Deque.

        Return an item if one is immediately available, else raise DequeEmpty.
        """

        self.__check_empty()

        item = self.__deque.popleft()

        self.__wakeup_next(self.__putters)

        return item

    async def get_right(self):
        """
        Remove and return an item from the back of the Deque.

        If Deque is empty, wait until an item is available.
        """

        await self.__wake_up_on_available_item()

        return self.get_right_nowait()

    def get_right_nowait(self):
        """Remove and return an item from the back of the Deque.

        Return an item if one is immediately available, else raise DequeEmpty.
        """
        self.__check_empty()

        item = self.__deque.pop()

        self.__wakeup_next(self.__putters)

        return item
