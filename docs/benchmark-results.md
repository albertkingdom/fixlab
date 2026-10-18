# 階段 3 實驗結果（2026-10-18）

> 這份文件記錄階段 3 第一次完整實驗的結果。**所有結論都只是「在這組題目上觀察到」**，不能推到別的題目或別的模型。數字都能由原始結果檔用 `report` 指令重現（見最後的「怎麼重現」）。

## 一句話看結果

- **Qwen3.5-9B：能自己跑測試，修好率從 25% 提高到 82%。** 同一題成對比較的平均差是 +0.57，95% 區間 [+0.22, +0.88]。
- **沒有 `run_tests` 時，Qwen 不是「亂宣稱修好了」，而是「一直不敢結束」。** 40 次執行全部跑滿 20 步、沒有一次宣告完成；最後 10 步的工具呼叫有 393／400 是 `grep`。
- **Claude Haiku 5.5：兩個條件都是 80／80 修好。** 這組題目對它太容易，看不出有沒有 `run_tests` 的差別。

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

**這有一部分是步數上限造成的。** 步數上限 20 是階段 1 訂的初始值，一直沒有用資料校準。我們不知道給它更多步數，它會不會最後宣告完成、宣告時又改對了沒有。所以 25% 比較像「在 20 步內修好」的比例。25% 的 10 次修好，是在步數用完以前就已經改對、只是沒有宣告完成。

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
- **步數上限 20 沒有校準**（見上）。

## 調整記錄

AGENTS.md 要求任何調整都寫進報告，這裡全部列出：

1. **題數由原本計畫的 15 到 20 題降到 8 題。** 這是在寫任何一題之前決定的（理由：8 題就能展示評估方法，寫題與執行成本低得多），不是看了結果才改。
2. **小規模實跑之後，在完整實驗之前，調整了模型設定**（小規模結果不算在這份報告裡）：Qwen 的供應商由 DeepInfra（bf16）改為 Venice（fp8），因為 DeepInfra 一直回 429 限流，一次執行要 8 到 10 分鐘；改用 Venice 後是 27 到 39 秒。想改用 bf16 的非中國供應商 Parasail，被 OpenRouter 拒絕（它的 Qwen3.5-9B 端點不支援工具呼叫），沒有花費；取消了原本設定的固定 seed（固定 seed 會讓 5 次重跑幾乎相同）。
3. **報告的總表多了「步數用完」一欄**，因為小規模實跑發現 Qwen 在沒有 `run_tests` 時會跑滿步數。
4. **完整實驗開始之後沒有改任何題目、模型設定或程式**；報告沒有題目摘要不一致的警告。沒有排除任何一次執行。
5. 寫題階段（實驗之前）修過一個錯：scheduler 的套件原本叫 `sched`，與標準函式庫同名，自我檢查抓到後改名為 `taskplan`。

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

