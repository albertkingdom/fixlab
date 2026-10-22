---
name: create-pr
description: "依 fixlab 的流程開 Pull Request：開 PR 前的檢查（分支、Spectra 歸檔、code review 紀錄、測試與 benchmark 自我檢查、README 與文件同步、來源與個資檢查）、PR 標題與英文說明格式、推送與等 CI。當使用者說「開 PR」「建立 PR」「create PR」「推上去開 PR」「準備合併」時使用。需要使用者明確要求才會 push 與開 PR。"
---

# 開 Pull Request（fixlab）

只在使用者**明確要求**時 push 與開 PR。預設分支是 `main`；新功能從它開 `feature/<name>`，不直接 commit 到 `main`（hook 會擋）。純文件的小修可用 `docs/<name>` 分支，這個 repo 近期的文件變更就是這樣做的。

## 1. 開 PR 前檢查（有一項沒過就停下回報）

```bash
git status -sb                                  # 工作區乾淨、不在 main
git log --oneline origin/main..HEAD             # 英文 Conventional Commits、沒有 AI 署名
git diff --stat origin/main...HEAD
```

| 項目 | 標準 |
|---|---|
| Spectra | 新功能有完成的提案（`/spectra-propose`）、任務做完、已歸檔（`/spectra-archive` 或 `/spectra-wrapup`）。文件或設定的小變更可以沒有，PR 說明要寫明 |
| Code review | 已跑 `project-review`，阻擋與重要問題都處理完（`review-findings`）。`.claude/state/review-passed` 要對應目前 HEAD（歸檔產生的、只動 `docs/spectra/` 的 commit 不會讓它失效），否則 `gh pr create` 與 `spectra archive`（不含 `--preview`）會被 hook 擋下；只改文件與規格的分支不需要。**不要手動寫這個檔案繞過**，補審查。順序是：實作 → review → 歸檔 → 開 PR；`git commit` 與 `gh pr create` 不要串在同一個指令（hook 會擋） |
| 測試 | `.venv/bin/python -m pytest -q` 全過；動到 benchmark 再跑 `python -m fixlab.bench check`。沙箱相關變更要在 macOS 跑過 |
| 文件 | 使用者看得到的差異已同步 `README.md` 與 `docs/`；新功能 README 已更新（合併前的規則） |
| 實驗紀錄 | 有新的實驗結果時：設定、日期、限制都寫進 `docs/benchmark-results.md`，沒有挑數字、沒有編造 |
| 個資與機密 | diff 中沒有金鑰、`.env`、`/Users/<name>` 之類的本機路徑或使用者名稱（README 與文章的範例輸出也要看） |
| 來源 | 引用或沿用他人內容的地方有來源與版權聲明（AGENTS.md 守則 7） |

教學文章相關：若文章描述的程式有變，提醒使用者 `article-NN` tag 是否需要更新。tag 只建在本機，**不自動推送**。

## 2. 推送

```bash
git push -u origin <branch>
```

只在網路錯誤時重試。**不 force push**，不推 tag（除非使用者明確指定）。

## 3. 建立 PR

標題：Conventional Commits 格式、英文、70 字內，例如 `docs(readme): add a recorded repair demo`。說明用英文：

```markdown
## Summary
<1-3 bullets: what changed and why>

## Changes
<by area: package / bench / docs / specs / CI>

## Testing
<commands actually run and their result; what was NOT run (for example sandbox tests off macOS) and why>

## Code review
<the summary block produced by review-findings, or "no blocking or important findings">

## Notes
<known limits, follow-ups, effects on the benchmark or on published numbers>
```

`Testing` 只寫實際執行過的。CI 在 macOS 跑 pytest，不跑 benchmark 的真模型實驗；沒跑就明講。

```bash
gh pr create --base main --title "<title>" --body-file <file>
```

說明很長時先寫進暫存檔再用 `--body-file`。

## 4. 之後

- 開完回報連結，用 `gh pr checks` 看 CI（`test` workflow）；紅燈時先讀失敗輸出再修，不盲目重跑。
- **不自動合併。** 合併由使用者決定。
- 這個 repo 近期的變更是用 merge commit 併入（`Merge branch 'docs/...'`）；合併方式由使用者決定。
