## 1. 專案骨架與範例專案

- [x] 1.1 只建骨架，不搬任何模組：依「複製自己的程式並整理，不做共用套件」，之後每個模組在自己的任務裡從 code-agent-eval 複製並加上 2–5 行繁體中文的模組開頭說明。pyproject.toml 宣告 openai、regex、pytest，並設 `norecursedirs = ["tests/fixtures"]`，建立 .venv 與空的 fixlab 套件。驗證：在 .venv 內 `python -c "import fixlab, regex"` 成功，`pytest --collect-only` 退出碼為 5（沒有測試）且不報錯。
- [x] 1.2 寫 tests/fixtures/timelog 小專案（工時紀錄解析）：timelog/parser.py 的 parse_duration 用 `re.match(r"(\d+)([hm])", text)` 只取第一個單位，使 "1h30m" 變成 60 分鐘；timelog/report.py 的 weekly_total 呼叫它並換算小時；干擾檔 timelog/formatting.py 與 timelog/test_formatting.py；失敗的測試在 tests/test_report.py，斷言訊息只寫 "3.75 != 4.25"，不透露原因。驗證：tests/test_fixture.py 把它複製到暫存目錄跑 pytest，未修時恰好 1 個失敗；只改 parser.py 的那一個運算式後全數通過；並確認 fixlab 根目錄的 `pytest --collect-only` 不收集 tests/fixtures。

## 2. tool call 解析

- [ ] 2.1 從 code-agent-eval 複製 toolparse 成 fixlab/toolparse.py 並依 specs 補測試：Native tool calls take precedence、Fallback parsing from reply text、Calls are validated against tool schemas（含 bash 被當成未知工具）、Broken call attempts are errors, not silence 四個需求的所有情境。驗證：tests/test_toolparse.py 逐情境對應一個測試函式，全數通過。

## 3. 七個工具（先不含沙箱）

- [ ] 3.1 實作 Workspace 的路徑解析與分派：依「工作目錄就是 repo 根目錄，任務文字由呼叫端傳入」的 Workspace 介面，加上 Paths stay inside the workspace 與 Tool errors never crash the loop，以及「blocked 旗標只留給路徑逃逸與受保護檔案」：../、sub/../../、絕對路徑、~ 開頭、符號連結逃逸都回 ok=false 並設 blocked；找不到檔案只回 ok=false 不設 blocked；未知工具 bash 與 old_string 傳數字都回 ok=false 而不是例外。驗證：tests/test_isolation.py 路徑表六列加 "Other errors are not blocked" 情境；tests/test_tools.py 未知工具與錯誤型別兩情境。
- [ ] 3.2 實作 read_file：依「輸出一律有上限，格式固定」，read_file returns numbered lines 用 splitlines、6 位右對齊行號加 tab、行範圍、空檔回 "(empty file)"、超過 20000 字元截斷並註明總量，整檔且未截斷的讀取記進 Workspace 的 files_read。驗證：tests/test_tools.py 的整檔（含結尾換行）、行範圍、空檔、缺檔四個情境加一個截斷測試。
- [ ] 3.3 實作 list_files 與 glob：依「遍歷工具不跟隨符號連結，跳過清單共用」，list_files shows the project layout 與 glob finds files by name pattern 遞迴、依完整相對路徑字串排序、跳過 .git、.venv、__pycache__、.pytest_cache、不列出符號連結、上限 200 並註明省略數量，glob 無符合回 "no files matched"。驗證：tests/test_tools.py 的小專案排序、250 檔上限、符號連結、`**/test_*.py`、無符合五個情境。
- [ ] 3.4 實作 grep：依「grep 自己實作，單行比對用 regex 套件加逾時」，grep searches file contents 輸出 路徑:行號:內容、單行只比對前 2000 字元、單行 1 秒與整體 5 秒的時間上限、不跟隨符號連結、上限 100 行、無效正規表示式回 ok=false。驗證：tests/test_tools.py 的找定義、無效 pattern、120 筆只回 100 行、`(a+)+$` 在 5 秒內回 "pattern too slow"、符號連結不被讀取五個情境。
- [ ] 3.5 實作 edit_file：依「edit_file 用「唯一出現的原字串」替換」，edit_file replaces one unique string 只在恰好出現一次時替換，0 次或多次都不改檔並回報實際次數，成功後把該檔從 files_read 移除。驗證：tests/test_tools.py 的唯一、2 次、0 次三個情境。
- [ ] 3.6 實作 write_file：依「write_file 覆寫既有檔案前必須先讀過」，write_file creates files and guards overwrites 新檔直接建立（含父目錄），覆寫既有檔需在 files_read 中，成功後記錄該檔，失敗的讀取不記錄。驗證：tests/test_tools.py 的建立新檔、未讀就覆寫、整檔讀後覆寫、部分讀取不算、截斷讀取不算、edit 後讀取過期六個情境。
- [ ] 3.7 實作 run_tests（先不套沙箱）：依「run_tests 的 pytest 指令固定，不讀專案外的設定」，run_tests runs pytest in the workspace 以固定指令執行、target 以 `--` 隔開且必須在工作目錄內、輸出上限 4000 字元、逾時 10 秒、測試失敗時 ok=true、旗標含 tests_passed 與 timed_out、不留下 .pytest_cache。驗證：tests/test_tools.py 用 timelog fixture 的失敗、指定單一測試檔、`--version` 當 target、target 在工作目錄外、無窮迴圈逾時、無快取目錄六個情境。

## 4. 隔離與沙箱

- [ ] 4.1 實作受保護路徑判定並接上 edit_file 與 write_file：依「測試檔以規則判定，路徑相對於工作目錄，指紋涵蓋整組」，Test files cannot be written 以相對工作目錄的路徑判定，涵蓋名稱規則與 tests、test 目錄，tests.py 刻意不受保護；寫入被擋時設 blocked。驗證：tests/test_isolation.py 對 write_file 與 edit_file 各跑完整的十列表格，另加「workspace 位於 /project/tests/fixtures/timelog 下，timelog/parser.py 仍可編輯」情境。
- [ ] 4.2 實作整組測試檔指紋：Tampering with test files is detected，建立時用共用跳過清單掃描並算 sha256，run_tests 後比對，修改、新增、刪除都設 test_file_tampered。驗證：tests/test_isolation.py 的改檔、沒變、刪檔、`__pycache__` 的 .pyc 不算四個情境。
- [ ] 4.3 實作子行程環境變數白名單：依「子行程環境變數用白名單」，Child processes get a minimal environment 只傳 PATH、LANG、LC_ALL、TMPDIR 與 PYTHONDONTWRITEBYTECODE=1，python 路徑不 resolve。驗證：tests/test_isolation.py 設 OPENROUTER_API_KEY 為 "sk-test-123" 後被測程式印出環境不含金鑰與名稱；LANG 能傳過去。
- [ ] 4.4 實作 fixlab/sandbox.py 的基本規則：依「沙箱：禁網路、限制讀寫範圍、測試檔不可寫」，Tests run in a sandbox 的禁網路、家目錄、專案與 deny_read 目錄不可讀（所有 deny 規則寫在放行工作目錄與 .venv 的 allow 之前）、只能寫工作目錄與 /dev、路徑一律用 -D 參數且規則文字不含字面路徑，並套到 run_tests。驗證：tests/test_isolation.py 的網路、讀取表格七列（含家目錄裡的假金鑰檔與 ~/.ssh 列表，假金鑰檔由測試建立在家目錄的暫存子目錄並在結束時刪除）、家目錄寫入、規則文字無字面路徑（含家目錄路徑）四組測試（僅 macOS，其他平台標記 skip）。
- [ ] 4.5 實作沙箱的受保護路徑規則：以 string-append 加跳脫過的 WS_RE 參數，在 OS 層擋住受保護檔案寫入、tests 或 test 目錄改名與搬移，並支援 workspace 位於專案目錄內。驗證：tests/test_isolation.py 的覆寫 tests/test_report.py、新建 tests/new_helper.py、改名 tests 目錄、workspace 名為 "a+b(c)"、workspace 在專案目錄內讀寫三個結果五個情境，且 run_tests 在 tests/fixtures/timelog 就地執行不再出現 pyproject.toml 的 PermissionError。

## 5. Agent 迴圈

- [ ] 5.1 從 code-agent-eval 複製 loop 成 fixlab/loop.py 的核心四步並改接任務文字：Task text is the first user message 與 Model decides the next step and when to stop，移除單次模式與題目訊息組裝。驗證：tests/test_loop.py 以假模型跑「讀、改、跑測試、結束」四步得到 stop reason done，並檢查第一則 user 訊息等於任務文字。
- [ ] 5.2 實作步數上限：依「預設步數上限提高到 20，並新增連續失敗上限 3」，Step budget is a safety net 預設 20、可由參數覆寫。驗證：tests/test_loop.py 的 max_steps=3 與預設 20 兩個情境。
- [ ] 5.3 實作連續失敗保險：Consecutive failing rounds stop the loop，有執行且全失敗才累計、沒執行工具的回合不動計數、blocked 算失敗、run_tests 測試失敗不算失敗、第 3 次以 stuck 結束並記 stuck_failures。驗證：tests/test_loop.py 的三輪全失敗、成功後歸零、混合輪、無效回覆夾在中間、blocked 三次、測試失敗三次六個情境。
- [ ] 5.4 複製回覆異常處理與重試：Invalid replies become feedback, not completion（缺參數、空回覆、被截斷）、Text-mode calls execute one at a time、Transient provider errors are retried, timeouts are not。驗證：tests/test_loop.py 對應的六個情境，重試延遲在測試中設為 0。
- [ ] 5.5 保留 trace 回呼：依「保留 trace 回呼，不在階段 1 決定 telemetry 格式」，Every step is traced 每個回覆一筆紀錄、參數與輸出超過 2000 字元截斷。驗證：tests/test_loop.py 的 read_file 步驟紀錄檢查，加一筆過長輸出被截斷的檢查。
- [ ] 5.6 建立黃金 trace 測試：用假模型跑完 timelog 修復流程，把 trace 存成 tests/golden/trace_golden.json 當行為基準，沿用 code-agent-eval 的 _normalize 輔助函式去除耗時與呼叫 id，避免測試不穩。驗證：tests/test_trace_golden.py 連跑 3 次都通過，且故意改一個工具輸出格式時會失敗（手動確認一次）。

## 6. 文件、smoke 與收尾

- [ ] 6.1 寫 scripts/smoke_fix.py：把 timelog fixture 複製到暫存目錄，用環境變數指定的 OpenAI 相容端點與模型跑一次 agent，印出 stop reason、步數、token 與每步工具名稱。驗證：用本機或 OpenRouter 的一個模型實際跑一次，修好 bug 且 tests_passed 為真（手動，結果貼進 README）。
- [ ] 6.2 更新 README.md、AGENTS.md 與 docs/spectra/config.yaml：README 寫讀程式順序（loop、toolparse、tools、workspace、sandbox）、七個工具的用途、一次真實 trace 的逐步註解與已知限制（硬連結、macOS only、sandbox-exec 已棄用、被測專案的第三方依賴）；依「設計依據與參考來源」列出參考來源與各自影響的決定；AGENTS.md 的工具清單補上 write_file、更新目錄結構，並與 config.yaml 一起加入「不得複製他人專案的程式碼或題目結構，參考來源要註明」。驗證：內容審閱，README 的指令照著做能跑起 pytest 與 smoke。
- [ ] 6.3 全部驗收後打 tag：在 .venv 內執行 `pytest` 全數通過、`spectra validate bootstrap-agent-core` 無錯誤後，commit 並建立 git tag stage-1。驗證：`git tag --list stage-1` 有輸出，且 tag 指向的 commit 上 pytest 通過。
