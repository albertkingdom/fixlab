# 第 1 篇：模型說要呼叫工具，程式怎麼接住

> 對應任務：bootstrap-agent-core 的 2.1、2.2（tool call 解析）與 3.1（Workspace 路徑守門與分派）。
> 完成度：兩個模組與測試都已完成（`pytest` 21 個通過）。把工具登記表轉成給模型看的清單（`tool_specs()`）是 3.2，還沒做。

agent 的核心是「模型決定下一步，程式負責執行」。模型只會回一段訊息，程式要從裡面認出「它想呼叫哪個工具、帶什麼參數」，再安全地執行。這一篇從最天真的寫法開始，看它怎麼壞，再一層一層加到現在的 `toolparse.py` 和 `workspace.py`。中間還有一段我先做了、後來又砍掉的設計。

```
模型的回覆 ──► 認出呼叫（解析） ──► 執行工具 ──► 結果送回給模型
```

## 先寫一個最天真的版本

只看 API 的 `tool_calls` 欄位，路徑直接 `open`：

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
native                 → [('read_file', {'path': 'a.py'})]
native 參數 JSON 壞掉      → 例外 JSONDecodeError: Expecting value: line 1 column 10 (char 9)
finished               → []
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

1. 解析：模型給的參數 JSON 壞掉，整個 loop 就崩潰了。
2. 守門：`../`、絕對路徑、符號連結都讀到了工作目錄外的檔案。
3. 錯誤：任何一個怪參數或不存在的工具都是例外，一樣讓 loop 崩潰。

## 解析：兩關

```python
def parse_message(message, tool_schemas):
    # 第 1 關 解碼：每個原生呼叫的參數是 JSON 字串，轉成 dict；轉不成就記一筆錯誤
    # 第 2 關 驗證：工具名稱存在、必要參數齊全，不合法的移到 errors
    return ParseResult(calls, errors)
```

沒有 `tool_calls` 的回覆就是純文字，文字裡就算有 JSON 也不理會。loop 對結果的判讀：

| calls | errors | loop 怎麼做 |
|---|---|---|
| 有 | 無 | 執行 |
| 有 | 有 | 執行合法的，並回報錯誤 |
| 無 | 有 | **不結束**，把錯誤回饋給模型再試一次 |
| 無 | 無 | 模型說完了，結束 |

同樣的情境，換成現在的 `parse_message`（工具是 `read_file`，必要參數 `path`）：

```
1 native      calls=[('read_file', {'path': 'a.py'})] errors=[]
2a text JSON  calls=[] errors=[]
2b bad args   calls=[] errors=['bad arguments for read_file: Expecting value: line 1 column 10 (char 9)']
3a unknown    calls=[] errors=["unknown tool: 'bash'"]
3b missing    calls=[] errors=["read_file: missing required argument(s) ['path']"]
4 finished    calls=[] errors=[]
```

- 2b：天真版本的例外，變成一筆錯誤文字，模型看得到、可以重送。
- 3a：fixlab 沒有 shell 工具，模型想用 `bash` 在解析階段就被擋下，不會走到執行。
- 2a 是刻意的：JSON 寫在文字裡不算呼叫，下一節說明為什麼。

## 我曾經做過四關，後來砍掉

第一版（commit `302bf7d`，從前一個專案 code-agent-eval 複製來的）有四關，多的兩關是：

- 備援解析：沒有 `tool_calls` 時，掃回覆文字裡的 JSON，有 `"name"` 的就當候選。
- 壞呼叫檢查：什麼都沒解析到、文字卻「像」在呼叫工具，補一筆錯誤，避免被當成「完成」。

它們存在的理由是 code-agent-eval 的試跑（`docs/pilot-results.md`）：

- qwen2.5-coder:7b 從不使用原生 `tool_calls`，20 題迴圈裡 96 次呼叫全靠備援，另有 33 次無效呼叫，只有 7/20 自行完成。
- 同一個模型有時用 Python 三引號或漏掉結尾引號，原本的解析器取不到東西，loop 把這一步當成完成。
- llama3.1:8b 會呼叫不存在的工具（`write_to_file`）並輸出壞 JSON。

後來我決定拿掉，因為我們要用的模型根本用不到：同一份試跑裡，qwen3.5:9b 的 20 題迴圈是 74 次原生、0 次備援，gemma4:12b 的煙霧測試是 30 次全部原生。選定的模型上，這兩關從頭到尾不會被觸發，卻讓「結束判斷不能只看 calls 是否為空」這類規則變得複雜。

取捨是：不使用原生格式的模型不再支援。這類模型把 JSON 寫在文字裡時，不會被偵測，看起來會是「第 1 步就宣告完成、沒呼叫任何工具」。之後 CLI 結束時會再跑一次 `run_tests`，並顯示 stop reason 與步數，所以不會被誤當成修好了。如果階段 3 要比較較弱的模型，可以用 `git show 302bf7d:fixlab/toolparse.py` 把舊版找回來。

## 執行：一層一層補

`Workspace` 是所有工具共用的單一出口，補的是前面的第 2、3 類問題。

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

**`call()` 永遠不丟例外。** 任何錯誤都變成 `ok=False` 的結果文字回給模型，模型看得到錯在哪、可以改。天真版本的三個例外在這裡都變成一般結果。

**路徑檢查靠 `resolve_inside()`。** 先拒絕絕對路徑和 `~` 開頭，再 `resolve()`（會展開 `../` 並跟隨符號連結），最後確認結果還在工作目錄底下。

**`blocked` 旗標只留給兩種情況：路徑逃逸（現在已有）與寫入受保護檔案（3.9 才加）。** 找不到檔案、參數型別不對都只是 `ok=False`。依據是我自己前一個專案的缺陷：code-agent-eval 把所有 `ToolError`（連 file not found 都算）設成 `blocked`，結果 `blocked_calls` 同時混了安全攔截和一般錯誤。階段 3 要統計「agent 嘗試越界的次數」，這個指標一混就沒意義。

同樣的七個呼叫，換成現在的 `Workspace`（測試裡的假 `read_file`，真的是 3.3）：

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

`../secret.txt`、`/etc/hosts`、符號連結都不再讀得到；`timelog/missing.py` 沒有 `blocked`，而 `link_secret` 有，這就是上面第三個決定的效果。連找不到檔案的訊息也不再洩漏暫存目錄的絕對路徑（天真版本的例外訊息會帶出來）。

## 怎麼驗證

- `tests/test_toolparse.py`（7 個）：規格的每個情境各一個測試函式，包含「原生加文字 JSON 只取原生」「JSON 只在文字裡 → 無呼叫」「兩個原生呼叫依序回傳」「原生參數壞掉 → bad arguments」。
- `tests/test_isolation.py`：路徑表六列（`../`、`sub/../../`、絕對路徑、`~`、符號連結、合法路徑），加上「找不到檔案不算 blocked」。
- `tests/test_tools.py`：未知工具、型別錯誤、缺參數與多餘參數、作業系統錯誤變成結果而不是例外。

## 已知限制（照實記錄，沒有修）

- **不支援文字模式的模型**：上面說明的取捨。這類模型的失敗不會被解析器抓到。
- **原生參數只認 JSON 字串**：OpenAI 格式的 `arguments` 是字串。如果某個供應商回的是已解析好的物件，會被當成 "bad arguments"，模型會收到錯誤。階段 1 用到的 Ollama 與 OpenRouter 都是字串。
- **驗證分在兩處**：`toolparse.validate` 只檢查工具存在與必要參數；多餘參數和型別是 `Workspace._check_args` 檢查。所以解析階段通過的呼叫，執行階段仍可能被退回。
- **schema 只認三種型別**：`string`、`integer`、`boolean`。之後如果工具要收陣列或物件，要擴充。
- **`~` 開頭的路徑訊息不準**：`~/.zprofile` 回的是「absolute paths are not allowed」，其實它不是絕對路徑。行為正確，訊息可以改得更準。
- **先 `resolve()` 再使用，中間沒有鎖**：如果有人在檢查後、使用前把檔案換成符號連結，守門會被繞過。階段 1 的情境是單一 agent 在自己的複本上跑，不處理這個競爭條件。
- **硬連結**：`resolve()` 看不出硬連結指向工作目錄外，這是 `design.md` 已記錄的限制，之後只在 README 列出。

## 參考來源與依據

- `toolparse.py` 的前身與試跑證據來自我自己的前身專案 code-agent-eval（程式碼是自己寫的，複製後整理，再依試跑數字砍掉備援解析）。
- 讀過高見龍 KeSi 連載的 Day 05（模型怎麼使用工具）與 Day 06（read_file），也看過其 repo（MIT，Copyright (c) 2026 Eddie Kao）。Day 06 的寫法是這篇「先寫天真版本再補」的敘事順序的靈感：他的第一版 `read_file` 加迴圈只有 110 行，之後才一天一天長大。他同樣把工具錯誤以文字回給模型、用 `resolve` 擋 `..` 與符號連結，做法與我們相近；Day 05 靠 Anthropic API 的 `strict` 模式約束參數，我們走 OpenAI 相容端點，不能依賴它，所以自己做參數檢查。我們的設計依據是 code-agent-eval 的缺陷與試跑結果，不是這兩篇；「`blocked` 只留給安全攔截」是我們自己的需求，他的文章沒有這個區分。

## 下一篇

3.2 把工具登記表轉成給模型看的清單，接著實作 `read_file`、`list_files`，並把迴圈與最小入口提前接上，讓模型先唯讀探索一次 timelog。第 2 篇會從那裡開始。
