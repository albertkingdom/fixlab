## Why

fixlab 要做的是能實際修多檔 bug 的 CLI coding agent，但目前專案只有規劃文件，沒有任何程式。前身專案 code-agent-eval 已經驗證過 agent 迴圈、tool call 解析與沙箱，但它的工具只服務「單檔函式題」（一個 solution.py 加一個測試檔），不能在多檔專案裡找 bug、局部修改。階段 1 要先把可運作的核心打好，後面的 CLI、telemetry、benchmark 才有東西可以接。

## What Changes

- 建立 Python 專案骨架（套件 fixlab、pyproject.toml、pytest 測試目錄）。pyproject 設定 norecursedirs 排除 tests/fixtures，fixlab 自己的 pytest 才不會收集範例專案裡故意失敗的測試。
- 從自己的前身專案 code-agent-eval 逐模組搬入並整理三個核心：agent 迴圈、tool call 解析、工具與隔離。搬過來後拿掉單次生成模式與 LeetCode 式題目訊息，改成接受任意一段「任務文字」。
- 工具集從三個擴充為七個：read_file（輸出行號、可指定行範圍）、list_files、glob、grep、edit_file（唯一字串替換）、write_file（建立新檔；覆寫既有檔案前必須先整檔讀過）、run_tests（固定的 pytest 指令，不讀專案外的設定）。
- 隔離補強：受保護的測試檔改以「相對工作目錄的路徑」判定並涵蓋整組指紋；沙箱同時在作業系統層擋住測試檔寫入與測試目錄改名，並預設擋住讀取使用者家目錄（只放行工作目錄與虛擬環境）；子行程只拿白名單環境變數；遍歷類工具不跟隨符號連結；grep 單行比對加逾時防災難性回溯。
- 迴圈增加「連續整輪工具全失敗 3 次就停」的保險（新 stop reason stuck），步數上限預設從 8 提高到 20。
- blocked 旗標只保留給「路徑逃逸」與「寫入受保護檔案」，其他工具錯誤只是 ok=false。
- 加入一個自寫的小型範例專案 timelog（工時紀錄解析，bug 藏在 parser 的正規表示式，失敗的測試經由 report 呼叫它），用來測試工具與做一次真模型的手動 smoke run。
- 補上「設計依據與參考來源」：每個設計決定的依據寫成自己的實驗結果或 Claude Code 的行為；外部文章只列為參考來源，且 AGENTS.md 與 Spectra 設定加入「不得複製他人專案的程式碼或題目結構」。
- 實作順序採 MVP 優先：先做工具註冊、read_file、list_files、edit_file（含受保護路徑）、run_tests（含環境變數白名單）、迴圈核心與步數上限，加上 smoke 用的最小入口 `fixlab fix PATH`（在暫存複本上跑、印 diff、`--apply` 在三個條件都符合時才寫回），用真模型修一次 timelog；之後才補 glob、grep、write_file、指紋、沙箱與迴圈保險。
- 完成後打 git tag stage-1。

## Non-Goals

- 不做正式的 CLI、互動模式與權限提示（階段 2）；階段 1 只有 smoke 驗證用的最小入口 `fixlab fix`，不新增 spec 需求。
- 不做 telemetry 的檔案格式與彙整報告（階段 2）；迴圈只保留既有的 trace 回呼介面。
- 不做 benchmark 題庫與隱藏測試評分（階段 3）。
- 不提供任意 shell 或 run_command 工具；不提供 git 操作。
- 不做 Anthropic 格式轉接層，只支援 OpenAI 相容 API。
- 不做驗證器的抽換介面；階段 1 的驗證只有 pytest，直接寫在 run_tests 裡。
- 不使用 agent 框架；迴圈自己寫。
- 不追求跨平台：沙箱只支援 macOS 的 sandbox-exec。
- 不處理硬連結（hard link）逃逸，只在 README 列為已知限制。
- 不處理被測專案有自己的第三方依賴的情況（run_tests 使用 fixlab 自己的 venv）。
- 不支援不使用原生 tool_calls 的模型（例如 qwen2.5-coder:7b），也不做從回覆文字解析 JSON 的備援；支援的模型必須有原生 tool calling。

## Capabilities

### New Capabilities

- `agent-loop`: 由模型決定下一步與何時完成的迴圈；步數上限、連續失敗上限、暫時性錯誤重試、每步 trace。
- `tool-call-parsing`: 把模型回覆解析成合法的工具呼叫，只解析原生 tool_calls；文字裡的 JSON 一律視為純文字。
- `agent-tools`: 七個檔案與測試工具的行為與輸出格式（行號、截斷上限、唯一字串替換、先讀後寫、固定的 pytest 指令）。
- `workspace-isolation`: 路徑限制、測試檔保護與整組指紋、macOS 沙箱、子行程環境變數白名單。

### Modified Capabilities

(none)

## Impact

- Affected specs: agent-loop、tool-call-parsing、agent-tools、workspace-isolation（皆為新增）。
- Affected code:
  - New: pyproject.toml
  - New: fixlab/__init__.py
  - New: fixlab/loop.py
  - New: fixlab/toolparse.py
  - New: fixlab/tools.py
  - New: fixlab/workspace.py
  - New: fixlab/sandbox.py
  - New: tests/test_loop.py
  - New: tests/test_toolparse.py
  - New: tests/test_tools.py
  - New: tests/test_isolation.py
  - New: tests/test_fixture.py
  - New: tests/test_trace_golden.py
  - New: tests/golden/trace_golden.json
  - New: tests/fixtures/timelog/ （含跨檔 bug 的小專案）
  - New: fixlab/cli.py
  - New: tests/test_cli.py
  - Modified: README.md
  - Modified: AGENTS.md
  - Modified: docs/spectra/config.yaml
  - Removed: (none)
