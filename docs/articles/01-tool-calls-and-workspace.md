# 第 1 篇：模型說要呼叫工具，程式怎麼接住

> 對應任務：bootstrap-agent-core 的 2.1、2.2（tool call 解析）與 3.1（Workspace 路徑守門與分派）。
> 完成度：兩個模組與測試都已完成（`pytest` 21 個通過）。把工具登記表轉成給模型看的清單（`tool_specs()`）是 3.2，還沒做。

agent 的核心是「模型決定下一步，程式負責執行」。模型只會回一段訊息，裡面可能帶著「我要呼叫 `read_file`，參數是 `path=a.py`」這樣的請求，這個請求叫 **tool call**。程式要做三件事：認出請求、檢查它合不合理、安全地執行。

```
模型的回覆 ──► 解析（toolparse.py） ──► 執行（workspace.py） ──► 結果送回給模型
              認出呼叫、檢查格式        檢查路徑、執行工具、不丟例外
```

這一篇從最天真的寫法開始，看它怎麼壞，再一層一層補成現在的兩個模組。

## 先寫一個最天真的版本

只看 API 回覆裡的 `tool_calls` 欄位，路徑直接 `open`：

```python
def parse_naive(message):
    return [(tc.function.name, json.loads(tc.function.arguments)) for tc in message.tool_calls or []]

def read_file(path):
    return open(os.path.join(root, path)).read()

# 迴圈裡：calls = parse_naive(msg)；沒有 calls 就當模型說完了，有就 tools[name](**args)
```

正常情況下它能動。下面是我實際執行它的結果。

**解析**

```
正常的原生呼叫           → [('read_file', {'path': 'a.py'})]
參數 JSON 壞掉          → 例外 JSONDecodeError: Expecting value: line 1 column 10 (char 9)
沒有任何呼叫             → []
```

**執行**（工作目錄是 `ws/`，旁邊放了一個不該被讀到的 `secret.txt`，`ws/link_secret` 是指向它的符號連結）

```
read_file({'path': 'a.py'})                  → 'x = 1\n'
read_file({'path': '../secret.txt'})         → 'secret\n'
read_file({'path': '/etc/hosts'})            → '##\n# Host Database\n#\n# localhost is used'
read_file({'path': 'link_secret'})           → 'secret\n'
read_file({'path': 'missing.py'})            → 例外 FileNotFoundError [Errno 2] No such file or directory: '/private/var/folders/s…
read_file({})                                → 例外 TypeError make_tools.<locals>.read_file() missing 1 required positiona…
bash({'command': 'ls'})                      → 例外 KeyError 'bash'
```

三類問題：

1. **解析**：模型給的參數 JSON 壞掉，整個迴圈就崩潰。
2. **守門**：`../`、絕對路徑、符號連結都讀到了工作目錄外的檔案。
3. **錯誤**：任何怪參數或不存在的工具都是例外，一樣讓迴圈崩潰。

模型會犯這些錯是常態，不是意外。程式要做的是把每一種錯都變成「文字」回給模型，讓它自己改。

## 解析：兩關

`parse_message` 把一則模型回覆變成「合法的呼叫」與「錯誤訊息」兩份清單：

```python
def parse_message(message, tool_schemas):
    # 第 1 關 解碼：每個呼叫的參數是 JSON 字串，轉成 dict；轉不成就記一筆錯誤
    # 第 2 關 驗證：工具名稱存在、必要參數齊全；不合法的移到錯誤清單
    return ParseResult(calls, errors)
```

同樣的情境，換成現在的 `parse_message`（工具只有 `read_file`，必要參數是 `path`）：

```
正常的原生呼叫        calls=[('read_file', {'path': 'a.py'})] errors=[]
參數 JSON 壞掉       calls=[] errors=['bad arguments for read_file: Expecting value: line 1 column 10 (char 9)']
工具不存在           calls=[] errors=["unknown tool: 'bash'"]
缺必要參數           calls=[] errors=["read_file: missing required argument(s) ['path']"]
JSON 只寫在文字裡     calls=[] errors=[]
純文字，沒有呼叫       calls=[] errors=[]
```

- 「參數 JSON 壞掉」：天真版本的例外，變成一筆錯誤文字，模型看得到、可以重送。
- 「工具不存在」：fixlab 沒有 shell 工具，模型想用 `bash` 在解析階段就被擋下，不會走到執行。
- 最後兩列的結果相同：沒有呼叫、沒有錯誤，下一節說明為什麼文字裡的 JSON 不算呼叫。

下一篇會寫的迴圈，看這份結果的方式：

| calls | errors | 迴圈怎麼做 |
|---|---|---|
| 有 | 無 | 執行 |
| 有 | 有 | 執行合法的，並把錯誤一起回報給模型 |
| 無 | 有 | **不結束**，把錯誤回給模型再試一次 |
| 無 | 無 | 模型說完了，結束 |

## 決定：只認 API 的 `tool_calls` 欄位

有些模型不用 `tool_calls` 欄位，而是把 `{"name": "read_file", ...}` 這樣的 JSON 直接寫在回覆文字裡。要支援它們，解析器得多一道「從文字裡撈 JSON」的步驟，而且判斷「模型說完了」時，就不能只看 calls 是不是空的，還得檢查文字像不像在呼叫工具。

fixlab 不做這件事：**沒有 `tool_calls` 的回覆就是純文字，文字裡就算有 JSON 也不理會。** 範圍是「有穩定 `tool_calls` 的模型」，決定與依據記在 `design.md` 的「只解析原生 tool_calls，不做文字備援解析」。

代價是：把 JSON 寫在文字裡的模型不支援。它們的回覆會被當成「第 1 步就宣告完成、沒呼叫任何工具」。為了不讓這種情況被誤認成修好了，之後 CLI 結束時會再自己跑一次 `run_tests`，並印出結束原因與步數。

## 執行：一層一層補

`Workspace` 是所有工具共用的單一出口，補的是前面的第 2、3 類問題。它做三件事：

```python
def call(self, name, args):
    try:
        tool = self._tools.get(name)          # 未知工具 → ToolError
        self._check_args(name, tool, args)    # 缺參數、多餘參數、型別不對 → ToolError
        return tool.func(**args)              # 工具內部用 resolve_inside(path) 檢查路徑
    except PathBlocked: return ToolResult(..., ok=False, flags={"blocked": True})
    except ToolError:   return ToolResult(..., ok=False)
    except OSError:     return ToolResult(..., ok=False)
```

`ToolResult` 有三個欄位：`output`（給模型看的文字）、`ok`（成功與否）、`flags`（給統計用的旗標，例如 `blocked`）。

**1. `call()` 永遠不丟例外。** 任何錯誤都變成 `ok=False` 的結果，錯誤訊息當成文字回給模型。天真版本的三個例外在這裡都變成一般結果。

**2. 路徑檢查靠 `resolve_inside()`。** 先拒絕絕對路徑和 `~` 開頭，再用 `resolve()`（會展開 `../` 並跟隨符號連結）算出真正的位置，最後確認它還在工作目錄底下。

**3. `blocked` 旗標只留給兩種情況：路徑逃逸，以及寫入受保護的測試檔（3.9 才做）。** 找不到檔案、參數型別不對只是 `ok=False`。原因是階段 3 要統計「agent 嘗試越界的次數」；如果連「檔案不存在」都算 `blocked`，這個數字就分不出是安全問題還是普通錯誤。

下面是實際執行結果。`read_file` 是測試裡的替身（真的 `read_file` 是 3.3），它先過路徑檢查再讀檔。前七列是 `read_file` 的 `path` 參數，後三列是完整的呼叫：

```
timelog/parser.py      ok=True  flags={} output='x = 1'
timelog/missing.py     ok=False flags={} output="error: file not found: 'timelog/missing.py'"
../secret.txt          ok=False flags={'blocked': True} output="error: path is outside the working directory: '../secret.txt'"
sub/../../secret.txt   ok=False flags={'blocked': True} output="error: path is outside the working directory: 'sub/../../secret.txt'"
/etc/hosts             ok=False flags={'blocked': True} output="error: absolute paths are not allowed: '/etc/hosts'"
~/.zprofile            ok=False flags={'blocked': True} output="error: absolute paths are not allowed: '~/.zprofile'"
link_secret            ok=False flags={'blocked': True} output="error: path is outside the working directory: 'link_secret'"
bash({'command': 'ls'})            ok=False flags={} output="error: unknown tool: 'bash'"
read_file({'path': 5})             ok=False flags={} output="error: read_file: argument 'path' must be a string, got int"
read_file({})                      ok=False flags={} output="error: read_file: missing required argument(s) ['path']"
```

`../secret.txt`、`/etc/hosts`、符號連結都不再讀得到。`timelog/missing.py` 沒有 `blocked`、`link_secret` 有，就是第 3 點的效果。連「找不到檔案」的訊息也不再洩漏暫存目錄的絕對路徑，天真版本的例外訊息會把它帶出來。

## 怎麼驗證

| 測試檔 | 驗證什麼 |
|---|---|
| `tests/test_toolparse.py`（7 個） | 規格的每個情境各一個測試：原生加文字 JSON 只取原生、JSON 只在文字裡 → 無呼叫、兩個呼叫依序回傳、參數壞掉 → `bad arguments`、缺必要參數、`bash` 被拒絕、一般文字 |
| `tests/test_isolation.py`（7 個） | 路徑表六列（`../`、`sub/../../`、絕對路徑、`~`、符號連結、合法路徑），加上「找不到檔案不算 `blocked`」 |
| `tests/test_tools.py`（4 個） | 未知工具、型別錯誤、缺參數與多餘參數、作業系統錯誤變成結果而不是例外 |

## 已知限制（照實記錄，沒有修）

- **不支援把 JSON 寫在文字裡的模型**：上面「決定」那一節說明的取捨。這類模型的失敗，解析器抓不到。
- **參數只認 JSON 字串**：OpenAI 格式的 `arguments` 是字串。如果某個供應商回的是已解析好的物件，會被當成 `bad arguments`，模型會收到錯誤。階段 1 用的 Ollama 與 OpenRouter 都是字串。
- **驗證分在兩處**：`parse_message` 只檢查工具存在與必要參數；多餘參數和型別是 `Workspace` 檢查。所以解析階段通過的呼叫，執行階段仍可能被退回。
- **參數型別只認三種**：`string`、`integer`、`boolean`。之後如果工具要收陣列或物件，要擴充。
- **`~` 開頭的路徑訊息不準**：`~/.zprofile` 回的是「absolute paths are not allowed」，其實它不是絕對路徑。行為正確，訊息可以改得更準。
- **檢查與使用之間有空窗**：路徑是先檢查、後使用。如果有人在這兩步之間把檔案換成符號連結，守門會被繞過。階段 1 的情境是單一 agent 在自己的複本上跑，不處理這個競爭條件。
- **硬連結**：`resolve()` 看不出硬連結指向工作目錄外。這在 `design.md` 已記錄，之後會寫進 README。

## 參考來源

讀過高見龍 KeSi 連載的 Day 05（模型怎麼使用工具）與 Day 06（read_file），也看過其 repo（MIT，Copyright (c) 2026 Eddie Kao）。採用的想法有兩個：「先寫天真版本、再逐步補上」的敘事順序，以及「工具錯誤以文字回給模型」。Day 05 靠 Anthropic API 的 `strict` 模式約束參數；fixlab 走 OpenAI 相容端點，不能依賴它，所以自己做參數檢查。「`blocked` 只留給安全攔截」是 fixlab 自己的需求，原文沒有這個區分。

## 下一篇

3.2 把工具登記表轉成給模型看的清單，接著實作 `read_file`、`list_files`，並把迴圈與最小入口提前接上，讓模型先唯讀探索一次 timelog。第 2 篇會從那裡開始。
