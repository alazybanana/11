"""system 模块业务逻辑层。

约定：
- 只有本模块的 `router.py` 可以调用本模块 service；
- 业务规则写在 service，SQL 写在 `repository.py`；
- 其它模块**禁止直接 import 本文件**，跨模块只能走 `contract.py` 暴露的 Service Contract。

分层结构：
- `BaseService`：16 张表共用的增删查改骨架（唯一性校验 + 钩子 + 提交事务）；
- 各实体 Service：只实现自己的业务规则（引用校验、级联、树形、密码、权限）。
"""

from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.pagination import PageData, PageParams
from app.core import security
from app.modules.system import errors, models, schemas
from app.modules.system.enums import ApprovalStatus, BomStatus, BomType, CommonStatus
from app.modules.system.repository import (
    BomLineRepository,
    BomRepository,
    CrudRepository,
    DictionaryItemRepository,
    DictionaryTypeRepository,
    EmployeeRepository,
    MaterialRepository,
    OperationLogRepository,
    OrganizationRepository,
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
    RoutingRepository,
    RoutingStepRepository,
    UserRepository,
    UserRoleRepository,
)


class BaseService:
    """通用 CRUD 服务骨架。"""

    repository_cls: type[CrudRepository[Any]]
    out_schema: type[BaseModel]
    not_found_message: str = "数据不存在"
    code_field: str | None = "code"
    """唯一编码字段；为 None 表示不做编码唯一性校验（由子类自行处理）。"""
    code_label: str = "编码"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = self.repository_cls(db)  # type: ignore[call-arg]

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def get_or_404(self, obj_id: int) -> Any:
        obj = self.repo.get(obj_id)
        if obj is None:
            raise BusinessException(errors.CODE_NOT_FOUND, self.not_found_message)
        return obj

    def page(
        self,
        *,
        params: PageParams,
        filters: Mapping[str, Any] | None = None,
        keyword: str | None = None,
    ) -> PageData[Any]:
        rows, total = self.repo.list_page(params=params, filters=filters, keyword=keyword)
        return PageData(
            page=params.page,
            page_size=params.page_size,
            total=total,
            items=self.to_out_list(rows),
        )

    def detail(self, obj_id: int) -> Any:
        return self.to_out(self.get_or_404(obj_id))

    def to_out(self, obj: Any) -> Any:
        """单条出参：复用批量逻辑，保证详情 / 新增 / 修改返回的增强字段与列表一致。"""
        return self.to_out_list([obj])[0]

    def to_out_list(self, objs: Sequence[Any]) -> list[Any]:
        """批量出参：子类重写本方法统一补充关联字段（如产品名、角色名、权限 ID）。"""
        return [self.out_schema.model_validate(obj) for obj in objs]

    # ------------------------------------------------------------------ #
    # 写入
    # ------------------------------------------------------------------ #
    def ensure_unique(self, value: Any, *, field: str = "code", exclude_id: int | None = None) -> None:
        """校验字段唯一（排除自身），冲突时抛 1002。"""
        if value is None:
            return
        existing = self.repo.get_by(**{field: value})
        if existing is not None and existing.id != exclude_id:
            raise BusinessException(
                errors.CODE_DUPLICATE_CODE, f"{self.code_label}「{value}」已存在"
            )

    def before_create(self, data: dict[str, Any]) -> None:
        """新增钩子：可修改 `data`。"""

    def after_create(self, obj: Any) -> None:
        """新增钩子：需要在拿到主键后处理的逻辑（如路径、关联表）。"""

    def before_update(self, obj: Any, data: dict[str, Any]) -> None:
        """更新钩子：可修改 `data`。"""

    def after_update(self, obj: Any, data: dict[str, Any]) -> None:
        """更新后钩子。"""

    def before_delete(self, obj: Any) -> None:
        """删除前校验钩子。"""

    def create(self, payload: BaseModel) -> Any:
        data = payload.model_dump()
        self.before_create(data)
        if self.code_field and self.code_field in data:
            self.ensure_unique(data[self.code_field])
        obj = self.repo.create(data)
        self.after_create(obj)
        self.db.commit()
        self.db.refresh(obj)
        return self.to_out(obj)

    def update(self, obj_id: int, payload: BaseModel) -> Any:
        obj = self.get_or_404(obj_id)
        data = payload.model_dump(exclude_unset=True)
        if self.code_field and self.code_field in data:
            self.ensure_unique(data[self.code_field], exclude_id=obj_id)
        self.before_update(obj, data)
        self.repo.update(obj, data)
        self.after_update(obj, data)
        self.db.commit()
        self.db.refresh(obj)
        return self.to_out(obj)

    def delete(self, obj_id: int) -> None:
        obj = self.get_or_404(obj_id)
        self.before_delete(obj)
        self.repo.delete(obj)
        self.db.commit()


# --------------------------------------------------------------------------- #
# 一、产品信息
# --------------------------------------------------------------------------- #
class MaterialService(BaseService):
    """物料主数据。"""

    repository_cls = MaterialRepository
    out_schema = schemas.MaterialOut
    not_found_message = "物料不存在"
    code_label = "物料编码"

    def before_delete(self, obj: models.Material) -> None:
        # 原 Product 与 Material 合并为一张表，所以这里要把"产品才有的"两条约束也一并守住：
        # 要么它被别的 BOM 当子件引用，要么它自己挂着 BOM / 工艺路线，都不允许删。
        if BomLineRepository(self.db).is_material_used(obj.id):
            raise BusinessException(
                errors.CODE_IN_USE, f"物料「{obj.code}」已被 BOM 引用，不能删除"
            )
        if BomRepository(self.db).exists(parent_material_id=obj.id):
            raise BusinessException(
                errors.CODE_IN_USE, f"物料「{obj.code}」已建立 BOM，不能删除"
            )
        if RoutingRepository(self.db).exists(material_id=obj.id):
            raise BusinessException(
                errors.CODE_IN_USE, f"物料「{obj.code}」已建立工艺路线，不能删除"
            )


class BomService(BaseService):
    """BOM 头 + BOM 行。"""

    repository_cls = BomRepository
    out_schema = schemas.BomOut
    not_found_message = "BOM 不存在"
    code_label = "BOM 编码"

    # ---------- 出参增强 ---------- #
    def to_out_list(self, objs: Sequence[models.Bom]) -> list[schemas.BomOut]:
        material_map = _index(
            MaterialRepository(self.db).get_by_ids({obj.parent_material_id for obj in objs})
        )
        line_counts = BomRepository(self.db).count_lines([obj.id for obj in objs])
        return [
            schemas.BomOut.model_validate(obj).model_copy(
                update={
                    "parent_material_code": _attr(
                        material_map.get(obj.parent_material_id), "code"
                    ),
                    "parent_material_name": _attr(
                        material_map.get(obj.parent_material_id), "name"
                    ),
                    "line_count": line_counts.get(obj.id, 0),
                }
            )
            for obj in objs
        ]

    # ---------- 校验 ---------- #
    def _validate_parent_material(self, parent_material_id: int) -> None:
        if MaterialRepository(self.db).get(parent_material_id) is None:
            raise BusinessException(errors.CODE_INVALID_REFERENCE, "所选父件物料不存在")

    def _validate_version(
        self, parent_material_id: int, version: str, bom_type: str, exclude_id: int | None = None
    ) -> None:
        """同一父件、同一类型、同一版本只能有一份 BOM（对应唯一约束）。"""
        existing = BomRepository(self.db).get_by(
            parent_material_id=parent_material_id, version=version, bom_type=bom_type
        )
        if existing is not None and existing.id != exclude_id:
            # bom_type 可能是 BomType 枚举，直接插值会渲染成 "BomType.MANUFACTURE"
            label = getattr(bom_type, "value", bom_type)
            raise BusinessException(
                errors.CODE_DUPLICATE_CODE,
                f"该父件已存在「{label}」类型、版本「{version}」的 BOM",
            )

    def _ensure_no_cycle(self, parent_material_id: int, child_material_id: int) -> None:
        """禁止 BOM 出现循环引用：自己套自己，或 A→B→A 这种绕回来的结构。

        做法：从这一行的子件出发向下逐层展开，只要能走回父件，插入这行就会成环。
        只看结构、不看 BOM 状态与类型，避免"草稿里埋的环"等到发布后才炸。
        `visited` 既用来剪枝，也保证图里已有环时不会无限循环。
        """
        if child_material_id == parent_material_id:
            raise BusinessException(errors.CODE_BOM_CYCLE, "子件不能是父件自身")

        repo = BomLineRepository(self.db)
        visited: set[int] = set()
        frontier: set[int] = {child_material_id}
        while frontier:
            if parent_material_id in frontier:
                raise BusinessException(
                    errors.CODE_BOM_CYCLE, "该子件的下层已包含父件，会形成循环引用"
                )
            frontier -= visited
            if not frontier:
                break
            visited |= frontier
            children = repo.map_child_ids_by_parent(sorted(frontier))
            frontier = {child_id for ids in children.values() for child_id in ids}

    def before_create(self, data: dict[str, Any]) -> None:
        self._validate_parent_material(data["parent_material_id"])
        self._validate_version(data["parent_material_id"], data["version"], data["bom_type"])

    def before_update(self, obj: models.Bom, data: dict[str, Any]) -> None:
        new_status = _enum_value(data.get("status", obj.status))

        # 已发布的 BOM 只允许改状态与备注，其余字段（换父件 / 版本 / 类型 / 有效期等）一律冻结
        if obj.status == BomStatus.RELEASED.value:
            frozen = sorted(set(data) - {"status", "remark"})
            if frozen:
                raise BusinessException(
                    errors.CODE_IN_USE,
                    f"已发布的 BOM 只允许修改状态与备注，不允许修改：{'、'.join(frozen)}",
                )
        # 空 BOM 不允许发布：没有任何子件的 BOM 发布后没有工程意义
        if new_status == BomStatus.RELEASED.value and obj.status != BomStatus.RELEASED.value:
            if not BomLineRepository(self.db).exists(bom_id=obj.id):
                raise BusinessException(
                    errors.CODE_IN_USE, "空 BOM 不允许发布，请先添加 BOM 行"
                )
        # 已作废的 BOM 不能直接回到已发布，必须退回草稿重新走发布流程
        if obj.status == BomStatus.OBSOLETE.value and new_status == BomStatus.RELEASED.value:
            raise BusinessException(
                errors.CODE_IN_USE, "已作废的 BOM 不能直接发布，请先置为草稿"
            )

        parent_material_id = data.get("parent_material_id", obj.parent_material_id)
        version = data.get("version", obj.version)
        bom_type = data.get("bom_type", obj.bom_type)
        if (
            parent_material_id != obj.parent_material_id
            or version != obj.version
            or bom_type != obj.bom_type
        ):
            self._validate_parent_material(parent_material_id)
            self._validate_version(parent_material_id, version, bom_type, exclude_id=obj.id)
        if parent_material_id != obj.parent_material_id:
            # 换父件等于重新定义了整棵子树，原有每一行都要重过一遍成环校验
            for line in BomLineRepository(self.db).list_by_bom(obj.id):
                self._ensure_no_cycle(parent_material_id, line.child_material_id)

    def before_delete(self, obj: models.Bom) -> None:
        """删除 BOM 时级联删除其行（行没有独立业务含义）。"""
        if obj.status == BomStatus.RELEASED.value:
            raise BusinessException(
                errors.CODE_IN_USE, f"BOM「{obj.code}」已发布，请先置为草稿或作废后再删除"
            )
        BomLineRepository(self.db).delete_where(bom_id=obj.id)

    # ---------- BOM 行 ---------- #
    def detail_with_lines(self, bom_id: int) -> schemas.BomDetailOut:
        bom = self.get_or_404(bom_id)
        base = self.to_out(bom)
        return schemas.BomDetailOut(**base.model_dump(), lines=self.list_lines(bom_id))

    def _line_out(self, line: models.BomLine) -> schemas.BomLineOut:
        material = MaterialRepository(self.db).get(line.child_material_id)
        return schemas.BomLineOut.model_validate(line).model_copy(
            update={
                "material_code": _attr(material, "code"),
                "material_name": _attr(material, "name"),
                "material_spec": _attr(material, "spec"),
            }
        )

    def list_lines(self, bom_id: int) -> list[schemas.BomLineOut]:
        self.get_or_404(bom_id)
        lines = BomLineRepository(self.db).list_by_bom(bom_id)
        material_map = _index(
            MaterialRepository(self.db).get_by_ids({line.child_material_id for line in lines})
        )
        return [
            schemas.BomLineOut.model_validate(line).model_copy(
                update={
                    "material_code": _attr(material_map.get(line.child_material_id), "code"),
                    "material_name": _attr(material_map.get(line.child_material_id), "name"),
                    "material_spec": _attr(material_map.get(line.child_material_id), "spec"),
                }
            )
            for line in lines
        ]

    def _validate_line(self, bom_id: int, data: dict[str, Any], exclude_line_id: int | None = None) -> None:
        if MaterialRepository(self.db).get(data["child_material_id"]) is None:
            raise BusinessException(errors.CODE_INVALID_REFERENCE, "所选子件物料不存在")
        existing = BomLineRepository(self.db).get_by(bom_id=bom_id, line_no=data["line_no"])
        if existing is not None and existing.id != exclude_line_id:
            raise BusinessException(errors.CODE_DUPLICATE_CODE, f"行号 {data['line_no']} 已存在")

    def _ensure_editable(self, bom_id: int) -> models.Bom:
        bom = self.get_or_404(bom_id)
        if bom.status == BomStatus.RELEASED.value:
            raise BusinessException(errors.CODE_IN_USE, "已发布的 BOM 不允许修改行，请先置为草稿")
        return bom

    def add_line(self, bom_id: int, payload: BaseModel) -> schemas.BomLineOut:
        bom = self._ensure_editable(bom_id)
        data = payload.model_dump()
        self._validate_line(bom_id, data)
        self._ensure_no_cycle(bom.parent_material_id, data["child_material_id"])
        line = BomLineRepository(self.db).create({**data, "bom_id": bom_id})
        self.db.commit()
        self.db.refresh(line)
        return self._line_out(line)

    def update_line(self, bom_id: int, line_id: int, payload: BaseModel) -> schemas.BomLineOut:
        bom = self._ensure_editable(bom_id)
        repo = BomLineRepository(self.db)
        line = repo.get(line_id)
        if line is None or line.bom_id != bom_id:
            raise BusinessException(errors.CODE_NOT_FOUND, "BOM 行不存在")
        data = payload.model_dump(exclude_unset=True)
        self._validate_line(
            bom_id,
            {
                "child_material_id": data.get("child_material_id", line.child_material_id),
                "line_no": data.get("line_no", line.line_no),
            },
            exclude_line_id=line_id,
        )
        self._ensure_no_cycle(
            bom.parent_material_id, data.get("child_material_id", line.child_material_id)
        )
        repo.update(line, data)
        self.db.commit()
        self.db.refresh(line)
        return self._line_out(line)

    # ---------- 多层展开 ---------- #
    def _material_or_404(self, material_id: int) -> models.Material:
        """取物料主数据。

        注意不能直接用 `self.get_or_404`——BomService 的 `repository_cls` 是 BomRepository，
        那样查出来的是 BOM 头，不是物料。
        """
        material = MaterialRepository(self.db).get(material_id)
        if material is None:
            raise BusinessException(errors.CODE_NOT_FOUND, "物料不存在")
        return material

    def _tree_node(
        self,
        material: models.Material,
        *,
        level: int,
        quantity: float,
        acc_quantity: float,
        line: models.BomLine | None = None,
    ) -> schemas.BomTreeNode:
        """把物料 + BOM 行的信息合成一个树节点。顶层没有对应的 BOM 行，`line` 为 None。"""
        return schemas.BomTreeNode(
            material_id=material.id,
            material_code=material.code,
            material_name=material.name,
            spec=material.spec,
            model=material.model,
            unit=material.unit,
            level=level,
            quantity=quantity,
            acc_quantity=acc_quantity,
            is_phantom=bool(line.is_phantom) if line is not None else False,
            is_optional=bool(line.is_optional) if line is not None else False,
            option_group=line.option_group if line is not None else None,
            substitute_group=line.substitute_group if line is not None else None,
            substitute_priority=line.substitute_priority if line is not None else 1,
        )

    def expand_tree(
        self,
        material_id: int,
        *,
        bom_type: str = BomType.MANUFACTURE.value,
        on_date: date | None = None,
        max_level: int = 20,
    ) -> schemas.BomTreeNode:
        """把某个物料的多层 BOM 展开成树，**层数不设上限**。

        逐层递进：每层固定两次批量查询（生效 BOM 头 + 对应的 BOM 行），
        所以查库次数只跟"层数"有关、跟节点个数无关，树再宽也不会拖慢。
        只展开已发布且在有效期内的 BOM（规则见 `BomRepository.map_effective_bom`），
        因此没挂 BOM 或 BOM 还是草稿的物料，就自然成为叶子节点。

        `acc_quantity` 是沿路径连乘得到的累计用量，已按各层 `base_qty` 折算
        （BOM 说的是"产出 base_qty 个父件需要 quantity 个子件"）。

        `max_level` 是防御性上限：写入时已禁止成环，正常数据不可能触到；
        真触到了说明库里存在历史脏数据，此时直接报错而不是悄悄截断。
        """
        material = self._material_or_404(material_id)
        if material.status == CommonStatus.DISABLED.value:
            raise BusinessException(
                errors.CODE_INVALID_REFERENCE, f"物料「{material.code}」已停用，不能展开 BOM"
            )
        on_date = on_date or date.today()
        root = self._tree_node(material, level=1, quantity=1, acc_quantity=1)

        bom_repo = BomRepository(self.db)
        line_repo = BomLineRepository(self.db)
        material_repo = MaterialRepository(self.db)

        # (节点, 该节点的累计用量)，一层推一层
        frontier: list[tuple[schemas.BomTreeNode, float]] = [(root, 1.0)]
        while frontier:
            if frontier[0][0].level > max_level:
                raise BusinessException(
                    errors.CODE_BOM_CYCLE,
                    f"BOM 展开已超过 {max_level} 层，疑似存在循环引用，请检查数据",
                )
            bom_map = bom_repo.map_effective_bom(
                [node.material_id for node, _ in frontier], bom_type=bom_type, on_date=on_date
            )
            line_map = line_repo.map_lines_by_bom([bom.id for bom in bom_map.values()])
            material_map = _index(
                material_repo.get_by_ids(
                    {line.child_material_id for lines in line_map.values() for line in lines}
                )
            )

            next_frontier: list[tuple[schemas.BomTreeNode, float]] = []
            for node, acc_quantity in frontier:
                bom = bom_map.get(node.material_id)
                if bom is None:
                    continue  # 没有下层 BOM，到此为止
                base_qty = float(bom.base_qty) or 1.0
                for line in line_map.get(bom.id, []):
                    child = material_map.get(line.child_material_id)
                    if child is None:
                        continue  # 子件物料已不存在（ID 引用无外键，只能跳过）
                    if child.status == CommonStatus.DISABLED.value:
                        continue  # 停用物料不参与展开，避免被带进 MRP 需求
                    child_acc = acc_quantity * float(line.quantity) / base_qty
                    child_node = self._tree_node(
                        child,
                        level=node.level + 1,
                        quantity=float(line.quantity),
                        acc_quantity=round(child_acc, 6),
                        line=line,
                    )
                    node.children.append(child_node)
                    next_frontier.append((child_node, child_acc))
            frontier = next_frontier

        return root

    def expand_lines(
        self,
        material_id: int,
        *,
        bom_type: str = BomType.MANUFACTURE.value,
        on_date: date | None = None,
        max_level: int = 20,
    ) -> list[schemas.BomTreeNode]:
        """把多层 BOM 展开后拉平成一维清单，供 MRP 算毛需求。

        与 `expand_tree` 的两点差别：
        1. **虚拟件不单独成行**——它不实际入库，需求直接穿到下层子件（下层照常保留，`level` 仍是真实层号）；
        2. 顶层物料自己不算一行，只列它下面真正需要的物料。

        可选件（`is_optional`）与替代料（`substitute_group`）原样保留、不做取舍，
        选哪一个属于配置 / MRP 的决定，本方法只负责如实摊开。
        """
        root = self.expand_tree(
            material_id, bom_type=bom_type, on_date=on_date, max_level=max_level
        )
        result: list[schemas.BomTreeNode] = []

        def walk(node: schemas.BomTreeNode) -> None:
            for child in node.children:
                if not child.is_phantom:
                    result.append(
                        schemas.BomTreeNode(**child.model_dump(exclude={"children"}))
                    )
                walk(child)

        walk(root)
        return result

    def delete_line(self, bom_id: int, line_id: int) -> None:
        self._ensure_editable(bom_id)
        repo = BomLineRepository(self.db)
        line = repo.get(line_id)
        if line is None or line.bom_id != bom_id:
            raise BusinessException(errors.CODE_NOT_FOUND, "BOM 行不存在")
        repo.delete(line)
        self.db.commit()


class RoutingService(BaseService):
    """工艺路线头 + 工序。"""

    repository_cls = RoutingRepository
    out_schema = schemas.RoutingOut
    not_found_message = "工艺路线不存在"
    code_label = "工艺路线编码"

    def to_out_list(self, objs: Sequence[models.Routing]) -> list[schemas.RoutingOut]:
        material_map = _index(
            MaterialRepository(self.db).get_by_ids({obj.material_id for obj in objs})
        )
        summary = RoutingStepRepository(self.db).summary_by_routing([obj.id for obj in objs])
        return [
            schemas.RoutingOut.model_validate(obj).model_copy(
                update={
                    "material_code": _attr(material_map.get(obj.material_id), "code"),
                    "material_name": _attr(material_map.get(obj.material_id), "name"),
                    "step_count": summary.get(obj.id, (0, 0.0))[0],
                    "total_minutes": summary.get(obj.id, (0, 0.0))[1],
                }
            )
            for obj in objs
        ]

    def _validate_material(self, material_id: int) -> None:
        if MaterialRepository(self.db).get(material_id) is None:
            raise BusinessException(errors.CODE_INVALID_REFERENCE, "所选物料不存在")

    def _validate_version(self, material_id: int, version: str, exclude_id: int | None = None) -> None:
        existing = RoutingRepository(self.db).get_by(material_id=material_id, version=version)
        if existing is not None and existing.id != exclude_id:
            raise BusinessException(
                errors.CODE_DUPLICATE_CODE, f"该物料已存在版本「{version}」的工艺路线"
            )

    def before_create(self, data: dict[str, Any]) -> None:
        self._validate_material(data["material_id"])
        self._validate_version(data["material_id"], data["version"])

    def after_create(self, obj: models.Routing) -> None:
        if obj.is_default:
            RoutingRepository(self.db).clear_default(obj.material_id, keep_id=obj.id)

    def before_update(self, obj: models.Routing, data: dict[str, Any]) -> None:
        material_id = data.get("material_id", obj.material_id)
        version = data.get("version", obj.version)
        if material_id != obj.material_id or version != obj.version:
            self._validate_material(material_id)
            self._validate_version(material_id, version, exclude_id=obj.id)

    def after_update(self, obj: models.Routing, data: dict[str, Any]) -> None:
        if obj.is_default:
            RoutingRepository(self.db).clear_default(obj.material_id, keep_id=obj.id)

    def before_delete(self, obj: models.Routing) -> None:
        RoutingStepRepository(self.db).delete_where(routing_id=obj.id)

    # ---------- 工序 ---------- #
    def detail_with_steps(self, routing_id: int) -> schemas.RoutingDetailOut:
        routing = self.get_or_404(routing_id)
        base = self.to_out(routing)
        return schemas.RoutingDetailOut(
            **base.model_dump(), steps=self.list_steps(routing_id)  # type: ignore[arg-type]
        )

    def list_steps(self, routing_id: int) -> list[schemas.RoutingStepOut]:
        self.get_or_404(routing_id)
        steps = RoutingStepRepository(self.db).list_by_routing(routing_id)
        return [schemas.RoutingStepOut.model_validate(step) for step in steps]

    def _validate_step(self, routing_id: int, data: dict[str, Any], exclude_id: int | None = None) -> None:
        existing = RoutingStepRepository(self.db).get_by(
            routing_id=routing_id, step_no=data["step_no"]
        )
        if existing is not None and existing.id != exclude_id:
            raise BusinessException(errors.CODE_DUPLICATE_CODE, f"工序号 {data['step_no']} 已存在")

    def add_step(self, routing_id: int, payload: BaseModel) -> schemas.RoutingStepOut:
        self.get_or_404(routing_id)
        data = payload.model_dump()
        self._validate_step(routing_id, data)
        step = RoutingStepRepository(self.db).create({**data, "routing_id": routing_id})
        self.db.commit()
        self.db.refresh(step)
        return schemas.RoutingStepOut.model_validate(step)

    def update_step(self, routing_id: int, step_id: int, payload: BaseModel) -> schemas.RoutingStepOut:
        self.get_or_404(routing_id)
        repo = RoutingStepRepository(self.db)
        step = repo.get(step_id)
        if step is None or step.routing_id != routing_id:
            raise BusinessException(errors.CODE_NOT_FOUND, "工序不存在")
        data = payload.model_dump(exclude_unset=True)
        self._validate_step(routing_id, {**data, "step_no": data.get("step_no", step.step_no)}, exclude_id=step_id)
        repo.update(step, data)
        self.db.commit()
        self.db.refresh(step)
        return schemas.RoutingStepOut.model_validate(step)

    def delete_step(self, routing_id: int, step_id: int) -> None:
        self.get_or_404(routing_id)
        repo = RoutingStepRepository(self.db)
        step = repo.get(step_id)
        if step is None or step.routing_id != routing_id:
            raise BusinessException(errors.CODE_NOT_FOUND, "工序不存在")
        repo.delete(step)
        self.db.commit()


# --------------------------------------------------------------------------- #
# 二、组织与人员
# --------------------------------------------------------------------------- #
class OrganizationService(BaseService):
    """组织结构树。"""

    repository_cls = OrganizationRepository
    out_schema = schemas.OrganizationOut
    not_found_message = "组织不存在"
    code_label = "组织编码"

    def _get_parent(self, parent_id: int | None) -> models.Organization | None:
        if parent_id is None:
            return None
        parent = self.repo.get(parent_id)
        if parent is None:
            raise BusinessException(errors.CODE_INVALID_PARENT, "上级组织不存在")
        return parent

    def before_create(self, data: dict[str, Any]) -> None:
        self._get_parent(data.get("parent_id"))

    def after_create(self, obj: models.Organization) -> None:
        """拿到主键后回填层级路径：`/父路径/自身 ID/`。"""
        parent = self._get_parent(obj.parent_id)
        obj.level = (parent.level + 1) if parent else 1
        obj.path = f"{parent.path}{obj.id}/" if parent else f"/{obj.id}/"
        self.db.flush()

    def before_update(self, obj: models.Organization, data: dict[str, Any]) -> None:
        if "parent_id" not in data or data["parent_id"] == obj.parent_id:
            return
        new_parent_id = data["parent_id"]
        if new_parent_id == obj.id:
            raise BusinessException(errors.CODE_INVALID_PARENT, "上级组织不能是自己")
        parent = self._get_parent(new_parent_id)
        if parent is not None and parent.path.startswith(obj.path):
            raise BusinessException(errors.CODE_INVALID_PARENT, "上级组织不能是自己的下级")
        old_path, old_level = obj.path, obj.level
        new_level = (parent.level + 1) if parent else 1
        new_path = f"{parent.path}{obj.id}/" if parent else f"/{obj.id}/"
        data["level"] = new_level
        data["path"] = new_path
        self._shift_descendants(old_path, new_path, new_level - old_level)

    def _shift_descendants(self, old_path: str, new_path: str, level_delta: int) -> None:
        """移动组织时同步调整所有下级的 `path` / `level`。"""
        for child in self.repo.list_all():
            if child.path.startswith(old_path) and child.path != old_path:
                child.path = new_path + child.path[len(old_path):]
                child.level = child.level + level_delta
        self.db.flush()

    def before_delete(self, obj: models.Organization) -> None:
        if self.repo.list_children(obj.id):
            raise BusinessException(errors.CODE_HAS_CHILDREN, "存在下级组织，不能删除")
        if EmployeeRepository(self.db).exists(org_id=obj.id):
            raise BusinessException(errors.CODE_IN_USE, "该组织下存在人员，不能删除")

    def tree(self, *, keyword: str | None = None) -> list[schemas.OrganizationTreeOut]:
        """返回组织结构树（按层级与排序字段组装）。"""
        nodes = self.repo.list_all(keyword=keyword)
        node_map: dict[int, schemas.OrganizationTreeOut] = {
            node.id: schemas.OrganizationTreeOut.model_validate(node) for node in nodes
        }
        roots: list[schemas.OrganizationTreeOut] = []
        for node in nodes:
            current = node_map[node.id]
            parent = node_map.get(node.parent_id) if node.parent_id else None
            if parent is None:
                roots.append(current)
            else:
                parent.children.append(current)
        return roots


class EmployeeService(BaseService):
    """人员档案。"""

    repository_cls = EmployeeRepository
    out_schema = schemas.EmployeeOut
    not_found_message = "人员不存在"
    code_label = "工号"

    def to_out_list(self, objs: Sequence[models.Employee]) -> list[schemas.EmployeeOut]:
        org_map = _index(
            OrganizationRepository(self.db).get_by_ids(
                {obj.org_id for obj in objs if obj.org_id is not None}
            )
        )
        return [
            schemas.EmployeeOut.model_validate(obj).model_copy(
                update={"org_name": _attr(org_map.get(obj.org_id), "name")}
            )
            for obj in objs
        ]

    def _validate_org(self, org_id: int | None) -> None:
        if org_id is not None and OrganizationRepository(self.db).get(org_id) is None:
            raise BusinessException(errors.CODE_INVALID_REFERENCE, "所选组织不存在")

    def before_create(self, data: dict[str, Any]) -> None:
        self._validate_org(data.get("org_id"))

    def before_update(self, obj: models.Employee, data: dict[str, Any]) -> None:
        self._validate_org(data.get("org_id"))

    def before_delete(self, obj: models.Employee) -> None:
        if UserRepository(self.db).exists(employee_id=obj.id):
            raise BusinessException(errors.CODE_IN_USE, "该人员已关联登录账号，不能删除")


# --------------------------------------------------------------------------- #
# 三、共性基础字典
# --------------------------------------------------------------------------- #
class DictionaryTypeService(BaseService):
    """字典类型。"""

    repository_cls = DictionaryTypeRepository
    out_schema = schemas.DictionaryTypeOut
    not_found_message = "字典类型不存在"
    code_label = "字典类型编码"

    def before_delete(self, obj: models.DictionaryType) -> None:
        if obj.is_system:
            raise BusinessException(errors.CODE_IN_USE, "系统内置字典类型不允许删除")
        if DictionaryItemRepository(self.db).exists(type_id=obj.id):
            raise BusinessException(errors.CODE_IN_USE, "该字典类型下存在字典项，不能删除")


class DictionaryItemService(BaseService):
    """字典项（按字典类型分组的层级列表）。"""

    repository_cls = DictionaryItemRepository
    out_schema = schemas.DictionaryItemOut
    not_found_message = "字典项不存在"
    code_field = None  # 唯一性作用域是"同一字典类型内"，由本类自行校验
    code_label = "字典项编码"

    def get_or_404(self, obj_id: int) -> Any:
        item = self.repo.get(obj_id)
        if item is None:
            raise BusinessException(errors.CODE_NOT_FOUND, self.not_found_message)
        return item

    def to_out_list(self, objs: Sequence[models.DictionaryItem]) -> list[schemas.DictionaryItemOut]:
        type_map = _index(
            DictionaryTypeRepository(self.db).get_by_ids({obj.type_id for obj in objs})
        )
        return [
            schemas.DictionaryItemOut.model_validate(obj).model_copy(
                update={"type_code": _attr(type_map.get(obj.type_id), "code")}
            )
            for obj in objs
        ]

    def page(  # type: ignore[override]
        self,
        *,
        params: PageParams,
        type_id: int | None = None,
        filters: Mapping[str, Any] | None = None,
        keyword: str | None = None,
    ) -> PageData[schemas.DictionaryItemOut]:
        merged = dict(filters or {})
        if type_id is not None:
            merged["type_id"] = type_id
        return super().page(params=params, filters=merged, keyword=keyword)

    def _validate(self, type_id: int, data: dict[str, Any], exclude_id: int | None = None) -> None:
        if DictionaryTypeRepository(self.db).get(type_id) is None:
            raise BusinessException(errors.CODE_INVALID_REFERENCE, "字典类型不存在")
        existing = self.repo.get_by(type_id=type_id, item_code=data["item_code"])
        if existing is not None and existing.id != exclude_id:
            raise BusinessException(
                errors.CODE_DUPLICATE_CODE, f"字典项编码「{data['item_code']}」已存在"
            )
        parent_id = data.get("parent_id")
        if parent_id is not None:
            parent = self.repo.get(parent_id)
            if parent is None or parent.type_id != type_id:
                raise BusinessException(errors.CODE_INVALID_PARENT, "上级字典项不存在")
            if exclude_id is not None and parent_id == exclude_id:
                raise BusinessException(errors.CODE_INVALID_PARENT, "上级字典项不能是自己")

    def create_item(self, type_id: int, payload: BaseModel) -> schemas.DictionaryItemOut:
        data = payload.model_dump()
        self._validate(type_id, data)
        item = self.repo.create({**data, "type_id": type_id})
        self.db.commit()
        self.db.refresh(item)
        return schemas.DictionaryItemOut.model_validate(item)

    def update_item(self, item_id: int, payload: BaseModel) -> schemas.DictionaryItemOut:
        item = self.get_or_404(item_id)
        data = payload.model_dump(exclude_unset=True)
        self._validate(
            item.type_id,
            {
                "item_code": data.get("item_code", item.item_code),
                "parent_id": data.get("parent_id", item.parent_id),
            },
            exclude_id=item_id,
        )
        self.repo.update(item, data)
        self.db.commit()
        self.db.refresh(item)
        return schemas.DictionaryItemOut.model_validate(item)

    def delete_item(self, item_id: int) -> None:
        item = self.get_or_404(item_id)
        if self.repo.exists(parent_id=item.id):
            raise BusinessException(errors.CODE_HAS_CHILDREN, "存在下级字典项，不能删除")
        self.repo.delete(item)
        self.db.commit()


# --------------------------------------------------------------------------- #
# 四、访问权限：用户 / 角色 / 权限
# --------------------------------------------------------------------------- #
class RoleService(BaseService):
    """角色（含数据访问范围与权限分配）。"""

    repository_cls = RoleRepository
    out_schema = schemas.RoleOut
    not_found_message = "角色不存在"
    code_label = "角色编码"

    def list_register_options(self) -> list[schemas.RoleOption]:
        """注册页可选身份列表：只返回启用中的角色。"""
        roles = [role for role in RoleRepository(self.db).list_all() if role.is_enabled]
        return [schemas.RoleOption(id=role.id, code=role.code, name=role.name) for role in roles]

    _pending_permissions: list[int] | None = None
    """新增 / 更新时需要写入 role_permission 的权限 ID，由钩子暂存。"""

    def to_out_list(self, objs: Sequence[models.Role]) -> list[schemas.RoleOut]:
        permission_map = RolePermissionRepository(self.db).map_permission_ids(
            [obj.id for obj in objs]
        )
        return [
            schemas.RoleOut.model_validate(obj).model_copy(
                update={"permission_ids": permission_map.get(obj.id, [])}
            )
            for obj in objs
        ]

    def _validate_permissions(self, permission_ids: Iterable[int]) -> list[int]:
        ids = list(dict.fromkeys(permission_ids))
        if not ids:
            return []
        found = {item.id for item in PermissionRepository(self.db).get_by_ids(ids)}
        missing = [item for item in ids if item not in found]
        if missing:
            raise BusinessException(
                errors.CODE_INVALID_REFERENCE, f"权限不存在：{missing}"
            )
        return ids

    def before_create(self, data: dict[str, Any]) -> None:
        self._pending_permissions = self._validate_permissions(data.pop("permission_ids", []))

    def after_create(self, obj: models.Role) -> None:
        RolePermissionRepository(self.db).replace(obj.id, self._pending_permissions or [])

    def before_update(self, obj: models.Role, data: dict[str, Any]) -> None:
        if "permission_ids" in data:
            self._pending_permissions = self._validate_permissions(data.pop("permission_ids"))
        else:
            self._pending_permissions = None

    def after_update(self, obj: models.Role, data: dict[str, Any]) -> None:
        if self._pending_permissions is not None:
            RolePermissionRepository(self.db).replace(obj.id, self._pending_permissions)

    def before_delete(self, obj: models.Role) -> None:
        if UserRoleRepository(self.db).exists(role_id=obj.id):
            raise BusinessException(errors.CODE_IN_USE, "该角色已分配给用户，不能删除")
        RolePermissionRepository(self.db).delete_where(role_id=obj.id)

    def assign_permissions(self, role_id: int, permission_ids: Sequence[int]) -> schemas.RoleOut:
        role = self.get_or_404(role_id)
        RolePermissionRepository(self.db).replace(role_id, self._validate_permissions(permission_ids))
        self.db.commit()
        return self.to_out(role)


class PermissionService(BaseService):
    """权限资源树。"""

    repository_cls = PermissionRepository
    out_schema = schemas.PermissionOut
    not_found_message = "权限不存在"
    code_label = "权限编码"

    def _get_parent(self, parent_id: int | None) -> models.Permission | None:
        if parent_id is None:
            return None
        parent = self.repo.get(parent_id)
        if parent is None:
            raise BusinessException(errors.CODE_INVALID_PARENT, "上级权限不存在")
        return parent

    def before_create(self, data: dict[str, Any]) -> None:
        self._get_parent(data.get("parent_id"))

    def before_update(self, obj: models.Permission, data: dict[str, Any]) -> None:
        if "parent_id" not in data or data["parent_id"] == obj.parent_id:
            return
        if data["parent_id"] == obj.id:
            raise BusinessException(errors.CODE_INVALID_PARENT, "上级权限不能是自己")
        self._get_parent(data["parent_id"])

    def before_delete(self, obj: models.Permission) -> None:
        if self.repo.exists(parent_id=obj.id):
            raise BusinessException(errors.CODE_HAS_CHILDREN, "存在下级权限，不能删除")
        if RolePermissionRepository(self.db).is_permission_used(obj.id):
            raise BusinessException(errors.CODE_IN_USE, "该权限已分配给角色，不能删除")

    def tree(self) -> list[schemas.PermissionTreeOut]:
        nodes = self.repo.list_all()
        node_map: dict[int, schemas.PermissionTreeOut] = {
            node.id: schemas.PermissionTreeOut.model_validate(node) for node in nodes
        }
        roots: list[schemas.PermissionTreeOut] = []
        for node in nodes:
            current = node_map[node.id]
            parent = node_map.get(node.parent_id) if node.parent_id else None
            if parent is None:
                roots.append(current)
            else:
                parent.children.append(current)
        return roots


class UserService(BaseService):
    """账号（登录、密码、角色分配）。"""

    repository_cls = UserRepository
    out_schema = schemas.UserOut
    not_found_message = "账号不存在"
    code_field = None  # 唯一字段是 username，语义与 code 不同，由本类自行校验
    code_label = "账号"

    _pending_roles: list[int] | None = None
    """新增账号时需要写入 user_role 的角色 ID，由钩子暂存。"""

    def to_out_list(self, objs: Sequence[models.User]) -> list[schemas.UserOut]:
        user_ids = [obj.id for obj in objs]
        role_ids_map = UserRoleRepository(self.db).map_role_ids(user_ids)
        role_map = _index(RoleRepository(self.db).get_by_ids(
            {role_id for ids in role_ids_map.values() for role_id in ids}
        ))
        org_map = _index(
            OrganizationRepository(self.db).get_by_ids(
                {obj.org_id for obj in objs if obj.org_id is not None}
            )
        )
        employee_map = _index(
            EmployeeRepository(self.db).get_by_ids(
                {obj.employee_id for obj in objs if obj.employee_id is not None}
            )
        )
        items = []
        for obj in objs:
            role_ids = role_ids_map.get(obj.id, [])
            items.append(
                schemas.UserOut.model_validate(obj).model_copy(
                    update={
                        "role_ids": role_ids,
                        "role_names": [
                            _attr(role_map.get(role_id), "name") for role_id in role_ids
                        ],
                        "org_name": _attr(org_map.get(obj.org_id), "name"),
                        "employee_name": _attr(employee_map.get(obj.employee_id), "name"),
                    }
                )
            )
        return items

    # ---------- 校验 ---------- #
    def ensure_username_unique(self, username: str, exclude_id: int | None = None) -> None:
        existing = UserRepository(self.db).get_by_username(username)
        if existing is not None and existing.id != exclude_id:
            raise BusinessException(errors.CODE_DUPLICATE_CODE, f"账号「{username}」已存在")

    def _validate_roles(self, role_ids: Iterable[int]) -> list[int]:
        ids = list(dict.fromkeys(role_ids))
        if not ids:
            return []
        found = {role.id for role in RoleRepository(self.db).get_by_ids(ids)}
        missing = [item for item in ids if item not in found]
        if missing:
            raise BusinessException(errors.CODE_INVALID_REFERENCE, f"角色不存在：{missing}")
        return ids

    def before_create(self, data: dict[str, Any]) -> None:
        self.ensure_username_unique(data["username"])
        data["password_hash"] = security.hash_password(data.pop("password"))
        self._pending_roles = self._validate_roles(data.pop("role_ids", []))

    def after_create(self, obj: models.User) -> None:
        UserRoleRepository(self.db).replace(obj.id, self._pending_roles or [])

    def before_update(self, obj: models.User, data: dict[str, Any]) -> None:
        if obj.is_superuser and data.get("is_enabled") is False:
            raise BusinessException(errors.CODE_SELF_OPERATION, "超级管理员账号不允许停用")

    def delete(self, obj_id: int, *, operator_id: int | None = None) -> None:
        obj = self.get_or_404(obj_id)
        if operator_id is not None and obj.id == operator_id:
            raise BusinessException(errors.CODE_SELF_OPERATION, "不能删除当前登录账号")
        if obj.is_superuser:
            raise BusinessException(errors.CODE_SELF_OPERATION, "超级管理员账号不允许删除")
        UserRoleRepository(self.db).delete_where(user_id=obj.id)
        self.repo.delete(obj)
        self.db.commit()

    def assign_roles(self, user_id: int, role_ids: Sequence[int]) -> schemas.UserOut:
        user = self.get_or_404(user_id)
        UserRoleRepository(self.db).replace(user_id, self._validate_roles(role_ids))
        self.db.commit()
        return self.to_out(user)

    def reset_password(self, user_id: int, new_password: str) -> None:
        user = self.get_or_404(user_id)
        self.repo.update(user, {"password_hash": security.hash_password(new_password)})
        self.db.commit()

    def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        user = self.get_or_404(user_id)
        if not security.verify_password(old_password, user.password_hash):
            raise BusinessException(errors.CODE_OLD_PASSWORD_WRONG, "原密码不正确")
        self.repo.update(user, {"password_hash": security.hash_password(new_password)})
        self.db.commit()

    # ---------- 登录 ---------- #
    def login(self, username: str, password: str) -> schemas.TokenOut:
        """校验账号密码并签发令牌。"""
        user = UserRepository(self.db).get_by_username(username)
        if user is None or not security.verify_password(password, user.password_hash):
            raise BusinessException(errors.CODE_LOGIN_FAILED, "账号或密码错误")
        if not user.is_enabled:
            raise BusinessException(errors.CODE_USER_DISABLED, "账号已停用，请联系管理员")
        if user.approval_status == ApprovalStatus.REJECTED.value:
            raise BusinessException(errors.CODE_ACCOUNT_REJECTED, "注册申请已被驳回，请联系人事主管")

        self.repo.update(user, {"last_login_at": datetime.now()})
        self.db.commit()
        token, expires_in = security.create_access_token(user.id, user.username)
        return schemas.TokenOut(
            access_token=token,
            expires_in=expires_in,
            user=self.login_user_info(user.id),
        )

    def login_user_info(self, user_id: int) -> schemas.LoginUserOut:
        """当前登录用户信息（含角色与权限编码，前端据此控制菜单 / 按钮）。

        权限按审批状态计算：
        - PENDING：只给「游客」角色的权限（注册后先信任、低权限使用）；
        - APPROVED：按实际绑定的角色给权限（注册时自选的身份此时生效）。
        """
        user = self.get_or_404(user_id)
        role_ids = UserRoleRepository(self.db).list_role_ids(user.id)
        roles = RoleRepository(self.db).get_by_ids(role_ids)
        permissions: list[str] = []
        if user.is_superuser:
            permissions = [item.code for item in PermissionRepository(self.db).list_all()]
        elif user.approval_status == ApprovalStatus.PENDING.value:
            guest = RoleRepository(self.db).get_by(code="GUEST")
            if guest is not None and guest.is_enabled:
                permission_ids = RolePermissionRepository(self.db).map_permission_ids([guest.id])
                flat_ids = {pid for ids in permission_ids.values() for pid in ids}
                permissions = [
                    item.code for item in PermissionRepository(self.db).get_by_ids(flat_ids)
                ]
            roles = []  # 审批前所选角色不生效，不对外暴露
        else:
            enabled_role_ids = [role.id for role in roles if role.is_enabled]
            permission_ids = RolePermissionRepository(self.db).map_permission_ids(enabled_role_ids)
            flat_ids = {pid for ids in permission_ids.values() for pid in ids}
            permissions = [item.code for item in PermissionRepository(self.db).get_by_ids(flat_ids)]
        return schemas.LoginUserOut(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            is_superuser=user.is_superuser,
            org_id=user.org_id,
            approval_status=user.approval_status,
            roles=[role.code for role in roles],
            permissions=permissions,
        )

    # ---------- 注册 / 审批 ---------- #
    def register(self, payload: schemas.RegisterRequest) -> schemas.UserOut:
        """公开注册：自选身份并直接绑定，但审批前只有游客权限（见 login_user_info）。"""
        self.ensure_username_unique(payload.username)
        role_ids = self._validate_roles([payload.role_id])
        created = self.create(
            schemas.UserCreate(
                username=payload.username,
                password=payload.password,
                real_name=payload.real_name,
                email=payload.email,
                phone=payload.phone,
                role_ids=role_ids,
            )
        )
        obj = self.repo.get(created.id)
        assert obj is not None  # 刚创建必然存在
        self.repo.update(obj, {"approval_status": ApprovalStatus.PENDING.value})
        self.db.commit()
        return self.to_out(obj)

    def _ensure_can_review(self, operator: models.User) -> None:
        """审批权限：超级管理员，或持有 `system:user:approve` 权限的已批准账号。

        注意：注册中（PENDING）的账号即使绑定了有审批权的角色，审批前权限也不生效
        （见 `login_user_info`），从权限编码上天然挡住。
        """
        if operator.is_superuser:
            return
        if operator.approval_status != ApprovalStatus.APPROVED.value:
            raise BusinessException(errors.CODE_FORBIDDEN, "仅已批准的管理人员可执行审批")
        if "system:user:approve" not in self.login_user_info(operator.id).permissions:
            raise BusinessException(errors.CODE_FORBIDDEN, f"无访问权限（缺少权限：system:user:approve）")

    def _review(self, user_id: int, operator: models.User, status: ApprovalStatus) -> schemas.UserOut:
        self._ensure_can_review(operator)
        if operator.id == user_id:
            raise BusinessException(errors.CODE_SELF_OPERATION, "不能审批自己的账号")
        user = self.get_or_404(user_id)
        self.repo.update(user, {"approval_status": status.value})
        self.db.commit()
        return self.to_out(user)

    def approve_user(self, user_id: int, operator: models.User) -> schemas.UserOut:
        """批准注册：所选角色权限自此生效。"""
        return self._review(user_id, operator, ApprovalStatus.APPROVED)

    def reject_user(self, user_id: int, operator: models.User) -> schemas.UserOut:
        """驳回注册：账号无法再登录。"""
        return self._review(user_id, operator, ApprovalStatus.REJECTED)


# --------------------------------------------------------------------------- #
# 五、操作日志
# --------------------------------------------------------------------------- #
class OperationLogService(BaseService):
    """操作日志：只写入与查询，不提供修改与删除单条的能力。"""

    repository_cls = OperationLogRepository
    out_schema = schemas.OperationLogOut
    not_found_message = "日志不存在"
    code_field = None

    def page(  # type: ignore[override]
        self,
        *,
        params: PageParams,
        filters: Mapping[str, Any] | None = None,
        keyword: str | None = None,
        created_from: Any = None,
        created_to: Any = None,
    ) -> PageData[schemas.OperationLogOut]:
        rows, total = OperationLogRepository(self.db).list_logs(
            params=params,
            filters=filters,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
        )
        return PageData(
            page=params.page,
            page_size=params.page_size,
            total=total,
            items=self.to_out_list(rows),
        )

    def write(
        self,
        *,
        module: str,
        action: str,
        description: str | None = None,
        user_id: int | None = None,
        username: str | None = None,
        method: str | None = None,
        path: str | None = None,
        ip: str | None = None,
        request_params: str | None = None,
        status: str = "SUCCESS",
        error_msg: str | None = None,
        duration_ms: int | None = None,
        commit: bool = True,
    ) -> None:
        """写一条操作日志（由 `log_operation` 契约与路由装饰器调用）。"""
        self.repo.create(
            {
                "module": module,
                "action": action,
                "description": description,
                "user_id": user_id,
                "username": username,
                "method": method,
                "path": path,
                "ip": ip,
                "request_params": request_params,
                "status": status,
                "error_msg": error_msg,
                "duration_ms": duration_ms,
            }
        )
        if commit:
            self.db.commit()

    def clear_before(self, moment: Any) -> int:
        removed = OperationLogRepository(self.db).delete_before(moment)
        self.db.commit()
        return removed


# --------------------------------------------------------------------------- #
# 内部工具
# --------------------------------------------------------------------------- #
def _index(objs: Iterable[Any]) -> dict[int, Any]:
    """把对象列表转成 `{id: 对象}` 映射，便于批量回填关联字段。"""
    return {obj.id: obj for obj in objs}


def _attr(obj: Any, name: str) -> Any:
    """安全取属性，`obj` 为 None 时返回 None。"""
    return getattr(obj, name, None) if obj is not None else None


def _enum_value(value: Any) -> Any:
    """把 Pydantic 传入的枚举统一成数据库里存的字符串值。"""
    return getattr(value, "value", value)
