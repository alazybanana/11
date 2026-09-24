"""BOM 状态流转规则测试：空 BOM 禁发布、RELEASED 头字段冻结、作废禁回发布、停用物料不展开。"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

BASE = "/api/v1/system"


def _code(response: Any) -> int:
    return response.json()["code"]


def _data(response: Any) -> dict:
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def _material(client: TestClient, headers: dict[str, str], code: str, **extra: Any) -> int:
    return _data(client.post(f"{BASE}/materials", headers=headers, json={"code": code, "name": code, **extra}))["id"]


def _bom(client: TestClient, headers: dict[str, str], parent_id: int, code: str = "BOM-S") -> int:
    return _data(
        client.post(
            f"{BASE}/boms",
            headers=headers,
            json={"code": code, "parent_material_id": parent_id},
        )
    )["id"]


def _line(
    client: TestClient, headers: dict[str, str], bom_id: int, child_id: int, quantity: float = 1
) -> None:
    # 行号按当前行数递增，避免同一 BOM 里行号冲突
    detail = _data(client.get(f"{BASE}/boms/{bom_id}/detail", headers=headers))
    line_no = (detail["line_count"] + 1) * 10
    _data(
        client.post(
            f"{BASE}/boms/{bom_id}/lines",
            headers=headers,
            json={"line_no": line_no, "child_material_id": child_id, "quantity": quantity},
        )
    )


def test_empty_bom_cannot_be_released(client: TestClient, admin_headers: dict[str, str]) -> None:
    parent_id = _material(client, admin_headers, "P-EMPTY", material_type="FINISHED")
    bom_id = _bom(client, admin_headers, parent_id)

    assert _code(
        client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "RELEASED"})
    ) == 1003

    # 补一行之后就能发布了
    child_id = _material(client, admin_headers, "C-EMPTY")
    _line(client, admin_headers, bom_id, child_id)
    assert _code(
        client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "RELEASED"})
    ) == 0


def test_released_bom_freezes_header_fields(client: TestClient, admin_headers: dict[str, str]) -> None:
    parent_id = _material(client, admin_headers, "P-FREEZE", material_type="FINISHED")
    child_id = _material(client, admin_headers, "C-FREEZE")
    bom_id = _bom(client, admin_headers, parent_id)
    _line(client, admin_headers, bom_id, child_id)
    _data(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "RELEASED"}))

    # 已发布后：换版本、改有效期、改编码都被冻结；只允许改状态与备注
    assert _code(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"version": "V2.0"})) == 1003
    assert _code(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"effective_from": "2026-01-01"})) == 1003
    assert _code(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"code": "BOM-X"})) == 1003
    assert _code(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"remark": "注意"})) == 0


def test_obsolete_bom_cannot_goto_released_directly(client: TestClient, admin_headers: dict[str, str]) -> None:
    parent_id = _material(client, admin_headers, "P-OBS", material_type="FINISHED")
    child_id = _material(client, admin_headers, "C-OBS")
    bom_id = _bom(client, admin_headers, parent_id)
    _line(client, admin_headers, bom_id, child_id)
    _data(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "RELEASED"}))

    # 发布 → 作废允许
    assert _code(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "OBSOLETE"})) == 0
    # 作废 → 直接发布禁止
    assert _code(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "RELEASED"})) == 1003
    # 作废 → 草稿 → 发布走完整流程允许
    assert _code(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "DRAFT"})) == 0
    assert _code(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "RELEASED"})) == 0


def test_disabled_material_is_excluded_from_expansion(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    parent_id = _material(client, admin_headers, "P-DIS", material_type="FINISHED", source_type="MAKE")
    ok_child = _material(client, admin_headers, "C-DIS-OK")
    off_child = _material(client, admin_headers, "C-DIS-OFF")
    bom_id = _bom(client, admin_headers, parent_id)
    _line(client, admin_headers, bom_id, ok_child, quantity=2)
    _line(client, admin_headers, bom_id, off_child, quantity=3)
    _data(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "RELEASED"}))

    # 停用一个子件后，展开不再包含它
    _data(client.put(f"{BASE}/materials/{off_child}", headers=admin_headers, json={"status": "DISABLED"}))
    flat = _data(
        client.get(f"{BASE}/boms/flat-lines", headers=admin_headers, params={"material_id": parent_id})
    )
    codes = {item["material_code"] for item in flat}
    assert "C-DIS-OK" in codes
    assert "C-DIS-OFF" not in codes

    # 根物料停用后整个展开被拒绝
    _data(client.put(f"{BASE}/materials/{parent_id}", headers=admin_headers, json={"status": "DISABLED"}))
    assert _code(
        client.get(f"{BASE}/boms/tree", headers=admin_headers, params={"material_id": parent_id})
    ) == 1005