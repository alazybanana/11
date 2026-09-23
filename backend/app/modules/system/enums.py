"""system 模块业务枚举。

只属于本模块的业务枚举定义在这里（公共层 `app/shared/enums.py` 只放跨模块共享枚举）。
数据库统一用 `String` 存枚举值，由 Pydantic Schema 做取值校验，
便于后续新增枚举值而不需要改表结构。
"""

from enum import Enum


class CommonStatus(str, Enum):
    """通用启用状态，产品 / 物料 / 字典 / 角色等复用。"""

    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


class ApprovalStatus(str, Enum):
    """账号注册审批状态。

    - PENDING   已注册、待人事主管批准，不能登录
    - APPROVED  已批准，正常登录（存量账号与管理员创建账号默认此值）
    - REJECTED  已驳回，不能登录
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OrgType(str, Enum):
    """组织类型。"""

    COMPANY = "COMPANY"
    DEPT = "DEPT"
    TEAM = "TEAM"


class EmployeeStatus(str, Enum):
    """人员在职状态。"""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LEAVE = "LEAVE"


class Gender(str, Enum):
    """性别。"""

    MALE = "MALE"
    FEMALE = "FEMALE"
    UNKNOWN = "UNKNOWN"


class MaterialType(str, Enum):
    """物料类型。"""

    RAW = "RAW"
    """原材料"""
    SEMI = "SEMI"
    """半成品"""
    FINISHED = "FINISHED"
    """成品"""
    PACK = "PACK"
    """包装物"""


class SourceType(str, Enum):
    """物料来源，MRP 运算据此区分"采购件"与"自制件"。"""

    PURCHASE = "PURCHASE"
    """采购"""
    MAKE = "MAKE"
    """自制"""


class BomType(str, Enum):
    """BOM 类型。

    同一个物料可以同时存在多种 BOM，各自独立编版本：
    - DESIGN      设计 BOM（EBOM），设计部门维护，描述"产品由什么构成"
    - MANUFACTURE 制造 BOM（MBOM），在 EBOM 基础上补工艺用料，MRP 运算以它为准
    - SALE        销售 BOM（SBOM），面向客户报价与选配
    """

    DESIGN = "DESIGN"
    MANUFACTURE = "MANUFACTURE"
    SALE = "SALE"


class BomStatus(str, Enum):
    """BOM 状态。"""

    DRAFT = "DRAFT"
    RELEASED = "RELEASED"
    OBSOLETE = "OBSOLETE"


class RoutingStatus(str, Enum):
    """工艺路线状态。"""

    DRAFT = "DRAFT"
    RELEASED = "RELEASED"
    OBSOLETE = "OBSOLETE"


class PermissionType(str, Enum):
    """权限（资源）类型。"""

    MENU = "MENU"
    """菜单"""
    BUTTON = "BUTTON"
    """按钮 / 操作"""
    API = "API"
    """后端接口"""


class DataScope(str, Enum):
    """角色的数据访问范围。"""

    ALL = "ALL"
    """全部数据"""
    ORG = "ORG"
    """本组织"""
    ORG_AND_CHILD = "ORG_AND_CHILD"
    """本组织及下级组织"""
    SELF = "SELF"
    """仅本人"""
    CUSTOM = "CUSTOM"
    """自定义组织集合"""


class OperationAction(str, Enum):
    """操作日志的动作类型。"""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    QUERY = "QUERY"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    OTHER = "OTHER"


class LogStatus(str, Enum):
    """操作结果状态。"""

    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
