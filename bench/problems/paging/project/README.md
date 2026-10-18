# pager

把清單分頁顯示。公開入口只有 `pager.display.render_page(items, page, size)`。

- `pager/pages.py` 的 `page_count(total, size)` 是**頁數的唯一定義**：總數除以每頁筆數，有餘數就多一頁；沒有任何項目時算 1 頁。
- `render_page` 顯示第 `page` 頁（從 1 開始）的項目，每個項目一行，接著一行頁尾 `Page 第幾頁/總頁數`；如果後面還有下一頁，頁尾後面加 ` (next)`。
- 沒有任何項目時，內容是 `(no items)`，頁尾是 `Page 1/1`。
- 頁數超出範圍時，用最接近的有效頁。
