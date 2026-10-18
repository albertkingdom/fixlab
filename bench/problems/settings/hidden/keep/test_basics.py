from conf.render import describe


def test_defaults_without_plugins():
    assert describe({}, []) == "retries=3\ntags=\ncache=/tmp/cache"


def test_an_override_replaces_the_default():
    assert describe({"retries": 7}, []) == "retries=7\ntags=\ncache=/tmp/cache"


def test_overriding_the_tags_directly():
    assert describe({"tags": ["pre"]}, []) == "retries=3\ntags=pre\ncache=/tmp/cache"
