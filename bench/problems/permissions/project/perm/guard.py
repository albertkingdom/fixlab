"""檢查使用者能不能做這個動作，不行就丟例外。"""

from perm.errors import BannedUser, NotLoggedIn, RoleTooLow
from perm.roles import REQUIRED, ROLE_RANK


def check(user, action):
    if user is None:
        raise NotLoggedIn(action)
    if user["banned"]:
        raise BannedUser(user["name"])
    if ROLE_RANK[user["role"]] < REQUIRED[action]:
        raise RoleTooLow(action)
