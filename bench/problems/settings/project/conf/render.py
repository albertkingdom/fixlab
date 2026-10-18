"""把設定描述成文字。"""

from conf.loader import load
from conf.plugins import register


def describe(overrides, plugins):
    settings = load(overrides)
    for name in plugins:
        register(settings, name)
    return "\n".join([
        f"retries={settings['retries']}",
        f"tags={','.join(settings['tags'])}",
        f"cache={settings['paths']['cache']}",
    ])
