"""system 模块核心业务链路测试。

覆盖六个功能域的主链路 + 跨域校验（引用检查、树形、权限、日志）。
"""

from fastapi.testclient import TestClient

BASE = "/api/v1/system"


def _data(response) -> dict:
    """拆包统一响应并断言成功。"""
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def _code(response) -> int:
    return response.json()["code"]


# --------------------------------------------------------------------------- #
# 一、认证与鉴权
# --------------------------------------------------------------------------- #
def test_login_and_auth_guard(client: TestClient) -> None:
    assert _code(client.get(f"{BASE}/materials")) == 1104
    assert _code(
        client.post(f"{BASE}/auth/login", json={"username": "admin", "password": "wrong"})
    ) == 1101

    body = client.post(
        f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}
    ).json()
    assert body["code"] == 0, body
    assert body["data"]["token_type"] == "Bearer"
    assert body["data"]["user"]["is_superuser"] is True

    token = body["data"]["access_token"]
    me = _data(client.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"}))
    assert me["username"] == "admin"


def test_change_own_password(client: TestClient, admin_headers: dict[str, str]) -> None:
    assert _code(
        client.post(
            f"{BASE}/auth/change-password",
            headers=admin_headers,
            json={"old_password": "bad-old", "new_password": "newpass123"},
        )
    ) == 1103

    _data(
        client.post(
            f"{BASE}/auth/change-password",
            headers=admin_headers,
            json={"old_password": "admin123", "new_password": "newpass123"},
        )
    )
    assert _code(
        client.post(f"{BASE}/auth/login", json={"username": "admin", "password": "newpass123"})
    ) == 0


# --------------------------------------------------------------------------- #
# 二、产品 / 物料 / BOM
# --------------------------------------------------------------------------- #
def test_material_crud(client: TestClient, admin_headers: dict[str, str]) -> None:
    created = _data(
        client.post(
            f"{BASE}/materials",
            headers=admin_headers,
            json={"code": "M-001", "name": "坐垫海绵", "unit": "块", "source_type": "PURCHASE"},
        )
    )
    assert created["code"] == "M-001"
    assert created["material_type"] == "RAW"
    material_id = created["id"]

    assert _code(
        client.post(
            f"{BASE}/materials", headers=admin_headers, json={"code": "M-001", "name": "重复"}
        )
    ) == 1002

    assert _data(client.get(f"{BASE}/materials/{material_id}", headers=admin_headers))["name"] == "坐垫海绵"

    updated = _data(
        client.put(
            f"{BASE}/materials/{material_id}", headers=admin_headers, json={"name": "坐垫海绵(改)"}
        )
    )
    assert updated["name"] == "坐垫海绵(改)"
    assert updated["code"] == "M-001"

    page = _data(client.get(f"{BASE}/materials", headers=admin_headers, params={"keyword": "坐垫"}))
    assert page["total"] == 1 and page["items"][0]["id"] == material_id

    _data(client.delete(f"{BASE}/materials/{material_id}", headers=admin_headers))
    assert _code(client.get(f"{BASE}/materials/{material_id}", headers=admin_headers)) == 1001


def test_bom_chain(client: TestClient, admin_headers: dict[str, str]) -> None:
    # 产品已并入物料：BOM 父件用 FINISHED 物料表达
    parent_id = _data(
        client.post(
            f"{BASE}/materials",
            headers=admin_headers,
            json={"code": "P-001", "name": "转椅 A", "material_type": "FINISHED", "source_type": "MAKE"},
        )
    )["id"]
    material_id = _data(
        client.post(
            f"{BASE}/materials", headers=admin_headers, json={"code": "M-002", "name": "五星脚"}
        )
    )["id"]

    bom = _data(
        client.post(
            f"{BASE}/boms",
            headers=admin_headers,
            json={"code": "BOM-001", "parent_material_id": parent_id, "version": "V1.0"},
        )
    )
    assert bom["status"] == "DRAFT" and bom["parent_material_code"] == "P-001"

    line = _data(
        client.post(
            f"{BASE}/boms/{bom['id']}/lines",
            headers=admin_headers,
            json={"line_no": 10, "child_material_id": material_id, "quantity": 5},
        )
    )
    assert line["material_code"] == "M-002"

    detail = _data(client.get(f"{BASE}/boms/{bom['id']}/detail", headers=admin_headers))
    assert detail["line_count"] == 1
    assert detail["lines"][0]["material_name"] == "五星脚"

    # 被 BOM 引用的物料不能删除
    assert _code(client.delete(f"{BASE}/materials/{material_id}", headers=admin_headers)) == 1003

    # 已发布的 BOM 不允许改行，也不允许删除
    _data(client.put(f"{BASE}/boms/{bom['id']}", headers=admin_headers, json={"status": "RELEASED"}))
    assert _code(
        client.post(
            f"{BASE}/boms/{bom['id']}/lines",
            headers=admin_headers,
            json={"line_no": 20, "child_material_id": material_id},
        )
    ) == 1003
    assert _code(client.delete(f"{BASE}/boms/{bom['id']}", headers=admin_headers)) == 1003


# --------------------------------------------------------------------------- #
# 三、工艺路线 / 工序
# --------------------------------------------------------------------------- #
def test_routing_chain(client: TestClient, admin_headers: dict[str, str]) -> None:
    material_id = _data(
        client.post(
            f"{BASE}/materials",
            headers=admin_headers,
            json={"code": "P-002", "name": "转椅 B", "material_type": "FINISHED", "source_type": "MAKE"},
        )
    )["id"]
    routing = _data(
        client.post(
            f"{BASE}/routings",
            headers=admin_headers,
            json={"code": "RT-001", "material_id": material_id, "name": "总装工艺", "is_default": True},
        )
    )

    _data(
        client.post(
            f"{BASE}/routings/{routing['id']}/steps",
            headers=admin_headers,
            json={"step_no": 10, "step_name": "裁剪", "run_minutes": 2.5},
        )
    )
    _data(
        client.post(
            f"{BASE}/routings/{routing['id']}/steps",
            headers=admin_headers,
            json={"step_no": 20, "step_name": "装配", "run_minutes": 7.5, "is_key": True},
        )
    )

    # 工序号重复
    assert _code(
        client.post(
            f"{BASE}/routings/{routing['id']}/steps",
            headers=admin_headers,
            json={"step_no": 20, "step_name": "重复"},
        )
    ) == 1002

    detail = _data(client.get(f"{BASE}/routings/{routing['id']}/detail", headers=admin_headers))
    assert detail["step_count"] == 2
    assert detail["total_minutes"] == 10
    assert detail["is_default"] is True


# --------------------------------------------------------------------------- #
# 四、组织与人员
# --------------------------------------------------------------------------- #
def test_organization_tree(client: TestClient, admin_headers: dict[str, str]) -> None:
    root = _data(
        client.post(
            f"{BASE}/organizations",
            headers=admin_headers,
            json={"code": "ORG-1", "name": "椅业集团", "org_type": "COMPANY"},
        )
    )
    assert root["level"] == 1 and root["path"] == f"/{root['id']}/"

    child = _data(
        client.post(
            f"{BASE}/organizations",
            headers=admin_headers,
            json={"code": "ORG-2", "name": "制造部", "parent_id": root["id"]},
        )
    )
    assert child["level"] == 2 and child["path"] == f"/{root['id']}/{child['id']}/"

    tree = _data(client.get(f"{BASE}/organizations/tree", headers=admin_headers))
    assert len(tree) == 1
    assert tree[0]["code"] == "ORG-1"
    assert [node["code"] for node in tree[0]["children"]] == ["ORG-2"]

    # 上级不能是自己，也不能是自己的下级
    assert _code(
        client.put(
            f"{BASE}/organizations/{root['id']}", headers=admin_headers, json={"parent_id": root["id"]}
        )
    ) == 1004
    assert _code(
        client.put(
            f"{BASE}/organizations/{root['id']}", headers=admin_headers, json={"parent_id": child["id"]}
        )
    ) == 1004

    # 有下级时不能删除
    assert _code(client.delete(f"{BASE}/organizations/{root['id']}", headers=admin_headers)) == 1006

    # 组织下有人时不能删除
    _data(
        client.post(
            f"{BASE}/employees",
            headers=admin_headers,
            json={"code": "E-001", "name": "张三", "org_id": child["id"]},
        )
    )
    assert _code(client.delete(f"{BASE}/organizations/{child['id']}", headers=admin_headers)) == 1003


def test_employee_rejects_unknown_org(client: TestClient, admin_headers: dict[str, str]) -> None:
    assert _code(
        client.post(
            f"{BASE}/employees",
            headers=admin_headers,
            json={"code": "E-002", "name": "李四", "org_id": 9999},
        )
    ) == 1005


# --------------------------------------------------------------------------- #
# 五、共性基础字典
# --------------------------------------------------------------------------- #
def test_dictionary_type_and_items(client: TestClient, admin_headers: dict[str, str]) -> None:
    type_id = _data(
        client.post(
            f"{BASE}/dictionary-types",
            headers=admin_headers,
            json={"code": "MATERIAL_CATEGORY", "name": "物料分类"},
        )
    )["id"]

    item = _data(
        client.post(
            f"{BASE}/dictionary-types/{type_id}/items",
            headers=admin_headers,
            json={"item_code": "SPONGE", "item_label": "海绵类"},
        )
    )
    assert item["type_id"] == type_id

    assert _code(
        client.post(
            f"{BASE}/dictionary-types/{type_id}/items",
            headers=admin_headers,
            json={"item_code": "SPONGE", "item_label": "重复"},
        )
    ) == 1002

    page = _data(
        client.get(f"{BASE}/dictionary-items", headers=admin_headers, params={"type_id": type_id})
    )
    assert page["total"] == 1 and page["items"][0]["type_code"] == "MATERIAL_CATEGORY"

    assert _code(client.delete(f"{BASE}/dictionary-types/{type_id}", headers=admin_headers)) == 1003
    _data(client.delete(f"{BASE}/dictionary-items/{item['id']}", headers=admin_headers))
    _data(client.delete(f"{BASE}/dictionary-types/{type_id}", headers=admin_headers))


# --------------------------------------------------------------------------- #
# 六、访问权限：权限 / 角色 / 账号
# --------------------------------------------------------------------------- #
def test_permission_role_user_flow(client: TestClient, admin_headers: dict[str, str]) -> None:
    permission_id = _data(
        client.post(
            f"{BASE}/permissions",
            headers=admin_headers,
            json={"code": "system:material:list", "name": "物料查询", "perm_type": "MENU"},
        )
    )["id"]

    role = _data(
        client.post(
            f"{BASE}/roles",
            headers=admin_headers,
            json={"code": "PLANNER", "name": "计划员", "permission_ids": [permission_id]},
        )
    )
    assert role["permission_ids"] == [permission_id]

    # 详情 / 单条更新的出参也要带上已分配的权限
    assert _data(client.get(f"{BASE}/roles/{role['id']}", headers=admin_headers))["permission_ids"] == [
        permission_id
    ]

    user = _data(
        client.post(
            f"{BASE}/users",
            headers=admin_headers,
            json={"username": "planner01", "password": "planner123", "role_ids": [role["id"]]},
        )
    )
    assert user["role_ids"] == [role["id"]] and user["role_names"] == ["计划员"]

    # 路由权限树
    tree = _data(client.get(f"{BASE}/permissions/tree", headers=admin_headers))
    assert [node["code"] for node in tree] == ["system:material:list"]

    # 普通用户登录后应拿到角色与权限编码
    login = _data(
        client.post(
            f"{BASE}/auth/login", json={"username": "planner01", "password": "planner123"}
        )
    )
    assert login["user"]["roles"] == ["PLANNER"]
    assert login["user"]["permissions"] == ["system:material:list"]

    # 已分配给角色的权限不能删除
    assert _code(client.delete(f"{BASE}/permissions/{permission_id}", headers=admin_headers)) == 1003
    # 已分配给用户的角色不能删除
    assert _code(client.delete(f"{BASE}/roles/{role['id']}", headers=admin_headers)) == 1003
    # 超级管理员账号不能删除
    assert _code(client.delete(f"{BASE}/users/1", headers=admin_headers)) == 1106


def test_assign_roles_and_reset_password(client: TestClient, admin_headers: dict[str, str]) -> None:
    role_id = _data(
        client.post(f"{BASE}/roles", headers=admin_headers, json={"code": "BUYER", "name": "采购员"})
    )["id"]
    user_id = _data(
        client.post(
            f"{BASE}/users",
            headers=admin_headers,
            json={"username": "buyer01", "password": "buyer123"},
        )
    )["id"]

    assigned = _data(
        client.put(
            f"{BASE}/users/{user_id}/roles", headers=admin_headers, json={"role_ids": [role_id]}
        )
    )
    assert assigned["role_ids"] == [role_id]

    _data(
        client.put(
            f"{BASE}/users/{user_id}/password", headers=admin_headers, json={"password": "reset123"}
        )
    )
    assert _code(
        client.post(f"{BASE}/auth/login", json={"username": "buyer01", "password": "reset123"})
    ) == 0


def test_assign_role_permissions(client: TestClient, admin_headers: dict[str, str]) -> None:
    permission_id = _data(
        client.post(
            f"{BASE}/permissions", headers=admin_headers, json={"code": "system:role:list", "name": "角色查询"}
        )
    )["id"]
    role_id = _data(
        client.post(f"{BASE}/roles", headers=admin_headers, json={"code": "AUDITOR", "name": "审计员"})
    )["id"]

    role = _data(
        client.put(
            f"{BASE}/roles/{role_id}/permissions",
            headers=admin_headers,
            json={"permission_ids": [permission_id]},
        )
    )
    assert role["permission_ids"] == [permission_id]


# --------------------------------------------------------------------------- #
# 七、操作日志
# --------------------------------------------------------------------------- #
def test_operation_log_recorded(client: TestClient, admin_headers: dict[str, str]) -> None:
    _data(
        client.post(
            f"{BASE}/materials", headers=admin_headers, json={"code": "M-003", "name": "扶手"}
        )
    )
    # 失败的操作同样要留痕
    client.post(f"{BASE}/materials", headers=admin_headers, json={"code": "M-003", "name": "重复"})

    success_page = _data(
        client.get(
            f"{BASE}/operation-logs",
            headers=admin_headers,
            params={"module": "system", "action": "CREATE", "status": "SUCCESS"},
        )
    )
    assert success_page["total"] == 1
    assert success_page["items"][0]["username"] == "admin"

    fail_page = _data(
        client.get(f"{BASE}/operation-logs", headers=admin_headers, params={"status": "FAIL"})
    )
    assert fail_page["total"] == 1

    login_logs = _data(
        client.get(f"{BASE}/operation-logs", headers=admin_headers, params={"action": "LOGIN"})
    )
    assert login_logs["total"] >= 1
