"""system 模块数据访问层。

约定：
- 只做数据库读写与查询拼装，**不写业务规则**（业务规则在 `service.py`）；
- 只允许被本模块的 `service.py` 调用；
- 其它模块**禁止直接 import 本文件**（见 docs/architecture/module-boundaries.md）。

设计说明：
本模块有 16 张表、大部分是标准增删查改，因此这里提供一个通用 `CrudRepository` 基类，
子类只需声明 `model` / `keyword_fields` / `order_by`。
需要联表的场景（如 BOM 行带子件信息）**不在这里 JOIN**，
而是由 `service.py` 用 `get_by_ids` 批量回填，保持每个仓储只关心自己的一张表。

多层 BOM 展开同理：本层只负责"按一批父件 ID 一次取出生效 BOM 头 / 按一批 BOM 一次取出行"，
逐层递进与树形组装放在 `service.py`，避免逐条查库（N+1）。
"""

from datetime import date
from typing import Any, Generic, Iterable, Mapping, Sequence, TypeVar

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.system import models
from app.modules.system.enums import BomStatus

M = TypeVar("M")


class CrudRepository(Generic[M]):
    """通用增删查改仓储。"""

    model: type[Any]
    """本仓储负责的 ORM 模型。"""

    keyword_fields: tuple[str, ...] = ()
    """模糊查询（keyword）命中的字段。"""

    order_by: tuple[str, ...] = ("id",)
    """默认排序字段；倒序请在子类里写成 "-id" 这种形式。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- 查询 ---------- #
    def _conditions(
        self, filters: Mapping[str, Any] | None, keyword: str | None
    ) -> list[Any]:
        conditions: list[Any] = []
        for name, value in (filters or {}).items():
            if value is None:
                continue
            column = getattr(self.model, name, None)
            if column is None:
                raise ValueError(f"{self.model.__name__} 不存在字段 {name}")
            conditions.append(column == value)
        if keyword and self.keyword_fields:
            pattern = f"%{keyword}%"
            conditions.append(
                or_(*[getattr(self.model, field).like(pattern) for field in self.keyword_fields])
            )
        return conditions

    def _apply_order(self, stmt: Select[Any]) -> Select[Any]:
        columns = []
        for name in self.order_by:
            if name.startswith("-"):
                columns.append(getattr(self.model, name[1:]).desc())
            else:
                columns.append(getattr(self.model, name))
        return stmt.order_by(*columns)

    def list_page(
        self,
        *,
        params: PageParams,
        filters: Mapping[str, Any] | None = None,
        keyword: str | None = None,
    ) -> tuple[list[M], int]:
        """分页查询，返回 `(当前页对象列表, 总条数)`。"""
        conditions = self._conditions(filters, keyword)
        total = self.db.scalar(
            select(func.count()).select_from(self.model).where(*conditions)
        )
        stmt = self._apply_order(
            select(self.model)
            .where(*conditions)
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(self.db.scalars(stmt).all()), int(total or 0)

    def list_all(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        keyword: str | None = None,
    ) -> list[M]:
        """不分页查询（用于下拉选项、树形结构等小数据集）。"""
        stmt = self._apply_order(select(self.model).where(*self._conditions(filters, keyword)))
        return list(self.db.scalars(stmt).all())

    def get(self, obj_id: int) -> M | None:
        return self.db.get(self.model, obj_id)  # type: ignore[return-value]

    def get_by(self, **filters: Any) -> M | None:
        return self.db.scalars(select(self.model).filter_by(**filters).limit(1)).first()

    def exists(self, **filters: Any) -> bool:
        return self.get_by(**filters) is not None

    def get_by_ids(self, ids: Iterable[int]) -> list[M]:
        id_list = list({item for item in ids if item is not None})
        if not id_list:
            return []
        return list(self.db.scalars(select(self.model).where(self.model.id.in_(id_list))).all())

    # ---------- 写入 ---------- #
    def create(self, data: Mapping[str, Any]) -> M:
        obj = self.model(**dict(data))
        self.db.add(obj)
        self.db.flush()
        return obj  # type: ignore[return-value]

    def update(self, obj: M, data: Mapping[str, Any]) -> M:
        for key, value in data.items():
            setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: M) -> None:
        self.db.delete(obj)
        self.db.flush()

    def delete_where(self, **filters: Any) -> int:
        result = self.db.execute(delete(self.model).filter_by(**filters))
        return int(result.rowcount or 0)


# --------------------------------------------------------------------------- #
# 一、产品信息
# --------------------------------------------------------------------------- #
class MaterialRepository(CrudRepository[models.Material]):
    model = models.Material
    keyword_fields = ("code", "name", "spec", "model")


class BomRepository(CrudRepository[models.Bom]):
    model = models.Bom
    keyword_fields = ("code", "version")
    order_by = ("-id",)

    def map_effective_bom(
        self,
        parent_material_ids: Sequence[int],
        *,
        bom_type: str,
        on_date: date,
    ) -> dict[int, models.Bom]:
        """批量取"父件物料 ID → 该父件当前生效的 BOM 头"。

        生效 = 状态为已发布、类型匹配、且 `on_date` 落在有效期内（起止为空表示不限）。
        同一父件若有多份都生效，取 id 最大的一份（最后录入的）。
        按层调用，一次查一批父件，因此层数再深也不会产生 N+1 查询。
        """
        if not parent_material_ids:
            return {}
        stmt = (
            select(models.Bom)
            .where(
                models.Bom.parent_material_id.in_(list(parent_material_ids)),
                models.Bom.bom_type == bom_type,
                models.Bom.status == BomStatus.RELEASED.value,
                or_(models.Bom.effective_from.is_(None), models.Bom.effective_from <= on_date),
                or_(models.Bom.effective_to.is_(None), models.Bom.effective_to >= on_date),
            )
            .order_by(models.Bom.id)
        )
        result: dict[int, models.Bom] = {}
        for bom in self.db.scalars(stmt).all():
            # 顺序遍历、后者覆盖前者，最终留下 id 最大的那份
            result[int(bom.parent_material_id)] = bom
        return result

    def count_lines(self, bom_ids: Sequence[int]) -> dict[int, int]:
        """批量统计 BOM 行数。"""
        if not bom_ids:
            return {}
        rows = self.db.execute(
            select(models.BomLine.bom_id, func.count(models.BomLine.id))
            .where(models.BomLine.bom_id.in_(list(bom_ids)))
            .group_by(models.BomLine.bom_id)
        ).all()
        return {int(bom_id): int(count) for bom_id, count in rows}


class BomLineRepository(CrudRepository[models.BomLine]):
    model = models.BomLine
    order_by = ("line_no", "id")

    def map_lines_by_bom(self, bom_ids: Sequence[int]) -> dict[int, list[models.BomLine]]:
        """批量取"BOM 头 ID → 行明细"，一次一批，供逐层展开使用。"""
        if not bom_ids:
            return {}
        stmt = (
            select(models.BomLine)
            .where(models.BomLine.bom_id.in_(list(bom_ids)))
            .order_by(models.BomLine.bom_id, models.BomLine.line_no, models.BomLine.id)
        )
        result: dict[int, list[models.BomLine]] = {}
        for line in self.db.scalars(stmt).all():
            result.setdefault(int(line.bom_id), []).append(line)
        return result

    def map_child_ids_by_parent(self, parent_material_ids: Sequence[int]) -> dict[int, list[int]]:
        """批量取"父件物料 ID → 它 BOM 下所有子件物料 ID"，用于成环校验。

        与 `map_lines_by_bom` 的区别：这里**不看 BOM 的状态 / 类型 / 有效期**，
        因为草稿或历史版本里埋下的环同样是隐患，校验时必须一并看到。
        """
        if not parent_material_ids:
            return {}
        rows = self.db.execute(
            select(models.Bom.parent_material_id, models.BomLine.child_material_id)
            .join(models.BomLine, models.BomLine.bom_id == models.Bom.id)
            .where(models.Bom.parent_material_id.in_(list(parent_material_ids)))
        ).all()
        result: dict[int, list[int]] = {}
        for parent_id, child_id in rows:
            result.setdefault(int(parent_id), []).append(int(child_id))
        return result

    def list_by_bom(self, bom_id: int) -> list[models.BomLine]:
        return list(
            self.db.scalars(
                select(models.BomLine)
                .where(models.BomLine.bom_id == bom_id)
                .order_by(models.BomLine.line_no, models.BomLine.id)
            ).all()
        )

    def is_material_used(self, material_id: int) -> bool:
        return self.db.scalars(
            select(models.BomLine.id).where(models.BomLine.child_material_id == material_id).limit(1)
        ).first() is not None


# --------------------------------------------------------------------------- #
# 二、工艺信息
# --------------------------------------------------------------------------- #
class RoutingRepository(CrudRepository[models.Routing]):
    model = models.Routing
    keyword_fields = ("code", "name", "version")
    order_by = ("-id",)

    def clear_default(self, material_id: int, keep_id: int | None = None) -> None:
        """把同一物料下其它工艺路线的"默认"标记取消。"""
        stmt = select(models.Routing).where(
            models.Routing.material_id == material_id, models.Routing.is_default.is_(True)
        )
        for routing in self.db.scalars(stmt).all():
            if keep_id is None or routing.id != keep_id:
                routing.is_default = False
        self.db.flush()


class RoutingStepRepository(CrudRepository[models.RoutingStep]):
    model = models.RoutingStep
    order_by = ("step_no", "id")

    def list_by_routing(self, routing_id: int) -> list[models.RoutingStep]:
        return list(
            self.db.scalars(
                select(models.RoutingStep)
                .where(models.RoutingStep.routing_id == routing_id)
                .order_by(models.RoutingStep.step_no, models.RoutingStep.id)
            ).all()
        )

    def summary_by_routing(self, routing_ids: Sequence[int]) -> dict[int, tuple[int, float]]:
        """批量统计工艺路线的工序数与单件总工时。"""
        if not routing_ids:
            return {}
        rows = self.db.execute(
            select(
                models.RoutingStep.routing_id,
                func.count(models.RoutingStep.id),
                func.coalesce(func.sum(models.RoutingStep.run_minutes), 0),
            )
            .where(models.RoutingStep.routing_id.in_(list(routing_ids)))
            .group_by(models.RoutingStep.routing_id)
        ).all()
        return {
            int(routing_id): (int(step_count), float(total_minutes))
            for routing_id, step_count, total_minutes in rows
        }


# --------------------------------------------------------------------------- #
# 三、组织与人员
# --------------------------------------------------------------------------- #
class OrganizationRepository(CrudRepository[models.Organization]):
    model = models.Organization
    keyword_fields = ("code", "name", "leader")
    order_by = ("level", "sort_order", "id")

    def list_children(self, parent_id: int | None) -> list[models.Organization]:
        stmt = select(models.Organization).where(models.Organization.parent_id == parent_id)
        return list(self.db.scalars(stmt.order_by(models.Organization.sort_order, models.Organization.id)).all())

    def descendant_ids(self, path: str) -> list[int]:
        """根据层级路径取所有下级组织 ID。"""
        return [
            int(row)
            for row in self.db.scalars(
                select(models.Organization.id).where(models.Organization.path.like(f"{path}%"))
            ).all()
        ]


class EmployeeRepository(CrudRepository[models.Employee]):
    model = models.Employee
    keyword_fields = ("code", "name", "phone", "position")

    def count_by_org(self, org_ids: Sequence[int]) -> dict[int, int]:
        if not org_ids:
            return {}
        rows = self.db.execute(
            select(models.Employee.org_id, func.count(models.Employee.id))
            .where(models.Employee.org_id.in_(list(org_ids)))
            .group_by(models.Employee.org_id)
        ).all()
        return {int(org_id): int(count) for org_id, count in rows if org_id is not None}


# --------------------------------------------------------------------------- #
# 四、共性基础字典
# --------------------------------------------------------------------------- #
class DictionaryTypeRepository(CrudRepository[models.DictionaryType]):
    model = models.DictionaryType
    keyword_fields = ("code", "name")


class DictionaryItemRepository(CrudRepository[models.DictionaryItem]):
    model = models.DictionaryItem
    keyword_fields = ("item_code", "item_label")
    order_by = ("sort_order", "id")


# --------------------------------------------------------------------------- #
# 五、访问权限
# --------------------------------------------------------------------------- #
class UserRepository(CrudRepository[models.User]):
    model = models.User
    keyword_fields = ("username", "real_name", "email", "phone")

    def get_by_username(self, username: str) -> models.User | None:
        return self.db.scalars(
            select(models.User).where(models.User.username == username).limit(1)
        ).first()


class RoleRepository(CrudRepository[models.Role]):
    model = models.Role
    keyword_fields = ("code", "name")
    order_by = ("sort_order", "id")


class PermissionRepository(CrudRepository[models.Permission]):
    model = models.Permission
    keyword_fields = ("code", "name", "path")
    order_by = ("sort_order", "id")


class UserRoleRepository(CrudRepository[models.UserRole]):
    model = models.UserRole

    def list_role_ids(self, user_id: int) -> list[int]:
        return [
            int(row)
            for row in self.db.scalars(
                select(models.UserRole.role_id).where(models.UserRole.user_id == user_id)
            ).all()
        ]

    def map_role_ids(self, user_ids: Sequence[int]) -> dict[int, list[int]]:
        """批量取"用户 → 角色 ID 列表"。"""
        if not user_ids:
            return {}
        rows = self.db.execute(
            select(models.UserRole.user_id, models.UserRole.role_id).where(
                models.UserRole.user_id.in_(list(user_ids))
            )
        ).all()
        result: dict[int, list[int]] = {}
        for user_id, role_id in rows:
            result.setdefault(int(user_id), []).append(int(role_id))
        return result

    def replace(self, user_id: int, role_ids: Sequence[int]) -> None:
        """重设某个用户的角色（先清后插）。"""
        self.db.execute(delete(models.UserRole).where(models.UserRole.user_id == user_id))
        for role_id in dict.fromkeys(role_ids):
            self.db.add(models.UserRole(user_id=user_id, role_id=role_id))
        self.db.flush()

    def count_by_role(self, role_ids: Sequence[int]) -> dict[int, int]:
        if not role_ids:
            return {}
        rows = self.db.execute(
            select(models.UserRole.role_id, func.count(models.UserRole.id))
            .where(models.UserRole.role_id.in_(list(role_ids)))
            .group_by(models.UserRole.role_id)
        ).all()
        return {int(role_id): int(count) for role_id, count in rows}


class RolePermissionRepository(CrudRepository[models.RolePermission]):
    model = models.RolePermission

    def list_permission_ids(self, role_id: int) -> list[int]:
        return [
            int(row)
            for row in self.db.scalars(
                select(models.RolePermission.permission_id).where(
                    models.RolePermission.role_id == role_id
                )
            ).all()
        ]

    def map_permission_ids(self, role_ids: Sequence[int]) -> dict[int, list[int]]:
        if not role_ids:
            return {}
        rows = self.db.execute(
            select(models.RolePermission.role_id, models.RolePermission.permission_id).where(
                models.RolePermission.role_id.in_(list(role_ids))
            )
        ).all()
        result: dict[int, list[int]] = {}
        for role_id, permission_id in rows:
            result.setdefault(int(role_id), []).append(int(permission_id))
        return result

    def list_permission_ids_by_user(self, user_id: int) -> list[int]:
        """取某个用户通过角色间接拥有的全部权限 ID。"""
        return [
            int(row)
            for row in self.db.scalars(
                select(models.RolePermission.permission_id)
                .join(models.UserRole, models.UserRole.role_id == models.RolePermission.role_id)
                .where(models.UserRole.user_id == user_id)
                .distinct()
            ).all()
        ]

    def replace(self, role_id: int, permission_ids: Sequence[int]) -> None:
        """重设某个角色的权限（先清后插）。"""
        self.db.execute(
            delete(models.RolePermission).where(models.RolePermission.role_id == role_id)
        )
        for permission_id in dict.fromkeys(permission_ids):
            self.db.add(models.RolePermission(role_id=role_id, permission_id=permission_id))
        self.db.flush()

    def count_permissions(self, role_ids: Sequence[int]) -> dict[int, int]:
        if not role_ids:
            return {}
        rows = self.db.execute(
            select(models.RolePermission.role_id, func.count(models.RolePermission.id))
            .where(models.RolePermission.role_id.in_(list(role_ids)))
            .group_by(models.RolePermission.role_id)
        ).all()
        return {int(role_id): int(count) for role_id, count in rows}

    def is_permission_used(self, permission_id: int) -> bool:
        return self.db.scalars(
            select(models.RolePermission.id)
            .where(models.RolePermission.permission_id == permission_id)
            .limit(1)
        ).first() is not None


# --------------------------------------------------------------------------- #
# 六、操作日志
# --------------------------------------------------------------------------- #
class OperationLogRepository(CrudRepository[models.OperationLog]):
    model = models.OperationLog
    keyword_fields = ("username", "path", "description")
    order_by = ("-id",)

    def list_logs(
        self,
        *,
        params: PageParams,
        filters: Mapping[str, Any] | None = None,
        keyword: str | None = None,
        created_from: Any = None,
        created_to: Any = None,
    ) -> tuple[list[models.OperationLog], int]:
        """按条件分页查询日志，`created_from` / `created_to` 为时间区间。"""
        conditions = self._conditions(filters, keyword)
        if created_from is not None:
            conditions.append(models.OperationLog.created_at >= created_from)
        if created_to is not None:
            conditions.append(models.OperationLog.created_at <= created_to)

        total = self.db.scalar(
            select(func.count()).select_from(models.OperationLog).where(*conditions)
        )
        stmt = self._apply_order(
            select(models.OperationLog)
            .where(*conditions)
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(self.db.scalars(stmt).all()), int(total or 0)

    def delete_before(self, moment: Any) -> int:
        """清理指定时间之前的日志（运维用）。"""
        result = self.db.execute(
            delete(models.OperationLog).where(models.OperationLog.created_at < moment)
        )
        return int(result.rowcount or 0)
