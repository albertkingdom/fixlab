from perm.handler import handle

MEMBER = {"name": "mia", "role": "member", "banned": False}
BANNED = {"name": "bob", "role": "member", "banned": True}


def test_member_can_write():
    assert handle(MEMBER, "write") == "OK"


def test_banned_user_cannot_even_read():
    assert handle(BANNED, "read") == "BANNED"
