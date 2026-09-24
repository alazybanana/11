"""接口级权限鉴权测试：注册自选身份 → 审批 → 按角色权限访问 system 接口。

约定：功能码 = 查看（列表 / 详情），`功能码:manage` = 写操作（新增 / 修改 / 删除），
高危操作使用独立 BUTTON 码。本文件验证接口层真正按这套约定拦截。
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.modules.system import models
from app.modules.system.seed import seed_roles_and_permissions

BASE = "/api/v1/system"


def _code(response: Any) -> int:
    return response.json()["code"]


def _data(response: Any) -> dict:
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def _seed(session_factory: Any) -> None:
    with session_factory() as db:
        seed_roles_and_permissions(db)


def _register(client: TestClient, session_factory: Any, role_code: str, username: str) -> int:
    with session_factory() as db:
        role_id = db.query(models.Role).filter(models.Role.code == role_code).first().id
    response = client.post(
        f"{BASE}/auth/register",
        json={
            "username": username,
            "password": "pass123456",
            "real_name": f"{role_code}用户",
            "role_id": role_id,
        },
    )
    assert _code(response) == 0, response.json()
    return _data(response)["id"]


def _login(client: TestClient, username: str, password: str = "pass123456") -> dict[str, str]:
    body = client.post(
        f"{BASE}/auth/login", json={"username": username, "password": password}
    ).json()
    assert body["code"] == 0, body
    return {"Authorization": f"Bearer {body['data']['access_token']}"}


def _approve(client: TestClient, admin_headers: dict[str, str], user_id: int) -> None:
    assert _code(
        client.post(f"{BASE}/users/{user_id}/approve", headers=admin_headers)
    ) == 0


def test_sales_can_view_but_not_write_materials(
    session_factory: Any, client: TestClient, admin_headers: dict[str, str]
) -> None:
    """销售人员：可查看物料，但新增物料、查看账号、查看 BOM 都要被拦。"""
    _seed(session_factory)
    user_id = _register(client, session_factory, "SALES", "sales1")
    _approve(client, admin_headers, user_id)
    headers = _login(client, "sales1")

    assert _code(client.get(f"{BASE}/materials", headers=headers)) == 0
    assert _code(
        client.post(
            f"{BASE}/materials", headers=headers, json={"code": "M-X", "name": "越权物料"}
        )
    ) == 1105
    assert _code(client.get(f"{BASE}/users", headers=headers)) == 1105
    assert _code(client.get(f"{BASE}/boms", headers=headers)) == 1105


def test_design_can_manage_materials_but_not_admin_users(
    session_factory: Any, client: TestClient, admin_headers: dict[str, str]
) -> None:
    """设计人员：可写物料 / BOM / 工艺，但账号 / 角色 / 权限管理一律禁止。"""
    _seed(session_factory)
    user_id = _register(client, session_factory, "DESIGN", "design1")
    _approve(client, admin_headers, user_id)
    headers = _login(client, "design1")

    material = _data(
        client.post(
            f"{BASE}/materials", headers=headers, json={"code": "D-M-01", "name": "设计物料"}
        )
    )
    assert material["code"] == "D-M-01"

    assert _code(client.get(f"{BASE}/users", headers=headers)) == 1105
    assert _code(client.get(f"{BASE}/roles", headers=headers)) == 1105
    assert _code(client.get(f"{BASE}/permissions", headers=headers)) == 1105
    assert _code(client.get(f"{BASE}/operation-logs", headers=headers)) == 1105
    # 查看类别的字典可见，但写被其 manage 码拦住
    assert _code(client.get(f"{BASE}/dictionary-types", headers=headers)) == 0
    assert _code(
        client.post(
            f"{BASE}/dictionary-types",
            headers=headers,
            json={"code": "D-X", "name": "越权字典"},
        )
    ) == 1105


def test_pending_user_has_guest_permissions(
    session_factory: Any, client: TestClient
) -> None:
    """审批前只有游客权限：能登录、能看自己的信息，但任何受权限码保护的接口都被拦。"""
    _seed(session_factory)
    _register(client, session_factory, "PURCHASE", "pending1")
    headers = _login(client, "pending1")

    assert _code(client.get(f"{BASE}/auth/me", headers=headers)) == 0
    assert _code(client.get(f"{BASE}/materials", headers=headers)) == 1105


def test_unauthenticated_requests_rejected(client: TestClient) -> None:
    assert _code(client.get(f"{BASE}/materials")) == 1104
    assert _code(client.post(f"{BASE}/materials", json={"code": "M-Y", "name": "匿名"})) == 1104


def test_high_risk_operations_require_button_codes(
    session_factory: Any, client: TestClient, admin_headers: dict[str, str]
) -> None:
    """注册审批 / 分配角色 / 分配权限 / 清日志这些高危操作只认独立权限码。"""
    _seed(session_factory)
    user_id = _register(client, session_factory, "INVENTORY", "inv1")
    _approve(client, admin_headers, user_id)
    headers = _login(client, "inv1")

    other_id = _register(client, session_factory, "PLAN", "plan1")
    assert _code(client.post(f"{BASE}/users/{other_id}/approve", headers=headers)) == 1105
    assert _code(client.put(f"{BASE}/users/{other_id}/roles", headers=headers, json={"role_ids": []})) == 1105
    assert _code(
        client.put(f"{BASE}/users/{other_id}/password", headers=headers, json={"password": "x123456"})
    ) == 1105
    assert _code(client.delete(f"{BASE}/operation-logs", headers=headers, params={"before": "2026-01-01T00:00:00"})) == 1105