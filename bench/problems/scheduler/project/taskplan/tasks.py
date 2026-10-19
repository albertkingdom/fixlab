"""任務。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    name: str
    priority: int
    due: int
