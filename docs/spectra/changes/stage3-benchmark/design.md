## Context

階段 1、2 已有：agent 迴圈、六個工具、沙箱、事件檔（每次執行一個 JSONL）、互動模式。缺的是「有根據的結論」：目前只有一個範例專案、一個模型、少數幾次實跑。這個變更補上題目、評分、實驗與報告，讓專案能回答三個問題：agent 能不能用測試自己驗證（有沒有 run_tests 的差別）、會不會假通過、會不會弄壞原本正常的功能。

本設計已由一個 Opus 子代理審查過計畫（2026-10-18），採納的修正：評分旗標要完整且有判定順序、每格要重跑 5 次並固定 temperature 與供應商、每題要自我檢查、換掉一題容易時好時壞的題目、每題要寫明正確行為。審查指出「pytest 設定檔可以讓失敗的測試被跳過」，實際上 run_tests 本來就用固定參數（不讀任何設定檔），所以評分器沿用同一份參數即可；「用 junit XML 逐案比對」不採用，因為被測程式能偽造那個檔。

現況限制：agent 在原地修改目錄；被測程式與 pytest 在同一個行程，所以能偽造測試結果（README 已列為已知限制）。這個變更只能降低風險，不能根治。

## Goals / Non-Goals

**Goals:**

- 8 題多檔 Python bug、隱藏測試、乾淨環境評分，產出能重現的數字。
- 有或沒有 run_tests 兩個條件，只差模型看得到的工具。
- 實驗條件完整記錄（模型版本、量化、runtime、context、題目、種子、日期、temperature、供應商、思考模式）。
- 彙整報告與每個里程碑一篇給人類讀者的白話教學文章。

**Non-Goals:**

- 測試檔指紋偵測、prompt 消融、tool output 截斷實驗、步數與連續失敗上限的校準。
- 多 agent、Connector（階段 4）。
- 模型排名、統計顯著性的宣稱。
- 根治被測程式偽造結果。

## Decisions

### 題目放在 bench 資料夾，每題一個資料夾，隱藏測試不進工作目錄

每題一個資料夾，內容是：problem.json（領域、bug 類型、bug 所在檔案、干擾檔、各組測試的預期數量）、project（給 agent 的初始專案，含規格、可見測試、干擾檔）、solution（標準解，只放有改動的檔案，覆蓋在 project 上）、hidden 的 fix 與 keep 兩個資料夾。agent 的工作目錄是 project 的暫存副本，所以隱藏測試與標準解永遠不在 agent 看得到的路徑裡；agent 的測試行程又被沙箱禁止讀取 fixlab 專案目錄，兩層都擋。

替代方案：把隱藏測試放在工作目錄裡再靠檔名保護。不選的原因：工具只擋寫入，讀取沒擋，模型讀得到就是洩漏。

### 評分器在乾淨暫存目錄重跑，用原版測試與固定的 pytest 參數

評分器對 agent 改完的工作目錄做三次獨立評分，每次都新建暫存目錄：複製 agent 的檔案（排除測試檔與設定檔），再依該次評分放進原版的檔案。可見測試那次，放回原版 project 裡所有的測試檔與 conftest.py，原路徑，目標是整個目錄；fix 或 keep 那次，只放原版 conftest.py（如果有，放在根目錄）與該組的隱藏測試（放進名為 tests_hidden 的資料夾），目標是 tests_hidden，所以可見測試不會一起跑。每次用 Workspace 呼叫 run_tests，所以沿用同一份固定參數、沙箱與環境變數清理，不重寫一份。

一組算通過的條件是：run_tests 回報測試通過，而且 pytest 輸出的**最後一行**摘要的通過數等於 problem.json 記的預期數量，沒有失敗或錯誤。只讀最後一行，因為被測程式可以先印一行假的摘要，真的摘要在最後；找不到摘要就不算通過。數量比對用來擋「用 deselect 少跑幾個再印全過」。

補上 run_tests 一直留到階段 3 的缺口：測試子行程的環境多設 PYTEST_DISABLE_PLUGIN_AUTOLOAD 為 1（不自動載入外掛，擋住在根目錄放一個 trio.py 搶先被載入的做法），並設 TZ 為 UTC 與 PYTHONHASHSEED 為 0，讓題目不依賴機器的時區與雜湊順序。這三個變數加在 child_environment，agent 自己的 run_tests 也一樣，所以兩邊行為一致。agent 新增的非測試檔列在評分結果的 added_files，當作人工查看的證據。

替代方案：直接在 agent 的工作目錄跑隱藏測試。不選的原因：agent 能放進設定檔或 conftest 影響結果。替代方案：解析 junit XML 逐案比對。不選的原因：被測程式能偽造那個檔，而且數量比對已經涵蓋大部分情況。

### 評分結果是獨立旗標，加上固定的判定順序

原始旗標：visible_passed、fix_passed、keep_passed、invalid。invalid 的定義是 agent 的工作目錄裡，任何測試檔或設定檔（pytest.ini、pyproject.toml、setup.cfg、tox.ini、conftest.py）與原版不同或是新增的；它只記錄，不影響評分用的檔案（評分一律用原版），但判定優先。

衍生：fixed 等於 fix 與 keep 都通過；broke_existing 等於 keep 沒通過；overfit 等於可見測試通過但 fix 沒通過。總結用的 outcome 依序判定：invalid、broke_existing、fixed、overfit、unfixed。沒有 run_tests 的條件，模型看不到測試結果，所以另外在實驗結果裡記 claimed_done_but_failed，意思是 stop_reason 是 done 但沒有 fixed。「刪掉功能讓測試通過」由 keep 組抓，task_end 的 changed_files 留作人工查看的證據。

替代方案：只分三態（修好、假通過、弄壞）。不選的原因：可見、fix、keep 各過或不過共 8 種組合，三態說不清楚，也沒有先後順序。

### 題目自我檢查不花 LLM 費用，題目寫完後凍結

fixlab.bench 的 check 子命令對每一題驗證：原始 project 的可見測試失敗數等於 problem.json 記的預期；原始 project 的 fix 組失敗、keep 組通過；套上標準解之後三組全過；原始與標準解各重跑 20 次，結果必須完全一致（抓 flaky）；原始專案的可見測試失敗輸出不含 problem.json 列出的 bug 檔名（驗證「不透露位置」）。這些都只跑 pytest，不呼叫模型。

規格要求靠人工審：每個 project 的 README 或模組 docstring 要寫明正確行為，隱藏測試只測規格寫明的部分，避免多種合理修法造成評分爭議。

題目凍結：一個題目只要被用來跑過要寫進報告的實驗，就不再修改；之後發現題目有缺陷，在報告中記錄並註明排除，不悄悄改題（AGENTS.md 守則 4）。

### 條件的差別只在模型看得到哪些工具

fixlab 新增 `--hide-tool NAME`（可重複）。被隱藏的工具不出現在給模型的工具清單，也不在解析回覆用的 schema 裡，所以模型即使亂叫也只會被當成不認識的工具；但程式自己仍可呼叫它（一次性模式結束時自己再跑一次測試就是這樣）。system prompt 與任務文字在兩個條件完全相同，目前的 prompt 沒有提到 run_tests，所以不用改。有 run_tests 條件就是不傳這個選項，沒有 run_tests 條件傳 `--hide-tool run_tests`。工具名稱不存在時以退出碼 2 結束。

模型在隱藏條件下仍可能亂叫看不到的工具。這會變成「不認識的工具」的解析錯誤，而解析錯誤不累計連續失敗（階段 1 已記的限制），所以模型可能一直叫到跑滿步數。為了讓報告分得出「找不到 bug」與「一直叫看不到的工具」，實驗執行器在每次執行後讀事件檔，數出 trace 裡解析錯誤提到被隱藏工具名稱的次數，記成 hidden_tool_calls；迴圈本身不改。

### 請求選項：temperature 與額外的請求參數

fixlab 新增 `--temperature FLOAT` 與 `--extra-body JSON`。前者放進請求；後者必須是 JSON 物件，原樣交給 SDK 的 extra_body，用來固定 OpenRouter 的供應商（例如 provider 的 order 與 allow_fallbacks）與思考模式，也可放 seed。run_start 記下 hidden_tools、temperature、extra_body（沒傳是 null）。這是新增欄位，schema 版本仍是 1，讀取的程式要忽略不認識的欄位。有些模型或供應商不接受 temperature，被拒絕時是請求失敗，會記在 trace，實驗執行器要把這種執行標成錯誤而不是未修好。

### 實驗執行器：先顯示計畫、需要明確確認，結果逐行寫入並可續跑

fixlab.bench 的 run 子命令讀一個模型設定檔與選項，展開成（題目、模型、條件、第幾次）的清單。沒加確認選項時只印計畫（次數、模型、條件、結果檔位置）就結束，因為每次執行都會花錢。確認後依序執行：每次把題目的 project 複製到暫存目錄、用一次性模式呼叫 fixlab 的 main（原樣呼叫，不改它的介面；帶上述選項與 meta：題目、條件、次數）、再用評分器打分、把結果寫成 results.jsonl 的一行，然後刪掉暫存目錄（保留事件檔）。

main 只回傳結束碼，所以執行器從這次執行專屬的事件檔取結果：每次執行用自己的紀錄資料夾，檔案不會混；task_end 給 stop_reason、步數、token、耗時，request_error 的 trace 給錯誤描述，task_end 與 trace 的內容見階段 2 的事件檔規格。每個模型自己的端點與金鑰，是在該次執行期間暫時設定 OPENAI_BASE_URL 與 OPENAI_API_KEY（執行完還原），所以 run_start 記到的 base_url 是對的；這次執行印出的畫面由執行器接走，不混進實驗的輸出。

沙箱不可用時（macOS 以外，或 sandbox-exec 不能用），agent 的 run_tests 可以讀到 fixlab 專案目錄裡的隱藏測試，所以正式實驗（有確認選項）要拒絕執行，以退出碼 2 結束；只印計畫不受影響。

續跑：results.jsonl 裡已有、而且沒有錯誤的組合會跳過；有錯誤的組合在續跑時重跑（錯誤通常是供應商暫時的問題，重跑才不會讓各組次數不一致）。同一個組合有多行時，報告只用最後一行。

模型設定檔每個模型的欄位：name、label、base_url、api_key_env（環境變數名稱，不放金鑰）、temperature、extra_body、price（每百萬 token 的輸入與輸出單價，加 source 與 date）、meta（量化方式、runtime、context 長度）。

### 報告：同題成對比較，信賴區間用對題目重抽樣

fixlab.bench 的 report 子命令讀 results.jsonl 與模型設定檔，輸出 markdown：實驗設定、每個（模型、條件）的修好、弄壞、過擬合、無效、未修好的次數與比率、宣稱完成但沒修好的次數、步數中位數、token 平均、每次與每修好一題的成本（沒有單價就只顯示 token）、同一模型兩個條件的逐題成對差異與平均差異、差異的 95% 信賴區間（對題目重抽樣 2000 次，固定亂數種子）、每題的修好比例矩陣、失敗執行的實例（結果檔中的事件檔路徑與工具呼叫序列）、固定的限制說明（題數少、被測程式可偽造結果、題數由 15 到 20 降到 8）。結論只寫「在這組題目上觀察到」。

### 教學文章：每個里程碑一篇，白話加圖

第 15 篇起，每個里程碑一篇：題目長什麼樣、評分器、題目自我檢查、實驗執行器、第一次實驗結果。寫法依這個專案的慣例：先寫天真做法、再看它怎麼壞、附真實輸出；用白話，每篇至少一張圖，名詞先用圖與例子說明再給定義。每篇完成時在對應的 commit 打 article-NN 的輕量 tag（只建在本機）。

## Implementation Contract

**Behavior**

- fixlab 命令列多三個選項：`--hide-tool`、`--temperature`、`--extra-body`。run_start 多三個欄位：hidden_tools（字串陣列）、temperature（數字或 null）、extra_body（物件或 null）。
- 新的 fixlab.bench 有四個子命令：check（題目自我檢查）、grade（對一個工作目錄評分，印 JSON）、run（實驗）、report（報告）。
- 8 題在 bench/problems 底下，題目 id 為 inventory、calendar、settings、billing、subscription、paging、scheduler、permissions。

**Interface / data shape**

- problem.json 的鍵：id、domain、bug_type、bug_files（陣列）、distractors（陣列）、visible（含 total 與 failing）、hidden（含 fix 與 keep 的測試數量）。
- 評分結果 JSON 的鍵：problem、visible_passed、fix_passed、keep_passed、invalid、tampered_files、added_files、fixed、broke_existing、overfit、outcome、sandbox（on 或 off）。
- results.jsonl 每行的鍵：problem、problem_digest、model、condition（with_tests 或 no_tests）、repeat、grade（上面那份）、stop_reason、steps、prompt_tokens、completion_tokens、seconds、claimed_done_but_failed、hidden_tool_calls、log_path、started_at、error（沒有錯誤是 null）。
- 模型設定檔與 problem.json 都是 JSON。

**Failure modes**

- check 有任何題目不符就以非 0 退出碼結束並逐題列出原因。
- run 在沒有確認選項時不呼叫模型；模型請求失敗的執行記為 error 並寫進 results.jsonl，不中斷整個實驗。
- report 遇到 results.jsonl 的題目集合與目前 bench 不同，或同一組合的次數不一致時，印警告並照樣輸出。
- 沙箱不可用時評分器仍可執行，並在結果裡記 sandbox 為 off；正式實驗在沙箱不可用時拒絕執行，退出碼 2。

**Acceptance criteria**

- 評分器、自我檢查、執行器、報告各有單元測試，使用玩具題目與假的模型 client，不呼叫任何真的 LLM。
- 8 題的 check 全部通過（含重跑 20 次）。
- 用真模型對 1 題、各條件各跑 1 次的小規模實跑（觀察，不是通過門檻）。
- 完整實驗經使用者確認費用後才執行，報告寫入 docs 並註明所有調整。

**Scope boundaries**

- 範圍內：上面列的程式、8 題、報告、文章、README 與 AGENTS.md 更新。
- 範圍外：指紋偵測、消融、校準、多 agent、Connector、雲端或批次排程。

## Risks / Trade-offs

- [8 題要做到真的隱晦、而且只有一種合理修法很難] → 每題自我檢查加人工審規格；題目凍結規則；發現缺陷時在報告記錄並排除，不改題。
- [被測程式與 pytest 同一個行程，能偽造結果] → 固定參數、乾淨環境重跑、只讀最後一行摘要與通過數比對、關閉外掛自動載入降低風險；報告寫明不能根治。
- [題目依賴機器的時區、雜湊順序、當前時間會讓換一台機器結果就不同] → 測試環境固定 TZ 與 PYTHONHASHSEED；題目規則禁止依賴環境，需要時區時由程式裡明確的時差常數決定；自我檢查重跑 20 次。
- [兩個模組各算一次的題目，改哪一邊都說得通] → 規格逐一寫明每個模組的約定，隱藏測試只透過 README 列出的公開入口做端對端測試。
- [8 題乘以 5 次的樣本小，差 2 題就是 25%] → 每格 5 次、同題成對比較、信賴區間；報告只寫觀察，不宣稱顯著。
- [實驗會花錢] → run 預設只顯示計畫，需明確確認；先做 1 題的小規模實跑再決定完整實驗。
- [OpenRouter 轉給哪家供應商、思考模式會改變結果] → 用 extra_body 固定並記錄；固定不了的在報告列為未控制條件。
- [有些供應商不接受 temperature] → 請求失敗會被標成 error，不算未修好。
- [題數由 15 到 20 降到 8] → 這是動手寫題目之前的規劃調整，不是看了數字才調；寫進報告與 AGENTS.md。
- [規模大，一個變更的任務很多] → AGENTS.md 要求每個階段一個變更；任務分成 10 組，每組可獨立驗收與 commit。

## Migration Plan

不需要遷移：新增的選項都有預設值，沒傳時行為與現在相同；事件檔只多欄位。回復方式是不使用新選項與 fixlab.bench。

## Open Questions

- 商用模型用哪一個、單價多少：實驗前決定，單價附來源與日期。
- 5 次夠不夠：先用 5 次；如果信賴區間太寬，可以增加次數，但要在看結果之前宣告，並寫進報告。
