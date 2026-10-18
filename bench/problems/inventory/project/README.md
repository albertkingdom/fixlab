# stock

把收貨單換算成庫存報表。公開入口只有 `stock.report.stock_report(receipt_lines)`。

- `receipt_lines` 是字串清單，每行是 `品號,數量,單位`，例如 `A100,2,case`。
- 單位有三種：`unit`（1 件）、`pack`（一包，件數見 `stock/catalog.py` 的 `per_pack`）、`case`（一箱，件數見 `per_case`）。
- 品號不在目錄裡的行直接略過。
- 報表每個品號一行，格式是 `品號 名稱: 件數`，依品號排序；最後一行是 `TOTAL units 總件數`。
- 空的收貨單只有 `TOTAL units 0` 一行。
