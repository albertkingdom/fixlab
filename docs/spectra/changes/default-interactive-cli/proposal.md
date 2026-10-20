## Why

本機已有可從任何目錄呼叫的啟動器，但 CLI 強制輸入 PATH 與 -i，讓進入目前專案的互動模式需要多餘參數。直接輸入 fixlab 即可開始，對應 JD 的 CLI AI Assistant 與 Developer Productivity Tool。

## What Changes

- 未提供 PATH 時使用目前工作目錄；未提供 PATH 與 --task 時預設進入互動模式。
- 保留 fixlab PATH 的一次性模式、-i 的明確互動模式；--task 可搭配省略 PATH 執行一次性任務。
- 更新說明與回歸測試，驗證本機既有啟動器可從專案外啟動。

## Capabilities

### New Capabilities

無。

### Modified Capabilities

- `interactive-session`: 增加目前目錄的預設互動入口，保留明確指定模式的相容性。

## Impact

影響 fixlab/cli.py、tests/test_cli.py、tests/test_interactive.py、README.md 與 docs/local-cli-setup.md。無新增依賴；不修改全域啟動器、模型設定或 agent 迴圈。
