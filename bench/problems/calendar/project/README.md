# cal

行事曆的衝突檢查與預訂天數。公開入口是 `cal.report.conflict_report(events)` 與 `cal.report.booking_summary(events)`。

- 一個活動是 `Event(name, start, end)`，`start` 與 `end` 都是 `datetime.date`。**`end` 是活動的最後一天，那一天也算在活動裡**（含頭含尾）。一天的活動 `start` 等於 `end`。
- 兩個活動只要有任何一天重疊就算衝突，包括一個活動的最後一天剛好是另一個活動的第一天。
- `conflict_report` 每個衝突一行，格式是 `甲 <-> 乙`，兩個名字依字母排序，各行也依字母排序；沒有衝突就是單獨一行 `No conflicts`。
- `booking_summary` 每個活動一行，格式是 `名稱: N days`，N 是活動含頭含尾的天數，依活動名稱排序。
