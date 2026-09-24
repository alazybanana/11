"""system 模块权限初始化数据（种子数据）。

提供注册页 / 管理界面里的 **九种人员身份**（角色）、覆盖五个模块功能的权限资源树，
以及角色与权限的绑定关系。调用入口：

- 迁移脚本 `backend/migrations/versions/20260924_01_seed_rbac_data.py`（随 `alembic upgrade head` 执行）
- 测试里直接调用 `seed_roles_and_permissions(db)` 构造数据

设计约定：
- 权限编码统一为 `模块:功能[:操作]` 形式，如 `system:user:approve`；
- 质检、财务没有独立业务模块，权限按业务域挂靠：
  - QC（质检人员）：`procurement:qc`（到货质检）、`planning:qc`（完工质检）；
  - FINANCE（财务）：各业务模块单据、计划结果与库存流水**只读查看**，不授予任何系统权限管理能力；
- 种子函数幂等：按唯一编码判断是否已存在，存在即跳过，不会覆盖运营期的人工调整。
"""

from typing import Any

from sqlalchemy.orm import Session

from app.modules.system import models
from app.modules.system.enums import DataScope, PermissionType


# --------------------------------------------------------------------------- #
# 一、九种人员身份（角色）
# --------------------------------------------------------------------------- #
ROLE_SEEDS: list[dict[str, Any]] = [
    {
        "code": "ADMIN",
        "name": "管理人员",
        "data_scope": DataScope.ALL.value,
        "sort_order": 1,
        "description": "拥有系统全部功能权限，可管理账号、角色与权限",
    },
    {
        "code": "DESIGN",
        "name": "设计人员",
        "data_scope": DataScope.ALL.value,
        "sort_order": 2,
        "description": "维护物料、BOM、工艺路线，查看基础字典",
    },
    {
        "code": "MAKE",
        "name": "制造人员",
        "data_scope": DataScope.SELF.value,
        "sort_order": 3,
        "description": "查看物料/BOM/工艺，执行生产作业、领料与完工入库",
    },
    {
        "code": "PURCHASE",
        "name": "采购人员",
        "data_scope": DataScope.ORG.value,
        "sort_order": 4,
        "description": "处理采购计划、采购需求、采购订单与到货",
    },
    {
        "code": "SALES",
        "name": "销售人员",
        "data_scope": DataScope.ORG_AND_CHILD.value,
        "sort_order": 5,
        "description": "处理销售需求、销售订单与发货指令，查看可发货量",
    },
    {
        "code": "INVENTORY",
        "name": "库存人员",
        "data_scope": DataScope.ALL.value,
        "sort_order": 6,
        "description": "管理出入库与实时库存，查看发货指令、领料单与到货信息",
    },
    {
        "code": "PLAN",
        "name": "计划管理人员",
        "data_scope": DataScope.ALL.value,
        "sort_order": 7,
        "description": "编制 MPS/MRP/作业计划并派工，查看 BOM/物料/库存/销售需求",
    },
    {
        "code": "QC",
        "name": "质检人员",
        "data_scope": DataScope.ALL.value,
        "sort_order": 8,
        "description": "负责到货质检与完工质检",
    },
    {
        "code": "FINANCE",
        "name": "财务",
        "data_scope": DataScope.ALL.value,
        "sort_order": 9,
        "description": "只读查看各业务单据、计划结果与库存流水，用于核算监督",
    },
]


# --------------------------------------------------------------------------- #
# 二、权限资源树（five modules 的功能划分）
# --------------------------------------------------------------------------- #
# 每条记录：code 权限编码 / name 权限名称 / perm_type 类型 / parent 上级权限编码 /
#           path 前端路由（占位）/ sort_order 排序。父节点必须先于子节点声明。
PERMISSION_SEEDS: list[dict[str, Any]] = [
    # ---- 模块根节点 ----
    {"code": "system", "name": "系统与基础信息管理", "perm_type": PermissionType.MENU.value,
     "parent": None, "path": "/system", "sort_order": 10},
    {"code": "sales", "name": "销售管理", "perm_type": PermissionType.MENU.value,
     "parent": None, "path": "/sales", "sort_order": 20},
    {"code": "planning", "name": "计划管理", "perm_type": PermissionType.MENU.value,
     "parent": None, "path": "/planning", "sort_order": 30},
    {"code": "procurement", "name": "采购管理", "perm_type": PermissionType.MENU.value,
     "parent": None, "path": "/procurement", "sort_order": 40},
    {"code": "inventory", "name": "库存管理", "perm_type": PermissionType.MENU.value,
     "parent": None, "path": "/inventory", "sort_order": 50},
    # ---- system：物料 / BOM / 工艺 / 组织人员 / 字典 / 账号 / 角色 / 权限 / 日志 ----
    {"code": "system:material", "name": "物料管理", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/material", "sort_order": 10},
    {"code": "system:bom", "name": "BOM 管理", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/bom", "sort_order": 20},
    {"code": "system:routing", "name": "工艺路线管理", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/routing", "sort_order": 30},
    {"code": "system:org", "name": "组织与人员", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/org", "sort_order": 40},
    {"code": "system:dictionary", "name": "基础字典", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/dictionary", "sort_order": 50},
    {"code": "system:user", "name": "账号管理", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/user", "sort_order": 60},
    {"code": "system:role", "name": "角色管理", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/role", "sort_order": 70},
    {"code": "system:permission", "name": "权限管理", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/permission", "sort_order": 80},
    {"code": "system:log", "name": "操作日志", "perm_type": PermissionType.MENU.value,
     "parent": "system", "path": "/system/log", "sort_order": 90},
    # system 高危操作（仅管理人员持有）
    {"code": "system:user:approve", "name": "注册审批", "perm_type": PermissionType.BUTTON.value,
     "parent": "system:user", "path": "/system/users/{id}/approve", "sort_order": 10},
    {"code": "system:user:assign", "name": "分配用户角色", "perm_type": PermissionType.BUTTON.value,
     "parent": "system:user", "path": "/system/users/{id}/roles", "sort_order": 20},
    {"code": "system:user:reset", "name": "重置密码", "perm_type": PermissionType.BUTTON.value,
     "parent": "system:user", "path": "/system/users/{id}/password", "sort_order": 30},
    {"code": "system:role:assign", "name": "分配角色权限", "perm_type": PermissionType.BUTTON.value,
     "parent": "system:role", "path": "/system/roles/{id}/permissions", "sort_order": 10},
    {"code": "system:log:clear", "name": "清理操作日志", "perm_type": PermissionType.BUTTON.value,
     "parent": "system:log", "path": "/system/operation-logs", "sort_order": 10},
    # ---- sales：订单 / 需求与预测 / 发货指令 / 可发货量 ----
    {"code": "sales:order", "name": "销售订单", "perm_type": PermissionType.MENU.value,
     "parent": "sales", "path": "/sales/order", "sort_order": 10},
    {"code": "sales:demand", "name": "销售需求与预测", "perm_type": PermissionType.MENU.value,
     "parent": "sales", "path": "/sales/demand", "sort_order": 20},
    {"code": "sales:shipping", "name": "发货指令", "perm_type": PermissionType.MENU.value,
     "parent": "sales", "path": "/sales/shipping", "sort_order": 30},
    {"code": "sales:stock", "name": "可发货量查询", "perm_type": PermissionType.MENU.value,
     "parent": "sales", "path": "/sales/stock", "sort_order": 40},
    # ---- planning：MPS / MRP / 作业计划 / 派工 / 领料 / 完工入库 / 完工质检 ----
    {"code": "planning:mps", "name": "主生产计划 MPS", "perm_type": PermissionType.MENU.value,
     "parent": "planning", "path": "/planning/mps", "sort_order": 10},
    {"code": "planning:mrp", "name": "物料需求计划 MRP", "perm_type": PermissionType.MENU.value,
     "parent": "planning", "path": "/planning/mrp", "sort_order": 20},
    {"code": "planning:schedule", "name": "生产作业计划", "perm_type": PermissionType.MENU.value,
     "parent": "planning", "path": "/planning/schedule", "sort_order": 30},
    {"code": "planning:dispatch", "name": "派工单", "perm_type": PermissionType.MENU.value,
     "parent": "planning", "path": "/planning/dispatch", "sort_order": 40},
    {"code": "planning:picking", "name": "领料单", "perm_type": PermissionType.MENU.value,
     "parent": "planning", "path": "/planning/picking", "sort_order": 50},
    {"code": "planning:finish", "name": "完工入库", "perm_type": PermissionType.MENU.value,
     "parent": "planning", "path": "/planning/finish", "sort_order": 60},
    {"code": "planning:qc", "name": "完工质检", "perm_type": PermissionType.MENU.value,
     "parent": "planning", "path": "/planning/qc", "sort_order": 70},
    # ---- procurement：采购计划 / 采购需求 / 采购订单 / 到货 / 到货质检 ----
    {"code": "procurement:plan", "name": "采购计划", "perm_type": PermissionType.MENU.value,
     "parent": "procurement", "path": "/procurement/plan", "sort_order": 10},
    {"code": "procurement:demand", "name": "采购需求", "perm_type": PermissionType.MENU.value,
     "parent": "procurement", "path": "/procurement/demand", "sort_order": 20},
    {"code": "procurement:order", "name": "采购订单", "perm_type": PermissionType.MENU.value,
     "parent": "procurement", "path": "/procurement/order", "sort_order": 30},
    {"code": "procurement:arrival", "name": "到货管理", "perm_type": PermissionType.MENU.value,
     "parent": "procurement", "path": "/procurement/arrival", "sort_order": 40},
    {"code": "procurement:qc", "name": "到货质检", "perm_type": PermissionType.MENU.value,
     "parent": "procurement", "path": "/procurement/qc", "sort_order": 50},
    # ---- inventory：库存状态 / 入库 / 出库 / 流水与结存 ----
    {"code": "inventory:stock", "name": "库存状态查询", "perm_type": PermissionType.MENU.value,
     "parent": "inventory", "path": "/inventory/stock", "sort_order": 10},
    {"code": "inventory:inbound", "name": "入库管理", "perm_type": PermissionType.MENU.value,
     "parent": "inventory", "path": "/inventory/inbound", "sort_order": 20},
    {"code": "inventory:outbound", "name": "出库管理", "perm_type": PermissionType.MENU.value,
     "parent": "inventory", "path": "/inventory/outbound", "sort_order": 30},
    {"code": "inventory:ledger", "name": "库存流水与结存", "perm_type": PermissionType.MENU.value,
     "parent": "inventory", "path": "/inventory/ledger", "sort_order": 40},
]

# 所有权限编码（供 ADMIN 全量授权使用）
ALL_PERMISSION_CODES: list[str] = [item["code"] for item in PERMISSION_SEEDS]

# --------------------------------------------------------------------------- #
# 三、角色-权限绑定（按五个模块的功能划分）
# --------------------------------------------------------------------------- #
ROLE_PERMISSION_BINDINGS: dict[str, list[str]] = {
    "ADMIN": ALL_PERMISSION_CODES,
    "DESIGN": ["system", "system:material", "system:bom", "system:routing", "system:dictionary"],
    "MAKE": [
        "system", "system:material", "system:bom", "system:routing",
        "planning", "planning:schedule", "planning:dispatch", "planning:picking", "planning:finish",
    ],
    "PURCHASE": [
        "procurement", "procurement:plan", "procurement:demand",
        "procurement:order", "procurement:arrival",
        "system:material", "system:dictionary",
    ],
    "SALES": [
        "sales", "sales:order", "sales:demand", "sales:shipping", "sales:stock",
        "system:material",
    ],
    "INVENTORY": [
        "inventory", "inventory:stock", "inventory:inbound",
        "inventory:outbound", "inventory:ledger",
        "sales", "sales:shipping",
        "planning", "planning:picking",
        "procurement", "procurement:arrival",
        "system:material",
    ],
    "PLAN": [
        "planning", "planning:mps", "planning:mrp", "planning:schedule",
        "planning:dispatch", "planning:picking", "planning:finish",
        "system:bom", "system:material",
        "inventory:stock",
        "sales:demand",
    ],
    "QC": [
        "procurement:qc", "procurement:arrival",
        "planning:qc", "planning:finish",
        "system:material", "system:routing",
    ],
    "FINANCE": [
        "sales:order", "sales:demand", "sales:shipping",
        "procurement:plan", "procurement:order", "procurement:arrival",
        "planning:mps", "planning:mrp", "planning:schedule", "planning:finish",
        "inventory:stock", "inventory:inbound", "inventory:outbound", "inventory:ledger",
        "system:material",
    ],
}


def seed_roles_and_permissions(db: Session) -> None:
    """幂等写入九种身份角色、权限资源树与角色-权限绑定（按编码存在即跳过）。"""

    # 1. 角色：按 code 存在即跳过，不覆盖人工调整
    role_map: dict[str, models.Role] = {}
    for spec in ROLE_SEEDS:
        code = spec["code"]
        role = db.query(models.Role).filter(models.Role.code == code).first()
        if role is None:
            role = models.Role(**spec)
            db.add(role)
            db.flush()
        role_map[code] = role

    # 2. 权限：父节点必须先于子节点写入，子节点拿父节点 ID 挂树
    perm_map: dict[str, models.Permission] = {}
    for spec in PERMISSION_SEEDS:
        code = spec["code"]
        existing = db.query(models.Permission).filter(models.Permission.code == code).first()
        if existing is not None:
            perm_map[code] = existing
            continue
        parent_code = spec.get("parent")
        if parent_code is not None and parent_code not in perm_map:
            raise ValueError(f"权限种子定义错误：{code} 的上级权限 {parent_code} 尚未声明")
        perm = models.Permission(
            code=code,
            name=spec["name"],
            perm_type=spec["perm_type"],
            parent_id=perm_map[parent_code].id if parent_code else None,
            path=spec.get("path"),
            sort_order=int(spec.get("sort_order", 0)),
        )
        db.add(perm)
        db.flush()
        perm_map[code] = perm

    # 3. 绑定：只补缺失的关联，不删除已存在的人工调整
    existing_pairs = {
        (row.role_id, row.permission_id) for row in db.query(models.RolePermission).all()
    }
    for role_code, perm_codes in ROLE_PERMISSION_BINDINGS.items():
        role = role_map[role_code]
        for perm_code in perm_codes:
            if perm_code not in perm_map:
                raise ValueError(f"角色 {role_code} 引用了未定义的权限编码：{perm_code}")
            perm = perm_map[perm_code]
            if (role.id, perm.id) not in existing_pairs:
                db.add(models.RolePermission(role_id=role.id, permission_id=perm.id))

    db.commit()