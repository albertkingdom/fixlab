"""存取失敗的種類。"""


class AccessError(Exception):
    pass


class NotLoggedIn(AccessError):
    pass


class RoleTooLow(AccessError):
    pass


class BannedUser(AccessError):
    pass
