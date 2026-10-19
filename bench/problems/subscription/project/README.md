# subs

判斷訂閱有沒有到期。公開入口只有 `subs.report.status_report(subscriptions, now_text)`。

- 到期時間寫成**本地時間**，格式 `YYYY-MM-DD HH:MM`。本地時間是 UTC 加 8 小時（固定時差，定義在 `subs/clock.py`，不看機器的時區設定）。
- `now_text` 是**UTC** 的現在時間，同樣的格式。
- 訂閱在「現在早於到期的那一刻」時有效；剛好等於到期的那一刻起算過期。
- `subscriptions` 是 `(名字, 到期時間)` 的清單。報表每個人一行，依名字排序：有效是 `名字: active until 到期時間（本地）`，過期是 `名字: expired`。
