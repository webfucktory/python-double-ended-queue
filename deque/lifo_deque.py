from typing import Any

from deque import Deque


class LifoDeque(Deque):
    def get(self) -> Any:
        return self.get_right()

    def get_nowait(self) -> Any:
        return self.get_right_nowait()

    def put(self, item: Any) -> None:
        self.put_right(item)

    def put_nowait(self, item: Any) -> None:
        self.put_right_nowait(item)
