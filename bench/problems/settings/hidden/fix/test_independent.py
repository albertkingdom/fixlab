from conf.render import describe


def test_a_plugin_does_not_leak_into_the_next_load():
    describe({}, ["first"])
    assert describe({}, []) == "retries=3\ntags=\ncache=/tmp/cache"


def test_the_same_plugin_twice_in_two_loads_shows_once_each():
    describe({}, ["a"])
    assert describe({}, ["a"]) == "retries=3\ntags=a\ncache=/tmp/cache"


def test_overrides_and_plugins_together_stay_separate():
    describe({"retries": 5}, ["x", "y"])
    assert describe({"retries": 1}, ["z"]) == "retries=1\ntags=z\ncache=/tmp/cache"
