## 1. fixlab 命令列選項

- [x] 1.1 「條件的差別只在模型看得到哪些工具」：Workspace 能隱藏工具，隱藏的工具不在給模型的工具清單與驗證回覆用的 schema 裡，但程式自己仍能呼叫；fixlab 新增 `--hide-tool NAME`（可重複），名稱不存在時以退出碼 2 結束且不建事件檔。對應 Tools can be hidden from the model 的四個情境（不被提供、模型亂叫被當成不認識的工具、結束時自己跑的最終測試照常、未知名稱）。驗證：tests/test_tools.py 與 tests/test_cli.py 各情境一個測試。
- [x] 1.2 「請求選項：temperature 與額外的請求參數」：fixlab 新增 `--temperature` 與 `--extra-body`（JSON 物件，原樣交給請求的 extra_body；不是物件或不是 JSON 以退出碼 2 結束且不建檔），並讓 run_start 多 hidden_tools、temperature、extra_body 三個欄位（沒傳是空陣列、null、null，schema 仍是 1）。對應 run_start records the request options and hidden tools 的四個情境。驗證：tests/test_cli.py 各情境一個測試，其中「temperature 進了每一次請求」用假 client 檢查收到的參數。

- [x] 1.3 「評分器在乾淨暫存目錄重跑，用原版測試與固定的 pytest 參數」要用的環境：run_tests 的測試子行程環境固定 TZ 為 UTC、PYTHONHASHSEED 為 0、PYTEST_DISABLE_PLUGIN_AUTOLOAD 為 1（加在 child_environment，agent 自己的測試執行也一樣）。對應 The test run environment is deterministic 的兩個情境。驗證：tests/test_tools.py：測試讀得到這三個值（不論父行程設什麼）、斷言 anyio 模組沒被匯入的測試會通過（anyio 的 pytest 外掛靠 entry point 註冊，自動載入時才會被匯入）。

## 2. 題目格式與載入

- [x] 2.1 「題目放在 bench 資料夾，每題一個資料夾，隱藏測試不進工作目錄」：fixlab/bench/problems.py 能載入並驗證題目資料夾與 problem.json（缺資料夾或缺鍵時丟出指名題目與缺項的錯誤）、為 agent 建立只含 project 內容的暫存工作目錄、計算題目的內容摘要（SHA-256，任何檔案改變摘要就改變）。對應 Each problem is a self-contained folder、Hidden tests and the solution never reach the agent、A problem has a content digest。驗證：tests/test_bench_problems.py 各情境一個測試（載入、缺項被拒、工作目錄不含 hidden 與 solution 與 problem.json、改一個字摘要就變）。
- [x] 2.2 玩具題目：tests/fixtures/bench_toy 放一個最小的題目（兩個模組、一個 bug、可見測試失敗一個、fix 與 keep 各有測試、標準解），後面評分器、自我檢查、執行器、報告的測試都用它，不呼叫任何模型。驗證：對它載入成功，且標準解套上後三組測試都通過（tests/test_bench_problems.py）。

## 3. 評分器

- [x] 3.1 「評分器在乾淨暫存目錄重跑，用原版測試與固定的 pytest 參數」：fixlab/bench/grader.py 對一個工作目錄做三次獨立評分（原版可見測試、fix 組、keep 組），每次新建暫存目錄、複製 agent 的檔案（排除測試檔與設定檔），可見測試那次放回原版所有測試檔與 conftest.py，fix 或 keep 那次放原版 conftest.py 與該組隱藏測試（放進 tests_hidden，目標只有這個資料夾），用 Workspace 呼叫 run_tests（沿用固定參數與沙箱）；不修改 agent 的工作目錄；agent 新增的非測試檔列在 added_files。對應 Grading runs in clean temporary directories。驗證：tests/test_bench_grader.py：agent 寫的 pytest.ini 不在暫存目錄裡（斷言檔案不存在，不是斷言測試失敗）、可見與 fix 的目標不同、評分前後工作目錄內容不變、added_files 列出新增的 .py。
- [x] 3.2 一組算通過的條件是 run_tests 回報通過、輸出最後一行摘要的通過數等於 problem.json 記的數量、沒有失敗與錯誤；只讀最後一行，找不到摘要算沒通過。對應 A group passes only when the pass count matches。驗證：tests/test_bench_grader.py：fix 組預期 5 個、實際只印 3 passed 時不算通過；程式先印一行假的 5 passed、真的最後一行是 2 failed 時不算通過。
- [x] 3.3 invalid 偵測：工作目錄裡任何測試檔或設定檔與原版 project 不同或是新增，設 invalid 並列出 tampered_files，評分仍用原版檔案。對應 Tampering is flagged as invalid 的三個情境。驗證：tests/test_bench_grader.py：改測試檔、新增 pytest.ini、只改原始碼各一個測試。
- [x] 3.4 「評分結果是獨立旗標，加上固定的判定順序」：輸出 visible_passed、fix_passed、keep_passed、invalid 與衍生的 fixed、broke_existing、overfit，並依 invalid、broke_existing、fixed、overfit、unfixed 的順序給 outcome；`grade` 子命令印出含 sandbox 與 added_files 欄位的 JSON。對應 Flags and outcome follow a fixed precedence、The grade command prints the result as JSON。驗證：tests/test_bench_grader.py：規格表的六列用參數化測試，另測 broke_existing 優先於 overfit，以及 grade 子命令對標準解印出 fixed。

## 4. 題目自我檢查

- [x] 4.1 「題目自我檢查不花 LLM 費用，題目寫完後凍結」：fixlab/bench/selfcheck.py 與 `check` 子命令驗證原始 project（可見測試失敗數等於預期、至少一個 fix 測試失敗、keep 全過、數量與 problem.json 相符）與套上標準解後（三組全過），逐題印一行，有任何題目不符就以非 0 退出碼結束；不呼叫任何模型。對應 The self-check verifies every problem without calling a model 的「正確的題目通過」與「fix 組本來就通過會被報告」。驗證：tests/test_bench_selfcheck.py 用玩具題目與它的壞掉版本（fix 組本來就通過）。
- [x] 4.2 重跑檢查：每種執行重複指定次數（預設 20），結果不一致的題目判失敗。對應 The self-check verifies every problem 的「flaky 會被報告」。驗證：tests/test_bench_selfcheck.py 用一個每次結果不同的玩具測試，重複次數用小值。
- [x] 4.3 位置洩漏檢查與路徑檢查：可見測試失敗輸出含 bug_files 任一檔案的檔名就判失敗；distractors 與 bug_files 列的路徑都必須存在於 project。對應 The self-check verifies every problem 的「失敗輸出點名 bug 檔」與 Each project states its correct behavior and contains distractors。驗證：tests/test_bench_selfcheck.py 兩個情境各一個測試。

## 5. 八個題目

每題都包含：project（模組、規格寫在 README 或 docstring、1 到 3 個干擾、1 到 2 個失敗的可見測試，斷言整個輸出、失敗輸出不點名 bug 檔）、hidden 的 fix 與 keep 兩組、solution、problem.json；寫完以 `check` 驗證（含重跑 20 次），並人工確認隱藏測試只測規格寫明的行為。每題的驗證相同：check 對該題通過，加上規格與隱藏測試的內容審閱。題目寫完並跑過要報告的實驗後即凍結。

- [x] 5.1 inventory（庫存）：匯入時「箱」換算成件數，讀錯倍率欄位，症狀出現在庫存報表總數；干擾是一個沒被用到的同名舊匯入函式。對應 Each problem is a self-contained folder。
- [x] 5.2 calendar（行事曆）：兩個模組對「結束日含不含」約定不一致，症狀是會議衝突檢查漏報；規格要逐一寫明兩個模組各自的約定，隱藏測試只透過 README 列出的公開入口做端對端測試，不直接測任一模組的內部函式（兩邊改哪一邊都說得通，不能讓其中一種修法被判成弄壞既有行為）；干擾是假日模組裡看似可疑但正確的 `+1`。對應 Each problem is a self-contained folder 與 A problem does not depend on the execution environment。
- [x] 5.3 settings（設定載入）：模組層級的預設字典被引用後在另一個模組被修改，症狀是第二次載入帶到第一次的值；不能是 grep 找得到的 `={}` 參數寫法；干擾是舊版設定模組。對應 Each problem is a self-contained folder。
- [x] 5.4 billing（金額）：折扣模組 `except` 後回傳 0，症狀是結帳總額偏高但不報錯；規格要寫明例外時應有的行為；干擾是另一個寫法相同但正確的 `except`。對應 Each problem is a self-contained folder。
- [x] 5.5 subscription（訂閱到期）：解析模組存 UTC、檢查模組用本地時間，邊界附近判斷錯；本地時差由程式裡明確的常數決定（測試環境的 TZ 固定為 UTC，不能靠系統時區讓 bug 出現），測試用固定時間，結果穩定可重現；干擾是一個看似多餘的時區轉換輔助函式。對應 Each problem is a self-contained folder 與 A problem does not depend on the execution environment。
- [x] 5.6 paging（分頁）：最後一頁的邊界在分頁模組與顯示模組各算一次，症狀是最後一頁少一筆；規格逐一寫明分頁模組與顯示模組各自的約定，隱藏測試只透過公開入口做端對端測試（同樣不能讓任一種合理修法被判成弄壞既有行為）；干擾是一個正確但寫法奇怪的頁數計算。對應 Each problem is a self-contained folder。
- [x] 5.7 scheduler（排程）：排序鍵改成 tuple，另一個模組依賴舊的型別；可見測試的失敗來自排序，但最自然的修法會讓 keep 組失敗，題目規格要寫清楚這個陷阱的正確行為；干擾是兩個相似的排序輔助函式。對應 Each problem is a self-contained folder。
- [x] 5.8 permissions（權限）：自訂例外的繼承層級讓 `except` 抓錯，某些情況悄悄放行；干擾是一個命名相近的權限檢查。對應 Each problem is a self-contained folder。

## 6. 實驗執行器

- [x] 6.1 「實驗執行器：先顯示計畫、需要明確確認，結果逐行寫入並可續跑」：fixlab/bench/runner.py 與 `run` 子命令讀模型設定檔（欄位見設計），展開成（題目、模型、條件、第幾次）的清單；沒有確認選項時只印計畫（次數、模型、條件、結果檔位置）、不呼叫模型；模型的 api_key_env 指到的環境變數沒設時、或有確認選項而沙箱不可用時，以退出碼 2 結束且不執行任何一次。對應 The plan is shown and nothing runs without confirmation、Model settings come from a file and secrets from the environment、Formal runs need the sandbox。驗證：tests/test_bench_runner.py：8 題 2 模型 2 條件 5 次印出 160 runs 且沒有請求、缺環境變數退出碼 2、沙箱不可用時退出碼 2。
- [x] 6.2 每次執行：複製 project 到暫存目錄、以一次性模式呼叫 fixlab 的 main（有 run_tests 條件不隱藏任何工具，沒有 run_tests 條件加 `--hide-tool run_tests`，其餘參數完全相同，並帶上 problem、condition、repeat、problem_digest 與模型的 meta 當 `--meta`，以及 temperature 與 extra_body）、評分、寫一行 results.jsonl、刪暫存目錄只留事件檔。fixlab 的 main 原樣呼叫，stop_reason、步數、token、耗時從該次執行專屬事件檔的 task_end 取，錯誤描述從 request_error 的 trace 取，hidden_tool_calls 數 trace 裡提到被隱藏工具的解析錯誤；每個模型的端點與金鑰在該次執行期間暫時設成 OPENAI_BASE_URL 與 OPENAI_API_KEY，之後還原。對應 The two conditions differ only in the visible tools、Each run uses a fresh copy of the problem、The conditions of each run are recorded、Results are appended one line per run and runs can resume。驗證：tests/test_bench_runner.py 用假 client：兩個條件的引數只差 `--hide-tool run_tests`、第二次執行從原始 project 開始、run_start 的 meta 含 problem、condition、repeat 與模型 meta、run_start 的 base_url 是該模型的端點、三次叫隱藏工具的紀錄算出 hidden_tool_calls 等於 3。
- [x] 6.3 結果與續跑：results.jsonl 每行含設計列出的鍵，claimed_done_but_failed 在 stop_reason 是 done 而 fixed 為 false 時為 true；同一個結果檔再次啟動時跳過已有且沒有錯誤的組合、重跑最後一行有錯誤的組合；請求失敗的執行仍評分、寫入 error 欄位、繼續下一次。對應 Results are appended one line per run and runs can resume、A failed request is recorded as an error, not as unfixed。驗證：tests/test_bench_runner.py：160 次中已有 37 行時只再跑 123 次、有錯誤的那一行續跑時會重跑、宣稱完成但沒修好的標記、請求失敗那一次有 error 且後面照跑。

## 7. 彙整報告

- [x] 7.1 fixlab/bench/report.py 與 `report` 子命令：每個（模型、條件）一列的 markdown 表（次數、五種結果的次數與百分比、宣稱完成但沒修好、hidden_tool_calls 總數、步數中位數、token 平均、錯誤欄；同一組合有多行時只用最後一行）；有單價時印每次與每修好一題的成本並在模型旁印單價來源與日期，沒有單價只印 token；有 error 的執行不算入任何結果。對應 The summary table covers every model and condition、Cost uses a stated price。驗證：tests/test_bench_report.py：40 次含 2 次錯誤的計數、成本範例（總成本 0.20、每次 0.02、每修好一次 0.04）、無單價時不印成本。
- [x] 7.2 「報告：同題成對比較，信賴區間用對題目重抽樣」：同一模型兩個條件逐題算修好率的差，平均差，以及對題目重抽樣 2000 次、固定亂數種子的 95% 區間；同一個檔案報告跑兩次數字完全相同。對應 The two conditions are compared per problem with an interval。驗證：tests/test_bench_report.py：兩題的範例平均差是 +0.2、跑兩次區間相同。
- [x] 7.3 失敗實例、限制與警告：每種非 fixed 結果列最多指定數量（預設 3）的執行與其工具呼叫序列和事件檔路徑；報告結尾固定印限制說明（題數與次數、被測程式可偽造結果、題數由 15 到 20 降到 8）；題目摘要與目前不同、同題兩個摘要、各組次數不一致、題目不存在時印警告仍輸出。對應 Failed runs are shown with their event logs、The limits are always printed、Mismatched inputs produce warnings。驗證：tests/test_bench_report.py 各情境一個測試。

## 8. 真實實驗

- [x] 8.1 小規模實跑（觀察，不是通過門檻）：用 OpenRouter 的開源模型對一個題目、兩個條件各跑一次，確認整條路（複製、跑 fixlab、評分、寫結果、報告）在真模型上能走完，記錄實際花費與耗時；發現的問題記進設計文件的 Risks 或補成任務。驗證：results.jsonl 兩行可解析、report 能印出、結果寫進設計文件。
- [ ] 8.2 完整實驗：模型與單價（附來源與日期）經使用者確認後，用確認選項執行 8 題、2 個模型、2 個條件、每格 5 次；原始紀錄在 runs 資料夾，不進版控；開始前記下 temperature、供應商與思考模式的固定方式。驗證：結果檔共 160 行（含標記為錯誤的執行），report 印出的次數與此一致。
- [ ] 8.3 結果報告：用 `report` 產生並寫入 docs/benchmark-results.md，註明每個模型的設定、單價來源與日期、未能控制的條件、被排除或有缺陷的題目、題數由 15 到 20 降到 8；結論只寫「在這組題目上觀察到」。驗證：內容審閱，並抽查三個數字可由 `report` 對原始結果重現。

## 9. 文件與教學文章

「教學文章：每個里程碑一篇，白話加圖」的共同要求：第 15 篇起；先寫天真做法、看它怎麼壞、附真實輸出；用白話，名詞先用圖與例子說明；每篇至少一張圖（draw.io 匯出的 PNG）；每篇結尾有「自己跑一次」的指令（讀者照著做能得到同樣的輸出）與一個簡短的名詞表；完成時在對應 commit 打輕量 tag article-NN（只建在本機）。

- [x] 9.1 第 15 篇 docs/articles/15-problems.md：一題從頭到尾長什麼樣（給 agent 看的專案、藏起來的測試、標準解）、為什麼測試要藏、為什麼症狀與原因要分開。驗證：內容審閱，圖檔存在，範例輸出來自真實的題目資料夾。
- [x] 9.2 第 16 篇 docs/articles/16-grader.md：評分器怎麼在乾淨環境打分、四個旗標與判定順序（附判定表的圖）、為什麼用原版測試、為什麼比對通過數。驗證：內容審閱，附真實的 grade 輸出。
- [x] 9.3 第 17 篇 docs/articles/17-self-check.md：怎麼證明題目量到想量的東西（原始 bug 一定失敗、標準解一定全過、重跑不 flaky、失敗輸出不洩漏位置），附 8 題的真實 check 輸出。驗證：內容審閱，輸出來自真實執行。
- [ ] 9.4 第 18 篇 docs/articles/18-experiment-runner.md：兩個條件怎麼只差一個工具、為什麼要固定 temperature 與供應商、先顯示計畫再確認、續跑，附小規模實跑的真實輸出。驗證：內容審閱。
- [ ] 9.5 第 19 篇 docs/articles/19-first-results.md：第一次完整實驗的結果與怎麼讀（用圖說明成對比較與區間）、哪些結論不能下。驗證：內容審閱，所有數字來自 docs/benchmark-results.md。
- [ ] 9.6 更新 README.md（階段 3 狀態與 tag、bench 的用法、已知限制）與 AGENTS.md（目錄結構加 bench、題數說明），並確認 docs/articles/10-protect-tests.md 的題數說法已與 8 題一致（這三處的題數修改已在工作區，隨第一個 commit 進去）。驗證：內容審閱，README 的指令照做能跑。

## 10. 收尾

- [ ] 10.1 全部驗收後打 tag：在 .venv 內 pytest 全數通過、`spectra validate stage3-benchmark` 無錯誤，commit 並建立 git tag stage-3（只建在本機）。驗證：git tag --list stage-3 有輸出，且 tag 指向的 commit 上 pytest 通過。
