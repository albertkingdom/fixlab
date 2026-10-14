"""fixlab：教學導向的最小 CLI coding agent。

給它一個有 bug 的多檔小專案，LLM 自己決定讀哪些檔、改哪裡、何時跑測試與結束；
程式只提供七個工具與安全保險。讀程式的順序：loop、toolparse、tools、workspace、sandbox。
"""
