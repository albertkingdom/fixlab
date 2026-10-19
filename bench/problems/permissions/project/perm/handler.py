"""把檢查的結果變成回應字串。"""

from perm.errors import BannedUser, NotLoggedIn, RoleTooLow
from perm.guard import check


def handle(user, action):
    try:
        check(user, action)
        return "OK"
    except NotLoggedIn:
        return "OK (guest)" if action == "read" else "LOGIN"
    except BannedUser:
        return "BANNED"
    except RoleTooLow:
        return "DENIED"
