"""七個工具的實作與登記入口。

各工具在自己的任務裡加進來。CLI 與測試都呼叫 register_tools()，所以工具清單只在這裡有一份。
"""

from fixlab.workspace import Workspace


def register_tools(ws: Workspace) -> None:
    """把所有工具登記到 ws。目前還沒有工具，之後每個工具的任務各加一行 ws.register(...)。"""
