# fixlab

教學導向的最小 CLI coding agent：給它一個有 bug 的多檔小專案，它自己找、改、驗證，並記錄每一步的 telemetry。

目前處於規劃階段，背景與範圍見 [AGENTS.md](AGENTS.md)。

## 為什麼做

想實際量測 coding agent 在「多檔小專案修 bug」上可靠到什麼程度，而不只是 demo 能跑。規劃涵蓋：

- **Tool-use agent**：由 LLM 決定下一步與何時完成；七個工具（讀、列、找、搜尋、改、寫、跑測試），解析原生與文字兩種 tool call，程式只設步數與連續失敗上限。
- **程式碼修改的自動化驗證**：用 pytest 驗證；隱藏測試分「要修好」與「不能壞掉」兩組；測試檔指紋偵測竄改；量測假通過與未驗證就宣稱完成。
- **評估與實驗框架**：自建 15–20 題多檔 Python bug benchmark；有／無 `run_tests` 的對照實驗，比較修好率、步數、token 與成本。
- **Telemetry**：每步事件寫成 JSONL（模型版本、context 長度、token、延遲、工具與結果）。
- **開源與商用模型對照**：透過 Ollama／OpenRouter 跑 Qwen、Gemma 等開源模型，與商用模型在同一套 benchmark 上比較。
- **Prompt／Context Engineering**：system prompt 規則消融、tool output 截斷策略。
- **安全隔離**：路徑限制在工作目錄、macOS 沙箱禁網路、子行程環境變數白名單。
- **CLI 開發者工具**：`fixlab fix <repo>` 一次性修復與互動模式。
- **選做**：多 agent 對照（修復者＋審查者）、MCP 或 GitHub issue connector。

前身是 `../code-agent-eval`（單檔函式題的評測），fixlab 把它擴展成能實際使用的多檔修復工具。
