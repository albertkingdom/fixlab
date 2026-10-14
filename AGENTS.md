# AGENTS.md — fixlab

給在此專案工作的 AI 工具與人類閱讀。先讀這份，再動手。語言：文件用繁體中文，程式碼與識別字用英文。

## 1. 專案目的

做一個**教學導向的最小 CLI coding agent**，專門修多檔小型專案裡的 bug：

> `fixlab fix ./某個有 bug 的 repo` → agent 自己找出 bug 在哪個檔案、讀懂相關程式、局部修改、用測試驗證。

並附上 telemetry 與 bug benchmark，量化它的表現（隱藏測試通過、弄壞既有行為、假通過、沒驗證卻宣稱完成、步數、成本）。

### 與 code-agent-eval 的關係
`../code-agent-eval` 是評測實驗：單檔函式題，agent 是受測對象，量「只用可見測試自我驗證可不可信」。
fixlab 是能實際使用的工具，沿用它的評測方法（可見／隱藏測試、假通過）與部分程式（迴圈、tool call 解析、沙箱）。
沙箱寫法最初參考 KeSi（github.com/kaochenlong/KeSi，MIT）；沿用須註明來源。

### 為什麼做（JD 對應）
華邦電子「軟體類 AI 應用工程師（竹北）」，104 職缺 `94ndv`：

| JD | fixlab 的對應 |
|---|---|
| Tool-use Agent、Coding Copilot（工作 3） | 多檔修 bug 的 agent 迴圈與工具 |
| CLI AI Assistant、Developer Productivity Tool（工作 8、加分 3） | 互動式 CLI 與一次性 `fix` 指令 |
| 評估、Telemetry、實驗框架、AI Evaluation Framework（工作 5、加分 1） | 事件記錄、彙整報告、bug benchmark |
| 程式碼生成的自動化驗證（工作 6） | 可抽換的 verifier（pytest） |
| 開源模型與推論框架（加分 2） | Ollama／OpenRouter 上的 Qwen、Gemma 對商用模型 |
| Prompt／Context Engineering（加分 1） | system prompt 規則消融、tool output 截斷 |
| Agent Workflow／Multi-Agent、平台 Connector（工作 2、8） | 後期選做 |

### 定位（面試時怎麼說）
- 可以說：「我實作了 CLI coding agent，並用自建的多檔 bug benchmark 量測驗證回饋、假通過與成本。」
- 不可以說：做了 Claude Code／商用 Copilot；有 EDA／Verilog／RTL 經驗（沒有，且本專案不做）。

## 2. Agent 的定義
「誰決定下一步」才是 agent 與 workflow 的差別。LLM 自己決定先做什麼、何時完成；程式只設保險（步數上限、連續失敗上限）。不得退化成寫死流程。

## 3. 範圍
- 工具：`read_file`（行號）、`list_files`、`glob`、`grep`、`edit_file`、`write_file`、`run_tests`（七個）。**不提供任意 shell**；之後若要加，需先有白名單與確認機制。
- 安全：路徑限制在工作目錄、測試檔不可改（整組測試檔算指紋）、macOS 沙箱（禁網路）、傳給子行程的環境變數要清理。
- Telemetry：每步事件寫 JSONL（模型版本、runtime、context 長度、token、延遲、工具、結果、是否撞步數上限／被截斷／改測試）。
- Benchmark：自寫 15–20 題多檔 Python bug（跨檔、斷言不透露原因、有干擾檔）；隱藏測試分「要修好」與「不能壞掉」兩組。
- 實驗：有／無 `run_tests` 兩組，system prompt 一致，只差工具。

### 非目標
Verilog／EDA、SWE-bench 與真實大型 repo（需 Docker、小模型成功率低）、Web UI、記憶、微調。

## 4. 階段
1. **骨架與規格**：Spectra 規格；從 code-agent-eval 搬迴圈、解析、沙箱。（tag `stage-1`）
2. **CLI 與 telemetry**：互動模式、權限提示、事件記錄。（`stage-2`）
3. **Benchmark 與實驗**：題目、評分、跑兩個以上模型、寫結果。（`stage-3`）
4. **選做**：多 agent 對照（單 agent 對 修復者＋審查者）；Connector（MCP 或 GitHub issue）二選一。（`stage-4`）

## 5. 工作守則
1. 先寫規格（Spectra）再實作；每個階段一個變更提案。
2. 隱藏測試與 agent 工作目錄隔離，要有自我檢查測試。
3. 每次實驗記錄：模型名稱與版本、量化、runtime 與版本、context 長度、題目子集、隨機種子、日期。
4. 不為了讓數字好看而調整題目或切分；任何調整寫入結果報告。不編造結果。
5. 引用外部數字註明來源與日期。
6. 版控：commit 訊息不提 AI 工具、不加 Co-Authored-By；Conventional Commits、英文。
   - 新功能一律從 `main` 開新分支，命名 `feature/{feature-name}`，不直接 commit 到 `main`。
   - 實作前要有完成的 Spectra 提案（`/spectra-propose`）。
   - 合併前更新 `README.md` 反映新功能。
   - 開 PR 前必須完成 code review，所有 blocking 與 important 的問題都要解決。
   - review 發現的問題依 `review-findings` skill（`.claude/skills/review-findings/`）處理。
7. **原創性**：不得複製他人專案的程式碼或題目結構（包含範例專案、bug 類型、檔案配置）。每個設計決定的依據必須是自己的實驗、自己程式的已知缺陷，或 Claude Code 的實際行為；外部文章只當參考，並在 README 與 `docs/spectra` 的設計文件註明讀過什麼、採用了哪個想法。

## 6. 參考來源（只是參考，不是設計依據）
- 高見龍 KeSi 連載：<https://kaochenlong.com/build-your-own-claude-code>。讀過 Day 11–18。影響到的想法：連續失敗只算「整輪全失敗」、環境變數洩漏是風險、重視 token 與成本量測、沙箱的風險清單。程式 repo 網址與授權查不到；沙箱寫法在 code-agent-eval 的註解標為參考 KeSi（MIT），沿用前要再核對。範例專案、bug 類型、檔案結構、規格與測試都是自己設計。
- 前身專案：`../code-agent-eval`（自己的程式與試跑結果 docs/pilot-results.md）。
- Claude Code 的工具行為（Edit 的唯一字串替換、Write 覆寫前需先讀過）。
