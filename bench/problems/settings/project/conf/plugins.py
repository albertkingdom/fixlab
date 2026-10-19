"""外掛：註冊時把名字加進標籤。"""


def register(settings, name):
    settings["tags"].append(name)
