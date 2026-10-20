## Context

build_parser 目前要求 path；main 只依 -i 決定模式。本機全域啟動器已載入固定位置的 .env 並轉交參數，不會切換目錄。設計依據是本專案已確認的參數限制，無新增外部參考。

## Goals / Non-Goals

目標：只輸入 fixlab 即以目前目錄進入互動模式，保留明確 PATH 的一次性入口。
非目標：不變更 agent、權限提示、模型設定、全域安裝機制或 shell 設定；不新增任意 shell 工具。

## Decisions

### 在 main 統一解析預設模式

path 改為可省略，使用 None 區分是否明確提供；--task 同樣以 None 辨識是否明確提供，再還原 DEFAULT_TASK。main 在建立工作區、事件檔之前決定模式：-i 或省略 PATH 即為互動；有 PATH 而無 -i 為一次性；省略 PATH 卻給 --task 且無 -i 則拒絕（結束碼 2），因為一次性執行寫檔不會詢問，目標目錄必須明確指定。省略 PATH 一律設為目前目錄。這樣後續工作區、權限提示與 telemetry 共用同一個模式。替代方案是在全域啟動器補參數，但會讓套件與本機入口行為不一致；全面改為互動則會破壞既有 fixlab PATH 的一次性使用方式。

## Implementation Contract

- fixlab、fixlab --model m：目前目錄互動，出現 fixlab>，等待任務，不自動呼叫模型或跑測試。
- fixlab -i、fixlab PATH -i：互動；fixlab PATH：維持一次性；fixlab --task TEXT（無 PATH、無 -i）：拒絕並提示改用 fixlab PATH --task TEXT 或加 -i。-i 與 --task 同時提供時維持原行為，使用者輸入任務而非自動執行 --task。
- 缺模型、缺金鑰、無效 PATH 與事件檔位於目標內的檢查維持結束碼 2；省略 PATH 且目前目錄包住預設事件檔目錄（通常是在家目錄執行）時，改提示到專案目錄執行或指定 PATH，不建議改 --log-dir；EOF 與 /exit 正常結束。
- API 影響：僅 CLI path 與 --task 的省略規則；無 HTTP API 或函式簽名變更。
- 資料影響：無 schema、migration、seed 變更；run_start 的 mode 與 path 記錄實際執行模式與目錄。
- 安全規則：仍使用現有工作目錄限制、測試檔保護與互動權限提示；不讀取或輸出金鑰值。
- 驗收／測試策略：假 client 驗證預設互動入口、明確 -i、PATH 一次性、--task 缺 PATH 被拒、家目錄啟動的提示、輸入驗證與 telemetry；實際全域入口從暫存目錄以 EOF 啟動，確認 prompt、目標目錄與結束碼。全套 pytest 驗證相容性。

## Risks / Trade-offs

原本沒有 PATH 的命令會從參數錯誤變為等待輸入 → --help 清楚說明；非終端機 EOF 直接退出。
指定 PATH 仍預設一次性 → README 列出 fixlab、fixlab PATH -i、fixlab PATH 的差別。
code review 延後的意見（不改程式）：
- 在任何目錄打 fixlab 都以該目錄為工作區，讀檔工具不需確認 → 這是本變更的目的；寫檔與跑測試仍會詢問，家目錄啟動已改為明確拒絕。
- -i 與 --task 同時提供時 --task 文字被忽略且不提示 → 沿用變更前行為，README 已說明 -i 優先、任務由提示字元輸入。
- --task "" 會送出空任務 → 沿用變更前行為，不在本變更處理。
- 一次性模式的快照整個讀進記憶體、讀不到的檔案會中斷 → 既有 KNOWN-ISSUE（cli.py take_snapshot）；一次性模式現在必須明確給 PATH，不會因省略 PATH 而擴大範圍。

## Migration Plan

修改 editable 安裝所用的 CLI 原始碼，本機啟動器無須重裝。還原程式碼即可恢復原行為。

## Open Questions

無。
