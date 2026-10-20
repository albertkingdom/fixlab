# 本機 CLI 啟動設定

設定日期：2026-10-19；2026-10-20 更新預設互動入口。以下記錄這台 macOS 電腦已完成的設定；啟動器位於版控之外，clone 本專案不會自動建立它們。

下文以 `$FIXLAB_HOME` 代表 fixlab clone 所在的絕對路徑；照著設定時換成你自己的位置。

## 使用方式

在要處理的專案目錄執行：

```bash
fixlab
```

或指定其他專案目錄：

```bash
fixlab /你的專案路徑 -i
```

啟動器不會切換目前目錄。省略 PATH 與 `--task` 時，CLI 預設以目前目錄進入互動模式；原本的 `fixlab . -i` 仍可使用。指定 PATH 而不加 `-i` 仍是一次性模式；一次性的 `--task` 必須搭配 PATH，例如 `fixlab . --task '任務內容'`；只給 `--task` 會被拒絕。

## 設定檔

每次啟動會載入固定路徑 `$FIXLAB_HOME/.env`，包含以下變數：

```dotenv
OPENAI_BASE_URL=你的模型服務端點
OPENAI_API_KEY=你的金鑰
FIXLAB_MODEL=你的模型名稱
```

這裡只記錄變數名稱，不記錄實際金鑰。`.env` 已由 `.gitignore` 排除。

啟動器透過 zsh 的 `source` 與 `set -a` 載入並匯出變數，因此檔案必須符合 zsh 語法；含空白或特殊字元的值應加引號。每次啟動都重新讀取，修改後不必手動 `source`。檔案內同名設定會覆蓋既有環境變數；`--model` 仍可覆寫 `FIXLAB_MODEL`。

## 兩個啟動入口

`~/.zshrc` 與 `~/.zprofile` 原本就會將 `~/.local/bin` 加入 `PATH`，本次未修改它們。

`~/.local/bin/fixlab` 最初建立為符號連結，之後改成以下啟動腳本：

```zsh
#!/bin/zsh
# 載入 fixlab 的本機模型設定，再啟動既有 CLI。
FIXLAB_HOME=/path/to/fixlab   # 換成實際的絕對路徑
set -a
source "$FIXLAB_HOME/.env" || exit 1
set +a
exec "$FIXLAB_HOME/.venv/bin/fixlab" "$@"
```

啟用本專案的 `.venv` 時，PATH 會優先找到 `.venv/bin/fixlab`，繞過全域啟動器。為了讓此入口也能自動載入設定，`$FIXLAB_HOME/.venv/bin/fixlab` 已改成：

```zsh
#!/bin/zsh
FIXLAB_HOME=/path/to/fixlab   # 換成實際的絕對路徑
set -a
source "$FIXLAB_HOME/.env" || exit 1
set +a
exec "$FIXLAB_HOME/.venv/bin/python3.14" -c 'import sys; from fixlab.cli import main; sys.argv[0] = "fixlab"; sys.exit(main())' "$@"
```

兩個腳本皆具有執行權限。原本的 Python 入口備份在 `.venv/bin/fixlab.before-env-loader`。目前經由全域入口啟動時，兩層腳本會各載入一次 `.env`；現有檔案只設定變數，請勿在其中加入會產生副作用的指令。

## 驗證紀錄

已清除測試行程的 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 與 `FIXLAB_MODEL`，確認下列情境能載入設定並進入 `fixlab>`，以 EOF 正常結束，結束碼為 0：

- 從專案以外的目錄，直接使用 `~/.local/bin/fixlab`。
- 直接使用 `.venv/bin/fixlab`。
- 啟用本專案的 `.venv` 後，從其他目錄執行 `fixlab`。

驗證沒有提交模型任務，也沒有呼叫模型 API 或執行目標專案的測試。

## 維護與還原

- 重新安裝套件可能覆蓋 `.venv/bin/fixlab`；重建 `.venv` 也會移除備份。屆時須重新套用該入口的設定。
- 兩個腳本使用固定絕對路徑。移動專案、改用其他 Python 版本或刪除 `.venv` 後，須更新路徑。
- 若再出現 `no model`，先用 `whence -a fixlab` 確認實際使用的入口。其他虛擬環境內安裝的 fixlab 不包含本次設定。
- 若要還原 `.venv` 入口，可將 `.venv/bin/fixlab.before-env-loader` 複製回 `.venv/bin/fixlab`，並確認仍有執行權限。全域啟動器仍會載入 `.env`。

預設目錄與互動模式由套件的 `fixlab/cli.py` 處理；自動載入 `.env` 是這台電腦的啟動器行為。
