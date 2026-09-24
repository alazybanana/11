"""add `:manage` button permissions for system module

Revision ID: 20260924_02
Revises: 20260924_01
Create Date: 2026-09-24

为 system 模块各功能补充写操作权限码（`模块:功能:manage`，BUTTON 类型）：
功能码只表示"查看"，`:manage` 表示新增 / 修改 / 删除等写操作，接口鉴权据此拆分。

同时把设计人员的角色绑定补上物料 / BOM / 工艺路线的写权限。
数据定义在 `app.modules.system.seed`，本迁移只负责调用一次；
种子函数幂等：已存在的编码跳过、已存在的绑定不重复插入。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision: str = '20260924_02'
down_revision: Union[str, None] = '20260924_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 本迁移新增的权限编码（与 seed.PERMISSION_SEEDS 中 ":manage" 结尾的 system 码保持一致）
MANAGE_CODES = [
    "system:material:manage",
    "system:bom:manage",
    "system:routing:manage",
    "system:org:manage",
    "system:dictionary:manage",
    "system:user:manage",
    "system:role:manage",
    "system:permission:manage",
    "system:log:manage",
]


def upgrade() -> None:
    from app.modules.system.seed import seed_roles_and_permissions

    bind = op.get_bind()
    with Session(bind=bind) as session:
        seed_roles_and_permissions(session)


def downgrade() -> None:
    """只撤掉本迁移新增的 `:manage` 码及其绑定，不动 20260924_01 及人工调整的数据。"""
    from app.modules.system import models

    bind = op.get_bind()
    with Session(bind=bind) as session:
        perm_ids = [
            item[0]
            for item in session.query(models.Permission.id)
            .filter(models.Permission.code.in_(MANAGE_CODES))
            .all()
        ]
        if perm_ids:
            session.query(models.RolePermission).filter(
                models.RolePermission.permission_id.in_(perm_ids)
            ).delete(synchronize_session=False)
            session.query(models.Permission).filter(
                models.Permission.id.in_(perm_ids)
            ).delete(synchronize_session=False)
        session.commit()