"""工作目錄與工具分派。

Workspace 只認一個根目錄。工具傳進來的路徑一律先過 resolve_inside()，必須落在根目錄內；
call() 依名稱分派工具，永遠回傳 ToolResult、不拋例外，模型給怪參數時 loop 才不會崩潰。
錯誤分兩類：路徑逃逸（PathBlocked）設 blocked 旗標，其餘（ToolError、OSError）只是 ok=False。
tool_specs() 與 schemas() 是登記表的兩個唯讀視圖，分別給模型看與給 toolparse 驗證，清單只有一份。
走訪檔案的工具（list_files、glob、grep、測試檔指紋）共用 SKIP_DIRS 與 iter_files()。
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# 走訪時跳過的目錄。list_files、glob、grep、測試檔指紋掃描與 CLI 的複製都用同一份，
# 各自維護的話，改一處就會漏掉另一處。
SKIP_DIRS = frozenset({".git", ".venv", "__pycache__", ".pytest_cache"})

# schema 的 JSON 型別名稱 → Python 型別。bool 是 int 的子類別，整數檢查要另外排除。
_JSON_TYPES = {"string": str, "integer": int, "boolean": bool}


def iter_files(folder: Path):
    """走訪 folder 底下所有一般檔案，跳過 SKIP_DIRS，不跟隨也不列出符號連結。順序不保證，要排序請自己排。"""
    for entry in folder.iterdir():
        # 這些工具在沙箱外以 Python 行程執行；工作目錄裡放一個指向外面的連結，就能讓它們讀到目錄外的內容。
        if entry.is_symlink():
            continue
        if entry.is_dir():
            if entry.name not in SKIP_DIRS:
                yield from iter_files(entry)  # 子資料夾的檔案由同一個函式產生，原樣轉吐出去
        else:
            yield entry


class ToolError(Exception):
    """一般的工具錯誤（找不到檔案、參數不對等）；訊息會回給模型，不設 blocked。"""


class PathBlocked(ToolError):
    """路徑逃逸：絕對路徑、~、跑出工作目錄、符號連結指向外面。會設 blocked 旗標。"""


@dataclass
class ToolResult:
    output: str
    ok: bool
    flags: dict = field(default_factory=dict)  # 例如 {"blocked": True}、之後的 {"tests_passed": True}


@dataclass
class Tool:
    func: Callable[..., ToolResult]
    schema: dict  # {"properties": {名稱: {"type": ...}}, "required": [...]}，與 toolparse 的 tool_schemas 同形
    description: str = ""  # 給模型看的用途說明


class Workspace:
    def __init__(self, root: Path, python: str = sys.executable):
        self.root = Path(root).resolve()  # 先解析一次，之後的路徑都跟它比
        self.python = python  # run_tests 用哪個直譯器；不 resolve，venv 的 python 是符號連結，解析後會找不到套件
        self._tools: dict[str, Tool] = {}
        # 模型「整檔、未截斷」讀過的檔案（解析後的真實路徑）。write_file 覆寫既有檔案前要查它，
        # 避免模型憑空改寫沒看過的內容；edit_file 成功後會把該檔移除。
        self.files_read: set[Path] = set()

    def register(self, name: str, func: Callable[..., ToolResult], schema: dict, description: str = "") -> None:
        self._tools[name] = Tool(func, schema, description)

    def tool_specs(self) -> list[dict]:
        """送給模型的工具清單（OpenAI 格式）。"""
        # schema 裡不存 "type": "object"，在這裡統一補上，之後每個工具和測試的假工具就不會漏寫。
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": {"type": "object", **tool.schema},
                },
            }
            for name, tool in self._tools.items()
        ]

    def schemas(self) -> dict[str, dict]:
        """給 toolparse.parse_message 驗證用的 {工具名稱: schema}。"""
        return {name: tool.schema for name, tool in self._tools.items()}

    def resolve_inside(self, rel: str) -> Path:
        """把相對路徑解析成工作目錄內的真實路徑；不合規就 raise。"""
        if not isinstance(rel, str) or not rel.strip():
            raise ToolError("path must be a non-empty string")
        if os.path.isabs(rel) or rel.startswith("~"):
            raise PathBlocked(f"absolute paths are not allowed: {rel!r}")
        # resolve() 會展開 ../ 並跟隨符號連結，所以 sub/../../x 與指向外面的連結在這裡都會被抓到
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise PathBlocked(f"path is outside the working directory: {rel!r}")
        return p

    def _check_args(self, name: str, tool: Tool, args: dict) -> None:
        props = tool.schema.get("properties", {})
        missing = [p for p in tool.schema.get("required", []) if p not in args]
        if missing:
            raise ToolError(f"{name}: missing required argument(s) {missing}")
        extra = [k for k in args if k not in props]
        if extra:
            raise ToolError(f"{name}: unexpected argument(s) {extra}")
        for key, value in args.items():
            expected = _JSON_TYPES.get(props[key].get("type"))
            bad_int = expected is int and isinstance(value, bool)
            if expected is not None and (not isinstance(value, expected) or bad_int):
                raise ToolError(f"{name}: argument {key!r} must be a {props[key]['type']}, got {type(value).__name__}")

    def call(self, name: str, args: dict) -> ToolResult:
        """執行一個工具呼叫。永遠不拋例外：任何錯誤都變成 ok=False 的 ToolResult。"""
        try:
            tool = self._tools.get(name)
            if tool is None:
                raise ToolError(f"unknown tool: {name!r}")
            self._check_args(name, tool, args)
            return tool.func(**args)
        except PathBlocked as e:
            return ToolResult(f"error: {e}", False, {"blocked": True})
        except ToolError as e:
            return ToolResult(f"error: {e}", False)
        except OSError as e:
            return ToolResult(f"error: {e}", False)
