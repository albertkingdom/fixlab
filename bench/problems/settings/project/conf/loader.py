"""載入設定：預設值加上使用者的覆寫。"""

from conf.defaults import DEFAULTS
from conf.overrides import merge


def load(overrides):
    settings = dict(DEFAULTS)
    merge(settings, overrides)
    return settings
