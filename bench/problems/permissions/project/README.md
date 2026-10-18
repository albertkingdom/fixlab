# perm

判斷使用者能不能做某個動作，回傳一個回應字串。公開入口只有 `perm.handler.handle(user, action)`。

- `user` 是 `None`（沒登入）或字典 `{"name": ..., "role": ..., "banned": 布林}`；`role` 是 `member` 或 `admin`。`action` 是 `read`、`write` 或 `delete`。
- 需要的角色：`read` 任何人（含沒登入）、`write` 至少 member、`delete` 只有 admin。
- 回應：
  - 沒登入：`read` 回 `OK (guest)`，其他動作回 `LOGIN`。
  - **被停權的使用者（`banned` 為真）：任何動作都回 `BANNED`**，不論角色。
  - 角色不夠：回 `DENIED`。
  - 其他：回 `OK`。
