"""事件檔：把每次執行寫成一個 JSON Lines 檔（一行一個 JSON 物件），給階段 3 的統計腳本讀。

每次執行建立自己的資料夾，永遠不覆寫、不附加到舊檔；每一行寫完立刻 flush，程式被殺掉也只少最後一行。
記錄只是旁路：寫不進去（磁碟滿、沒有權限）只警告一次，之後略過，不能害修 bug 的主流程失敗。
這個模組只管「怎麼寫」；每種事件要放哪些欄位，由入口（cli.py）決定。
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def default_log_dir() -> Path:
    # 放在家目錄，不放進被修的目錄：不然快照 diff 會看到它，模型與被測的程式也碰得到自己的紀錄。
    return Path.home() / ".fixlab" / "runs"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(moment: datetime) -> str:
    """2026-10-18T09:30:05.123Z：UTC、毫秒、結尾 Z。"""
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def make_unique_directory(parent: Path, name: str) -> Path:
    """在 parent 底下建立名叫 name 的新資料夾；名字被用掉了就試 name-2、name-3……"""
    number = 1
    while True:
        candidate = parent / (name if number == 1 else f"{name}-{number}")
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            number += 1


class EventLog:
    def __init__(self, log_dir, model: str, now=utc_now):
        """now 是取得目前時間的函式，測試用固定的時間取代它。"""
        self.now = now
        self.path = None  # 建立失敗時維持 None
        self._file = None
        self._broken = False  # 壞掉之後的 write 一律略過

        # 模型名稱常含斜線（qwen/qwen3.5-9b），資料夾名稱只留字母、數字、點、底線、減號
        safe_model = re.sub(r"[^A-Za-z0-9._-]", "-", model)
        name = self.now().strftime("%Y%m%dT%H%M%SZ") + "-" + safe_model
        try:
            directory = make_unique_directory(Path(log_dir), name)
            self.path = directory / "events.jsonl"
            self._file = open(self.path, "w", encoding="utf-8")
        except OSError as error:
            self._stop(f"cannot create it ({error})")

    def write(self, event: str, **fields) -> None:
        if self._broken:
            return
        record = {"event": event, "ts": format_timestamp(self.now()), **fields}
        # default=str：Path 之類不是 JSON 型別的值寫成文字，不讓一個欄位弄壞整個執行
        line = json.dumps(record, ensure_ascii=False, default=str)
        try:
            self._file.write(line + "\n")
            self._file.flush()
        except OSError as error:
            self._stop(f"write failed ({error})")

    def close(self) -> None:
        if self._file is not None:
            self._file.close()

    def _stop(self, reason: str) -> None:
        """停止記錄，只警告這一次。"""
        self._broken = True
        print(f"fixlab: warning: the event log is unavailable, {reason}; the run continues without it", file=sys.stderr)
