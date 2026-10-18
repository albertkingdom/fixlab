from perm.handler import handle

MEMBER = {"name": "mia", "role": "member", "banned": False}
ADMIN = {"name": "root", "role": "admin", "banned": False}


def test_guest_can_read_but_not_write():
    assert handle(None, "read") == "OK (guest)"
    assert handle(None, "write") == "LOGIN"


def test_member_cannot_delete():
    assert handle(MEMBER, "delete") == "DENIED"


def test_admin_can_do_everything():
    assert [handle(ADMIN, action) for action in ("read", "write", "delete")] == ["OK", "OK", "OK"]


def test_member_can_read_and_write():
    assert [handle(MEMBER, action) for action in ("read", "write")] == ["OK", "OK"]
