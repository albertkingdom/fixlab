# taskplan

把任務排成執行順序。公開入口是 `taskplan.report.execution_order(tasks)` 與 `taskplan.report.summary(tasks)`。

- 一個任務是 `Task(name, priority, due)`：`priority` 是整數，**數字越大越先做**；`due` 是到期的第幾天，越小越急。
- 執行順序：priority 大的先；priority 一樣，due 小的先；還一樣，名字依字母排序。
- `execution_order(tasks)` 回傳依執行順序排好的任務名字清單。
- `summary(tasks)` 每個任務一行 `序號. 名字 (P優先權, due 到期日)`，最後一行是 `Buckets: P3=2 P1=1`：依優先權由大到小，列出每個優先權有幾個任務。沒有任務時只有 `Buckets:`。
- `taskplan/queue.py` 的 `bucket_of(task)` 把任務分到優先權的桶子，`summary` 的 `Buckets` 行靠它計算。
