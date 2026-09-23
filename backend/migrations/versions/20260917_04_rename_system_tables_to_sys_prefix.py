"""rename system tables to sys_ prefix

Revision ID: 20260917_04
Revises: a91a25db68da
Create Date: 2026-09-23

统一按 data-ownership.md 的模块前缀规范，把 system 模块的 15 张业务表
改名为 `sys_` 前缀，并把 MySQL 中随表名自动命名的普通索引 `ix_<旧表名>_*`
同步改名为 `ix_<新表名>_*`（`uq_*` 显式约束名保持不变）。

表名映射：
    material -> sys_material
    bom -> sys_bom
    bom_line -> sys_bom_item
    routing -> sys_routing
    routing_step -> sys_routing_operation
    organization -> sys_organization
    employee -> sys_personnel
    dictionary_type -> sys_dictionary
    dictionary_item -> sys_dictionary_item
    user -> sys_user
    role -> sys_role
    permission -> sys_permission
    user_role -> sys_user_role
    role_permission -> sys_role_permission
    operation_log -> sys_operation_log
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260917_04'
down_revision: Union[str, None] = 'a91a25db68da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 旧表名 -> 新表名（15 张表，顺序先"子/行"后"头"无关紧要，无外键依赖）
TABLE_RENAMES: list[tuple[str, str]] = [
    ("material", "sys_material"),
    ("bom", "sys_bom"),
    ("bom_line", "sys_bom_item"),
    ("routing", "sys_routing"),
    ("routing_step", "sys_routing_operation"),
    ("organization", "sys_organization"),
    ("employee", "sys_personnel"),
    ("dictionary_type", "sys_dictionary"),
    ("dictionary_item", "sys_dictionary_item"),
    ("user", "sys_user"),
    ("role", "sys_role"),
    ("permission", "sys_permission"),
    ("user_role", "sys_user_role"),
    ("role_permission", "sys_role_permission"),
    ("operation_log", "sys_operation_log"),
]


def _rename_indexes(old_name: str, new_name: str) -> None:
    """把 `ix_<旧表名>_*` 索引改名为 `ix_<新表名>_*`，其余（uq_* 等）不动。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    prefix = f"ix_{old_name}_"
    new_prefix = f"ix_{new_name}_"
    for index in inspector.get_indexes(new_name):
        index_name = index["name"]
        if index_name.startswith(prefix):
            target = new_prefix + index_name[len(prefix):]
            op.execute(
                f"ALTER TABLE `{new_name}` RENAME INDEX `{index_name}` TO `{target}`"
            )


def upgrade() -> None:
    for old_name, new_name in TABLE_RENAMES:
        op.rename_table(old_name, new_name)
        _rename_indexes(old_name, new_name)


def downgrade() -> None:
    # 索引改名反向：先把 ix_<新表名>_* 改回 ix_<旧表名>_*，再改回旧表名
    reverse = list(reversed(TABLE_RENAMES))
    for old_name, new_name in reverse:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        prefix = f"ix_{new_name}_"
        old_prefix = f"ix_{old_name}_"
        for index in inspector.get_indexes(new_name):
            index_name = index["name"]
            if index_name.startswith(prefix):
                target = old_prefix + index_name[len(prefix):]
                op.execute(
                    f"ALTER TABLE `{new_name}` RENAME INDEX `{index_name}` TO `{target}`"
                )
    for old_name, new_name in reverse:
        op.rename_table(new_name, old_name)