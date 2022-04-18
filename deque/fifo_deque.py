from typing import Any

from deque import Deque


class FifoDeque(Deque):
    def get(self) -> Any:
        return self.get_left()

    def get_nowait(self) -> Any:
        return self.get_left_nowait()

    def put(self, item: Any) -> None:
        self.put_right(item)

    def put_nowait(self, item: Any) -> None:
        self.put_right_nowait(item)
