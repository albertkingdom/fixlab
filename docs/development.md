# 開發與教學指南

[回到首頁](../README.md)

## 快速開始（開發用）

需要 Python 3.11 以上。以下指令從 fixlab 原始碼根目錄執行。clone 專案後以 editable 方式安裝，改了程式碼不必重裝：

```
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pytest                     # fixlab 自己的測試，約 30 秒
```

跑 agent 要有一個 OpenAI 相容的端點。三個環境變數（或用 `--model` 覆寫模型）：

```
export OPENAI_BASE_URL=https://openrouter.ai/api/v1   # 用 Ollama 就是 http://localhost:11434/v1
export OPENAI_API_KEY=...                              # Ollama 隨便填一個占位值
export FIXLAB_MODEL=qwen/qwen3.5-9b
```

想實際展示互動 CLI，可照 [Demo 操作手冊](cli-demo.md) 操作：修復工時報表、接續補說明、權限控制與查看事件紀錄。

然後對**範例專案的複本**執行（`fixlab` 會直接修改你指定的目錄）：

```
cp -R tests/fixtures/timelog /某個暫存目錄/timelog-try
.venv/bin/fixlab /某個暫存目錄/timelog-try
```

## 讀程式的順序

從入口與迴圈開始，再讀工具、安全限制與記錄，最後看 benchmark。每個檔案的開頭都有說明它在整體流程中的角色。

| 順序 | 檔案 | 做什麼 |
|---|---|---|
| 1 | `fixlab/cli.py` | 入口：檢查參數；一次性模式（拍快照、跑 agent、自己再跑一次測試、印結果）與互動模式（一次讀一行、保留對話、權限提示、中斷） |
| 2 | `fixlab/loop.py` | agent 迴圈：問模型 → 解讀回覆 → 執行工具；步數上限、連續失敗上限、重試、trace 回呼（每一步把這一步的紀錄交給它，畫面上的進度與事件檔都由它產生） |
| 3 | `fixlab/toolparse.py` | 把模型的回覆解析成工具呼叫：只認原生 `tool_calls`，參數對照 schema 驗證 |
| 4 | `fixlab/tools.py` | 六個工具的實作與登記 |
| 5 | `fixlab/workspace.py` | 工作目錄：路徑必須落在根目錄內、測試檔唯讀、工具分派、錯誤不丟例外 |
| 6 | `fixlab/sandbox.py` | 用 macOS `sandbox-exec` 包住 `run_tests`：禁網路、限制讀寫 |
| 7 | `fixlab/interpreter.py` | 選擇與檢查測試用 Python、驗證基底安裝目錄與符號連結，決定沙箱可放行的環境 |
| 8 | `fixlab/telemetry.py` | 事件檔：一次執行一個資料夾、一行一個 JSON、每行立刻寫入、寫不進去只警告 |
| 9 | `fixlab/display.py` | 互動模式的畫面：標題行、差異、結果行、用量行、顏色（只回傳字串，不直接印） |
| 10 | `fixlab/mcp_tools.py` | 選用的 MCP connector：讀設定檔、以官方 SDK 連 stdio server、把工具登記成 `mcp__<server>__<tool>`、轉換結果、關閉 server |
| 11 | `fixlab/bench/` | 階段 3：`problems.py`（題目載入與摘要）、`grader.py`（評分器）、`selfcheck.py`（題目自我檢查）、`runner.py`（實驗執行器）、`report.py`（報告）、`__main__.py`（上面四個指令） |

## 教學文章

在 [docs/articles/](articles/)。每篇對應一個 git tag，可以 `git checkout article-NN` 看到當時的程式。

| 篇 | 主題 |
|---|---|
| 01 | [模型說要呼叫工具，程式怎麼接住（tool call 與 Workspace）](articles/01-tool-calls-and-workspace.md) |
| 02 | [讓模型看得到專案（`read_file`、`list_files`）](articles/02-seeing-the-project.md) |
| 03 | [讓迴圈跑起來，`fixlab PATH` 與第一次真模型探索](articles/03-the-agent-loop.md) |
| 04 | [讓模型改檔案（`edit_file`）](articles/04-edit-file.md) |
| 05 | [讓模型跑測試（`run_tests`）](articles/05-run-tests.md) |
| 06 | [第一次完整的真模型修復](articles/06-first-full-repair.md) |
| 07 | [在檔案內容裡搜尋（`grep`）](articles/07-grep.md) |
| 08 | [建立與覆寫整個檔案（`write_file`）](articles/08-write-file.md) |
| 09 | [限制測試程式能做什麼（沙箱）](articles/09-sandbox.md) |
| 10 | [不讓測試檔被偷偷改掉（沙箱的受保護路徑，與兩輪 code review）](articles/10-protect-tests.md) |
| 11 | [模型卡住時要停下來（連續失敗保險，與迴圈的測試補齊）](articles/11-loop-safeguards.md) |
| 12 | [把每次執行存下來（事件檔）](articles/12-event-log.md) |
| 13 | [連續下指令（互動模式）](articles/13-interactive-session.md) |
| 14 | [改檔和跑測試之前先問你（權限提示）](articles/14-permissions.md) |
| 15 | [題目長什麼樣（8 道有 bug 的小專案）](articles/15-problems.md) |
| 16 | [評分器（修好、假通過、弄壞、無效）](articles/16-grader.md) |
| 17 | [題目自我檢查（怎麼證明題目量到想量的東西）](articles/17-self-check.md) |
| 18 | [實驗執行器（有 `run_tests` 對沒有）](articles/18-experiment-runner.md) |
| 19 | [第一次實驗結果，以及怎麼讀它](articles/19-first-results.md) |
| 20 | [Qwen 沒有測試時為什麼停不下來](articles/20-why-qwen-wont-stop.md)（量化、步數上限與 prompt 的後續實驗） |

## 規格與設計文件

用 Spectra 管理，在 [docs/spectra/](spectra/)：[specs/](spectra/specs/) 是行為規格，[changes/archive/](spectra/changes/archive/) 底下是每個階段的提案、設計（每個決定的替代方案與取捨，以及風險清單）和任務：階段 1 是 `bootstrap-agent-core`，階段 2 是 `stage2-cli-telemetry`，階段 3 是 `stage3-benchmark`（歸檔後的資料夾名稱前面有日期）。

## 參考來源

只是參考，不是設計依據：每個設計決定的依據是自己的實驗、自己程式的已知缺陷，或 Claude Code 的實際行為。以下是讀過什麼、採用了哪個想法（詳細的對照在設計文件〈設計依據與參考來源〉一節與各篇文章）。範例專案、bug 類型、檔案結構、規格與測試都是自己設計的。

**高見龍〈用 AI 打造自己的 Claude Code〉連載與 KeSi 專案**（<https://kaochenlong.com/build-your-own-claude-code>、<https://github.com/kaochenlong/KeSi>，MIT 授權，Copyright (c) 2026 Eddie Kao；讀過 Day 01–18 與 repo，2026-10-17 查證 LICENSE）

- 連續失敗只算「整輪全失敗」（第 11 篇）；步數上限 20 與失敗上限 3 的數字也相同，不能排除受他影響。
- 環境變數洩漏列為風險、重視 token 與成本量測、沙箱的風險清單。
- 〈讓 Agent 看見專案〉：空結果要明確回報，讓模型分得出「沒找到」與「沒執行成功」。他的 `list_files` 只列一層，這裡選遞迴。
- `kesi.py`（commit `dfa0cd0`）：`edit_file` 用 bytes 讀寫以保留換行字元、判斷唯一時把重疊的匹配也算進去；`write_file` 記讀的當下的 sha256、覆寫前比對；沙箱用 `(regex (string-append "^" (regex-quote (param …)) …))` 接路徑（他用來禁止讀、這裡用來禁止寫測試檔）、沙箱不可用時直接執行並顯示狀態。
- Day 13 示範：結束後印 diff、再跑一次測試、用「沒有 shell」對照；與這裡的快照 diff、結束後再跑一次測試、有／無 `run_tests` 實驗是相同的想法，不能排除受他影響。
- 〈用 ripgrep 搜尋程式碼〉讀過，`grep` 目前自己實作，尚未決定是否改用 `rg`。
- 沙箱規則（`fixlab/sandbox.py`）的結構參考 `sandbox_spec`，檔頭附有他的 MIT 授權全文。
- 階段 2（互動模式，第 13、14 篇）：設計時只看過他的 commit 標題與指令名稱，`/exit`、`/reset`、整個 session 一份對話、`y`／`a`／`N` 與「這個 session 都好」的想法與他相同，不能排除受他影響；完成後才讀了 `kesi.py` 的 `main`、`run_agent`、`check_permission`、`ask_user`、`seal_dangling_tool_use`。讀完**改了做法**的一項：Ctrl-C 從「整個任務丟掉」改成「保留已完成的部分並補上結果」。採用的畫面想法是縮排分層與每輪結束一行用量。不同的地方：他串流、顯示費用、授權範圍記在每個檔案與每個指令、有 `/permissions` 與 `/revoke`；我們顯示差異與結果行、授權範圍是整個工具、沒有串流與費用。他沒有事件記錄，所以事件檔（第 12 篇）沒有可參考的做法。

**Claude Code**（官方文件與實際行為，2026-10-17 查閱）

- `Edit` 的「唯一字串替換」與 `Write`「覆寫前需先讀過」：`edit_file`、`write_file` 的規則。
- 沙箱文件的「Protected paths」：「裁判用的東西，不能被受審的程式改寫」，這裡對應測試檔。
- `/diff` 與 `/rewind` 的快照：用快照回答「這一次改了什麼」。
- 寫檔與執行指令前問「這次允許、這個 session 一律允許、拒絕」三種：互動模式的 `y`／`a`／`N`（憑使用經驗，沒有重新查文件）。
