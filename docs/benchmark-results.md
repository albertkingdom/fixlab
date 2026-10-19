# 階段 3 實驗結果（2026-10-18）

> 這份文件記錄階段 3 第一次完整實驗的結果。**所有結論都只是「在這組題目上觀察到」**，不能推到別的題目或別的模型。數字都能由原始結果檔用 `report` 指令重現（見最後的「怎麼重現」）。

## 一句話看結果

- **Qwen3.5-9B：能自己跑測試，修好率從 25% 提高到 82%。** 同一題成對比較的平均差是 +0.57，95% 區間 [+0.22, +0.88]。
- **沒有 `run_tests` 時，Qwen 不是「亂宣稱修好了」，而是「一直不敢結束」。** 40 次執行全部跑滿 20 步、沒有一次宣告完成；最後 10 步的工具呼叫有 393／400 是 `grep`。
- **Claude Haiku 5.5：兩個條件都是 80／80 修好。** 這組題目對它太容易，看不出有沒有 `run_tests` 的差別。
- **後續小實驗：Qwen 停不下來，不是量化也不是步數上限，prompt 影響很大。** 換成 bf16、或把步數放寬到 40（各 16 次），都沒有一次自己宣告完成；在 system prompt 加一句「沒有測試時怎麼辦」（實驗 C，32 次），沒有 `run_tests` 時的修好次數從前 2 輪的 4／16 變成 13／16，但仍有 12／16 沒有自己宣告完成（見〈後續實驗〉）。

## 做了什麼

| 項目 | 設定 |
|---|---|
| 題目 | 8 題（billing、calendar、inventory、paging、permissions、scheduler、settings、subscription），內容見第 15 篇 |
| 條件 | `with_tests`：六個工具都有；`no_tests`：隱藏 `run_tests`。system prompt 與任務文字完全相同 |
| 次數 | 每個（題目、模型、條件）5 次，共 8 × 2 × 2 × 5 = 160 次，全部完成，**0 次錯誤、沒有排除任何一次** |
| 開源模型 | `qwen/qwen3.5-9b`，經 OpenRouter，供應商固定為 Venice，量化 fp8，temperature 0.2，思考模式維持預設（開），context 262144 |
| 商用模型 | `anthropic/claude-haiku-5.5`，經 OpenRouter，供應商固定為 Anthropic，**無法設定 temperature**（供應商的支援參數裡沒有它），思考模式維持預設，context 1000000 |
| 隨機種子 | 都不固定，每次重跑是獨立的樣本 |
| 單價（每百萬 token 輸入／輸出） | Qwen $0.10／$0.15（OpenRouter models API，venice/fp8 端點，2026-10-18）；Haiku $0.10／$0.50（同來源，anthropic 端點，2026-10-18） |
| 執行環境 | macOS 沙箱開啟（160 次全部確認）；一次性模式，步數上限 20、每次最多 8192 個輸出 token；fixlab 版本 `1ca88d4` |
| 時間 | 2026-10-18 07:36 到 08:36（UTC），實際牆上時間約 59 分鐘 |
| 花費 | 約 $0.41（Qwen $0.255、Haiku $0.159） |

## 結果

### 每個模型與條件

| 模型 | 條件 | 修好 | 弄壞既有功能 | 假通過 | 沒修好 | 宣稱完成但沒修好 | 步數用完 | 步數中位數 |
|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | 有 `run_tests` | 40／40 | 0 | 0 | 0 | 0 | 0 | 6 |
| Haiku 5.5 | 沒有 | 40／40 | 0 | 0 | 0 | 0 | 0 | 5 |
| Qwen3.5-9B | 有 `run_tests` | 33／40（82%） | 5 | 2 | 0 | 7 | 0 | 10 |
| Qwen3.5-9B | 沒有 | 10／40（25%） | 2 | 0 | 28 | 0 | 40 | 20 |

「假通過」是可見測試過了、但 bug 沒修好。「宣稱完成但沒修好」是 agent 自己宣告完成，結果不是修好。

### Qwen3.5-9B 逐題比較

| 題目 | 有 `run_tests` | 沒有 | 差 |
|---|---|---|---|
| billing | 5／5 | 0／5 | +1.00 |
| permissions | 5／5 | 0／5 | +1.00 |
| settings | 5／5 | 0／5 | +1.00 |
| scheduler | 4／5 | 0／5 | +0.80 |
| subscription | 5／5 | 1／5 | +0.80 |
| paging | 1／5 | 0／5 | +0.20 |
| inventory | 5／5 | 5／5 | 0.00 |
| calendar | 3／5 | 4／5 | −0.20 |

平均差 +0.57，95% 區間 [+0.22, +0.88]（對 8 題重抽樣 2000 次，亂數種子 0）。

### 成本

| 模型 | 總成本 | 每次 | 每修好一題 |
|---|---|---|---|
| Qwen3.5-9B | $0.2547 | $0.0032 | $0.0059 |
| Haiku 5.5 | $0.1587 | $0.0020 | $0.0020 |

Qwen 的每百萬 token 單價比 Haiku 低，但**每修好一題反而貴約 3 倍**：它在沒有 `run_tests` 時花很多步數卻很少修好，有 `run_tests` 時也有一成多是弄壞或假通過。

## 怎麼讀這些數字

**Qwen 沒有 `run_tests` 時為什麼修好率掉這麼多？** 看事件檔，它大部分的步數花在 `grep`：最後 10 步的 400 次工具呼叫中，`grep` 有 393 次、`list_files` 4 次、`read_file` 3 次。它沒有辦法確認自己改對了沒有，就一直搜尋，沒有宣告完成，直到步數用完。所以它的主要失敗模式不是「沒驗證卻宣稱完成」（這一格是 0 次），而是「沒有驗證手段就無法結束」。

**這有一部分是步數上限造成的。** 步數上限 20 是階段 1 訂的初始值，一直沒有用資料校準。我們不知道給它更多步數，它會不會最後宣告完成、宣告時又改對了沒有。所以 25% 比較像「在 20 步內修好」的比例。25% 的 10 次修好，是在步數用完以前就已經改對、只是沒有宣告完成。**後續實驗（見〈後續實驗〉一節）把上限放寬到 40 步，16 次一樣沒有一次宣告完成，這個猜測沒有被證實；反而是改 prompt（實驗 C）讓修好次數大增，原因看起來是它從「只搜尋、不動手改」變成「會動手改」。**

**Qwen 有 `run_tests` 時的 7 次「宣稱完成但沒修好」** 是這次最直接的「假通過」例子：5 次弄壞既有功能、2 次可見測試過了但 bug 還在（兩次都是 calendar）。能自己跑測試，不代表它一定改對。

**Haiku 的結果不能說它「不需要測試」。** 它 160 次中有 80 次都修好、沒有一次需要步數上限，這組題目對它太容易，分不出差別。要看它有沒有幫助，需要更難的題目。

**「沒有 `run_tests`」不等於「看不到測試」。** agent 仍然能用 `read_file` 讀測試檔，只是不能執行它。

## 沒有控制到的條件與限制

- **題目只有 8 題、每格 5 次。** 信賴區間只反映「題目之間的差異」（對題目重抽樣），模型本身的隨機性只透過每題 5 次的比例反映。
- **Haiku 的 temperature 無法設定。** 兩個模型的取樣設定不同，不能直接比較它們的穩定程度。
- **思考模式沿用供應商的預設，沒有關閉。** 不同供應商、不同時間的預設可能不同。
- **供應商只固定在 OpenRouter 的路由層。** 一整個實驗在約一小時內跑完，供應商當下的負載可能影響速度，但不影響評分。
- **只有一個開源模型與一個商用模型。** 不能推論到別的模型。
- **被測的程式與 pytest 在同一個行程，能偽造測試結果。** 評分器只降低這個風險，不能根治（第 16 篇）。這次沒有任何一次的結果被標成 `invalid`。
- **題目是我自己寫的，沒有第三方審題。** 自我檢查只證明題目做對了，不證明題目夠好（第 17 篇）。
- **步數上限 20 沒有校準**（見上）。後續實驗放寬到 40 步也沒有改變 Qwen 的行為，但只測了一個模型、16 次。

## 調整記錄

AGENTS.md 要求任何調整都寫進報告，這裡全部列出：

1. **題數由原本計畫的 15 到 20 題降到 8 題。** 這是在寫任何一題之前決定的（理由：8 題就能展示評估方法，寫題與執行成本低得多），不是看了結果才改。
2. **小規模實跑之後，在完整實驗之前，調整了模型設定**（小規模結果不算在這份報告裡）：Qwen 的供應商由 DeepInfra（bf16）改為 Venice（fp8），因為 DeepInfra 一直回 429 限流，一次執行要 8 到 10 分鐘；改用 Venice 後是 27 到 39 秒。想改用 bf16 的非中國供應商 Parasail，被 OpenRouter 拒絕（它的 Qwen3.5-9B 端點不支援工具呼叫），沒有花費；取消了原本設定的固定 seed（固定 seed 會讓 5 次重跑幾乎相同）。
3. **報告的總表多了「步數用完」一欄**，因為小規模實跑發現 Qwen 在沒有 `run_tests` 時會跑滿步數。
4. **完整實驗開始之後沒有改任何題目、模型設定或程式**；報告沒有題目摘要不一致的警告。沒有排除任何一次執行。
5. 寫題階段（實驗之前）修過一個錯：scheduler 的套件原本叫 `sched`，與標準函式庫同名，自我檢查抓到後改名為 `taskplan`。

## 後續實驗：Qwen 沒有 `run_tests` 時為什麼停不下來（2026-10-18）

第一次實驗之後，我想分開幾個可能的原因：模型被量化得太笨（實驗 A）、步數上限 20 太小（實驗 B）、或 system prompt 沒告訴它沒有測試時該怎麼結束（實驗 C）。這一節是**事後補做的小規模實驗**，A、B 各 16 次、C 32 次，力度比上面的完整實驗低。A、B 在前面，C 在〈調整與紀錄〉之後。

### 做了什麼

兩個實驗各只改一個設定，其餘與第一次實驗相同，對照組取自第一次實驗 Qwen 沒有 `run_tests` 的第 1、2 輪（16 次，Venice fp8，20 步）。

| 項目 | A：量化 | B：步數上限 |
|---|---|---|
| 問的問題 | fp8 換成 bf16，會不會比較懂得停 | 步數上限放寬到 40，會不會自己停 |
| 只改的設定 | 供應商 DeepInfra（bf16）；步數上限仍是 20 | `max_steps` 40；供應商仍是 Venice（fp8） |
| 題目、條件、次數 | 8 題 × `no_tests` × 2 次 = 16 次 | 同左 |
| 模型與其他設定 | `qwen/qwen3.5-9b`，經 OpenRouter，temperature 0.2，思考模式預設（開），不固定 seed，每次最多 8192 個輸出 token，context 262144，macOS 沙箱 | 同左 |
| 單價（每百萬 token 輸入／輸出） | $0.10／$0.15（OpenRouter models API，deepinfra/bf16 端點，2026-10-18） | $0.10／$0.15（venice/fp8 端點，同日） |
| 時間 | 約 12:47 起，總執行時間約 50 分鐘（UTC） | 13:35 到 13:52（UTC），約 17 分鐘 |
| 花費 | 約 $0.067 | 約 $0.169 |
| 原始紀錄 | `runs/stage3-qwen-bf16/` | `runs/stage3-qwen-steps40/` |

兩個實驗的最後幾分鐘有重疊，各走各的供應商，互不影響。

### 結果

| 組別 | 次數 | 自己宣告完成 | 撞到步數上限 | 修好 | 弄壞既有功能 | 假通過 | 沒修好 | 輸入 token | 每次平均秒數 |
|---|---|---|---|---|---|---|---|---|---|
| 對照：fp8、20 步（第一次實驗的前 2 輪） | 16 | 0 | 16 | 4 | 1 | 0 | 11 | 63 萬 | 31 |
| A：bf16、20 步 | 16 | 0 | 16 | 2 | 0 | 1 | 13 | 63 萬 | 188 |
| B：fp8、40 步 | 16 | 0 | 16 | 4 | 0 | 0 | 12 | 163 萬 | 65 |

三組共 48 次，**沒有一次自己宣告完成**，也沒有錯誤、沒有排除任何一次。

- **多給的步數都花在 `grep`。** B 的第 21 到 40 步共 320 次工具呼叫，全部是 `grep`。A 的第 11 到 20 步 160 次裡，`grep` 有 156 次、`list_files` 3 次、`read_file` 1 次，與第一次實驗的 393／400 同一種型態。
- **修好次數（4、2、4）的差異在 16 次的樣本裡不能解讀。**
- **B 花的錢是對照組的 2.6 倍**，因為每一步都要把整段對話重送一次，步數加倍、輸入 token 增加得更多。

### 這代表什麼，不代表什麼

- **排除：量化不是主因。** 換成 bf16 之後 16 次一樣沒有一次停下來。
- **排除：步數上限 20 不是主因。** 放寬到 40 步一樣沒有一次停下來，多出來的步數都花在重複搜尋。所以上面「這有一部分是步數上限造成的」的猜測，在這 16 次裡**沒有被證實**，25% 的修好率不能解釋成「只是步數不夠」。
- **A、B 沒有分開：模型本身，還是 prompt 的停止條件。** system prompt 寫的是「有把握修對了就回覆結束」，沒有測試可以跑時，模型沒有東西能讓自己「有把握」。這需要改 prompt 才能區分，那就是下面的實驗 C。
- **fixlab 目前沒有「同一個呼叫重複太多次」的保險。** 只有「整輪全失敗」才算卡住，重複的 `grep`（回傳都成功）不算失敗，所以會一路跑到步數上限。
- **限制：** 每個實驗 16 次；A 換的是供應商，除了量化之外，DeepInfra 與 Venice 的其他差異也混在裡面；對照組與兩個實驗不是同一時段跑的（第一次實驗在 07:36 到 08:36，這兩個在 12:47 之後，約 4 小時後）；只有一個模型。

### 調整與紀錄

1. **B 需要新功能。** 執行器原本沒有地方設定步數上限，所以先做了 Spectra 變更 `runner-max-steps`（模型設定可寫選填的 `max_steps`），**實驗在功能完成之後才開始**。A 沒用到這個功能。
2. **兩個實驗都用新的模型標籤（`qwen3.5-9b-bf16`、`qwen3.5-9b-steps40`）與新的輸出資料夾**，不會與第一次實驗的 160 次混在一起。
3. **fixlab 版本。** B 的事件檔記錄的是 `6aadd21`。A 的事件檔記錄了 5 個不同的 commit（`d1a5c2e` 到 `4e6451e`），因為 A 在跑的時候，我在同一個工作目錄的功能分支上做了 commit。A 的行程是在 `d1a5c2e` 時啟動的，之後這些 commit 在 `fixlab/` 套件裡只改了 `fixlab/bench/runner.py` 與 `fixlab/bench/report.py`，沒有動迴圈、工具與命令列，所以 agent 的行為不受影響。
4. 沒有改題目與評分，沒有排除任何一次執行。
5. `results.jsonl` 的 SHA-256 開頭：A 是 `099da6493492f2b4`，B 是 `dd2b4ab9ad9b68d2`。

重現：複製 `bench/models.json` 裡 Qwen 的那一筆，A 把標籤改成 `qwen3.5-9b-bf16`、供應商改成 `DeepInfra`、`meta.quantization` 改成 `bf16`；B 把標籤改成 `qwen3.5-9b-steps40` 並加上 `"max_steps": 40`。然後：

```
python -m fixlab.bench run --models 你的設定檔 --out runs/某資料夾 --conditions no_tests --repeats 2 --confirm
```

### 實驗 C：換一個 prompt

**問題：** 沒有 `run_tests` 時，Qwen 是不是因為 prompt 只說「有把握才結束」、沒說沒有測試時該怎麼辦，才一直搜尋？

#### 做了什麼

只改 system prompt：在預設 prompt 後面空一行，接上這一句（兩個條件都接同一句，有 `run_tests` 的條件用來檢查它有沒有害到原本正常的行為）：

> If you have no way to run the tests, do not keep searching for proof. Once you have made the fix, re-read the changed code once, and then reply with a short final message without any tool call.

| 項目 | 設定 |
|---|---|
| 對照 | 第一次實驗的 Qwen 第 1、2 輪：沒有 `run_tests` 與有 `run_tests` 各 16 次（Venice fp8，20 步，預設 prompt） |
| 實驗組 | 同一個模型與設定（`qwen/qwen3.5-9b`，Venice，fp8，temperature 0.2，思考模式預設，不固定 seed，20 步，每次最多 8192 個輸出 token，context 262144，macOS 沙箱），8 題 × 2 個條件 × 2 次 = 32 次 |
| 時間 | 2026-10-18 14:43 到 15:19（UTC），約 36 分鐘 |
| 花費 | 約 $0.126（單價同上：$0.10／$0.15 每百萬 token） |
| fixlab 版本 | 32 次的事件檔都記錄 `a89f042`；實驗進行中沒有 commit |
| 原始紀錄 | `runs/stage3-qwen-rule/`，`results.jsonl` 的 SHA-256 開頭 `cdd6bb7777da4e6c` |

用的是新功能 `system_prompt_extra`（Spectra 變更 `prompt-extra-rule`），它在實驗開始前已完成並通過 code review。預設 prompt 沒有改，所有之前的結果不受影響。

#### 結果

| 組別 | 次數 | 自己宣告完成 | 撞到步數上限 | 修好 | 弄壞既有功能 | 假通過 | 沒修好 | 宣稱完成但沒修好 | 每次平均秒數 | 花費 |
|---|---|---|---|---|---|---|---|---|---|---|
| 沒有 `run_tests`：對照 | 16 | 0 | 16 | 4 | 1 | 0 | 11 | 0 | 31 | $0.068 |
| 沒有 `run_tests`：加了那句 | 16 | 4 | 12 | **13** | 1 | 0 | 2 | 0 | 101 | $0.084 |
| 有 `run_tests`：對照 | 16 | 16 | 0 | 14 | 1 | 1 | 0 | 2 | 20 | $0.035 |
| 有 `run_tests`：加了那句 | 16 | 15 | 1 | 14 | 2 | 0 | 0 | 2 | 41 | $0.042 |

沒有錯誤、沒有排除任何一次。

#### 觀察

- **沒有 `run_tests` 時，修好次數從 4／16 變成 13／16。** 看事件檔，原因是行為變了：對照組 16 次裡有 **11 次從頭到尾沒有呼叫過 `edit_file` 或 `write_file`**，只是一直搜尋；加了那句之後只有 2 次沒有動手改（billing 第 1 次、permissions 第 2 次）。也就是說，原本的主要問題不是「改了卻不敢結束」，而是「根本沒有動手改」。
- **但仍然不太會結束。** 16 次裡只有 4 次自己宣告完成（billing 第 2 次、permissions 第 1 次、subscription 兩次，用了 14 到 16 步，4 次都修好），12 次用完步數。在 14 次有動手改的執行裡（含那 4 次有結束的），第一次修改之後共有 57 次 `read_file`、61 次 `grep`、11 次 `list_files`、7 次再改，也就是它照著「重讀改過的程式」去做，但一直重讀，沒有停。注意：12 次用完步數的執行裡，有 9 次最後的狀態其實已經是修對的，只是模型沒有說它完成了。
- **有 `run_tests` 時沒有看到明顯的傷害。** 修好都是 14／16；弄壞既有功能 1 次變 2 次、假通過 1 次變 0 次、多了 1 次用完步數（settings 第 1 次）。16 次分不出差別。
- **花費。** 沒有 `run_tests` 的組別多花約 $0.016，因為多了動手改與重讀的步驟。

#### 這代表什麼，不代表什麼

- **prompt 是很強的槓桿。** 第一次實驗的結論「Qwen 沒有 `run_tests` 時修好率掉很多」，至少有一大部分是這份 prompt 造成的，不是 Qwen 做不到：告訴它沒有測試時該怎麼辦，它就會動手改，而且多數修對了。
- **但這不能說成「prompt 寫得不好」。** 這句話等於直接叫模型「不要再搜尋、改完就結束」，它證明的是 prompt 能改變行為，不是預設 prompt 在一般情況下是錯的。有 `run_tests` 的條件下預設 prompt 運作得很好。
- **「自己宣告完成」的問題只解決一部分。** 模型多半修對了，但仍然會一直重讀。「重讀一次」這個指示可能本身就讓它進入重讀的迴圈，也可能是 9B 模型不太會遵守「只做一次」；這份資料分不開，要換措辭才能知道。
- **限制：** 每組只有 16 次；對照組是第一次實驗跑的，與實驗組相隔約 7 小時（07:36 到 08:36 與 14:43 到 15:19），供應商的狀況可能不同；只測了一句、一種措辭，也只有一個模型；「修好」是指最後的程式是對的，不代表模型有說它完成了；對照組取的是原本 40 次裡的前 2 輪，不是另外重跑的。

#### 調整與紀錄

1. 沒有改題目、評分、預設 prompt，也沒有排除任何一次執行。
2. 這一句話是**在看到實驗 A、B 的結果之後才決定的**，措辭只用了這一個版本，沒有挑選過或試過別的措辭。
3. 實驗 C 的 `bench/models.json` 設定放在 `runs/stage3-qwen-rule/models.json`（`runs/` 不進版控）；它是 Qwen 的那一筆，標籤改成 `qwen3.5-9b-rule`，加上 `system_prompt_extra`。

重現：複製 `bench/models.json` 裡 Qwen 的那一筆，標籤改成 `qwen3.5-9b-rule`，加上 `"system_prompt_extra": "上面那一句"`，然後：

```
python -m fixlab.bench run --models 你的設定檔 --out runs/某資料夾 --repeats 2 --confirm
```

## 怎麼重現

原始紀錄在 `runs/stage3/`（每次執行的事件檔與 `results.jsonl`，共 160 行；`runs/` 不進版控，檔案含模型的回覆）。`results.jsonl` 的 SHA-256 開頭是 `271bbfad2b1d9c9e`。

```
source .env     # 內含 OpenRouter 的金鑰（變數 OPENAI_API_KEY）
python -m fixlab.bench run --models bench/models.json --out runs/stage3 --confirm
python -m fixlab.bench report runs/stage3/results.jsonl --models bench/models.json
```

重跑會花約 $0.4、約 1 小時，而且因為沒有固定 seed，結果不會一樣，只會是同一個分布的另一組樣本。

我另外用獨立的算法驗算了三個數字，與 `report` 一致：Qwen 有 `run_tests` 的修好次數（33／40）、Haiku 的總成本（$0.1587）、Qwen 的總成本（$0.2547）。

## 附錄：`report` 指令的完整輸出

### 實驗報告（原樣輸出）

#### 實驗設定

- 題目：8 題（billing, calendar, inventory, paging, permissions, scheduler, settings, subscription）
- 條件：with_tests, no_tests
- 每個（題目、模型、條件）的次數：1 到 5；共 160 次執行
- 時間：2026-10-18T07:36:13+00:00 到 2026-10-18T08:36:44+00:00
- 模型 claude-haiku-5.5：anthropic/claude-haiku-5.5，temperature None，extra_body {"provider": {"order": ["Anthropic"], "allow_fallbacks": false}}，紀錄的條件 {"quantization": "not applicable (commercial API)", "runtime": "OpenRouter -> Anthropic", "context_length": "1000000", "thinking": "provider default", "seed": "not fixed (each repeat is an independent sample)"}
- 模型 qwen3.5-9b：qwen/qwen3.5-9b，temperature 0.2，extra_body {"provider": {"order": ["Venice"], "allow_fallbacks": false}}，紀錄的條件 {"quantization": "fp8", "runtime": "OpenRouter -> Venice", "context_length": "262144", "thinking": "provider default (on)", "seed": "not fixed (each repeat is an independent sample)"}

#### 結果總表

| 模型 | 條件 | 執行數 | fixed | broke_existing | overfit | invalid | unfixed | 宣稱完成但沒修好 | 步數用完 | 叫了看不到的工具 | 步數中位數 | prompt token 平均 | completion token 平均 | 錯誤 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | no_tests | 40 | 40 (100%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 | 0 | 0 | 5.0 | 11,609 | 1,408 | 0 |
| claude-haiku-5.5 | with_tests | 40 | 40 (100%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 | 0 | 0 | 6.0 | 15,785 | 1,047 | 0 |
| qwen3.5-9b | no_tests | 40 | 10 (25%) | 2 (5%) | 0 (0%) | 0 (0%) | 28 (70%) | 0 | 40 | 0 | 20.0 | 39,463 | 1,682 | 0 |
| qwen3.5-9b | with_tests | 40 | 33 (82%) | 5 (12%) | 2 (5%) | 0 (0%) | 0 (0%) | 7 | 0 | 0 | 10.0 | 18,986 | 1,797 | 0 |

#### 成本

| 模型 | 總成本 | 每次 | 每修好一題 | 單價（每百萬 token 的輸入／輸出，來源，日期） |
|---|---|---|---|---|
| claude-haiku-5.5 | 0.1587 | 0.0020 | 0.0020 | 0.1 / 0.5，OpenRouter models API, endpoint anthropic，2026-10-18 |
| qwen3.5-9b | 0.2547 | 0.0032 | 0.0059 | 0.1 / 0.15，OpenRouter models API, endpoint venice/fp8，2026-10-18 |

#### 有無 run_tests 的比較（同一題成對）

### claude-haiku-5.5

| 題目 | 有 run_tests 修好比例 | 沒有 run_tests 修好比例 | 差 |
|---|---|---|---|
| billing | 1.00 | 1.00 | +0.00 |
| calendar | 1.00 | 1.00 | +0.00 |
| inventory | 1.00 | 1.00 | +0.00 |
| paging | 1.00 | 1.00 | +0.00 |
| permissions | 1.00 | 1.00 | +0.00 |
| scheduler | 1.00 | 1.00 | +0.00 |
| settings | 1.00 | 1.00 | +0.00 |
| subscription | 1.00 | 1.00 | +0.00 |

平均差 +0.00，95% 區間 [+0.00, +0.00]（對 8 題重抽樣 2000 次，亂數種子 0）

### qwen3.5-9b

| 題目 | 有 run_tests 修好比例 | 沒有 run_tests 修好比例 | 差 |
|---|---|---|---|
| billing | 1.00 | 0.00 | +1.00 |
| calendar | 0.60 | 0.80 | -0.20 |
| inventory | 1.00 | 1.00 | +0.00 |
| paging | 0.20 | 0.00 | +0.20 |
| permissions | 1.00 | 0.00 | +1.00 |
| scheduler | 0.80 | 0.00 | +0.80 |
| settings | 1.00 | 0.00 | +1.00 |
| subscription | 1.00 | 0.20 | +0.80 |

平均差 +0.57，95% 區間 [+0.22, +0.88]（對 8 題重抽樣 2000 次，亂數種子 0）

#### 每題修好的比例

| 題目 | claude-haiku-5.5 with_tests | claude-haiku-5.5 no_tests | qwen3.5-9b with_tests | qwen3.5-9b no_tests |
|---|---|---|---|---|
| billing | 5/5 | 5/5 | 5/5 | 0/5 |
| calendar | 5/5 | 5/5 | 3/5 | 4/5 |
| inventory | 5/5 | 5/5 | 5/5 | 5/5 |
| paging | 5/5 | 5/5 | 1/5 | 0/5 |
| permissions | 5/5 | 5/5 | 5/5 | 0/5 |
| scheduler | 5/5 | 5/5 | 4/5 | 0/5 |
| settings | 5/5 | 5/5 | 5/5 | 0/5 |
| subscription | 5/5 | 5/5 | 5/5 | 1/5 |

#### 失敗實例

### broke_existing

- paging / qwen3.5-9b / with_tests / 第 1 次：done，7 步；工具呼叫：run_tests, read_file, list_files, read_file, edit_file, run_tests；事件檔：runs/stage3/logs/paging-qwen3.5-9b-with_tests-1/20261018T073940Z-qwen-qwen3.5-9b/events.jsonl
- scheduler / qwen3.5-9b / no_tests / 第 2 次：max_steps，20 步；工具呼叫：list_files, grep, read_file, read_file, read_file, edit_file, grep, list_files, read_file, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep；事件檔：runs/stage3/logs/scheduler-qwen3.5-9b-no_tests-2/20261018T075134Z-qwen-qwen3.5-9b/events.jsonl
- paging / qwen3.5-9b / with_tests / 第 3 次：done，7 步；工具呼叫：run_tests, read_file, read_file, edit_file, run_tests；事件檔：runs/stage3/logs/paging-qwen3.5-9b-with_tests-3/20261018T075919Z-qwen-qwen3.5-9b/events.jsonl

### overfit

- calendar / qwen3.5-9b / with_tests / 第 2 次：done，9 步；工具呼叫：run_tests, list_files, read_file, read_file, read_file, edit_file, run_tests；事件檔：runs/stage3/logs/calendar-qwen3.5-9b-with_tests-2/20261018T074628Z-qwen-qwen3.5-9b/events.jsonl
- calendar / qwen3.5-9b / with_tests / 第 5 次：done，9 步；工具呼叫：run_tests, list_files, read_file, read_file, read_file, edit_file, run_tests；事件檔：runs/stage3/logs/calendar-qwen3.5-9b-with_tests-5/20261018T082402Z-qwen-qwen3.5-9b/events.jsonl

### unfixed

- billing / qwen3.5-9b / no_tests / 第 1 次：max_steps，20 步；工具呼叫：grep, read_file, grep, read_file, read_file, grep, read_file, grep, grep, grep, grep, grep, grep, list_files, grep, grep, grep, grep, grep, grep；事件檔：runs/stage3/logs/billing-qwen3.5-9b-no_tests-1/20261018T073629Z-qwen-qwen3.5-9b/events.jsonl
- paging / qwen3.5-9b / no_tests / 第 1 次：max_steps，20 步；工具呼叫：list_files, grep, read_file, read_file, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep；事件檔：runs/stage3/logs/paging-qwen3.5-9b-no_tests-1/20261018T073952Z-qwen-qwen3.5-9b/events.jsonl
- permissions / qwen3.5-9b / no_tests / 第 1 次：max_steps，20 步；工具呼叫：grep, grep, read_file, list_files, read_file, read_file, read_file, grep, grep, list_files, grep, grep, grep, grep, grep, grep, grep, grep, grep, grep；事件檔：runs/stage3/logs/permissions-qwen3.5-9b-no_tests-1/20261018T074103Z-qwen-qwen3.5-9b/events.jsonl

#### 限制

- 題數與次數：這份報告只用了上面列的題目與次數，結果只描述這一組題目，不能推到別的題目或別的模型。
- 被測的程式與 pytest 在同一個行程，可以偽造測試結果（例如印假的摘要再結束）。評分器用固定參數、乾淨環境重跑、只讀最後一行摘要、比對通過數與不自動載入外掛來降低風險，不能根治，所以數字只是降低了這個風險。
- 題數由原本計畫的 15 到 20 題降到 8 題，這項調整是在寫任何一題之前決定的，不是看了結果才改。

