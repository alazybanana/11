"""create system module base tables

系统与基础信息管理模块（system）首批建表：产品 / 物料 / BOM / 工艺路线 /
组织人员 / 字典 / 用户角色权限 / 操作日志。

Revision ID: 20260917_01
Revises:
Create Date: 2026-09-17

说明：表之间统一用 ID 引用、不建外键（见 docs/architecture/data-ownership.md
"单据之间的关联使用 ID 引用，不要用跨模块外键约束"），因此本脚本可以按任意顺序建表。
本脚本为人工编写（开发机未安装 MySQL，无法 autogenerate），
拿到 MySQL 环境后请执行 `alembic upgrade head` 并核对 `alembic revision --autogenerate`
的输出应为"无变更"。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260917_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_columns() -> list[sa.Column]:
    """创建/更新时间公共字段。"""
    return [
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, comment="创建时间"
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, comment="更新时间"
        ),
    ]


def upgrade() -> None:
    # ---------- 一、产品信息 ----------
    op.create_table(
        "material",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="物料编码"),
        sa.Column("name", sa.String(length=64), nullable=False, comment="物料名称"),
        sa.Column("spec", sa.String(length=128), nullable=True, comment="规格型号"),
        sa.Column("unit", sa.String(length=16), nullable=False, comment="计量单位"),
        sa.Column("category_code", sa.String(length=32), nullable=True, comment="物料分类"),
        sa.Column("material_type", sa.String(length=16), nullable=False, comment="物料类型"),
        sa.Column("source_type", sa.String(length=16), nullable=False, comment="来源"),
        sa.Column("standard_cost", sa.Numeric(precision=12, scale=2), nullable=True, comment="标准成本"),
        sa.Column("safety_stock", sa.Numeric(precision=14, scale=4), nullable=True, comment="安全库存"),
        sa.Column("lead_time_days", sa.Integer(), nullable=True, comment="采购提前期（天）"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_material_code", "material", ["code"], unique=True)
    op.create_index("ix_material_category_code", "material", ["category_code"])

    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="产品编码"),
        sa.Column("name", sa.String(length=64), nullable=False, comment="产品名称"),
        sa.Column("spec", sa.String(length=128), nullable=True, comment="规格型号"),
        sa.Column("model", sa.String(length=64), nullable=True, comment="产品型号"),
        sa.Column("unit", sa.String(length=16), nullable=False, comment="计量单位"),
        sa.Column("category_code", sa.String(length=32), nullable=True, comment="产品分类"),
        sa.Column("standard_cost", sa.Numeric(precision=12, scale=2), nullable=True, comment="标准成本"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_code", "product", ["code"], unique=True)
    op.create_index("ix_product_category_code", "product", ["category_code"])

    op.create_table(
        "bom",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="BOM 编码"),
        sa.Column("product_id", sa.Integer(), nullable=False, comment="所属产品 ID"),
        sa.Column("version", sa.String(length=16), nullable=False, comment="版本号"),
        sa.Column("base_qty", sa.Numeric(precision=12, scale=4), nullable=False, comment="基准数量"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态"),
        sa.Column("effective_from", sa.Date(), nullable=True, comment="生效日期"),
        sa.Column("effective_to", sa.Date(), nullable=True, comment="失效日期"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "version", name="uq_bom_product_version"),
    )
    op.create_index("ix_bom_code", "bom", ["code"], unique=True)
    op.create_index("ix_bom_product_id", "bom", ["product_id"])

    op.create_table(
        "bom_line",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bom_id", sa.Integer(), nullable=False, comment="所属 BOM ID"),
        sa.Column("line_no", sa.Integer(), nullable=False, comment="行号"),
        sa.Column("child_material_id", sa.Integer(), nullable=False, comment="子件物料 ID"),
        sa.Column("quantity", sa.Numeric(precision=14, scale=4), nullable=False, comment="单位用量"),
        sa.Column("unit", sa.String(length=16), nullable=True, comment="单位"),
        sa.Column("loss_rate", sa.Numeric(precision=6, scale=4), nullable=False, comment="损耗率"),
        sa.Column("position", sa.String(length=64), nullable=True, comment="装配位置"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bom_id", "line_no", name="uq_bom_line_no"),
    )
    op.create_index("ix_bom_line_bom_id", "bom_line", ["bom_id"])
    op.create_index("ix_bom_line_child_material_id", "bom_line", ["child_material_id"])

    # ---------- 二、工艺信息 ----------
    op.create_table(
        "routing",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="工艺路线编码"),
        sa.Column("product_id", sa.Integer(), nullable=False, comment="适用产品 ID"),
        sa.Column("name", sa.String(length=64), nullable=False, comment="工艺路线名称"),
        sa.Column("version", sa.String(length=16), nullable=False, comment="版本号"),
        sa.Column("is_default", sa.Boolean(), nullable=False, comment="是否默认"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "version", name="uq_routing_product_version"),
    )
    op.create_index("ix_routing_code", "routing", ["code"], unique=True)
    op.create_index("ix_routing_product_id", "routing", ["product_id"])

    op.create_table(
        "routing_step",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("routing_id", sa.Integer(), nullable=False, comment="所属工艺路线 ID"),
        sa.Column("step_no", sa.Integer(), nullable=False, comment="工序号"),
        sa.Column("step_code", sa.String(length=32), nullable=True, comment="工序编码"),
        sa.Column("step_name", sa.String(length=64), nullable=False, comment="工序名称"),
        sa.Column("work_center", sa.String(length=32), nullable=True, comment="工作中心"),
        sa.Column("equipment", sa.String(length=64), nullable=True, comment="设备 / 工装"),
        sa.Column("setup_minutes", sa.Numeric(precision=10, scale=2), nullable=True, comment="准备工时"),
        sa.Column("run_minutes", sa.Numeric(precision=10, scale=2), nullable=True, comment="单件工时"),
        sa.Column("is_key", sa.Boolean(), nullable=False, comment="是否关键工序"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("routing_id", "step_no", name="uq_routing_step_no"),
    )
    op.create_index("ix_routing_step_routing_id", "routing_step", ["routing_id"])

    # ---------- 三、组织与人员 ----------
    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="组织编码"),
        sa.Column("name", sa.String(length=64), nullable=False, comment="组织名称"),
        sa.Column("parent_id", sa.Integer(), nullable=True, comment="上级组织 ID"),
        sa.Column("path", sa.String(length=255), nullable=False, comment="层级路径"),
        sa.Column("level", sa.Integer(), nullable=False, comment="层级"),
        sa.Column("org_type", sa.String(length=16), nullable=False, comment="组织类型"),
        sa.Column("leader", sa.String(length=32), nullable=True, comment="负责人"),
        sa.Column("phone", sa.String(length=32), nullable=True, comment="联系电话"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="同级排序"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organization_code", "organization", ["code"], unique=True)
    op.create_index("ix_organization_parent_id", "organization", ["parent_id"])

    op.create_table(
        "employee",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="工号"),
        sa.Column("name", sa.String(length=32), nullable=False, comment="姓名"),
        sa.Column("gender", sa.String(length=8), nullable=False, comment="性别"),
        sa.Column("phone", sa.String(length=32), nullable=True, comment="手机号"),
        sa.Column("email", sa.String(length=64), nullable=True, comment="邮箱"),
        sa.Column("org_id", sa.Integer(), nullable=True, comment="所属组织 ID"),
        sa.Column("position", sa.String(length=32), nullable=True, comment="岗位"),
        sa.Column("hire_date", sa.Date(), nullable=True, comment="入职日期"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="在职状态"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_code", "employee", ["code"], unique=True)
    op.create_index("ix_employee_org_id", "employee", ["org_id"])

    # ---------- 四、共性基础字典 ----------
    op.create_table(
        "dictionary_type",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="字典类型编码"),
        sa.Column("name", sa.String(length=32), nullable=False, comment="字典类型名称"),
        sa.Column("is_system", sa.Boolean(), nullable=False, comment="是否系统内置"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dictionary_type_code", "dictionary_type", ["code"], unique=True)

    op.create_table(
        "dictionary_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False, comment="所属字典类型 ID"),
        sa.Column("parent_id", sa.Integer(), nullable=True, comment="上级字典项 ID"),
        sa.Column("item_code", sa.String(length=32), nullable=False, comment="字典项编码"),
        sa.Column("item_label", sa.String(length=64), nullable=False, comment="字典项显示名"),
        sa.Column("item_value", sa.String(length=64), nullable=True, comment="字典项值"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="排序"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("extra", sa.JSON(), nullable=True, comment="扩展属性"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_id", "item_code", name="uq_dict_item_code"),
    )
    op.create_index("ix_dictionary_item_type_id", "dictionary_item", ["type_id"])
    op.create_index("ix_dictionary_item_parent_id", "dictionary_item", ["parent_id"])

    # ---------- 五、访问权限 ----------
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False, comment="登录账号"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="密码哈希"),
        sa.Column("real_name", sa.String(length=32), nullable=True, comment="姓名"),
        sa.Column("employee_id", sa.Integer(), nullable=True, comment="关联人员 ID"),
        sa.Column("org_id", sa.Integer(), nullable=True, comment="所属组织 ID"),
        sa.Column("email", sa.String(length=64), nullable=True, comment="邮箱"),
        sa.Column("phone", sa.String(length=32), nullable=True, comment="手机号"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, comment="是否超级管理员"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True, comment="最后登录时间"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_username", "user", ["username"], unique=True)
    op.create_index("ix_user_employee_id", "user", ["employee_id"])
    op.create_index("ix_user_org_id", "user", ["org_id"])

    op.create_table(
        "role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="角色编码"),
        sa.Column("name", sa.String(length=32), nullable=False, comment="角色名称"),
        sa.Column("data_scope", sa.String(length=16), nullable=False, comment="访问范围"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="排序"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("description", sa.String(length=255), nullable=True, comment="描述"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_role_code", "role", ["code"], unique=True)

    op.create_table(
        "permission",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False, comment="权限编码"),
        sa.Column("name", sa.String(length=32), nullable=False, comment="权限名称"),
        sa.Column("perm_type", sa.String(length=16), nullable=False, comment="类型"),
        sa.Column("parent_id", sa.Integer(), nullable=True, comment="上级权限 ID"),
        sa.Column("path", sa.String(length=128), nullable=True, comment="路径"),
        sa.Column("method", sa.String(length=8), nullable=True, comment="HTTP 方法"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="排序"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permission_code", "permission", ["code"], unique=True)
    op.create_index("ix_permission_parent_id", "permission", ["parent_id"])

    op.create_table(
        "user_role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="用户 ID"),
        sa.Column("role_id", sa.Integer(), nullable=False, comment="角色 ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_index("ix_user_role_user_id", "user_role", ["user_id"])
    op.create_index("ix_user_role_role_id", "user_role", ["role_id"])

    op.create_table(
        "role_permission",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False, comment="角色 ID"),
        sa.Column("permission_id", sa.Integer(), nullable=False, comment="权限 ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index("ix_role_permission_role_id", "role_permission", ["role_id"])
    op.create_index("ix_role_permission_permission_id", "role_permission", ["permission_id"])

    # ---------- 六、操作日志 ----------
    op.create_table(
        "operation_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True, comment="操作人 ID"),
        sa.Column("username", sa.String(length=64), nullable=True, comment="操作人账号"),
        sa.Column("module", sa.String(length=32), nullable=True, comment="所属模块"),
        sa.Column("action", sa.String(length=16), nullable=False, comment="动作类型"),
        sa.Column("description", sa.String(length=128), nullable=True, comment="操作描述"),
        sa.Column("method", sa.String(length=8), nullable=True, comment="HTTP 方法"),
        sa.Column("path", sa.String(length=128), nullable=True, comment="请求路径"),
        sa.Column("ip", sa.String(length=64), nullable=True, comment="客户端 IP"),
        sa.Column("request_params", sa.Text(), nullable=True, comment="请求参数（已脱敏）"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="结果"),
        sa.Column("error_msg", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("duration_ms", sa.Integer(), nullable=True, comment="耗时（毫秒）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="操作时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operation_log_user_id", "operation_log", ["user_id"])
    op.create_index("ix_operation_log_username", "operation_log", ["username"])
    op.create_index("ix_operation_log_module", "operation_log", ["module"])
    op.create_index("ix_operation_log_created_at", "operation_log", ["created_at"])


def downgrade() -> None:
    for table in (
        "operation_log",
        "role_permission",
        "user_role",
        "permission",
        "role",
        "user",
        "dictionary_item",
        "dictionary_type",
        "employee",
        "organization",
        "routing_step",
        "routing",
        "bom_line",
        "bom",
        "product",
        "material",
    ):
        op.drop_table(table)
