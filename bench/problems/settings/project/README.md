# conf

載入設定並描述它。公開入口只有 `conf.render.describe(overrides, plugins)`。

- 預設設定在 `conf/defaults.py`：`retries`（重試次數）、`tags`（標籤清單）、`paths`（含 `cache` 路徑）。
- `describe` 載入設定、套用 `overrides`（一個字典，鍵與預設相同，值取代預設的值）、再依序註冊 `plugins`（每個外掛的名字加進 `tags`），然後回傳三行文字：`retries=3`、`tags=a,b`（標籤以逗號相連，沒有標籤就是空字串）、`cache=/tmp/cache`。
- **每次載入都是獨立的**：註冊外掛、或對載入結果做任何修改，都不能影響之後的載入。
