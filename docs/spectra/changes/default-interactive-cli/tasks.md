## 1. 預設互動入口

- [x] 1.1 實作「在 main 統一解析預設模式」與 Interactive mode is entered with -i 契約：省略 PATH 使用目前目錄，省略 PATH 與 --task 時互動；新增假 client 測試驗證 prompt、工作目錄、無模型請求與 telemetry，並保留 PATH 一次性行為；--task 缺 PATH 時拒絕。

## 2. 文件與驗證

- [x] 2.1 [after: 1.1] 更新 README.md 與 docs/local-cli-setup.md，列出裸 fixlab 與相容入口；內容審查確認安裝、設定與模式說明一致。
- [x] 2.2 [after: 2.1] 執行完整 pytest，從專案外以全域 fixlab 加 EOF 驗證預設互動與結束碼，完成 diff 自我審查並記錄結果。

## 驗證紀錄

以下前五項是第一次提交（85025fb）之前、工作樹上的驗證結果：

- 2026-10-20：spectra analyze 無 findings，spectra validate 通過。
- 外層沙箱禁止 sandbox-exec，取得權限後在沙箱外重跑完整 pytest：555 passed。
- 追加兩個互動參數組合後，定向重跑 omitted_path 測試：5 passed, 52 deselected。
- 從 /private/tmp 的專案目錄透過 PATH 的 fixlab 與 .venv/bin/fixlab 啟動，EOF 正常結束（exit 0）；prompt、目標目錄、interactive telemetry 正確，沒有 task_start 或模型呼叫。驗證事件檔放在暫存 HOME，未寫入使用者的正式事件目錄。
- 已審查本次 CLI、測試、文件與規格差異，無阻擋或重要問題；git diff --check 通過。保留原有未提交文件內容，當時尚未 commit、未歸檔。
- 2026-10-20 code review 兩輪修正後（9a8bd73）：完整 pytest 559 passed；spectra validate 通過。新增或修改的測試都先確認修正前會失敗。
