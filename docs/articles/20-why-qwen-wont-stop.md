# 第 20 篇：Qwen 沒有測試時為什麼停不下來

> 對應變更：Spectra 的 `runner-max-steps` 與 `prompt-extra-rule`，以及 `docs/benchmark-results.md` 的〈後續實驗〉。
> 完成度：完成。三個小實驗共 64 次，0 次錯誤，沒有排除任何一次。

**這一篇的實驗比第 19 篇小很多**（A、B 各 16 次，C 32 次），所有結論都只是「在這 8 題、這一個模型上觀察到」。

## 問題從哪裡來

第 19 篇最意外的結果：Qwen3.5-9B 沒有 `run_tests`（執行測試的工具）時，**40 次全部跑滿 20 步，沒有一次自己宣告完成**。最後 10 步的工具呼叫幾乎都是 `grep`。

「停不下來」有幾種可能的原因：

| 猜測 | 怎麼檢查 | 實驗 |
|---|---|---|
| 模型被量化得太笨 | fp8 換成 bf16 | A |
| 步數上限 20 太小 | 放寬到 40 步 | B |
| system prompt 沒說沒有測試時該怎麼結束 | 在 prompt 後面加一句 | C |

每個實驗**只改一個設定**，其他與第一次實驗相同。對照組取第一次實驗裡 Qwen 沒有 `run_tests` 的第 1、2 輪，共 16 次。

（量化：把模型的數字存成比較少的位元，省記憶體也省錢，但可能變笨。fp8 是 8 位元，bf16 是 16 位元。）

## 先試最天真的做法：給它更多步數

最直覺的想法：它不是不會停，是步數不夠，還沒找完。那就給它 40 步。

要做這件事，執行器得先能設定步數上限。原本的 `bench/models.json`（實驗用的模型設定）沒有這個欄位，所以先做了 `runner-max-steps`：模型設定可以多寫一個選填的 `max_steps`。

```json
{"label": "qwen3.5-9b-steps40", "name": "qwen/qwen3.5-9b", "max_steps": 40, ...}
```

執行器把它轉成 fixlab 的命令列參數，兩個條件傳同一個值，讓「有沒有 `run_tests`」仍然是兩個條件唯一的差別：

```python
if model.max_steps is not None:  # 沒寫就不傳，fixlab 用自己的預設；兩個條件都傳同一個值
    arguments += ["--max-steps", str(model.max_steps)]
```

結果：

| 組別 | 次數 | 自己宣告完成 | 撞到步數上限 | 修好 | 輸入 token | 花費 |
|---|---|---|---|---|---|---|
| 對照：fp8、20 步 | 16 | 0 | 16 | 4 | 63 萬 | 約 $0.068 |
| B：fp8、40 步 | 16 | 0 | 16 | 4 | 163 萬 | 約 $0.169 |

**多給的 20 步，320 次工具呼叫全部是 `grep`。** 沒有一次停下來，修好的次數也一樣。

花費卻變成約 2.6 倍。原因是 agent 每一步都要把整段對話重送給模型一次：步數加倍，每一步送的對話也越來越長，所以輸入 token 增加得比步數還多。

**這個天真做法失敗了**，第 19 篇「25% 可能只是步數不夠」的猜測，在這 16 次裡沒有被證實。

## 第二個猜測：是量化讓它變笨

Qwen 在 OpenRouter（一個轉接多家模型供應商的服務）上經 Venice 供應，用的是 fp8。換成提供 bf16 的 DeepInfra，步數維持 20：

| 組別 | 次數 | 自己宣告完成 | 撞到步數上限 | 修好 | 每次平均秒數 |
|---|---|---|---|---|---|
| 對照：fp8 | 16 | 0 | 16 | 4 | 31 |
| A：bf16 | 16 | 0 | 16 | 2 | 188 |

一樣沒有一次停下來。最後 10 步的 160 次呼叫裡 156 次是 `grep`，和第一次實驗是同一種樣子。修好次數 4 對 2，在 16 次裡分不出差別。

這個實驗不只換了量化，也換了供應商，所以兩家的其他差異（例如速度慢了 6 倍）都混在裡面。但「完全不停」這件事沒有改變，所以**量化不是主因**。

這個實驗不需要新功能：供應商本來就能用 `extra_body` 指定（第 18 篇）。

## 第三個猜測：prompt 沒告訴它怎麼結束

fixlab 的 system prompt 說：有把握修對了，就回覆結束。有 `run_tests` 時，「測試過了」就是把握；沒有 `run_tests` 時，模型沒有任何東西能讓自己有把握。

所以試一句話，接在預設 prompt 後面：

> If you have no way to run the tests, do not keep searching for proof. Once you have made the fix, re-read the changed code once, and then reply with a short final message without any tool call.

**預設 prompt 不改**，之前所有結果都不受影響。為此做了 `prompt-extra-rule`：fixlab 多一個 `--system-prompt-extra TEXT` 參數，模型設定多一個選填的 `system_prompt_extra`。迴圈裡只有三行：

```python
prompt = SYSTEM_PROMPT
if system_prompt_extra is not None:
    prompt = SYSTEM_PROMPT + "\n\n" + system_prompt_extra
```

**兩個條件都加同一句。** 有 `run_tests` 的那組用來檢查：這句話會不會害到原本正常的行為。

| 組別 | 次數 | 自己宣告完成 | 撞到步數上限 | 修好 | 弄壞既有功能 | 假通過 |
|---|---|---|---|---|---|---|
| 沒有 `run_tests`：對照 | 16 | 0 | 16 | 4 | 1 | 0 |
| 沒有 `run_tests`：加了那句 | 16 | 4 | 12 | **13** | 1 | 0 |
| 有 `run_tests`：對照 | 16 | 16 | 0 | 14 | 1 | 1 |
| 有 `run_tests`：加了那句 | 16 | 15 | 1 | 14 | 2 | 0 |

### 修好次數從 4 變 13，原因是它開始動手改

看事件檔（第 12 篇的 JSONL 紀錄）才知道真正的問題：對照組 16 次裡，**有 11 次從頭到尾沒有呼叫過 `edit_file` 或 `write_file`**。它不是「改了卻不敢結束」，是**根本沒有動手改**，一直在找證據。

加了那句之後，只剩 2 次沒有動手改。

### 但它仍然不太會結束

16 次只有 4 次自己宣告完成，12 次還是用完步數。在有動手改的 14 次裡，第一次修改之後共有 57 次 `read_file`、61 次 `grep`。它照著「重讀改過的程式」去做，但一直重讀，沒有停在「一次」。

而且 12 次用完步數的執行裡，**有 9 次最後的程式其實已經是對的**，只是模型沒有說它完成了。

### 有 `run_tests` 時沒有看到明顯的傷害

修好都是 14／16。弄壞既有功能多 1 次、假通過少 1 次，16 次分不出差別。

## 三個實驗合起來

```
不停下來的原因？
├─ 量化太低     → A：bf16 也 0／16 停下來        → 排除
├─ 步數太少     → B：40 步也 0／16 停下來        → 排除
└─ prompt 沒講  → C：開始動手改，修好 4 → 13      → 大部分是它
                     但只有 4／16 自己停下來        → 結束的問題只解一半
```

## code review 抓到的兩個 bug

`prompt-extra-rule` 在跑實驗 C 之前做了 code review（AGENTS.md 的規定）。抓到兩個問題，都是「傳一段任意文字」才會碰到的。

### bug 一：以 `-` 開頭的文字被當成另一個選項

執行器原本這樣傳：

```python
arguments += ["--system-prompt-extra", model.system_prompt_extra]
```

argparse（Python 內建的命令列解析）看到一個以 `-` 開頭的參數，會猜它是不是另一個選項。實際跑一次：

```
'- Never edit tests.' -> '- Never edit tests.'
'--terse' -> SystemExit 2
fixlab: error: argument --system-prompt-extra: expected one argument
```

有空白的 `- Never edit tests.` 沒事（argparse 看到空白就當它是一般文字），沒有空白的 `--terse` 就失敗。

更糟的是後果：執行器在同一個行程裡呼叫 fixlab 的 `main()`，argparse 失敗會丟出 `SystemExit`，**整個實驗在第一次執行就中止**，而不是只記一次錯誤。

修法：用 `=` 連成一個參數，argparse 就不會再猜。

```python
# 用 = 連成一個參數：文字以 - 開頭時，分開傳會被 argparse 當成另一個選項，整個實驗當場中止
arguments += [f"--system-prompt-extra={model.system_prompt_extra}"]
```

`--system-prompt-extra=--terse` 會得到 `'--terse'`。先補了一個用 `-Finish` 的測試，看它失敗，再修。

### bug 二：有換行的文字把報告切成好幾行

報告的「實驗設定」每個模型一行，原本直接把文字放進去。文字有換行時：

```
- 模型 x：max_steps 預設，system_prompt_extra Rule one.
Rule two.，紀錄的條件 {}
```

一行變兩行，後面的欄位跑到下一行，看起來像是另一筆設定。改成用 `json.dumps` 顯示，和 `extra_body`、`meta` 的顯示方式一樣：

```
- 模型 x：max_steps 預設，system_prompt_extra "Rule one.\nRule two."，紀錄的條件 {}
```

換行變成 `\n`，前後有沒有多餘的空白也看得出來。

**兩個 bug 都不會在實驗 C 發生**（那句話不是 `-` 開頭，也沒有換行）。但這個功能就是讓人放任意文字做 prompt 實驗，下一句話就可能碰到。

## 這代表什麼，不代表什麼

- **prompt 是很強的槓桿。** 第 19 篇「Qwen 沒有 `run_tests` 時修好率掉很多」，至少有一大部分是 prompt 造成的，不是 Qwen 做不到。
- **不能說預設 prompt 寫得不好。** 那句話等於直接叫它「改完就結束」。有 `run_tests` 時，預設 prompt 運作得很好。
- **「自己結束」只解決一部分。** 可能是「重讀一次」這個指示本身讓它進入重讀的迴圈，也可能是 9B 模型不太會遵守「只做一次」。這份資料分不開，要換措辭才知道。
- **fixlab 沒有「重複同一個呼叫太多次」的保險。** 第 11 篇的保險只算「整輪全失敗」，而重複的 `grep` 每次都成功，所以一路跑到步數上限。

## 限制

- 每組只有 16 次；只有一個模型。
- 對照組是第一次實驗的前 2 輪，不是另外重跑的，與 A、B、C 相隔 4 到 7 小時，供應商的狀況可能不同。
- A 換的是供應商，量化以外的差異混在裡面。
- C 只試了一句、一種措辭。這句話是**看到 A、B 的結果之後才決定的**，沒有試過別的措辭再挑。
- 沒有固定 seed。
- 「修好」是指最後的程式是對的，不代表模型有說它完成了。

三個實驗共花約 $0.36。完整的設定（時間、單價、fixlab 版本、`results.jsonl` 的雜湊）在 `docs/benchmark-results.md` 的〈後續實驗〉。

## 自己跑一次

複製 `bench/models.json` 裡 Qwen 的那一筆，改標籤，再依實驗加上設定：

| 實驗 | 改的地方 |
|---|---|
| A | 供應商改成 `DeepInfra`，`meta.quantization` 改成 `bf16` |
| B | 加上 `"max_steps": 40` |
| C | 加上 `"system_prompt_extra": "上面那一句"` |

```
source .env
# A、B 只跑沒有 run_tests 的條件
python -m fixlab.bench run --models 你的設定檔 --out runs/某資料夾 --conditions no_tests --repeats 2 --confirm
# C 兩個條件都跑
python -m fixlab.bench run --models 你的設定檔 --out runs/某資料夾 --repeats 2 --confirm
```

## 名詞表

| 詞 | 意思 |
|---|---|
| 量化 | 用比較少的位元存模型的數字；fp8 是 8 位元，bf16 是 16 位元 |
| 供應商 | 實際跑模型的公司；OpenRouter 會轉給其中一家 |
| 對照組 | 不改任何設定的那一組，用來和實驗組比較 |
| 撞到步數上限 | agent 沒有宣告完成，直到步數用完才被迫停下 |
| 宣告完成 | 模型回覆一段沒有工具呼叫的訊息，迴圈因此結束 |
| `system_prompt_extra` | 接在預設 system prompt 後面的實驗文字，中間空一行 |

## 下一步可以做什麼（還沒做）

- 換「重讀一次」的措辭，看能不能讓它自己結束。
- 加一個「同一個呼叫重複太多次」的保險，並先用資料決定「太多」是多少。
- 用別的小模型重跑 C，看是不是 Qwen 獨有。

## 參考

這一篇的設計依據都是 fixlab 自己的實驗與事件檔。
