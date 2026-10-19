"""把覆寫的值蓋到設定上。"""


def merge(settings, overrides):
    """直接修改傳進來的 settings（呼叫的人都傳新建的字典，所以沒有副作用）。"""
    for key, value in overrides.items():
        settings[key] = value
    return settings
