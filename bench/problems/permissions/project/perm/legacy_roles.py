"""舊版的角色判斷，已經停用，留著對照。沒有任何地方匯入它。"""


def old_is_admin(user):
    return user is not None and user.get("role") == "admin"
