# -*- coding: utf-8 -*-
"""生成《系统与基础信息管理》ER 图（关键字段版，PNG）。

用法（Windows，在仓库根目录执行）:
    backend\\.venv\\Scripts\\python.exe tools\\gen_er_diagram.py

输出: docs/system/er-diagram.png
表结构来源: backend/app/modules/system/models.py（15 张表，统一 sys_ 前缀，六大功能分组）。
绘图规范:
- 直线正交连线、无彩色底纹；
- 关系均为 N:1 —— "N" 标在子表端，"1" 标在父表端；
- 程序化碰撞修正：基数标注与说明文字会自动避开表框、连线与其它标注。
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# --------------------------------------------------------------------------- #
# 表定义: key -> (标题, x, y_top, [(前缀, 文本), ...])
# 前缀 ∈ {"PK", "UK", "FK", ""}；表宽固定 TABLE_W，高度 = TITLE_H + ROW_H × 行数
# --------------------------------------------------------------------------- #
TABLE_W = 4.4
ROW_H = 0.62
TITLE_H = 0.85

TABLES = {
    "organization": ("sys_organization 组织", 1.2, 31.6, [
        ("PK", "id"),
        ("UK", "code"),
        ("", "name"),
        ("FK", "parent_id → 组织"),
        ("", "org_type"),
        ("", "leader"),
    ]),
    "personnel": ("sys_personnel 人员档案", 7.0, 31.6, [
        ("PK", "id"),
        ("UK", "code"),
        ("", "name"),
        ("FK", "org_id → 组织"),
        ("", "position"),
        ("", "status"),
    ]),
    "user": ("sys_user 账号", 1.2, 17.4, [
        ("PK", "id"),
        ("UK", "username"),
        ("", "real_name"),
        ("FK", "employee_id → 人员"),
        ("FK", "org_id → 组织"),
        ("", "approval_status"),
        ("", "is_superuser"),
    ]),
    "role": ("sys_role 角色", 5.6, 17.4, [
        ("PK", "id"),
        ("UK", "code"),
        ("", "name"),
        ("", "data_scope"),
    ]),
    "permission": ("sys_permission 权限资源", 10.0, 17.4, [
        ("PK", "id"),
        ("UK", "code"),
        ("", "name"),
        ("", "perm_type"),
        ("FK", "parent_id → 权限"),
    ]),
    "user_role": ("sys_user_role 用户-角色", 3.0, 10.2, [
        ("PK", "id"),
        ("FK", "user_id → 账号"),
        ("FK", "role_id → 角色"),
    ]),
    "role_permission": ("sys_role_permission 角色-权限", 7.6, 10.2, [
        ("PK", "id"),
        ("FK", "role_id → 角色"),
        ("FK", "permission_id → 权限"),
    ]),
    "operation_log": ("sys_operation_log 操作日志", 1.2, 6.6, [
        ("PK", "id"),
        ("FK", "user_id → 账号"),
        ("", "username"),
        ("", "action"),
        ("", "path"),
        ("", "status"),
        ("", "created_at"),
    ]),
    "dictionary": ("sys_dictionary 字典类型", 17.2, 31.6, [
        ("PK", "id"),
        ("UK", "code"),
        ("", "name"),
        ("", "is_system"),
    ]),
    "dictionary_item": ("sys_dictionary_item 字典项", 22.6, 31.6, [
        ("PK", "id"),
        ("FK", "type_id → 字典类型"),
        ("FK", "parent_id → 字典项"),
        ("", "item_code"),
        ("", "item_label"),
        ("", "sort_order"),
    ]),
    "material": ("sys_material 物料主数据", 17.2, 21.9, [
        ("PK", "id"),
        ("UK", "code"),
        ("", "name"),
        ("", "spec"),
        ("", "unit"),
        ("FK", "category_code → 字典项"),
        ("", "material_type"),
        ("", "source_type"),
    ]),
    "bom": ("sys_bom BOM 头", 23.0, 21.9, [
        ("PK", "id"),
        ("UK", "code"),
        ("FK", "parent_material_id → 物料"),
        ("", "bom_type"),
        ("", "version"),
        ("", "status"),
    ]),
    "bom_item": ("sys_bom_item BOM 明细", 28.2, 21.9, [
        ("PK", "id"),
        ("FK", "bom_id → BOM"),
        ("", "line_no"),
        ("FK", "child_material_id → 物料"),
        ("", "quantity"),
        ("", "loss_rate"),
    ]),
    "routing": ("sys_routing 工艺路线", 17.2, 11.2, [
        ("PK", "id"),
        ("UK", "code"),
        ("FK", "material_id → 物料"),
        ("", "version"),
        ("", "is_default"),
        ("", "status"),
    ]),
    "routing_operation": ("sys_routing_operation 工序", 22.6, 11.2, [
        ("PK", "id"),
        ("FK", "routing_id → 工艺路线"),
        ("", "step_no"),
        ("", "step_name"),
        ("", "work_center"),
        ("", "run_minutes"),
    ]),
}

# 六大功能分组框: (x, y_bottom, x_right, y_top, 标题)
GROUPS = [
    (0.6, 26.5, 12.4, 33.5, "三、组织与人员信息管理"),
    (0.6, 7.0, 15.2, 18.35, "五、系统访问权限管理"),
    (0.6, 0.9, 6.6, 7.4, "六、系统操作日志管理"),
    (16.4, 26.5, 28.4, 33.5, "四、共性基础字典管理"),
    (16.4, 14.9, 33.6, 22.85, "一、物料与 BOM 管理"),
    (16.4, 5.8, 28.4, 12.0, "二、工艺信息管理"),
]


def ry(key: str, i: int) -> float:
    """第 key 张表第 i 行（0 起）的文字中心 y。"""
    _, _, y_top, _ = TABLES[key]
    return y_top - TITLE_H - (i + 0.5) * ROW_H


# --------------------------------------------------------------------------- #
# 关系连线: {"pts": 折线点, "cards": [(文本, 锚点x, 锚点y)], "notes": [(文本, x, y, ha)]}
# 全部 N:1 —— "N" 靠子表端，"1" 靠父表端。锚点即线段端点，落位由碰撞修正自动搜索。
# --------------------------------------------------------------------------- #
EDGES = [
    # 1 人员档案.org_id → 组织
    {"pts": [(5.6, ry("personnel", 3)), (7.0, ry("personnel", 3))],
     "cards": [("N", 7.0, ry("personnel", 3)), ("1", 5.6, ry("personnel", 3))], "notes": []},
    # 2 账号.employee_id → 人员档案
    {"pts": [(4.4, 17.4), (4.4, 20.6), (6.3, 20.6), (6.3, ry("personnel", 4)), (7.0, ry("personnel", 4))],
     "cards": [("N", 4.4, 17.4), ("1", 7.0, ry("personnel", 4))],
     "notes": [("关联人员", 4.72, 19.6, "left")]},
    # 3 账号.org_id → 组织
    {"pts": [(2.0, 17.4), (2.0, 27.03)],
     "cards": [("N", 2.0, 17.4), ("1", 2.0, 27.03)],
     "notes": [("所属组织", 2.35, 22.5, "left")]},
    # 4 用户-角色.user_id → 账号
    {"pts": [(3.0, ry("user_role", 1)), (2.4, ry("user_role", 1)), (2.4, 12.21)],
     "cards": [("N", 3.0, ry("user_role", 1)), ("1", 2.4, 12.21)], "notes": []},
    # 5 用户-角色.role_id → 角色
    {"pts": [(6.2, 10.2), (6.2, 14.07)],
     "cards": [("N", 6.2, 10.2), ("1", 6.2, 14.07)], "notes": []},
    # 6 角色-权限.role_id → 角色
    {"pts": [(8.6, 10.2), (8.6, 14.07)],
     "cards": [("N", 8.6, 10.2), ("1", 8.6, 14.07)], "notes": []},
    # 7 角色-权限.permission_id → 权限
    {"pts": [(11.3, 10.2), (11.3, 13.45)],
     "cards": [("N", 11.3, 10.2), ("1", 11.3, 13.45)], "notes": []},
    # 8 权限.parent_id 自引用
    {"pts": [(14.4, ry("permission", 4)), (14.85, ry("permission", 4)),
             (14.85, ry("permission", 0)), (14.4, ry("permission", 0))],
     "cards": [("N", 14.4, ry("permission", 4)), ("1", 14.4, ry("permission", 0))], "notes": []},
    # 9 组织.parent_id 自引用
    {"pts": [(2.6, 31.6), (2.6, 32.6), (4.0, 32.6), (4.0, 31.6)],
     "cards": [("N", 2.6, 32.6), ("1", 4.0, 32.6)], "notes": []},
    # 10 操作日志.user_id → 账号
    {"pts": [(1.2, ry("operation_log", 1)), (0.5, ry("operation_log", 1)),
             (0.5, ry("user", 1)), (1.2, ry("user", 1))],
     "cards": [("N", 1.2, ry("operation_log", 1)), ("1", 1.2, ry("user", 1))],
     "notes": [("操作人", 0.82, 9.6, "left")]},
    # 11 字典项.type_id → 字典类型
    {"pts": [(21.6, ry("dictionary_item", 1)), (22.6, ry("dictionary_item", 1))],
     "cards": [("N", 22.6, ry("dictionary_item", 1)), ("1", 21.6, ry("dictionary_item", 1))], "notes": []},
    # 12 字典项.parent_id 自引用
    {"pts": [(27.0, ry("dictionary_item", 2)), (27.8, ry("dictionary_item", 2)),
             (27.8, ry("dictionary_item", 0)), (27.0, ry("dictionary_item", 0))],
     "cards": [("N", 27.0, ry("dictionary_item", 2)), ("1", 27.0, ry("dictionary_item", 0))], "notes": []},
    # 13 物料.category_code → 字典项
    {"pts": [(17.2, ry("material", 5)), (16.6, ry("material", 5)), (16.6, 26.95),
             (22.95, 26.95), (22.95, 27.03)],
     "cards": [("N", 17.2, ry("material", 5)), ("1", 22.95, 27.03)],
     "notes": [("物料分类", 16.95, 23.5, "left")]},
    # 14 BOM头.parent_material_id → 物料
    {"pts": [(21.6, ry("bom", 2)), (23.0, ry("bom", 2))],
     "cards": [("N", 23.0, ry("bom", 2)), ("1", 21.6, ry("bom", 2))], "notes": []},
    # 15 BOM明细.bom_id → BOM头
    {"pts": [(27.4, ry("bom_item", 1)), (28.2, ry("bom_item", 1))],
     "cards": [("N", 28.2, ry("bom_item", 1)), ("1", 27.4, ry("bom_item", 1))], "notes": []},
    # 16 BOM明细.child_material_id → 物料
    {"pts": [(29.4, 17.33), (29.4, 15.5), (22.0, 15.5), (22.0, 17.01), (21.6, 17.01)],
     "cards": [("N", 29.4, 17.33), ("1", 21.6, 17.01)],
     "notes": [("子件/用量", 24.2, 16.25, "left")]},
    # 17 工艺路线.material_id → 物料
    {"pts": [(18.6, 11.2), (18.6, 16.09)],
     "cards": [("N", 18.6, 11.2), ("1", 18.6, 16.09)],
     "notes": [("适用物料", 19.12, 13.9, "left")]},
    # 18 工序.routing_id → 工艺路线
    {"pts": [(21.6, ry("routing_operation", 1)), (22.6, ry("routing_operation", 1))],
     "cards": [("N", 22.6, ry("routing_operation", 1)), ("1", 21.6, ry("routing_operation", 1))], "notes": []},
]

# 标注候选偏移环（数据单位），越靠前越贴近锚点；碰撞时依次尝试
CARD_RING = [
    (0.42, 0.12), (-0.42, 0.12), (0.42, -0.12), (-0.42, -0.12),
    (0, 0.42), (0, -0.42), (0.3, 0.3), (-0.3, 0.3), (0.3, -0.3), (-0.3, -0.3),
    (0.6, 0), (-0.6, 0), (0, 0.6), (0, -0.6), (0.75, 0.25), (-0.75, 0.25),
    (0.75, -0.25), (-0.75, -0.25), (0.9, 0), (-0.9, 0),
    (0.45, 0.45), (-0.45, 0.45), (0.45, -0.45), (-0.45, -0.45),
]
NOTE_RING = [
    (0.55, 0.25), (-0.55, 0.25), (0.55, -0.25), (-0.55, -0.25),
    (0, 0.5), (0, -0.5), (0.4, 0.4), (-0.4, 0.4), (0.4, -0.4), (-0.4, -0.4),
    (0.7, 0.35), (-0.7, 0.35), (0.7, -0.35), (-0.7, -0.35),
    (0, 0.75), (0, -0.75), (0.9, 0.15), (-0.9, 0.15), (0.9, -0.15), (-0.9, -0.15),
    (0.25, 0.75), (-0.25, 0.75), (0.25, -0.75), (-0.25, -0.75),
]

TABLE_PAD = 0.06   # 表框外扩
LINE_PAD = 0.08    # 与连线的最小间距
TEXT_PAD = 0.08    # 标注相互间距

EDGE_PTS: list = []


def table_rects() -> list[tuple[float, float, float, float]]:
    rects = []
    for _, (_, x, y_top, rows) in TABLES.items():
        h = TITLE_H + ROW_H * len(rows)
        rects.append((x, y_top - h, x + TABLE_W, y_top))
    return rects


def _point_seg_dist(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> float:
    vx, vy = bx - ax, by - ay
    if vx == 0 and vy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)
    t = max(0.0, min(1.0, t))
    qx, qy = ax + t * vx, ay + t * vy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


def _rect_vs_segment(b: tuple, s: tuple) -> bool:
    ((ax, ay), (bx, by)) = s
    (bx0, by0, bx1, by1) = b
    corners = [(bx0, by0), (bx0, by1), (bx1, by0), (bx1, by1), ((bx0 + bx1) / 2, (by0 + by1) / 2)]
    return any(_point_seg_dist(ax, ay, bx, by, px, py) <= LINE_PAD for px, py in corners)


def _rects_overlap(a: tuple, b: tuple, pad: float) -> bool:
    x_over = a[2] + pad > b[0] and b[2] + pad > a[0]
    y_over = a[3] + pad > b[1] and b[3] + pad > a[1]
    return x_over and y_over


def collide(b: tuple, anns: list, skip_idx: int) -> bool:
    # 与表框
    for (x0, y0, x1, y1) in table_rects():
        if _rects_overlap(b, (x0 - TABLE_PAD, y0 - TABLE_PAD, x1 + TABLE_PAD, y1 + TABLE_PAD), 0.0):
            return True
    # 与连线
    for pts in EDGE_PTS:
        for a, c in zip(pts[:-1], pts[1:]):
            if _rect_vs_segment(b, (a, c)):
                return True
    # 与其它标注
    for i, o in enumerate(anns):
        if i == skip_idx or o["bbox"] is None:
            continue
        if _rects_overlap(b, o["bbox"], TEXT_PAD):
            return True
    return False


def draw_table(ax: plt.Axes, title: str, x: float, y_top: float, rows: list) -> None:
    h = TITLE_H + ROW_H * len(rows)
    y_bot = y_top - h
    ax.add_patch(Rectangle((x, y_bot), TABLE_W, h, fill=True, facecolor="white",
                           edgecolor="#3F3F3F", lw=1.3, zorder=5))
    ax.add_patch(Rectangle((x, y_top - TITLE_H), TABLE_W, TITLE_H, fill=True,
                           facecolor="#F2F2F2", edgecolor="#3F3F3F", lw=1.3, zorder=5))
    ax.plot([x, x + TABLE_W], [y_top - TITLE_H, y_top - TITLE_H],
            color="#3F3F3F", lw=1.1, zorder=6)
    ax.text(x + 0.15, y_top - TITLE_H / 2, title, ha="left", va="center",
            fontsize=9.5, fontweight="bold", color="#111", zorder=6)
    for i, (prefix, text) in enumerate(rows):
        row_y = y_top - TITLE_H - i * ROW_H - ROW_H / 2
        if i > 0:
            ax.plot([x + 0.06, x + TABLE_W - 0.06], [y_top - TITLE_H - i * ROW_H] * 2,
                    color="#E6E6E6", lw=0.5, zorder=6)
        label = f"{prefix:<2}  {text}"
        ax.text(x + 0.18, row_y, label, ha="left", va="center", fontsize=8.6,
                color="#111", zorder=6)


def main() -> None:
    fig, ax = plt.subplots(figsize=(17.0, 16.4), dpi=160)
    ax.set_xlim(-0.3, 34.3)
    ax.set_ylim(0.7, 34.05)
    ax.set_aspect("equal")
    ax.axis("off")

    # 分组框
    for x, y_bot, x_r, y_top, title in GROUPS:
        ax.add_patch(Rectangle((x, y_bot), x_r - x, y_top - y_bot, fill=False,
                               edgecolor="#A8A8A8", lw=1.0, zorder=1))
        ax.text(x + 0.28, y_top - 0.38, title, ha="left", va="center",
                fontsize=10.5, fontweight="bold", color="#333", zorder=3)

    # 关系连线（先画，压在表框之下）
    global EDGE_PTS
    EDGE_PTS = [e["pts"] for e in EDGES]
    for e in EDGES:
        ax.plot([p[0] for p in e["pts"]], [p[1] for p in e["pts"]],
                color="#4A4A4A", lw=1.15, zorder=2, solid_capstyle="butt")

    # 表
    for _, (title, x, y_top, rows) in TABLES.items():
        draw_table(ax, title, x, y_top, rows)

    # 总标题
    ax.text(16.95, 33.78,
            "MTS-ERP 系统与基础信息管理模块 ER 图（15 张表 · 关键字段 · 六大功能分组）",
            ha="center", va="center", fontsize=13, fontweight="bold", color="#111")

    # 图例（右下空白区）
    ax.text(17.2, 4.6,
            "图例：PK = 主键    UK = 唯一键    FK / 实线 = 逻辑引用（跨表仅存 ID，不建物理外键）",
            ha="left", va="center", fontsize=8.5, color="#666")
    ax.text(17.2, 3.85,
            "关系均为 N:1 —— N 标在子表端，1 标在父表端；多级 BOM：BOM 头 / 明细共同引用 sys_material",
            ha="left", va="center", fontsize=8.5, color="#666")
    ax.text(17.2, 3.1,
            "本图由 tools/gen_er_diagram.py 生成 · 表名遵循 data-ownership.md 模块前缀规范（sys_*）",
            ha="left", va="center", fontsize=8.5, color="#666")

    # ------------------------------------------------------------------ #
    # 标注：先放锚点位置，再按碰撞检测重新落位（最多迭代 10 轮）
    # ------------------------------------------------------------------ #
    anns: list = []
    for e in EDGES:
        for text, ax0, ay0 in e["cards"]:
            t = ax.text(ax0, ay0, text, ha="center", va="center", fontsize=9,
                        fontweight="bold", color="#2F2F2F", zorder=7)
            anns.append({"obj": t, "anchor": (ax0, ay0), "ring": CARD_RING, "idx": -1,
                         "bbox": None, "ha": "center"})
        for text, ax0, ay0, ha in e["notes"]:
            t = ax.text(ax0, ay0, text, ha=ha, va="center", fontsize=8,
                        style="italic", color="#8A8A8A", zorder=7)
            anns.append({"obj": t, "anchor": (ax0, ay0), "ring": NOTE_RING, "idx": -1,
                         "bbox": None, "ha": ha})

    def get_bbox(t) -> tuple:
        r = fig.canvas.get_renderer()
        bb = t.get_window_extent(renderer=r)
        (x0, y0) = ax.transData.inverted().transform((bb.x0, bb.y0))
        (x1, y1) = ax.transData.inverted().transform((bb.x1, bb.y1))
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    for _ in range(10):
        changed = False
        fig.canvas.draw()
        for i, item in enumerate(anns):
            b = get_bbox(item["obj"])
            item["bbox"] = b
            if not collide(b, anns, i):
                continue
            # 需要挪：依次尝试候选环
            placed = False
            for di, (dx, dy) in enumerate(item["ring"]):
                nx, ny = item["anchor"][0] + dx, item["anchor"][1] + dy
                item["obj"].set_position((nx, ny))
                # 快速重算 bbox（先 draw 一次才能拿到新窗口范围）
                fig.canvas.draw()
                nb = get_bbox(item["obj"])
                if not collide(nb, anns, i):
                    item["bbox"] = nb
                    placed = True
                    break
            changed = changed or placed
            if not placed:
                item["obj"].set_position(item["anchor"])
        if not changed:
            break
    fig.canvas.draw()

    # 最终自检：打印仍存在碰撞的标注（若有）
    bad = []
    for i, item in enumerate(anns):
        item["bbox"] = get_bbox(item["obj"])
        if collide(item["bbox"], anns, i):
            bad.append(f"card/note: '{item['obj'].get_text()}' anchor={item['anchor']}")
    if bad:
        print("WARNING: 仍有碰撞的标注:")
        for s in bad:
            print("  ", s)
    else:
        print("OK: 所有标注均已避开表框 / 连线 / 其它标注")

    out = r"docs/system/er-diagram.png"
    fig.savefig(out, format="png", dpi=160, facecolor="white", pad_inches=0.15)
    plt.close(fig)
    print("saved:", out)


if __name__ == "__main__":
    main()