"""system 模块错误码（占用 1000~1999 区段，见 docs/api/README.md）。

业务代码统一 `raise BusinessException(code=..., message=...)`，
由公共层的统一异常处理器转换成 `{ code, message, data }` 响应。
"""

# ---------- 通用 ---------- #
CODE_NOT_FOUND: int = 1001
"""数据不存在"""
CODE_DUPLICATE_CODE: int = 1002
"""编码已存在"""
CODE_IN_USE: int = 1003
"""数据被引用，不允许删除"""
CODE_INVALID_PARENT: int = 1004
"""上级节点非法（不存在 / 形成环）"""
CODE_INVALID_REFERENCE: int = 1005
"""引用的对象不存在（如产品、组织、字典类型）"""
CODE_HAS_CHILDREN: int = 1006
"""存在下级节点，不允许删除"""
CODE_BOM_CYCLE: int = 1007
"""BOM 结构形成循环引用（自己套自己，或 A→B→A）"""

# ---------- 认证与权限 ---------- #
CODE_LOGIN_FAILED: int = 1101
"""账号或密码错误"""
CODE_USER_DISABLED: int = 1102
"""账号已停用"""
CODE_OLD_PASSWORD_WRONG: int = 1103
"""原密码不正确"""
CODE_UNAUTHORIZED: int = 1104
"""未登录或登录已过期"""
CODE_FORBIDDEN: int = 1105
"""无访问权限"""
CODE_SELF_OPERATION: int = 1106
"""不能对自己执行该操作"""
CODE_ACCOUNT_REJECTED: int = 1107
"""注册申请已被驳回"""
