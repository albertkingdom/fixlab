## Context

fixlab 目前只有規劃文件（AGENTS.md）。前身專案 code-agent-eval 已有可用的 agent 迴圈（約 220 行含輔助函式）、tool call 解析（約 120 行）與三個工具加沙箱（約 215 行），並且有 40 多個測試與一份黃金 trace。但它的設計綁死「單檔函式題」：工作目錄固定是 solution.py 加一個測試檔，任務訊息由題目格式組成，測試指紋只算一個檔。

階段 1 的任務是把這三塊搬過來，改成「一個任意的 repo 目錄」，補上找 bug 需要的工具，並補上 code-agent-eval 與 subagent review 找到的安全缺口：測試檔指紋只算一個檔、子行程繼承整個環境變數（含放在 .env 的 API 金鑰）、迴圈沒有連續失敗保險、沙箱在 workspace 位於專案目錄內時會讓 pytest 讀不到設定檔。

教學性質要求：程式讀起來像偽碼、註解用繁體中文說明「為什麼」、每個模組開頭 2–5 行說明角色。原創性要求：每個決定的依據是自己的實驗結果或 Claude Code 的行為，外部文章只列為參考來源（見「設計依據與參考來源」）。

## Goals / Non-Goals

**Goals:**

- 任何一個含 pytest 測試、依賴只有標準函式庫的 Python 目錄，都能當成 agent 的工作目錄，包含位於 fixlab 專案目錄內的 workspace。
- 七個工具足以完成「找出 bug 在哪個檔案、讀懂、局部修改、跑測試」的流程。
- 測試檔不可被 agent 以任何工具或被測程式修改，且事後能偵測到被改過。
- 子行程拿不到 API 金鑰、網路與工作目錄外的寫入。
- 搬過來的行為由測試保護：原有的迴圈、解析、隔離測試依新介面改寫後全數通過。

**Non-Goals:**

- 正式的 CLI、權限提示、telemetry 檔案格式、benchmark、隱藏測試評分（階段 2 與 3）。
- 任意 shell 工具、git 工具。
- 驗證器抽換介面、Anthropic 轉接層、串流。
- 跨平台沙箱（只支援 macOS 的 sandbox-exec）。
- 硬連結逃逸、被測專案的第三方依賴。

## Decisions

### MVP 優先的實作順序，最小入口在暫存複本上跑

任務順序改成先做能端到端跑通的最小切片（工具註冊、read_file、list_files、edit_file、受保護路徑只接 edit_file、run_tests 加環境變數白名單、迴圈核心與步數上限、最小入口 `fixlab fix`），用真模型實際修一次 timelog，再補 glob、grep、write_file、指紋、沙箱與迴圈保險。原因：原順序要到後段才有迴圈，最早的真實回饋要等很久；先跑通能提早發現工具輸出格式與提示詞的問題。

環境變數白名單不等沙箱，跟 run_tests 一起上。依據是自己程式的已知缺陷：code-agent-eval 的 run_tests 把整個 os.environ 傳給子行程，而 smoke 會在 shell 匯出真的 API 金鑰；被執行的程式包含模型改寫過的檔案，只要印出環境，金鑰就會進入測試輸出、對話與 README 紀錄。

取捨：沙箱完成前仍沒有網路與家目錄限制，所以最小入口只改暫存複本，複製用 `copytree(symlinks=True)`（預設會跟隨符號連結，把目錄外的內容複製進來），這段期間只對自己寫的 fixture 執行。沒有沙箱與指紋，被測程式也能改複本裡的測試檔，所以 `--apply` 只在每個要寫回的檔都不是受保護路徑、原檔不是符號連結、原檔內容與複製當下相同時才寫，任何一個不符合就整個中止；diff 則涵蓋包含測試檔在內的所有檔。`fixlab fix` 只是 smoke 用的最小入口，不代表階段 2 的 CLI 設計。

替代方案：另開 fixlab-mvp 專案或 spike 分支；不選的原因：會複製已完成的 workspace、toolparse 與 fixture，之後合併回來還要重寫一次。

### 複製自己的程式並整理，不做共用套件

code-agent-eval 的檔案逐模組複製到 fixlab/ 並改寫，兩個專案之後各自演進。替代方案：把 agent 核心抽成共用套件讓兩邊依賴。不選的原因：共用套件要處理版本與發版，對兩個個人專案是負擔；教學專案也希望讀者在一個 repo 裡讀完全部程式。取捨：之後 code-agent-eval 的修正不會自動同步，需要時手動搬。搬檔發生在各模組自己的任務裡，不在骨架任務一次搬完。

### 工作目錄就是 repo 根目錄，任務文字由呼叫端傳入

Workspace 只認一個根目錄，不再知道 solution.py。run_agent 收一段任務文字（例如「tests 在 pytest 下失敗，請找出原因並修好」），第一則 user 訊息就是它。替代方案：保留題目 dict 與 stub 格式。不選的原因：多檔專案沒有「stub」；題目如何變成文字是 benchmark（階段 3）的事，不該放在核心。

### 預設步數上限提高到 20，並新增連續失敗上限 3

多檔探索比單檔多很多步，試跑的 8 步上限是為單檔題設的。20 是初始值，沒有實測依據，階段 3 用 telemetry 的步數分佈校準。連續失敗上限的算法：只有「本回合至少執行了一個工具、且所有被執行的工具都 ok=false」才累計；只要有一個成功就歸零；沒有執行任何工具的回合（無效回覆、空回覆、被截斷）既不累計也不歸零，因為那些回合已有各自的回饋機制。累計到 3 次以新的 stop reason stuck 結束。run_tests 在測試失敗時仍回 ok=true（失敗的測試是有用的資訊，不是工具錯誤），所以不會觸發。替代方案：只靠步數上限；不選的原因：模型反覆用錯誤參數呼叫，會白白燒完 20 步。重複呼叫偵測不做，留待階段 2 看 telemetry 再決定。

### edit_file 用「唯一出現的原字串」替換

edit_file(path, old_string, new_string)：old_string 在檔案中必須剛好出現一次；零次或多次都回錯誤並說明次數，讓模型補更多上下文。替代方案：行號範圍替換、unified diff。不選的原因：行號在模型連續編輯後會漂移，diff 對小模型太容易寫錯（試跑中小模型常把換行寫成字面的 \n 或寫壞 JSON）；唯一字串替換在使用者每天用的 Claude Code 的 Edit 工具上就是這個語意，錯誤訊息也最容易解釋。

### write_file 覆寫既有檔案前必須先讀過

write_file 對「已存在」的檔案，要求本次 Workspace 生命週期中，read_file 曾「整檔、未截斷」地回傳過它；否則拒絕並提示先讀。狀態存在 Workspace 實例的 files_read 集合：只有不帶行範圍、也未被 20000 字元上限截斷的 read_file 才記錄；edit_file 成功後清除該檔的記錄（模型沒看過編輯後的全文）；write_file 成功後記錄該檔（模型知道自己寫了什麼）。建立新檔不受限。這個限制的依據是 Claude Code 自己的 Write 工具對既有檔案的行為（必須先讀過才能覆寫）。替代方案：完全不管。不選的原因：多檔專案裡整檔覆寫是最容易弄壞東西的操作；部分讀取後整檔覆寫，等於憑空捏造沒看過的部分。

### 輸出一律有上限，格式固定

read_file 每行加行號並可指定 start_line 與 end_line，以 splitlines 切行；list_files 與 glob 最多 200 筆，依完整相對路徑的字串順序排序；grep 最多 100 行；測試輸出最多 4000 字元；任何輸出超過上限就截斷並註明總量。原因：工具輸出會留在對話歷史裡每一輪重送，是成本與小模型 context 的主要壓力；試跑中被截斷的回覆是小模型最大宗的失敗原因之一，所以截斷時一定要明講，模型才知道自己沒看到全部。

### grep 自己實作，單行比對用 regex 套件加逾時

遍歷工作目錄，逐行比對正規表示式，輸出 路徑:行號:內容。單行最長只比對前 2000 字元；比對使用第三方套件 regex（它的 search 支援 timeout 參數），單行超過 1 秒就中止整個搜尋並回報 pattern too slow，防止 `(a+)+$` 這類災難性回溯卡死在沙箱外的行程。替代方案：呼叫系統的 rg；不選的原因：多一個要安裝的外部依賴，而且一旦呼叫外部指令，路徑限制與沙箱就要再處理一次。再一個替代方案：用標準 re 並在子行程裡跑；不選的原因：實作與測試都複雜很多。取捨：多一個 pip 依賴 regex；速度比 rg 慢，但小型專案沒有差別。

### 遍歷工具不跟隨符號連結，跳過清單共用

list_files、glob、grep 與測試檔指紋掃描共用同一份跳過清單（.git、.venv、__pycache__、.pytest_cache），且一律不跟隨、不列出符號連結。原因：這些工具在沙箱外以 Python 行程執行，工作目錄裡放一個指向 ../secret 的連結，就能讓 grep 讀到工作目錄外的內容；單一的使用者路徑解析擋不住這種情況。替代方案：對每個走訪到的檔案都 resolve 並檢查；不選的原因：實作較繁、效能較差，而且測試專案本來就不需要符號連結。

### 測試檔以規則判定，路徑相對於工作目錄，指紋涵蓋整組

「受保護檔案」的判定規則，一律對「相對於工作目錄根的路徑」套用：檔名（不分大小寫）以 test_ 開頭、以 _test.py 結尾、等於 conftest.py，或路徑中任一層目錄名為 tests 或 test。工作目錄本身位於名為 tests 的目錄底下（例如 tests/fixtures/timelog）不影響判定。tests.py 這類單一檔名不受保護，這是刻意的：pytest 預設不會收集它，保護範圍與 pytest 收集規則對齊。Workspace 建立時掃描所有受保護檔案（用共用跳過清單），對「相對路徑加內容」排序後算一個 sha256 指紋；run_tests 跑完再算一次，不同就設 test_file_tampered 旗標（刪除或新增受保護檔案也算）。write_file 與 edit_file 都先過同一個判定函式。替代方案：只保護 test_*.py。不選的原因：tests/helpers.py 或 fixtures 檔改掉，同樣能讓測試變綠而不修 bug。

### 子行程環境變數用白名單

run_tests 啟動子行程時，環境只放 PATH、LANG、LC_ALL、TMPDIR 與 PYTHONDONTWRITEBYTECODE=1，其餘全部不傳。依據是自己的程式：code-agent-eval 的 run_tests 把整個 os.environ 傳進子行程，而專案根目錄的 .env 放了 OpenRouter 金鑰，被測程式只要印出環境就能讓金鑰進入 trace 與對話。已用實驗確認白名單下以 sandbox-exec 啟動 venv 的 python 與 pytest 可行，不需要 HOME、VIRTUAL_ENV 或 PYTHONPATH。替代方案：黑名單（移除名稱含 KEY、TOKEN 的變數）；不選的原因：命名無法窮舉（OPENAI_KEY、STRIPE_SK、GH_PAT）。取捨：若被測專案的測試需要特定環境變數，要明確加進白名單（階段 1 不開放設定）。

### run_tests 的 pytest 指令固定，不讀專案外的設定

run_tests 執行的指令固定為：python -m pytest -q -p no:cacheprovider -c /dev/null --rootdir=. --confcutdir=. -- 加上 target（預設為 .）。-c /dev/null、--rootdir=. 與 --confcutdir=. 讓 pytest 不往上層目錄找 pyproject.toml 或 conftest.py；沒有這幾個參數時，workspace 位於 fixlab 專案目錄內（例如 tests/fixtures/timelog）會因為沙箱禁止讀取專案目錄而在 locate_config 階段崩潰（subagent review 以實驗重現）。-p no:cacheprovider 避免在工作目錄產生 .pytest_cache。-- 讓以 - 開頭的 target 不會被當成 pytest 選項。target 必須是工作目錄內的路徑，否則同樣 blocked。替代方案：workspace 一律複製到專案外的暫存目錄；不選的原因：使用者之後要對自己的 repo 就地執行，必須支援任意位置。

### 沙箱：禁網路、限制讀寫範圍、測試檔不可寫

沿用 code-agent-eval 的 sandbox-exec 規則：預設允許、禁網路；使用者家目錄、專案目錄與額外的 deny_read 目錄不可讀，再放行自己的工作目錄與 .venv（後面的規則覆蓋前面的，所以順序就是邏輯：所有 deny 寫在 allow 之前）；只能寫工作目錄（加 /dev）。擋家目錄是新增的：code-agent-eval 只擋專案目錄，被測程式仍能讀 ~/.ssh、~/.aws 或其他專案的 .env，雖然禁網路，內容仍可經 pytest 輸出進入 run_tests 的結果、對話與 trace，最後送到 LLM 供應商。已用實驗確認：家目錄被擋時，位於家目錄底下的工作目錄與 .venv 經 allow 放行後，pytest 仍能正常執行與 import；venv 的基底 Python 位於 /opt/homebrew 不受影響。替代方案：改成預設拒絕再逐一放行系統目錄；不選的原因：Python 與 pytest 需要讀的系統路徑很多，清單難以維護。取捨：若基底 Python 裝在家目錄底下（例如 pyenv 或 uv 管理的 Python），會被擋而無法啟動，屆時需把基底 Python 目錄加入放行清單。新增：工作目錄內的受保護路徑不可寫，且 tests 或 test 目錄不可改名或搬移。因為 SBPL 的 param 無法直接放進正規表示式，規則用 string-append 把「已用反斜線跳脫過所有正規表示式特殊字元的工作目錄路徑」（參數 WS_RE）接上目錄與檔名樣式；目錄樣式用 [Tt][Ee][Ss][Tt][Ss]? 加 (/|$) 結尾以涵蓋不分大小寫與改名。檔名規則（test_、_test.py、conftest.py）同樣編進沙箱。這些規則由 subagent review 以實驗驗證可行，並確認工作目錄路徑含 a+b(c) 這類字元時若不跳脫，保護會悄悄失效。路徑全部以 -D 參數傳入，不直接拼進規則字串。已知限制：硬連結能指向工作目錄外的檔案而沙箱只檢查路徑，階段 1 不處理，只在 README 列為已知限制。

### blocked 旗標只留給路徑逃逸與受保護檔案

code-agent-eval 把所有 ToolError（包括 file not found）都設成 blocked 旗標，使 blocked_calls 同時混了安全攔截與一般錯誤。fixlab 只在「路徑逃逸」與「寫入受保護檔案」時設 blocked 並計入 blocked_calls；其他錯誤（找不到檔案、old_string 出現次數不對、先讀後寫失敗）只是 ok=false。原因：階段 3 要統計 agent 嘗試越界的次數，指標必須乾淨。

### 保留 trace 回呼，不在階段 1 決定 telemetry 格式

迴圈繼續接受一個 trace(record) 回呼，每個回覆呼叫一次，欄位沿用現有的（step、latency、token、tool_calls…）。階段 2 再決定寫檔格式與彙整。替代方案：現在就設計完整的事件 schema。不選的原因：還沒有實際的 CLI 與 benchmark 來決定需要哪些欄位，提前設計容易白做。

### 設計依據與參考來源

每個決定的依據必須是三類之一：自己 pilot 的實驗結果（docs 與 code-agent-eval/docs/pilot-results.md）、自己程式碼的已知缺陷、Claude Code 工具的實際行為。外部文章只列為「參考來源」，註明讀過什麼、採用了哪個想法，不當作設計依據，也不複製其程式碼或題目結構。已讀過的參考：高見龍的 KeSi 連載（kaochenlong.com，Day 11–18），影響了：連續失敗計數只算「整輪全失敗」、環境變數洩漏列為風險、成本與 token 量測的重視。範例專案 timelog 的領域、bug 類型（解析邏輯而非比較運算子）與檔案結構都是自己設計，刻意不沿用他實驗題的骨架。沙箱規則最初寫在 code-agent-eval 時參考過 KeSi 的 sandbox_spec，註解標為 MIT，但 AGENTS.md 記載查不到其 repo 與授權，所以沿用前要再核對，README 也要註明。另讀過同一作者的〈讓 Agent 看見專案〉：採用的想法只有「空結果要明確回報，讓模型分得出沒找到與沒執行成功」，並列出 .env 外洩風險；其 list_files 只列一層、fixlab 選遞迴，理由是 benchmark 專案小，一次看到全部結構比較省步數。〈用 ripgrep 搜尋程式碼〉也讀過，尚未決定是否改用 rg，決定時再補上採用了哪些想法。替代方案：不寫來源。不選的原因：面試時必須能說清楚哪些是自己的設計、哪些是參考。

## Implementation Contract

**Behavior**

- `run_agent(client, model, ws, task, max_steps=20, request_extra=None, trace=...)` 回傳 AgentResult，stop_reason 為 done、max_steps、error、stuck 之一。
- `Workspace(root, python=sys.executable, deny_read=(), project_root=...)`；`ws.call(name, args)` 永遠回傳 ToolResult(output, ok, flags)，不拋例外。
- 七個工具：read_file(path, start_line?, end_line?)、list_files(path?)、glob(pattern)、grep(pattern, path?)、edit_file(path, old_string, new_string)、write_file(path, content)、run_tests(target?)。
- read_file 輸出每行格式為 6 位右對齊行號、一個 tab、原文；空檔輸出 "(empty file)"；結尾換行不產生多餘的編號空行。
- grep、glob、list_files 的路徑一律是相對於工作目錄的相對路徑，不跟隨符號連結。
- run_tests 的指令固定如「run_tests 的 pytest 指令固定」所述，逾時 10 秒，輸出超過 4000 字元就截斷並加註；旗標含 tests_passed、timed_out，必要時含 test_file_tampered。
- `fixlab fix PATH`（fixlab/cli.py，smoke 用的最小入口）：把 PATH 以 `copytree(symlinks=True)` 複製到暫存目錄（略過共用跳過清單），用 OpenAI 相容端點（`OpenAI(timeout=600, max_retries=0)`）在複本上跑 agent，每步在 stderr 印工具名稱、ok 與 flags；結束後在複本上再跑一次 run_tests，並印 stop reason、步數、token 與涵蓋所有檔（含測試檔）的 unified diff。預設不動 PATH；`--apply` 只在每個要寫回的檔都不是受保護路徑、原檔不是符號連結、原檔內容與複製當下相同時才寫回。

**Failure modes**

- 路徑在工作目錄外、絕對路徑、以 ~ 開頭、跟隨符號連結後跑出工作目錄、run_tests 的 target 在工作目錄外：ok=false 並設 blocked。
- 寫入受保護檔案：ok=false 並設 blocked，檔案不變。
- 其他工具錯誤（找不到檔案、edit_file 的次數不是 1、覆寫沒整檔讀過的檔案、無效正規表示式、grep 太慢）：ok=false，不設 blocked。
- `--apply` 遇到任何不符合寫回條件的檔：整個中止、不寫任何檔並說明原因。複本裡的符號連結不跟隨（read_file 被擋）。沒設 OPENAI_API_KEY：結束並給清楚的錯誤訊息。
- 連續 3 次「有執行工具且全失敗」的回合：迴圈以 stuck 結束，counters 記錄 stuck_failures。
- 回覆被截斷、空回覆、壞掉的 JSON：行為與 code-agent-eval 相同（回饋給模型，不算完成，也不影響連續失敗計數）。

**Acceptance criteria**

- `pytest` 在 fixlab 根目錄全數通過，且不收集 tests/fixtures；測試涵蓋迴圈、解析、七個工具、隔離（路徑、測試檔保護、指紋、沙箱讀寫、環境變數、workspace 位於專案內、含特殊字元的 workspace 路徑、tests 目錄改名）。
- 範例專案 tests/fixtures/timelog 在未修復時 run_tests 恰有 1 個失敗，只改 parser 一處後通過；對「就地執行」與「複製到暫存目錄」兩種位置都成立。
- 手動 smoke：先把範例專案複製到暫存目錄，對那個複本執行 `fixlab fix`（絕不對 tests/fixtures/timelog 本身用 `--apply`），用 OpenAI 相容端點與一個模型跑一次。這是觀察不是通過門檻：修好與否都照實記錄 stop reason、步數、token、最終測試結果與 AGENTS.md 守則 3 的欄位，貼進 README；真模型這一次不納入自動測試。`--apply` 的寫回條件與複製規則由 tests/test_cli.py 以假 client 驗證。
- README 說明讀程式順序、七個工具、已知限制與「設計依據與參考來源」。

**Scope boundaries**

- In：fixlab 套件、tests、範例專案、smoke 用的最小入口 `fixlab fix`（fixlab/cli.py）、README、AGENTS.md 與 docs/spectra/config.yaml 的現況與原創性規則更新。
- Out：正式 CLI（互動模式、權限提示、規格）、telemetry 檔案、benchmark、評分、shell 工具、多 agent、connector。

## Risks / Trade-offs

- [MVP 階段 run_tests 在沙箱完成前直接執行被測程式（含模型改寫過的檔案），沒有網路與家目錄限制；被測程式可讀家目錄的機密檔，也能改複本裡的測試檔] → 環境變數白名單已隨 run_tests 一起上，API 金鑰不會進子行程；最小入口只改暫存複本，`--apply` 有三個寫回條件；沙箱任務完成前，只對自己寫的 fixture 執行並人工看過 diff，不對別人的 repo 跑。
- [白名單環境變數讓某些專案的測試跑不起來] → 階段 1 只服務自己寫的題目；階段 2 若要跑別人的 repo，再加可設定的白名單。
- [sandbox-exec 已被 Apple 標為棄用，且只有 macOS] → 在 README 與 AGENTS.md 明講；沙箱介面保持單一模組，之後可換成 Docker。
- [受保護目錄規則太寬（tests 或 test 目錄整個不可改）] → 對本專案的 benchmark 是想要的；若真實專案把原始碼放在名為 test 的目錄，會被誤擋，階段 1 接受這個限制。
- [提高步數到 20 會增加成本，且 20 沒有實測依據] → 成本由階段 2 的 telemetry 量測；上限可由參數調整。
- [grep 用 Python 實作在大專案很慢] → 只服務小型專案；輸出已有上限，逾時也會中止。
- [regex 套件的 timeout 只在比對一行時生效，整體仍可能很慢] → 另設整體搜尋時間上限 5 秒，超過就回傳已找到的結果並加註。
- [list_files 遞迴加 200 筆上限，專案變大時依路徑排序的後段目錄會被整個截掉，模型只知道省略筆數] → benchmark 專案小，階段 1 接受；若 smoke 或 benchmark 出現找不到檔案，再改成分層列出或加 depth 參數。
- [跳過清單沒有 .env，對真實 repo 執行時模型能 read_file 讀到金鑰並送到模型供應商] → 階段 1 只跑自己寫的 fixture，沒有影響；階段 2 對別人的 repo 執行前，要把 .env 與 .env.* 加進共用跳過清單，並限制 read_file。
- [被測程式讀取家目錄的機密檔（~/.ssh、~/.aws、其他專案的 .env），經測試輸出送進對話與 LLM 供應商] → 沙箱預設擋住整個家目錄的讀取，只放行工作目錄與 .venv；家目錄以外仍可讀的機密（例如 /etc 底下的設定）不在階段 1 範圍。
- [基底 Python 裝在家目錄底下時，擋家目錄會讓 pytest 無法啟動] → run_tests 回報啟動失敗而不是靜默通過；需要時把基底 Python 目錄加入放行清單。
- [SBPL 的正規表示式與 Python 的 re 不完全相同，跳脫字元集合可能漏掉] → 以含 +、(、)、.、[ 的目錄名做測試；若有遺漏，保護會悄悄失效，所以測試要實際嘗試寫入受保護檔案而不只檢查規則文字。
- [KeSi 授權與網址在 AGENTS.md 記為查不到，但 code-agent-eval 的沙箱註解寫 MIT] → 沿用前先到 repo 核對授權；README 註明參考來源。

## Open Questions

(none)
