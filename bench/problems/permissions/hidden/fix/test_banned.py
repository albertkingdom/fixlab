from perm.handler import handle


def test_banned_user_writing_is_banned_not_asked_to_log_in():
    assert handle({"name": "bob", "role": "member", "banned": True}, "write") == "BANNED"


def test_banned_admin_is_still_banned():
    assert handle({"name": "root", "role": "admin", "banned": True}, "delete") == "BANNED"


def test_banned_member_reading_is_banned():
    assert handle({"name": "kim", "role": "member", "banned": True}, "read") == "BANNED"
