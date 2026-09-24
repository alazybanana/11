"""contract.py 对外契约测试：BOM 头 / 子件行 / 多层展开 / 工艺工序。

用 API 造数据、直接调契约函数验证返回的 dict 字段与规则，
保证其它模块（planning 的 MRP 展开等）拿到的数据是对的。
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.modules.system import contract

BASE = "/api/v1/system"


def _data(response: Any) -> dict:
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def _material(client: TestClient, admin_headers: dict[str, str], code: str, name: str, **extra: Any) -> int:
    return _data(
        client.post(
            f"{BASE}/materials",
            headers=admin_headers,
            json={"code": code, "name": name, **extra},
        )
    )["id"]


def _bom(client: TestClient, admin_headers: dict[str, str], parent_id: int, code: str, version: str = "V1.0") -> int:
    return _data(
        client.post(
            f"{BASE}/boms",
            headers=admin_headers,
            json={"code": code, "parent_material_id": parent_id, "version": version},
        )
    )["id"]


def _line(client: TestClient, admin_headers: dict[str, str], bom_id: int, child_id: int, **extra: Any) -> None:
    _data(
        client.post(
            f"{BASE}/boms/{bom_id}/lines",
            headers=admin_headers,
            json={"line_no": extra.pop("line_no", 10), "child_material_id": child_id, **extra},
        )
    )


def _release(client: TestClient, admin_headers: dict[str, str], bom_id: int) -> None:
    _data(client.put(f"{BASE}/boms/{bom_id}", headers=admin_headers, json={"status": "RELEASED"}))


def test_contract_bom_and_expand(session_factory: Any, client: TestClient, admin_headers: dict[str, str]) -> None:
    # 成品 FIN-1：普通子件 C-001(×2) + 虚拟半成品 SEMI-1(×1)
    # SEMI-1 再挂一层：C-002(×3) —— 展开时虚拟件穿透，C-002 直接出现且用量连乘
    fin_id = _material(
        client, admin_headers, "FIN-1", "成品甲", material_type="FINISHED", source_type="MAKE"
    )
    semi_id = _material(
        client, admin_headers, "SEMI-1", "虚拟半成品", material_type="SEMI", source_type="MAKE"
    )
    c1_id = _material(client, admin_headers, "C-001", "普通子件")
    c2_id = _material(client, admin_headers, "C-002", "半成品子件")

    fin_bom = _bom(client, admin_headers, fin_id, "BOM-FIN")
    _line(client, admin_headers, fin_bom, c1_id, line_no=10, quantity=2)
    _line(
        client, admin_headers, fin_bom, semi_id, line_no=20, quantity=1,
        is_phantom=True, position="A1", substitute_group="G1", substitute_priority=1,
    )
    semi_bom = _bom(client, admin_headers, semi_id, "BOM-SEMI")
    _line(client, admin_headers, semi_bom, c2_id, line_no=10, quantity=3)
    _release(client, admin_headers, fin_bom)
    _release(client, admin_headers, semi_bom)

    # 再加一个未发布的 V2.0 草稿，验证"按版本取"与"生效过滤"的差异
    draft_bom = _bom(client, admin_headers, fin_id, "BOM-FIN-V2", version="V2.0")
    _line(client, admin_headers, draft_bom, c1_id, line_no=10, quantity=9)

    with session_factory() as db:
        # 生效 BOM 头：只认已发布且在有效期内的版本
        active = contract.get_active_bom(db, fin_id)
        assert active is not None
        assert active["material_id"] == fin_id
        assert active["version"] == "V1.0"
        assert active["status"] == "RELEASED"

        # 指定版本可取到草稿头（供 planning 校对指定版本）
        by_version = contract.get_active_bom(db, fin_id, version="V2.0")
        assert by_version is not None and by_version["status"] == "DRAFT"

        # 生效子件行：未发布版本不参与，字段含虚拟件 / 选配 / 替代料信息
        lines = contract.get_bom_lines(db, fin_id)
        assert [item["material_code"] for item in lines] == ["C-001", "SEMI-1"]
        line_10 = next(item for item in lines if item["line_no"] == 10)
        line_20 = next(item for item in lines if item["line_no"] == 20)
        assert line_10["quantity"] == 2 and line_10["is_phantom"] is False
        assert line_20["is_phantom"] is True
        assert line_20["position"] == "A1"
        assert line_20["substitute_group"] == "G1"
        assert line_20["substitute_priority"] == 1

        # 指定版本取子件行（不走生效过滤）
        draft_lines = contract.get_bom_lines(db, fin_id, version="V2.0")
        assert len(draft_lines) == 1 and draft_lines[0]["quantity"] == 9

        # 多层展开：虚拟件穿透，SEMI-1 不单独成行，C-002 累计用量 = 1 × 3
        flat = contract.expand_bom_lines(db, fin_id)
        codes = {item["material_code"] for item in flat}
        assert "C-001" in codes and "C-002" in codes and "SEMI-1" not in codes
        c2 = next(item for item in flat if item["material_code"] == "C-002")
        assert c2["level"] == 3 and c2["acc_quantity"] == 3

        # 没有 BOM 的物料返回空清单
        assert contract.get_bom_lines(db, c1_id) == []
        assert contract.expand_bom_lines(db, c1_id) == []


def test_contract_routing_steps(session_factory: Any, client: TestClient, admin_headers: dict[str, str]) -> None:
    material_id = _material(
        client, admin_headers, "FIN-2", "成品乙", material_type="FINISHED", source_type="MAKE"
    )
    routing = _data(
        client.post(
            f"{BASE}/routings",
            headers=admin_headers,
            json={"code": "RT-1", "name": "总装", "material_id": material_id, "is_default": True},
        )
    )
    _data(
        client.post(
            f"{BASE}/routings/{routing['id']}/steps",
            headers=admin_headers,
            json={"step_no": 10, "step_name": "总装", "work_center": "WC1", "run_minutes": 12.5, "is_key": True},
        )
    )

    with session_factory() as db:
        steps = contract.get_routing_steps(db, material_id)
        assert len(steps) == 1
        step = steps[0]
        assert step["routing_code"] == "RT-1"
        assert step["step_name"] == "总装"
        assert step["work_center"] == "WC1"
        assert step["run_minutes"] == 12.5
        assert step["is_key"] is True
        # 没有工艺路线的物料返回空列表
        assert contract.get_routing_steps(db, 99999) == []