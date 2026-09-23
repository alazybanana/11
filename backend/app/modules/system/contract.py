"""system 模块对外契约（Service Contract）。

**这是其它模块唯一允许 import 的 system 模块文件**（见 docs/architecture/module-boundaries.md）。
sales / planning / procurement / inventory 需要产品、物料、BOM、工艺路线、组织人员、
字典时，请调用本文件的函数，**不要** import `service.py` / `repository.py` / `models.py`，
也不要跨模块 JOIN 本模块的表。

约定：
1. 本文件的函数**都是只读**的，返回 `dict` 而非 ORM 对象，避免把本模块的表结构泄漏出去；
2. 返回的 `dict` 键名即为契约的一部分，变更键名等同于破坏性变更，需要同步通知各模块；
3. 写操作（新增 / 修改基础数据）不提供契约，只能通过 `/api/v1/system/...` 接口由管理员操作。

典型用法：

```python
# planning 做 MRP 展开时需要 BOM 子件
from app.modules.system.contract import get_bom_lines

for line in get_bom_lines(db, product_id=12):
    material_code, quantity = line["material_code"], line["quantity"]
```
"""

from datetime import date
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.modules.system import models
from app.modules.system.deps import (
    CurrentUser,
    OptionalCurrentUser,
    client_ip,
    get_current_user,
    get_optional_current_user,
    operation_log,
    require_permission,
)
from app.modules.system.enums import BomStatus
from app.modules.system.repository import (
    BomLineRepository,
    BomRepository,
    DictionaryItemRepository,
    DictionaryTypeRepository,
    EmployeeRepository,
    MaterialRepository,
    OrganizationRepository,
    PermissionRepository,
    ProductRepository,
    RolePermissionRepository,
    RoleRepository,
    RoutingRepository,
    RoutingStepRepository,
    UserRepository,
    UserRoleRepository,
)

__all__ = [
    # 认证与日志
    "CurrentUser",
    "OptionalCurrentUser",
    "get_current_user",
    "get_optional_current_user",
    "require_permission",
    "operation_log",
    "client_ip",
    "log_operation",
    # 产品 / 物料
    "get_product",
    "get_products_by_ids",
    "get_material",
    "get_materials_by_ids",
    # BOM / 工艺路线
    "get_active_bom",
    "get_bom_lines",
    "get_routing_steps",
    # 组织 / 人员
    "get_organization",
    "get_organization_scope_ids",
    "get_employee",
    # 字典
    "get_dictionary_items",
    # 账号 / 角色 / 权限
    "get_user",
    "get_user_role_codes",
    "get_user_permission_codes",
]


# --------------------------------------------------------------------------- #
# 产品 / 物料
# --------------------------------------------------------------------------- #
def _product_dict(product: models.Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "code": product.code,
        "name": product.name,
        "spec": product.spec,
        "model": product.model,
        "unit": product.unit,
        "category_code": product.category_code,
        "standard_cost": float(product.standard_cost) if product.standard_cost is not None else None,
        "status": product.status,
    }


def _material_dict(material: models.Material) -> dict[str, Any]:
    return {
        "id": material.id,
        "code": material.code,
        "name": material.name,
        "spec": material.spec,
        "unit": material.unit,
        "category_code": material.category_code,
        "material_type": material.material_type,
        # PURCHASE=采购件（MRP 产生采购需求）/ MAKE=自制件（MRP 产生生产需求）
        "source_type": material.source_type,
        "standard_cost": float(material.standard_cost) if material.standard_cost is not None else None,
        "safety_stock": float(material.safety_stock) if material.safety_stock is not None else None,
        "lead_time_days": material.lead_time_days,
        "status": material.status,
    }


def get_product(db: Session, product_id: int) -> Optional[dict[str, Any]]:
    """按 ID 取产品，不存在返回 None。"""
    product = ProductRepository(db).get(product_id)
    return _product_dict(product) if product is not None else None


def get_products_by_ids(db: Session, product_ids: Iterable[int]) -> list[dict[str, Any]]:
    """批量取产品（sales 做订单行、planning 做 MPS 时常用）。"""
    return [_product_dict(item) for item in ProductRepository(db).get_by_ids(product_ids)]


def get_material(db: Session, material_id: int) -> Optional[dict[str, Any]]:
    """按 ID 取物料，不存在返回 None。"""
    material = MaterialRepository(db).get(material_id)
    return _material_dict(material) if material is not None else None


def get_materials_by_ids(db: Session, material_ids: Iterable[int]) -> list[dict[str, Any]]:
    """批量取物料。"""
    return [_material_dict(item) for item in MaterialRepository(db).get_by_ids(material_ids)]


# --------------------------------------------------------------------------- #
# BOM / 工艺路线
# --------------------------------------------------------------------------- #
def get_active_bom(db: Session, product_id: int) -> Optional[dict[str, Any]]:
    """取产品当前生效的 BOM 头（优先取"已发布且在有效期内"的版本）。"""
    candidates = [
        bom
        for bom in BomRepository(db).list_all(filters={"product_id": product_id})
        if bom.status == BomStatus.RELEASED.value
    ]
    if not candidates:
        return None
    today = date.today()
    effective = [
        bom
        for bom in candidates
        if (bom.effective_from is None or bom.effective_from <= today)
        and (bom.effective_to is None or bom.effective_to >= today)
    ]
    bom = max(effective or candidates, key=lambda item: item.id)
    return {
        "id": bom.id,
        "code": bom.code,
        "product_id": bom.product_id,
        "version": bom.version,
        "base_qty": float(bom.base_qty),
        "status": bom.status,
        "effective_from": bom.effective_from,
        "effective_to": bom.effective_to,
    }


def get_bom_lines(db: Session, product_id: int, version: Optional[str] = None) -> list[dict[str, Any]]:
    """取产品 BOM 的子件行，供 MRP / 生产作业计划展开用料。

    返回字段：`bom_id`、`bom_version`、`line_no`、`material_id`、`material_code`、
    `material_name`、`material_unit`、`quantity`、`loss_rate`、`source_type`。

    - 不传 `version` 时取当前生效 BOM（`get_active_bom`）；
    - BOM 不存在或未发布时返回空列表（调用方据此判断能否展开）。
    """
    if version is None:
        bom_info = get_active_bom(db, product_id)
    else:
        bom = BomRepository(db).get_by(product_id=product_id, version=version)
        bom_info = {"id": bom.id, "version": bom.version} if bom is not None else None
    if bom_info is None:
        return []

    lines = BomLineRepository(db).list_by_bom(int(bom_info["id"]))
    material_map = {
        item.id: item for item in MaterialRepository(db).get_by_ids(
            {line.child_material_id for line in lines}
        )
    }
    result: list[dict[str, Any]] = []
    for line in lines:
        material = material_map.get(line.child_material_id)
        result.append(
            {
                "bom_id": line.bom_id,
                "bom_version": bom_info["version"],
                "line_no": line.line_no,
                "material_id": line.child_material_id,
                "material_code": getattr(material, "code", None),
                "material_name": getattr(material, "name", None),
                "material_unit": getattr(material, "unit", None) or line.unit,
                "quantity": float(line.quantity),
                "loss_rate": float(line.loss_rate),
                "source_type": getattr(material, "source_type", None),
            }
        )
    return result


def get_routing_steps(db: Session, product_id: int, version: Optional[str] = None) -> list[dict[str, Any]]:
    """取产品工艺路线的工序列表，供 planning 排产 / 派工单使用。

    返回字段：`routing_id`、`routing_code`、`step_no`、`step_code`、`step_name`、
    `work_center`、`equipment`、`setup_minutes`、`run_minutes`、`is_key`。
    默认取该产品被标记为"默认"的工艺路线。
    """
    repo = RoutingRepository(db)
    routing = (
        repo.get_by(product_id=product_id, version=version)
        if version is not None
        else repo.get_by(product_id=product_id, is_default=True)
    )
    if routing is None:
        return []

    return [
        {
            "routing_id": routing.id,
            "routing_code": routing.code,
            "step_no": step.step_no,
            "step_code": step.step_code,
            "step_name": step.step_name,
            "work_center": step.work_center,
            "equipment": step.equipment,
            "setup_minutes": float(step.setup_minutes) if step.setup_minutes is not None else None,
            "run_minutes": float(step.run_minutes) if step.run_minutes is not None else None,
            "is_key": step.is_key,
        }
        for step in RoutingStepRepository(db).list_by_routing(routing.id)
    ]


# --------------------------------------------------------------------------- #
# 组织 / 人员
# --------------------------------------------------------------------------- #
def get_organization(db: Session, org_id: int) -> Optional[dict[str, Any]]:
    """按 ID 取组织。"""
    org = OrganizationRepository(db).get(org_id)
    if org is None:
        return None
    return {
        "id": org.id,
        "code": org.code,
        "name": org.name,
        "parent_id": org.parent_id,
        "path": org.path,
        "level": org.level,
        "org_type": org.org_type,
        "is_enabled": org.is_enabled,
    }


def get_organization_scope_ids(db: Session, org_id: int, *, include_children: bool = True) -> list[int]:
    """取组织的数据范围 ID 列表（含自身，可选含全部下级）。

    供各模块实现"访问范围"过滤：`ORG` 用自身，`ORG_AND_CHILD` 传 `include_children=True`。
    """
    org = OrganizationRepository(db).get(org_id)
    if org is None:
        return []
    if not include_children:
        return [org.id]
    return OrganizationRepository(db).descendant_ids(org.path)


def get_employee(db: Session, employee_id: int) -> Optional[dict[str, Any]]:
    """按 ID 取人员档案。"""
    employee = EmployeeRepository(db).get(employee_id)
    if employee is None:
        return None
    return {
        "id": employee.id,
        "code": employee.code,
        "name": employee.name,
        "org_id": employee.org_id,
        "position": employee.position,
        "status": employee.status,
    }


# --------------------------------------------------------------------------- #
# 字典
# --------------------------------------------------------------------------- #
def get_dictionary_items(db: Session, type_code: str) -> list[dict[str, Any]]:
    """按键取字典项（前端下拉、后端校验枚举值都用它）。"""
    dict_type = DictionaryTypeRepository(db).get_by(code=type_code)
    if dict_type is None:
        return []
    items = DictionaryItemRepository(db).list_all(
        filters={"type_id": dict_type.id, "is_enabled": True}
    )
    return [
        {
            "id": item.id,
            "item_code": item.item_code,
            "item_label": item.item_label,
            "item_value": item.item_value,
            "parent_id": item.parent_id,
        }
        for item in items
    ]


# --------------------------------------------------------------------------- #
# 账号 / 角色 / 权限
# --------------------------------------------------------------------------- #
def get_user(db: Session, user_id: int) -> Optional[dict[str, Any]]:
    """按 ID 取账号（不含密码哈希）。"""
    user = UserRepository(db).get(user_id)
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "org_id": user.org_id,
        "employee_id": user.employee_id,
        "is_superuser": user.is_superuser,
        "is_enabled": user.is_enabled,
    }


def get_user_role_codes(db: Session, user_id: int) -> list[str]:
    """取用户拥有的角色编码列表。"""
    role_ids = UserRoleRepository(db).list_role_ids(user_id)
    return [role.code for role in RoleRepository(db).get_by_ids(role_ids)]


def get_user_permission_codes(db: Session, user_id: int) -> list[str]:
    """取用户拥有的权限编码列表（超级管理员返回全部权限编码）。"""
    user = UserRepository(db).get(user_id)
    if user is None:
        return []
    if user.is_superuser:
        return [item.code for item in PermissionRepository(db).list_all()]
    permission_ids = _flat_permission_ids(db, user_id)
    return [item.code for item in PermissionRepository(db).get_by_ids(permission_ids)]


def _flat_permission_ids(db: Session, user_id: int) -> set[int]:
    role_ids = [
        role.id
        for role in RoleRepository(db).get_by_ids(UserRoleRepository(db).list_role_ids(user_id))
        if role.is_enabled
    ]
    mapped = RolePermissionRepository(db).map_permission_ids(role_ids)
    return {permission_id for ids in mapped.values() for permission_id in ids}


# --------------------------------------------------------------------------- #
# 操作日志（横切能力，供其它模块调用）
# --------------------------------------------------------------------------- #
def log_operation(
    db: Session,
    *,
    module: str,
    action: str,
    description: Optional[str] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    ip: Optional[str] = None,
    request_params: Optional[str] = None,
    status: str = "SUCCESS",
    error_msg: Optional[str] = None,
    duration_ms: Optional[int] = None,
    commit: bool = True,
) -> None:
    """写一条操作日志。

    其它模块**不要自己建日志表**，统一调用本函数（或直接使用 `operation_log` 依赖项）：

    ```python
    log_operation(db, module="planning", action="CREATE", description="下达派工单")
    ```
    """
    # 延迟导入避免与其依赖的 service 形成循环导入
    from app.modules.system.service import OperationLogService

    OperationLogService(db).write(
        module=module,
        action=action,
        description=description,
        user_id=user_id,
        username=username,
        method=method,
        path=path,
        ip=ip,
        request_params=request_params,
        status=status,
        error_msg=error_msg,
        duration_ms=duration_ms,
        commit=commit,
    )
