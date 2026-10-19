"""載入設定：預設值加上使用者的覆寫。"""

from copy import deepcopy

from conf.defaults import DEFAULTS
from conf.overrides import merge


def load(overrides):
    settings = deepcopy(DEFAULTS)
    merge(settings, overrides)
    return settings
