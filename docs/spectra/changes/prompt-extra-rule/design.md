## Context

system prompt 目前是 `fixlab/loop.py` 裡的一個常數，`run_agent` 在對話是空的時候把它放進第一則訊息。沒有任何地方可以在不改這個常數的情況下加一句話。實驗 A、B 之後，要分開「模型本身」和「prompt 的停止條件」，只能改 prompt、其他條件不動。

涉及四個模組：迴圈（組 system prompt）、命令列（選項、檢查、記錄）、執行器（讀模型設定、傳選項）、報告（顯示設定）。它們串成一條線，每個模組只多一小段，所以值得先把決定寫下來。

## Goals / Non-Goals

**Goals:**

- 能在不改預設 prompt 的情況下，替某個模型的每次執行加一段 system prompt 文字。
- 這段文字一定會被記錄（事件檔的 `run_start`、報告的實驗設定），之後看得出是哪個 prompt 跑的。
- 沒用這個功能時，送出的請求與現在一個字都不差。

**Non-Goals:**

- 不改預設 system prompt；不做從檔案讀 prompt、多段規則、整份替換。
- 不在這個變更裡跑實驗 C。
- 不處理「重複呼叫的保險」。

## Decisions

### 接在預設 prompt 後面，不整段替換

加一個 `--system-prompt-extra`，把文字接在預設 prompt 後面（中間空一行）。替代方案是 `--system-prompt` 整段替換：這樣每次實驗都得貼整份 prompt，很容易順手改到預設裡的其他句子，變因就不只一個。附加的好處是對照組與實驗組只差「這一段」，讀者一眼看得出差在哪。

### 放在模型設定檔，不放 `run` 指令

和 `max_steps` 一樣，寫成模型設定的選填欄位 `system_prompt_extra`。替代方案是 `run --system-prompt-extra`：會讓這次 `run` 的所有模型共用同一段，而且文字只出現在命令列、不會跟其他設定一起留在檔案裡。放在設定檔，一個檔案就描述完整的實驗條件，用不同標籤就能並排比較（例如 `qwen3.5-9b` 與 `qwen3.5-9b-rule`）。

### 兩個條件傳同一段文字

有沒有 `run_tests` 的兩個條件都收到同一段。既有規格要求兩個條件只差工具；文字寫成「如果沒有辦法跑測試……」，在有 `run_tests` 的條件下只是一句用不到的話，也能順便檢查它有沒有害到原本正常的行為。

### 空字串視為錯誤，不是「沒給」

`--system-prompt-extra ""` 或只有空白會以退出碼 2 結束。替代方案是當成沒給：但最可能的來源是 shell 變數沒設（`--system-prompt-extra "$RULE"`），悄悄用預設 prompt 跑完實驗，會讓人以為自己測了 prompt 其實沒有。和 `--extra-body` 不合法時的處理一致：寧可一開始就停。

### 由 `run_agent` 的新參數組 prompt，不由命令列組好再傳 `messages`

`run_agent(..., system_prompt_extra=None)`：迴圈自己決定 system message 的內容。替代方案是命令列先組出 system message、放進 `messages` 傳進去：互動模式的第一個任務和一次性模式都要各自處理，prompt 的組法散在兩處。參數只在「這次要放入 system prompt」時有效（對話是空的），對話已經有內容時不動它，避免第二則 system 訊息。

## Implementation Contract

- **Behavior：** 給了 `--system-prompt-extra TEXT`，每個任務的第一個請求的 system message 是「預設 prompt、一個空行、TEXT」；沒給，與現在相同。模型設定檔的 `system_prompt_extra` 讓執行器為該模型的每次執行（兩個條件）傳同一段。報告的實驗設定一節在每個模型那一行顯示它。
- **Interface／資料形狀：** 命令列選項 `--system-prompt-extra TEXT`；`run_agent` 的關鍵字參數 `system_prompt_extra`（預設 None）；`run_start` 的鍵 `system_prompt_extra`（字串或 null）；`ModelConfig.system_prompt_extra`；模型設定檔的選填欄位 `system_prompt_extra`；報告的設定行多一段 `system_prompt_extra <文字或 無>`。
- **Failure modes：** 命令列的值為空或只有空白：退出碼 2、訊息點名選項、不建立任何檔案。模型設定的值不是「至少有一個非空白字元的字串」也不是 null：設定錯誤，訊息有模型標籤與值，一次都不跑。
- **Acceptance：** 黃金 trace 測試仍通過（沒給時請求不變）；新增的測試涵蓋規格裡每個情境與範例表；完整測試通過；`spectra validate` 與 `spectra analyze` 沒有 Critical 與 Warning。
- **Scope：** 範圍內：`run_agent`、命令列、`run_start`、執行器的模型設定與參數、報告的設定行、README。範圍外：預設 prompt、事件檔 schema 版本、實驗 C 的執行與結果、重複呼叫的保險。

## Risks / Trade-offs

- **措辭會影響結果。** 實驗 C 的那句話等於直接叫模型停下來。如果它停了，只說明「prompt 能讓它停」，還要看停下來之後修對了沒有（修好率、宣稱完成但沒修好的次數），才能說這是好的停止。
- **對照組不是同一時段。** 實驗 C 的對照取自第一次實驗的前 2 輪，供應商的負載或行為可能不同；報告要寫明。
- **文字從命令列傳進來，沒有長度限制。** 這個專案只在實驗裡用它，由執行器在程式內部傳參數（不經 shell），不需要處理跳脫；人從終端機傳很長的文字時，shell 的引號要自己負責。
- **檢查「有看得見的字」寫了兩份。** 命令列（`fixlab/cli.py`）與模型設定（`fixlab/bench/runner.py`）各有一個函式，述詞相同、錯誤型別不同。目前行為一致；之後若要改規則（例如也拒絕控制字元），兩處要一起改。code review 第一輪列為建議，延後。
