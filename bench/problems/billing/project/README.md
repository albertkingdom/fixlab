# bill

把購物明細結帳成一張收據。公開入口只有 `bill.receipt.checkout(lines, code=None)`。

- `lines` 是 `(品號, 數量)` 的清單；單價（單位是分）在 `bill/prices.py`。
- `code` 是折扣碼，區分大小寫。折扣表在 `bill/discounts.py`，值是折扣的百分比。沒有折扣碼就不打折。
- 折扣金額是小計乘百分比，無條件捨去到分（見 `bill/rounding.py`）。
- 收據每個品項一行，格式是 `品號 x數量: 金額`；有折扣再加一行 `DISCOUNT -金額`；最後一行是 `TOTAL 金額`。
- **折扣碼不在折扣表裡（包含空字串、大小寫不同），整張收據只有一行 `ERROR: unknown discount code 碼`**，沒有品項也沒有 TOTAL。
