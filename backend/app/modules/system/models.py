"""system 模块 ORM 模型（Owner: system 模块）。

本文件定义**系统与基础信息管理**的全部业务表：

1. 产品与物料信息：`sys_material`（成品/半成品/原材料统一主数据）、`sys_bom`、`sys_bom_item`
2. 工艺信息：`sys_routing`、`sys_routing_operation`
3. 组织与人员：`sys_organization`、`sys_personnel`（全系统唯一员工）
4. 共性基础字典：`sys_dictionary`、`sys_dictionary_item`
5. 访问权限：`sys_user`、`sys_role`、`sys_permission`、`sys_user_role`、`sys_role_permission`
6. 操作日志：`sys_operation_log`

表名已按 data-ownership.md 的模块前缀规范统一为 `sys_` 前缀。

约束（见 docs/architecture/data-ownership.md）：
- 这些表**只有 system 模块能写**，其它模块只能通过本模块的 `contract.py` / HTTP 接口读取；
- 表间关系一律用 ID 引用，**不对其它模块的表建外键**；
- 新增表后必须执行 `alembic revision --autogenerate -m "..."` 生成迁移，并更新 data-ownership.md。
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.system.enums import (
    ApprovalStatus,
    BomStatus,
    BomType,
    CommonStatus,
    DataScope,
    EmployeeStatus,
    Gender,
    MaterialType,
    OrgType,
    PermissionType,
    RoutingStatus,
    SourceType,
)


class TimestampMixin:
    """创建 / 更新时间公共字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间"
    )


# --------------------------------------------------------------------------- #
# 一、产品信息管理：产品 / 物料 / BOM
# --------------------------------------------------------------------------- #
class Material(TimestampMixin, Base):
    """物料主数据（Owner: system）。

    采购件与自制件都在这张表里，`source_type` 决定 MRP 是产生采购需求还是生产需求。
    """

    __tablename__ = "sys_material"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="物料编码")
    name: Mapped[str] = mapped_column(String(64), comment="物料名称")
    spec: Mapped[str | None] = mapped_column(String(128), comment="规格型号")
    model: Mapped[str | None] = mapped_column(String(64), comment="型号（成品 / 半成品常用）")
    unit: Mapped[str] = mapped_column(String(16), default="个", comment="计量单位")
    category_code: Mapped[str | None] = mapped_column(
        String(32), index=True, comment="物料分类（引用 sys_dictionary_item.item_code）"
    )
    material_type: Mapped[str] = mapped_column(
        String(16), default=MaterialType.RAW.value, comment="物料类型 RAW/SEMI/FINISHED/PACK"
    )
    source_type: Mapped[str] = mapped_column(
        String(16), default=SourceType.PURCHASE.value, comment="来源 PURCHASE/MAKE"
    )
    standard_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="标准成本")
    safety_stock: Mapped[float | None] = mapped_column(Numeric(14, 4), comment="安全库存")
    lead_time_days: Mapped[int | None] = mapped_column(Integer, comment="采购提前期（天）")
    status: Mapped[str] = mapped_column(
        String(16), default=CommonStatus.ENABLED.value, comment="状态 ENABLED/DISABLED"
    )
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")


class Bom(TimestampMixin, Base):
    """BOM 头（Owner: system）。

    父件与子件都引用 `material`，因此多层 BOM 天然成立：半成品物料自己再挂一份 BOM
    即可继续向下展开，不需要额外的类型判别列。
    """

    __tablename__ = "sys_bom"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="BOM 编码")
    parent_material_id: Mapped[int] = mapped_column(
        Integer, index=True, comment="父件物料 ID（本 BOM 描述它由哪些子件构成）"
    )
    bom_type: Mapped[str] = mapped_column(
        String(16), default=BomType.MANUFACTURE.value, comment="BOM 类型 DESIGN/MANUFACTURE/SALE"
    )
    version: Mapped[str] = mapped_column(String(16), default="V1.0", comment="版本号")
    base_qty: Mapped[float] = mapped_column(
        Numeric(12, 4), default=1, comment="基准数量（BOM 行用量对应的产出量）"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=BomStatus.DRAFT.value, comment="状态 DRAFT/RELEASED/OBSOLETE"
    )
    effective_from: Mapped[date | None] = mapped_column(Date, comment="生效日期")
    effective_to: Mapped[date | None] = mapped_column(Date, comment="失效日期")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")

    __table_args__ = (
        UniqueConstraint(
            "parent_material_id", "version", "bom_type", name="uq_bom_parent_version_type"
        ),
    )


class BomLine(Base):
    """BOM 行（Owner: system）。子件统一引用 `material`，半成品物料自身再挂 BOM 形成多级结构。"""

    __tablename__ = "sys_bom_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(Integer, index=True, comment="所属 BOM ID")
    line_no: Mapped[int] = mapped_column(Integer, default=10, comment="行号")
    child_material_id: Mapped[int] = mapped_column(Integer, index=True, comment="子件物料 ID")
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), default=1, comment="单位用量")
    unit: Mapped[str | None] = mapped_column(String(16), comment="单位")
    loss_rate: Mapped[float] = mapped_column(Numeric(6, 4), default=0, comment="损耗率（0~1）")
    position: Mapped[str | None] = mapped_column(String(64), comment="装配位置")
    is_phantom: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="虚拟件：不实际入库，展开时直接穿透到下层子件"
    )
    is_optional: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="可选件：与同选配组的其它行按配置择一"
    )
    option_group: Mapped[str | None] = mapped_column(
        String(32), index=True, comment="选配组编码（同组即为同一个可选配置点）"
    )
    substitute_group: Mapped[str | None] = mapped_column(
        String(32), index=True, comment="替代料组编码（同组内互为替代）"
    )
    substitute_priority: Mapped[int] = mapped_column(
        Integer, default=1, comment="替代优先级，数字小者优先选用"
    )
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (UniqueConstraint("bom_id", "line_no", name="uq_bom_line_no"),)


# --------------------------------------------------------------------------- #
# 二、工艺信息管理：工艺路线 / 工序
# --------------------------------------------------------------------------- #
class Routing(TimestampMixin, Base):
    """工艺路线头（Owner: system）。"""

    __tablename__ = "sys_routing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="工艺路线编码")
    material_id: Mapped[int] = mapped_column(Integer, index=True, comment="适用物料 ID")
    name: Mapped[str] = mapped_column(String(64), comment="工艺路线名称")
    version: Mapped[str] = mapped_column(String(16), default="V1.0", comment="版本号")
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否该产品默认工艺路线"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=RoutingStatus.DRAFT.value, comment="状态 DRAFT/RELEASED/OBSOLETE"
    )
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")

    __table_args__ = (
        UniqueConstraint("material_id", "version", name="uq_routing_material_version"),
    )


class RoutingStep(Base):
    """工序（工艺路线行，Owner: system）。"""

    __tablename__ = "sys_routing_operation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    routing_id: Mapped[int] = mapped_column(Integer, index=True, comment="所属工艺路线 ID")
    step_no: Mapped[int] = mapped_column(Integer, default=10, comment="工序号（步序）")
    step_code: Mapped[str | None] = mapped_column(String(32), comment="工序编码")
    step_name: Mapped[str] = mapped_column(String(64), comment="工序名称")
    work_center: Mapped[str | None] = mapped_column(String(32), comment="工作中心")
    equipment: Mapped[str | None] = mapped_column(String(64), comment="设备 / 工装")
    setup_minutes: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="准备工时（分钟）")
    run_minutes: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="单件工时（分钟）")
    is_key: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否关键工序")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("routing_id", "step_no", name="uq_routing_step_no"),
    )


# --------------------------------------------------------------------------- #
# 三、组织与人员信息管理
# --------------------------------------------------------------------------- #
class Organization(TimestampMixin, Base):
    """组织 / 部门（Owner: system）。树形结构：`parent_id` 指向父节点，`path` 便于查子树。"""

    __tablename__ = "sys_organization"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="组织编码")
    name: Mapped[str] = mapped_column(String(64), comment="组织名称")
    parent_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="上级组织 ID")
    path: Mapped[str] = mapped_column(
        String(255), default="/", comment="层级路径，形如 /1/3/，用于查子树"
    )
    level: Mapped[int] = mapped_column(Integer, default=1, comment="层级，从 1 开始")
    org_type: Mapped[str] = mapped_column(
        String(16), default=OrgType.DEPT.value, comment="类型 COMPANY/DEPT/TEAM"
    )
    leader: Mapped[str | None] = mapped_column(String(32), comment="负责人")
    phone: Mapped[str | None] = mapped_column(String(32), comment="联系电话")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="同级排序")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")


class Employee(TimestampMixin, Base):
    """人员档案（Owner: system）。账号（`user`）挂在人员上，实现"人员"与"账号"分离。"""

    __tablename__ = "sys_personnel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="工号")
    name: Mapped[str] = mapped_column(String(32), comment="姓名")
    gender: Mapped[str] = mapped_column(
        String(8), default=Gender.UNKNOWN.value, comment="性别 MALE/FEMALE/UNKNOWN"
    )
    phone: Mapped[str | None] = mapped_column(String(32), comment="手机号")
    email: Mapped[str | None] = mapped_column(String(64), comment="邮箱")
    org_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="所属组织 ID")
    position: Mapped[str | None] = mapped_column(String(32), comment="岗位")
    hire_date: Mapped[date | None] = mapped_column(Date, comment="入职日期")
    status: Mapped[str] = mapped_column(
        String(16), default=EmployeeStatus.ACTIVE.value, comment="在职状态"
    )
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")


# --------------------------------------------------------------------------- #
# 四、共性基础字典管理
# --------------------------------------------------------------------------- #
class DictionaryType(TimestampMixin, Base):
    """字典类型（Owner: system）。例如"物料分类""计量单位""工序类型"。"""

    __tablename__ = "sys_dictionary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="字典类型编码")
    name: Mapped[str] = mapped_column(String(32), comment="字典类型名称")
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="系统内置字典（禁止删除）"
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")


class DictionaryItem(TimestampMixin, Base):
    """字典项（Owner: system）。`parent_id` 支持层级字典（如物料分类树）。"""

    __tablename__ = "sys_dictionary_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True, comment="所属字典类型 ID")
    parent_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="上级字典项 ID")
    item_code: Mapped[str] = mapped_column(String(32), comment="字典项编码")
    item_label: Mapped[str] = mapped_column(String(64), comment="字典项显示名")
    item_value: Mapped[str | None] = mapped_column(String(64), comment="字典项值")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    extra: Mapped[dict | None] = mapped_column(JSON, comment="扩展属性")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")

    __table_args__ = (
        UniqueConstraint("type_id", "item_code", name="uq_dict_item_code"),
    )


# --------------------------------------------------------------------------- #
# 五、系统访问权限管理
# --------------------------------------------------------------------------- #
class User(TimestampMixin, Base):
    """账号（Owner: system）。密码只存哈希，绝不存明文。"""

    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="登录账号")
    password_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希")
    real_name: Mapped[str | None] = mapped_column(String(32), comment="姓名")
    employee_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="关联人员 ID")
    org_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="所属组织 ID")
    email: Mapped[str | None] = mapped_column(String(64), comment="邮箱")
    phone: Mapped[str | None] = mapped_column(String(32), comment="手机号")
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否超级管理员")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    approval_status: Mapped[str] = mapped_column(
        String(16),
        default=ApprovalStatus.APPROVED.value,
        index=True,
        comment="注册审批状态 PENDING/APPROVED/REJECTED（管理员与存量账号默认 APPROVED）",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最后登录时间")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")


class Role(TimestampMixin, Base):
    """角色（Owner: system）。`data_scope` 即"访问范围"。"""

    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="角色编码")
    name: Mapped[str] = mapped_column(String(32), comment="角色名称")
    data_scope: Mapped[str] = mapped_column(
        String(16), default=DataScope.ALL.value, comment="访问范围 ALL/ORG/ORG_AND_CHILD/SELF/CUSTOM"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    description: Mapped[str | None] = mapped_column(String(255), comment="描述")


class Permission(TimestampMixin, Base):
    """权限资源（Owner: system）。菜单 / 按钮 / 接口统一用一棵资源树描述。"""

    __tablename__ = "sys_permission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="权限编码")
    name: Mapped[str] = mapped_column(String(32), comment="权限名称")
    perm_type: Mapped[str] = mapped_column(
        String(16), default=PermissionType.MENU.value, comment="类型 MENU/BUTTON/API"
    )
    parent_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="上级权限 ID")
    path: Mapped[str | None] = mapped_column(String(128), comment="前端路由 / 接口路径")
    method: Mapped[str | None] = mapped_column(String(8), comment="HTTP 方法（perm_type=API 时）")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")


class UserRole(Base):
    """用户-角色关联（Owner: system）。"""

    __tablename__ = "sys_user_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, comment="用户 ID")
    role_id: Mapped[int] = mapped_column(Integer, index=True, comment="角色 ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)


class RolePermission(Base):
    """角色-权限关联（Owner: system）。"""

    __tablename__ = "sys_role_permission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, index=True, comment="角色 ID")
    permission_id: Mapped[int] = mapped_column(Integer, index=True, comment="权限 ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)


# --------------------------------------------------------------------------- #
# 六、系统操作日志管理
# --------------------------------------------------------------------------- #
class OperationLog(Base):
    """操作日志（Owner: system）。只插入、不修改，查询接口只读。"""

    __tablename__ = "sys_operation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="操作人 ID")
    username: Mapped[str | None] = mapped_column(String(64), index=True, comment="操作人账号")
    module: Mapped[str | None] = mapped_column(String(32), index=True, comment="所属模块")
    action: Mapped[str] = mapped_column(String(16), default="OTHER", comment="动作类型")
    description: Mapped[str | None] = mapped_column(String(128), comment="操作描述")
    method: Mapped[str | None] = mapped_column(String(8), comment="HTTP 方法")
    path: Mapped[str | None] = mapped_column(String(128), comment="请求路径")
    ip: Mapped[str | None] = mapped_column(String(64), comment="客户端 IP")
    request_params: Mapped[str | None] = mapped_column(Text, comment="请求参数（已脱敏）")
    status: Mapped[str] = mapped_column(String(16), default="SUCCESS", comment="结果 SUCCESS/FAIL")
    error_msg: Mapped[str | None] = mapped_column(Text, comment="错误信息")
    duration_ms: Mapped[int | None] = mapped_column(Integer, comment="耗时（毫秒）")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False, index=True, comment="操作时间"
    )
