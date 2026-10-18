"""活動。end 是最後一天，含在活動裡。"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Event:
    name: str
    start: date
    end: date
