"""RBAC 种子数据测试：九种身份角色、权限资源树与角色-权限绑定。

复用 `conftest.py` 的 SQLite 内存库夹具，不依赖本机 MySQL。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.system import models
from app.modules.system.seed import (
    PERMISSION_SEEDS,
    ROLE_PERMISSION_BINDINGS,
    ROLE_SEEDS,
    seed_roles_and_permissions,
)

EXPECTED_ROLE_CODES = [
    "ADMIN", "DESIGN", "MAKE", "PURCHASE", "SALES", "INVENTORY", "PLAN", "QC", "FINANCE",
]


def _count(db: Session, model: Any) -> int:
    return db.query(model).count()


def _granted(db: Session, role_code: str) -> set[str]:
    """取某个角色实际拥有的权限编码集合。"""
    rows = (
        db.query(models.Permission.code)
        .join(models.RolePermission, models.RolePermission.permission_id == models.Permission.id)
        .join(models.Role, models.Role.id == models.RolePermission.role_id)
        .filter(models.Role.code == role_code)
        .all()
    )
    return {row[0] for row in rows}


def test_seed_creates_nine_roles(session_factory: Any) -> None:
    with session_factory() as db:
        seed_roles_and_permissions(db)
        roles = {role.code: role for role in db.query(models.Role).all()}
        assert sorted(roles) == sorted(EXPECTED_ROLE_CODES)
        assert all(role.is_enabled for role in roles.values())


def test_seed_creates_permission_tree(session_factory: Any) -> None:
    with session_factory() as db:
        seed_roles_and_permissions(db)
        perms = {perm.code: perm for perm in db.query(models.Permission).all()}
        # 每个声明过的权限编码都已落库
        assert set(perms) == {spec["code"] for spec in PERMISSION_SEEDS}
        # 非根节点都挂到了存在的父节点上
        for spec in PERMISSION_SEEDS:
            if spec.get("parent"):
                assert perms[spec["code"]].parent_id == perms[spec["parent"]].id


def test_role_permission_bindings_resolve_to_existing_rows(session_factory: Any) -> None:
    with session_factory() as db:
        seed_roles_and_permissions(db)
        roles = {role.code: role.id for role in db.query(models.Role).all()}
        perms = {perm.code: perm.id for perm in db.query(models.Permission).all()}
        pairs = {
            (row.role_id, row.permission_id)
            for row in db.query(models.RolePermission).all()
        }
        for role_code, perm_codes in ROLE_PERMISSION_BINDINGS.items():
            assert role_code in roles
            for perm_code in perm_codes:
                assert perm_code in perms
                assert (roles[role_code], perms[perm_code]) in pairs


def test_qc_and_finance_scope(session_factory: Any) -> None:
    """QC 只管质检、财务只有业务域只读权限，都不碰系统权限管理。"""
    with session_factory() as db:
        seed_roles_and_permissions(db)

        assert "procurement:qc" in _granted(db, "QC")
        assert "planning:qc" in _granted(db, "QC")
        assert "system:permission" not in _granted(db, "QC")
        # 财务只读监督，不授予系统权限管理能力
        finance = _granted(db, "FINANCE")
        assert "system:permission" not in finance
        assert "system:role" not in finance
        assert "inventory:ledger" in finance


def test_manage_permissions_bindings(session_factory: Any) -> None:
    """功能码=查看、`:manage`=写操作：设计人员可写物料/BOM/工艺，QC/财务没有任何写码。"""
    with session_factory() as db:
        seed_roles_and_permissions(db)

        design = _granted(db, "DESIGN")
        assert "system:material:manage" in design
        assert "system:bom:manage" in design
        assert "system:routing:manage" in design
        assert "system:dictionary:manage" not in design
        assert "system:user" not in design

        # 质检与财务只有查看类权限，不持有任何 :manage 写码
        for role_code in ("QC", "FINANCE"):
            assert not {code for code in _granted(db, role_code) if code.endswith(":manage")}

        # 管理人员全量：含新增的 :manage 码
        admin = _granted(db, "ADMIN")
        for spec in PERMISSION_SEEDS:
            assert spec["code"] in admin


def test_seed_is_idempotent(session_factory: Any) -> None:
    with session_factory() as db:
        seed_roles_and_permissions(db)
        role_count = _count(db, models.Role)
        perm_count = _count(db, models.Permission)
        binding_count = _count(db, models.RolePermission)
        # 重复执行不产生重复数据
        seed_roles_and_permissions(db)
        assert _count(db, models.Role) == role_count
        assert _count(db, models.Permission) == perm_count
        assert _count(db, models.RolePermission) == binding_count


def test_register_options_include_qc_and_finance(session_factory: Any, client: Any) -> None:
    """注册页可选身份应包含新增的质检人员与财务。"""
    with session_factory() as db:
        seed_roles_and_permissions(db)
    response = client.get("/api/v1/system/auth/roles-available")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    options = {item["code"]: item["name"] for item in body["data"]}
    assert options["QC"] == "质检人员"
    assert options["FINANCE"] == "财务"
    assert set(options) == set(EXPECTED_ROLE_CODES)