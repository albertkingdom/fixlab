from conf.render import describe


def test_one_plugin():
    assert describe({}, ["a"]) == "retries=3\ntags=a\ncache=/tmp/cache"


def test_two_loads_are_independent():
    describe({}, ["a"])
    assert describe({}, ["b"]) == "retries=3\ntags=b\ncache=/tmp/cache"
