---
name: add-bench-problem
description: "新增或修改 fixlab 的 benchmark 題目：題目資料夾結構（project、solution、hidden/fix、hidden/keep、problem.json）、設計原則（失敗輸出不能點名 bug 檔、README 寫出正確行為、要有干擾檔、不依賴環境）、註冊到 EXPECTED_IDS、用 fixlab.bench check 自我檢查，以及題集變動對既有實驗結果與 README 數字的影響。當使用者說「新增題目」「加一題 benchmark」「改題目」「寫 bug 題」「題目 check 沒過」，或要擴充或調整 bench/problems 時使用。"
---

# 新增 benchmark 題目

題目是這個專案的量尺。**題集一變，既有的實驗數字就不再描述同一把尺。** 先讀完「題集變動的後果」再動手。

## 題集變動的後果（先和使用者確認）

- 題集固定為 8 題（`fixlab/bench/problems.py` 的 `EXPECTED_IDS`）。README 與 `docs/benchmark-results.md` 的所有結論（例如「這組 8 題」、修好率、95% 區間）都只適用那 8 題。
- 新增一題等於**新的題集**：舊結果仍屬於舊的 8 題，**不能和含新題的結果混在一起，也不能直接把「8 題」改成「9 題」**。要重跑完整實驗（`bench run --confirm`，花錢）才有新題集的數字，這由使用者決定。
- AGENTS.md 守則 4：**不為了讓數字好看而調整題目或切分。** 看過模型在某題的表現之後才改那一題，或才決定加哪一題，都是在挑題。新題要在看到任何模型結果之前寫好、定案，並把「為什麼加、什麼時候加、有沒有看過結果」寫進 `docs/benchmark-results.md`。
- 這件事需要 Spectra change（`/spectra-propose`），因為 `benchmark-problems` 規格涵蓋題目與題數。

## 邊界

- **原創**（守則 7）：不複製他人的題目、專案配置或 bug 類型（包含 SWE-bench 等公開題庫、教學文章裡的範例）。設計依據要寫是自己想的，或來自自己實驗發現的缺口。
- 不呼叫模型：題目的驗證用 `fixlab.bench check`，不花錢。**不要為了「試試看題目難不難」去跑 `bench run --confirm`。**
- 不提交 `__pycache__`、`.pytest_cache`。

## 先看現有題目，避免重複

```bash
for f in bench/problems/*/problem.json; do python3 -c "import json,sys; d=json.load(open('$f')); print(d['id'], '|', d['domain'], '|', d['bug_type'])"; done
```

新題的 `bug_type` 與領域要和現有 8 題不同，才增加量尺的涵蓋面；若是故意做同類不同難度，要在提案寫明理由。

## 資料夾結構

```
bench/problems/<id>/
  problem.json        id（必須等於資料夾名）、domain、bug_type、bug_files、distractors、visible、hidden
  project/            給 agent 的專案：原始碼套件、README（規格）、tests/（可見測試）
  solution/           標準解：只放「有改動的檔案」，覆蓋在 project 上
  hidden/fix/         隱藏測試：bug 真的修好了嗎
  hidden/keep/        隱藏測試：原本正常的功能還正常嗎
```

agent 只會拿到 `project` 的副本；`hidden/` 與 `solution/` 永遠不在它看得到的路徑裡。

`problem.json` 範例（`billing`）：

```json
{
  "id": "billing",
  "domain": "金額",
  "bug_type": "例外被吞掉",
  "bug_files": ["bill/discounts.py"],
  "distractors": ["bill/rounding.py", "bill/prices.py"],
  "visible": {"total": 2, "failing": 1},
  "hidden": {"fix": 3, "keep": 3}
}
```

`visible.total`／`failing` 與 `hidden.fix`／`keep` 是**測試數量**，必須和實際一致（自我檢查會比對）。

## 設計原則

1. **README 寫出正確行為。** `project/README.md` 說明公開入口、規則與邊界情況，讓人（和 agent）不看 bug 也能知道「對的行為是什麼」。隱藏的 fix 測試驗證的行為必須在 README 找得到依據，不能考 README 沒寫的事。
2. **失敗輸出不能點名 bug 檔。** 原始專案的可見測試失敗時，輸出裡不能出現 `bug_files` 的檔名（自我檢查會擋）。斷言要寫成看結果的形式，不要讓 traceback 直接指到錯誤位置；否則題目變成「照 traceback 改」而不是「找 bug」。
3. **至少一個可見測試失敗**，可見測試通過的部分覆蓋正常功能，讓 agent 有可以跑的回饋。（靠人工判斷；自我檢查只比對 `problem.json` 記的失敗數，不要求它大於零。）
4. **有干擾檔。** `distractors` 列出與 bug 看起來相關、但沒有 bug 的檔案（例如 `rounding.py`、`prices.py`）。（靠人工判斷；自我檢查只確認列出的路徑存在，不要求非空。）
5. **fix 與 keep 各自要有意義**：fix 測試在原始專案必須至少一個失敗、套上標準解後全過；keep 測試在兩種情況都全過，用來抓「修好 A 弄壞 B」。
6. **不依賴執行環境。** 不依賴時區、語系、目前時間、隨機數、檔案系統順序。需要時間就寫死偏移或傳入固定值。
7. **標準解要最小**：只放有改動的檔案；不要順手重構，否則「標準解」變成「重寫」。
8. 專案要小（現有 8 題的非測試 `.py` 檔約 5 到 7 個），測試要快（整個題目的 `check` 要能重跑 20 次）。

## 步驟

1. 在 Spectra 提案寫明：題目要量什麼、`bug_type`、為什麼和現有題不同、不做什麼（Non-goals），以及上面「題集變動的後果」的處理方式。
2. 建立資料夾與檔案（見結構）。先寫 `project` 與 `solution`，再寫測試。
3. **註冊**：把 `<id>` 加進 `fixlab/bench/problems.py` 的 `EXPECTED_IDS`。沒註冊會被自我檢查當成 `extra`，註冊了卻缺資料夾會被當成 `missing`。
4. 自我檢查（不花錢）：

   ```bash
   .venv/bin/python -m fixlab.bench check <id>            # 預設重跑 20 次，確認不 flaky
   .venv/bin/python -m fixlab.bench check                 # 全部題目
   ```

   檢查項目：路徑都存在；原始專案的可見失敗數、fix 至少一個失敗、keep 全過、各組數量與 `problem.json` 一致；套上標準解後三組全過；重跑結果完全一樣；失敗輸出不點名 bug 檔。有一項沒過就修題目，不要改檢查。
5. 跑 fixlab 自己的測試：`.venv/bin/python -m pytest -q`。多數 benchmark 測試用 `tests/fixtures/bench_toy` 的玩具題目，不受正式題集影響；若有測試因題目清單或題數失敗，**先讀失敗訊息再改**，確認是「題數從 8 變 9」的合理更新，不是弄壞了別的東西。
6. 同步文件：題數出現在 `fixlab/bench/problems.py` 的註解與 `EXPECTED_IDS`、`AGENTS.md`（「8 題左右」「8 個 benchmark 題目」）、`fixlab/bench/report.py` 的 `LIMITS`（寫死「降到 8 題」，會輸出到報告）與 `tests/test_bench_report.py` 鎖定它的斷言、`fixlab/bench/__main__.py` 與 `selfcheck.py` 的註解和 docstring、規格 `benchmark-problems`（"exactly the eight problems"，這要走 Spectra change 改）、`tests/test_bench_selfcheck.py` 的測試名稱（`..._exactly_the_eight_problems`）、`docs/benchmark.md`（「8 道題」）、`docs/safety.md`、`docs/development.md`（教學文章表的「8 道有 bug 的小專案」）。`README.md` 與 `docs/benchmark-results.md` 中的「8 題」只在**重跑實驗並有新結果之後**才改；在那之前，結果報告加一段說明「題集已增加，這份數字仍是原 8 題」。教學文章 15 到 20 描述了題目、評分、自我檢查與實驗結果，題目數量或規則變了要提醒使用者文章是否需要更新（`article-NN` tag 只建在本機，不自動推送）。
7. 走完整流程：`project-review`（含 `bench` 區域的檢查清單）→ `review-findings` → `create-pr`。

## 修改既有題目

改題目會改變 `problem_digest`（內容摘要），也就是舊結果所對應的題目版本。已有實驗結果的題目**原則上不改**；非改不可（例如發現題目有錯），要在 `docs/benchmark-results.md` 記錄改了什麼、為什麼、在看過哪些結果之後改的，並說明舊結果是否還有效。

## 回報

```
新增／修改題目：<id>
- 量什麼：<bug_type>，與現有題的差異：<...>
- 自我檢查：check <id> 通過（重跑 <n> 次）；全部題目通過／未通過
- 測試：pytest <通過數>；更新了哪些題數相關的斷言
- 題集變動：舊結果的處理方式；README 與結果報告是否已加說明
- 沒做：沒有呼叫模型、沒有重跑實驗
```
