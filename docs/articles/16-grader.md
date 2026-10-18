# 第 16 篇：評分器（修好、假通過、弄壞、無效）

> 對應任務：stage3-benchmark 的 1.3 與 3.1 到 3.4。
> 完成度：完成。

agent 改完一道題之後，要有一個辦法打分數。分數如果不可信，後面所有的比較都沒有意義。這一篇講評分器怎麼做，以及它怎麼分辨四種結果。

## 先試最天真的做法，看它怎麼壞掉

最直覺的做法：在 agent 的工作目錄裡，把隱藏測試放進去，跑 `pytest`，看有沒有全部通過。

它有三個問題：

1. **agent 能影響結果。** 它可以改測試檔，讓失敗的測試變成通過。下面是我真的做的實驗：在庫存題裡，把看得到的測試改成配合現在的（錯的）答案：

   ```
   {"visible_passed": false, "fix_passed": false, "keep_passed": true, "invalid": true, "tampered_files": ["tests/test_stock_report.py"], "outcome": "invalid"}
   ```

   如果評分是用 agent 改過的測試，這次會得到「通過」。評分器改用題目資料夾裡**原版**的測試，所以改過的測試救不了它（`visible_passed` 還是 `false`），而且被記成 `invalid`（無效）。

2. **agent 也能放設定檔。** 例如一個 `pytest.ini` 讓 pytest 跳過失敗的測試，最後還是印出「N passed」。

3. **「通過」只看有沒有印出 passed 的話，少跑幾個測試也能過。** 所以還要確認「跑了多少個測試」。

## 做法：三次獨立評分，每次都在乾淨的暫存目錄

![評分器的流程](images/16-grader-flow.drawio.png)

評分器對 agent 改完的工作目錄做**三次**評分。每一次：

1. 新建一個暫存目錄。
2. 把 agent 的原始碼複製進去，**但不複製測試檔和設定檔**（`pytest.ini`、`pyproject.toml`、`setup.cfg`、`tox.ini`、`conftest.py`）。
3. 放進這一次要用的原版測試：第一次是可見測試，第二次是 `fix` 組，第三次是 `keep` 組。
4. 跑測試，記錄結果，刪掉暫存目錄。

跑測試用的就是 agent 自己用的 `run_tests` 工具，所以兩邊用同樣的 pytest 參數、同樣的沙箱、同樣清理過的環境變數。不另外寫一份，就不會兩邊行為不一致。

**一組測試算「通過」的條件**：`run_tests` 回報通過，而且 pytest 輸出的**最後一行**摘要（例如 `3 passed in 0.02s`）的通過數，剛好等於題目記錄的數量，沒有失敗也沒有錯誤。只看最後一行，是因為被測試的程式可以先自己印一行假的摘要，真的摘要一定在最後。數量要剛好，是為了擋住「用設定檔少跑幾個測試」。

階段 3 還補了一個 `run_tests` 一直留著的缺口：測試行程的環境多了 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，pytest 不再自動載入外掛。原本在專案根目錄放一個名字和外掛相依套件相同的檔案（例如 `trio.py`），有機會在外掛載入時被搶先執行。同時固定了 `TZ=UTC` 和 `PYTHONHASHSEED=0`，讓測試結果不依賴機器的時區與集合的順序。這三項加在 agent 自己的測試執行上，兩邊一致。

## 四個旗標，加一個固定的判定順序

評分器先量四件事：

| 旗標 | 意思 |
|---|---|
| `visible_passed` | 可見測試（原版）全過了嗎 |
| `fix_passed` | `fix` 組全過了嗎（bug 修好了嗎） |
| `keep_passed` | `keep` 組全過了嗎（原本正常的功能還正常嗎） |
| `invalid` | agent 的工作目錄裡，有測試檔或設定檔與原版不同、或原版沒有 |

再推出一個總結 `outcome`，依這個順序找第一個成立的：

![判定的順序](images/16-outcome-order.drawio.png)

下面是我對庫存題做的五種結果，真的跑 `grade` 的輸出：

| 這個結果是怎麼來的 | 輸出 |
|---|---|
| 標準解 | `visible true, fix true, keep true, invalid false` → **fixed** |
| 什麼都沒改 | `visible false, fix false, keep true, invalid false` → **unfixed** |
| 只對螺絲寫死答案 | `visible true, fix false, keep true, invalid false` → **overfit** |
| 箱修好了，但不認識的品號改成會出錯 | `visible true, fix true, keep false, invalid false` → **broke_existing** |
| 把測試改成配合錯的答案 | `visible false, fix false, keep true, invalid true` → **invalid** |

為什麼是這個順序？

- **`invalid` 最優先。** 動了測試或設定檔，後面的旗標再好看也不可信。
- **`broke_existing` 先於 `fixed`。** 弄壞了原本正常的功能，就不能算修好。
- **`broke_existing` 先於 `overfit`。** 兩個都成立時，弄壞的問題比較嚴重。三個旗標都照實記錄，所以要分開統計時，兩個旗標仍然各自有值。

沒有 `run_tests` 的條件下，agent 看不到測試結果，所以「假通過」不能用「可見測試過了」來定義。第 18 篇會另外記一個「宣稱完成但隱藏測試沒過」（`claimed_done_but_failed`）。

## 自己跑一次

評分器的指令是：

```
python -m fixlab.bench grade inventory <agent 改完的工作目錄>
```

例如把題目的 `project` 複製一份，套上標準解，再評分：

```
cp -r bench/problems/inventory/project /tmp/try
cp bench/problems/inventory/solution/stock/importer.py /tmp/try/stock/importer.py
python -m fixlab.bench grade inventory /tmp/try
```

輸出是一個 JSON，`outcome` 是 `fixed`。

## 名詞表

| 詞 | 意思 |
|---|---|
| 乾淨的暫存目錄 | 每次評分新建、只放 agent 的原始碼與原版測試的目錄，用完就刪 |
| 旗標 | 一個真或假的測量結果，例如 `fix_passed` |
| `outcome` | 由旗標依固定順序推出的總結：`invalid`、`broke_existing`、`fixed`、`overfit`、`unfixed` |
| 假通過（`overfit`） | 可見測試過了，但 bug 沒修好 |
| 無效（`invalid`） | agent 動了測試檔或設定檔 |

## 已知限制

被測試的程式和 pytest 在同一個行程裡，所以它**有辦法偽造結果**（例如註冊一個結束時才執行的函式，印出假的摘要再以 0 離開）。評分器用「最後一行摘要、數量要剛好、不自動載入外掛、固定參數」降低這個風險，但沒有根治。真要根治，得把被測的程式和測試放在不同的行程，那是另一個大工程。結果報告會把這點寫在限制裡。

## 下一篇

題目自我檢查：怎麼證明每一道題做對了，而且量得到我想量的東西。
