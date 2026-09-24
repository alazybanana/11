"""seed default roles / permissions / bindings

Revision ID: 20260924_01
Revises: 20260917_04
Create Date: 2026-09-24

为系统预置 **九种人员身份**（角色）、覆盖五个模块功能的权限资源树及
角色-权限绑定，作为注册页可自选身份与后续接口鉴权的基础数据。

数据定义与写入逻辑统一在 `app.modules.system.seed`，本迁移只负责在
`alembic upgrade head` 时调用一次；种子函数幂等，重复执行不会产生脏数据。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision: str = '20260924_01'
down_revision: Union[str, None] = '20260917_04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.modules.system.seed import seed_roles_and_permissions

    bind = op.get_bind()
    with Session(bind=bind) as session:
        seed_roles_and_permissions(session)


def downgrade() -> None:
    """删除种子数据：先删绑定，再删权限与角色（表之间没有外键，需手动清理）。"""
    from app.modules.system import models
    from app.modules.system.seed import PERMISSION_SEEDS, ROLE_SEEDS

    bind = op.get_bind()
    with Session(bind=bind) as session:
        role_ids = [
            item[0]
            for item in session.query(models.Role.id)
            .filter(models.Role.code.in_([spec["code"] for spec in ROLE_SEEDS]))
            .all()
        ]
        perm_ids = [
            item[0]
            for item in session.query(models.Permission.id)
            .filter(models.Permission.code.in_([spec["code"] for spec in PERMISSION_SEEDS]))
            .all()
        ]
        if perm_ids:
            session.query(models.RolePermission).filter(
                models.RolePermission.permission_id.in_(perm_ids)
            ).delete(synchronize_session=False)
        if role_ids:
            session.query(models.RolePermission).filter(
                models.RolePermission.role_id.in_(role_ids)
            ).delete(synchronize_session=False)
        if perm_ids:
            session.query(models.Permission).filter(
                models.Permission.id.in_(perm_ids)
            ).delete(synchronize_session=False)
        if role_ids:
            session.query(models.Role).filter(
                models.Role.id.in_(role_ids)
            ).delete(synchronize_session=False)
        session.commit()