"""system 模块 Pydantic Schema（信息模型）。

命名约定（全模块统一）：

| 后缀 | 用途 |
| --- | --- |
| `XxxCreate` | 新增入参（`POST`） |
| `XxxUpdate` | 修改入参（`PUT` / `PATCH`），由 `make_update_schema` 自动生成为"全字段可选" |
| `XxxOut` | 出参（不含密码等敏感字段） |

所有 `XxxOut` 继承 `ORMSchema`，可直接由 ORM 对象转换（`from_attributes=True`）。
"""

from datetime import date, datetime
from typing import List, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, create_model

from app.common.response import ApiResponse
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
from app.shared.types import HealthData

# 占位健康检查响应，与其它四个模块保持完全一致的返回结构
HealthResponse = ApiResponse[HealthData]


class ORMSchema(BaseModel):
    """可由 ORM 对象直接转换的出参基类。"""

    model_config = ConfigDict(from_attributes=True)


def make_update_schema(name: str, base: Type[BaseModel]) -> Type[BaseModel]:
    """由 `XxxCreate` 生成"全字段可选"的 `XxxUpdate`，避免两边字段漂移。

    更新接口统一使用 `model_dump(exclude_unset=True)`，
    因此未传的字段不会被覆盖（PUT / PATCH 都表现为局部更新）。
    """
    fields = {
        field_name: (Optional[field.annotation], None)
        for field_name, field in base.model_fields.items()
    }
    return create_model(name, **fields)  # type: ignore[call-overload]


# --------------------------------------------------------------------------- #
# 一、产品信息：物料 / BOM
# --------------------------------------------------------------------------- #
class MaterialBase(BaseModel):
    name: str = Field(max_length=64, description="物料名称")
    spec: Optional[str] = Field(default=None, max_length=128, description="规格型号")
    model: Optional[str] = Field(default=None, max_length=64, description="型号（成品 / 半成品常用）")
    unit: str = Field(default="个", max_length=16, description="计量单位")
    category_code: Optional[str] = Field(default=None, max_length=32, description="物料分类编码")
    material_type: MaterialType = Field(default=MaterialType.RAW, description="物料类型")
    source_type: SourceType = Field(default=SourceType.PURCHASE, description="来源：采购 / 自制")
    standard_cost: Optional[float] = Field(default=None, ge=0, description="标准成本")
    safety_stock: Optional[float] = Field(default=None, ge=0, description="安全库存")
    lead_time_days: Optional[int] = Field(default=None, ge=0, description="采购提前期（天）")
    status: CommonStatus = Field(default=CommonStatus.ENABLED, description="状态")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class MaterialCreate(MaterialBase):
    code: str = Field(max_length=32, description="物料编码")


MaterialUpdate = make_update_schema("MaterialUpdate", MaterialCreate)


class MaterialOut(MaterialBase, ORMSchema):
    id: int
    code: str
    created_at: datetime
    updated_at: datetime


# 成品 / 半成品 / 原材料统一由 `material` 表达，不再单独定义 Product：
# BOM 的父件与子件都只是 `material_id`，多层 BOM 因此天然成立。
class BomBase(BaseModel):
    parent_material_id: int = Field(description="父件物料 ID（本 BOM 描述它由哪些子件构成）")
    bom_type: BomType = Field(default=BomType.MANUFACTURE, description="BOM 类型：设计 / 制造 / 销售")
    version: str = Field(default="V1.0", max_length=16, description="版本号")
    base_qty: float = Field(default=1, gt=0, description="基准数量")
    status: BomStatus = Field(default=BomStatus.DRAFT, description="状态")
    effective_from: Optional[date] = Field(default=None, description="生效日期")
    effective_to: Optional[date] = Field(default=None, description="失效日期")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class BomCreate(BomBase):
    code: str = Field(max_length=32, description="BOM 编码")


BomUpdate = make_update_schema("BomUpdate", BomCreate)


class BomLineBase(BaseModel):
    line_no: int = Field(default=10, ge=1, description="行号")
    child_material_id: int = Field(description="子件物料 ID")
    quantity: float = Field(default=1, gt=0, description="单位用量")
    unit: Optional[str] = Field(default=None, max_length=16, description="单位")
    loss_rate: float = Field(default=0, ge=0, le=1, description="损耗率（0~1）")
    position: Optional[str] = Field(default=None, max_length=64, description="装配位置")
    is_phantom: bool = Field(default=False, description="虚拟件：不实际入库，展开时穿透到下层子件")
    is_optional: bool = Field(default=False, description="可选件：与同选配组的其它行按配置择一")
    option_group: Optional[str] = Field(default=None, max_length=32, description="选配组编码")
    substitute_group: Optional[str] = Field(default=None, max_length=32, description="替代料组编码")
    substitute_priority: int = Field(default=1, ge=1, description="替代优先级，数字小者优先")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class BomLineCreate(BomLineBase):
    """BOM 行的新增入参，`bom_id` 由路径参数决定。"""


BomLineUpdate = make_update_schema("BomLineUpdate", BomLineCreate)


class BomLineOut(BomLineBase, ORMSchema):
    id: int
    bom_id: int
    material_code: Optional[str] = Field(default=None, description="子件物料编码")
    material_name: Optional[str] = Field(default=None, description="子件物料名称")
    material_spec: Optional[str] = Field(default=None, description="子件规格")


class BomOut(BomBase, ORMSchema):
    id: int
    code: str
    parent_material_code: Optional[str] = Field(default=None, description="父件物料编码")
    parent_material_name: Optional[str] = Field(default=None, description="父件物料名称")
    line_count: int = Field(default=0, description="BOM 行数")
    created_at: datetime
    updated_at: datetime


class BomDetailOut(BomOut):
    lines: List[BomLineOut] = Field(default_factory=list, description="BOM 行明细")


class BomTreeNode(BaseModel):
    """多层 BOM 树节点（递归结构）。

    层数不设上限：半成品自己挂了 BOM 就往下多一层，没挂就是叶子节点。
    `acc_quantity` 是沿路径连乘得到的累计用量，MRP 展开可直接用它算毛需求。
    """

    material_id: int = Field(description="物料 ID")
    material_code: str = Field(description="物料编码")
    material_name: str = Field(description="物料名称")
    spec: Optional[str] = Field(default=None, description="规格")
    model: Optional[str] = Field(default=None, description="型号")
    unit: Optional[str] = Field(default=None, description="计量单位")
    level: int = Field(default=1, description="层级，顶层为 1")
    quantity: float = Field(default=1, description="上阶单位用量")
    acc_quantity: float = Field(default=1, description="累计用量（沿路径连乘）")
    is_phantom: bool = Field(default=False, description="虚拟件：展开时穿透，本节点不单独计入需求")
    is_optional: bool = Field(default=False, description="可选件")
    option_group: Optional[str] = Field(default=None, description="选配组编码")
    substitute_group: Optional[str] = Field(default=None, description="替代料组编码")
    substitute_priority: int = Field(default=1, description="替代优先级")
    children: List["BomTreeNode"] = Field(default_factory=list, description="下层子件")


BomTreeNode.model_rebuild()


# --------------------------------------------------------------------------- #
# 二、工艺信息：工艺路线 / 工序
# --------------------------------------------------------------------------- #
class RoutingBase(BaseModel):
    material_id: int = Field(description="适用物料 ID（成品 / 半成品）")
    name: str = Field(max_length=64, description="工艺路线名称")
    version: str = Field(default="V1.0", max_length=16, description="版本号")
    is_default: bool = Field(default=False, description="是否该物料的默认工艺路线")
    status: RoutingStatus = Field(default=RoutingStatus.DRAFT, description="状态")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class RoutingCreate(RoutingBase):
    code: str = Field(max_length=32, description="工艺路线编码")


RoutingUpdate = make_update_schema("RoutingUpdate", RoutingCreate)


class RoutingStepBase(BaseModel):
    step_no: int = Field(default=10, ge=1, description="工序号")
    step_code: Optional[str] = Field(default=None, max_length=32, description="工序编码")
    step_name: str = Field(max_length=64, description="工序名称")
    work_center: Optional[str] = Field(default=None, max_length=32, description="工作中心")
    equipment: Optional[str] = Field(default=None, max_length=64, description="设备 / 工装")
    setup_minutes: Optional[float] = Field(default=None, ge=0, description="准备工时（分钟）")
    run_minutes: Optional[float] = Field(default=None, ge=0, description="单件工时（分钟）")
    is_key: bool = Field(default=False, description="是否关键工序")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class RoutingStepCreate(RoutingStepBase):
    """工序新增入参，`routing_id` 由路径参数决定。"""


RoutingStepUpdate = make_update_schema("RoutingStepUpdate", RoutingStepCreate)


class RoutingStepOut(RoutingStepBase, ORMSchema):
    id: int
    routing_id: int


class RoutingOut(RoutingBase, ORMSchema):
    id: int
    code: str
    material_code: Optional[str] = Field(default=None, description="物料编码")
    material_name: Optional[str] = Field(default=None, description="物料名称")
    step_count: int = Field(default=0, description="工序数")
    total_minutes: Optional[float] = Field(default=None, description="单件总工时（分钟）")
    created_at: datetime
    updated_at: datetime


class RoutingDetailOut(RoutingOut):
    steps: List[RoutingStepOut] = Field(default_factory=list, description="工序明细")


# --------------------------------------------------------------------------- #
# 三、组织与人员
# --------------------------------------------------------------------------- #
class OrganizationBase(BaseModel):
    name: str = Field(max_length=64, description="组织名称")
    parent_id: Optional[int] = Field(default=None, description="上级组织 ID")
    org_type: OrgType = Field(default=OrgType.DEPT, description="组织类型")
    leader: Optional[str] = Field(default=None, max_length=32, description="负责人")
    phone: Optional[str] = Field(default=None, max_length=32, description="联系电话")
    sort_order: int = Field(default=0, description="同级排序")
    is_enabled: bool = Field(default=True, description="是否启用")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class OrganizationCreate(OrganizationBase):
    code: str = Field(max_length=32, description="组织编码")


OrganizationUpdate = make_update_schema("OrganizationUpdate", OrganizationCreate)


class OrganizationOut(OrganizationBase, ORMSchema):
    id: int
    code: str
    path: str
    level: int
    created_at: datetime
    updated_at: datetime


class OrganizationTreeOut(OrganizationOut):
    """组织结构树节点。"""

    children: List["OrganizationTreeOut"] = Field(default_factory=list)


class EmployeeBase(BaseModel):
    name: str = Field(max_length=32, description="姓名")
    gender: Gender = Field(default=Gender.UNKNOWN, description="性别")
    phone: Optional[str] = Field(default=None, max_length=32, description="手机号")
    email: Optional[str] = Field(default=None, max_length=64, description="邮箱")
    org_id: Optional[int] = Field(default=None, description="所属组织 ID")
    position: Optional[str] = Field(default=None, max_length=32, description="岗位")
    hire_date: Optional[date] = Field(default=None, description="入职日期")
    status: EmployeeStatus = Field(default=EmployeeStatus.ACTIVE, description="在职状态")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class EmployeeCreate(EmployeeBase):
    code: str = Field(max_length=32, description="工号")


EmployeeUpdate = make_update_schema("EmployeeUpdate", EmployeeCreate)


class EmployeeOut(EmployeeBase, ORMSchema):
    id: int
    code: str
    org_name: Optional[str] = Field(default=None, description="所属组织名称")
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# 四、共性基础字典
# --------------------------------------------------------------------------- #
class DictionaryTypeBase(BaseModel):
    name: str = Field(max_length=32, description="字典类型名称")
    is_enabled: bool = Field(default=True, description="是否启用")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class DictionaryTypeCreate(DictionaryTypeBase):
    code: str = Field(max_length=32, description="字典类型编码")


DictionaryTypeUpdate = make_update_schema("DictionaryTypeUpdate", DictionaryTypeCreate)


class DictionaryTypeOut(DictionaryTypeBase, ORMSchema):
    id: int
    code: str
    is_system: bool = Field(default=False, description="系统内置字典（禁止删除）")
    created_at: datetime
    updated_at: datetime


class DictionaryItemBase(BaseModel):
    parent_id: Optional[int] = Field(default=None, description="上级字典项 ID")
    item_code: str = Field(max_length=32, description="字典项编码")
    item_label: str = Field(max_length=64, description="字典项显示名")
    item_value: Optional[str] = Field(default=None, max_length=64, description="字典项值")
    sort_order: int = Field(default=0, description="排序")
    is_enabled: bool = Field(default=True, description="是否启用")
    extra: Optional[dict] = Field(default=None, description="扩展属性")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class DictionaryItemCreate(DictionaryItemBase):
    """字典项新增入参，`type_id` 由路径参数决定。"""


DictionaryItemUpdate = make_update_schema("DictionaryItemUpdate", DictionaryItemCreate)


class DictionaryItemOut(DictionaryItemBase, ORMSchema):
    id: int
    type_id: int
    type_code: Optional[str] = Field(default=None, description="字典类型编码")
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# 五、访问权限：用户 / 角色 / 权限
# --------------------------------------------------------------------------- #
class RoleBase(BaseModel):
    name: str = Field(max_length=32, description="角色名称")
    data_scope: DataScope = Field(default=DataScope.ALL, description="数据访问范围")
    sort_order: int = Field(default=0, description="排序")
    is_enabled: bool = Field(default=True, description="是否启用")
    description: Optional[str] = Field(default=None, max_length=255, description="描述")


class RoleCreate(RoleBase):
    code: str = Field(max_length=32, description="角色编码")
    permission_ids: List[int] = Field(default_factory=list, description="关联权限 ID 列表")


RoleUpdate = make_update_schema("RoleUpdate", RoleCreate)


class RoleOut(RoleBase, ORMSchema):
    id: int
    code: str
    permission_ids: List[int] = Field(default_factory=list, description="关联权限 ID 列表")
    created_at: datetime
    updated_at: datetime


class PermissionBase(BaseModel):
    name: str = Field(max_length=32, description="权限名称")
    perm_type: PermissionType = Field(default=PermissionType.MENU, description="类型")
    parent_id: Optional[int] = Field(default=None, description="上级权限 ID")
    path: Optional[str] = Field(default=None, max_length=128, description="前端路由 / 接口路径")
    method: Optional[str] = Field(default=None, max_length=8, description="HTTP 方法")
    sort_order: int = Field(default=0, description="排序")
    is_enabled: bool = Field(default=True, description="是否启用")


class PermissionCreate(PermissionBase):
    code: str = Field(max_length=64, description="权限编码")


PermissionUpdate = make_update_schema("PermissionUpdate", PermissionCreate)


class PermissionOut(PermissionBase, ORMSchema):
    id: int
    code: str
    created_at: datetime
    updated_at: datetime


class PermissionTreeOut(PermissionOut):
    """权限资源树节点。"""

    children: List["PermissionTreeOut"] = Field(default_factory=list)


class UserBase(BaseModel):
    real_name: Optional[str] = Field(default=None, max_length=32, description="姓名")
    employee_id: Optional[int] = Field(default=None, description="关联人员 ID")
    org_id: Optional[int] = Field(default=None, description="所属组织 ID")
    email: Optional[str] = Field(default=None, max_length=64, description="邮箱")
    phone: Optional[str] = Field(default=None, max_length=32, description="手机号")
    is_superuser: bool = Field(default=False, description="是否超级管理员")
    is_enabled: bool = Field(default=True, description="是否启用")
    approval_status: str = Field(
        default=ApprovalStatus.APPROVED.value,
        description="注册审批状态 PENDING/APPROVED/REJECTED",
    )
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class UserCreate(UserBase):
    username: str = Field(min_length=3, max_length=64, description="登录账号")
    password: str = Field(min_length=6, max_length=64, description="初始密码（仅入库哈希）")
    role_ids: List[int] = Field(default_factory=list, description="关联角色 ID 列表")


UserUpdate = make_update_schema("UserUpdate", UserBase)


class UserPasswordUpdate(BaseModel):
    """管理员重置密码。"""

    password: str = Field(min_length=6, max_length=64, description="新密码")


class UserOut(UserBase, ORMSchema):
    id: int
    username: str
    role_ids: List[int] = Field(default_factory=list, description="关联角色 ID 列表")
    role_names: List[str] = Field(default_factory=list, description="关联角色名称")
    org_name: Optional[str] = Field(default=None, description="所属组织名称")
    employee_name: Optional[str] = Field(default=None, description="关联人员姓名")
    last_login_at: Optional[datetime] = Field(default=None, description="最后登录时间")
    created_at: datetime
    updated_at: datetime


class UserRoleAssign(BaseModel):
    """给用户分配角色。"""

    role_ids: List[int] = Field(default_factory=list, description="角色 ID 列表，传空数组表示清空")


class RolePermissionAssign(BaseModel):
    """给角色分配权限。"""

    permission_ids: List[int] = Field(default_factory=list, description="权限 ID 列表")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, description="登录账号")
    password: str = Field(min_length=1, max_length=64, description="密码")


class LoginUserOut(BaseModel):
    """登录返回的用户信息，前端据此渲染菜单与按钮。"""

    id: int
    username: str
    real_name: Optional[str] = None
    is_superuser: bool
    org_id: Optional[int] = None
    approval_status: str = Field(description="注册审批状态 PENDING/APPROVED/REJECTED")
    roles: List[str] = Field(default_factory=list, description="角色编码列表")
    permissions: List[str] = Field(default_factory=list, description="权限编码列表")


class RoleOption(BaseModel):
    """注册页可自选的身份（启用中的角色）。"""

    id: int
    code: str
    name: str


class RegisterRequest(BaseModel):
    """公开注册：自选身份，注册后即可登录（仅游客权限），审批通过后所选角色权限生效。"""

    username: str = Field(min_length=3, max_length=64, description="登录账号")
    password: str = Field(min_length=6, max_length=64, description="密码（仅入库哈希）")
    real_name: Optional[str] = Field(default=None, max_length=32, description="姓名")
    email: Optional[str] = Field(default=None, max_length=64, description="邮箱")
    phone: Optional[str] = Field(default=None, max_length=32, description="手机号")
    role_id: int = Field(description="注册时自选的身份（角色 ID），审批通过后生效")


class TokenOut(BaseModel):
    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(description="有效期（秒）")
    user: LoginUserOut


class ChangePasswordRequest(BaseModel):
    """当前登录用户修改自己的密码。"""

    old_password: str = Field(min_length=1, max_length=64, description="原密码")
    new_password: str = Field(min_length=6, max_length=64, description="新密码")


# --------------------------------------------------------------------------- #
# 六、操作日志
# --------------------------------------------------------------------------- #
class OperationLogOut(ORMSchema):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    module: Optional[str] = None
    action: str
    description: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    ip: Optional[str] = None
    request_params: Optional[str] = None
    status: str
    error_msg: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime
