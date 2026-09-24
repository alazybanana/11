"""system 模块路由（系统与基础信息管理）。

统一前缀 `/api/v1/system` 由 `app/main.py` 注入，本文件只写相对路径。

接口分组：
| 分组 | 路径 | 说明 |
| --- | --- | --- |
| 健康检查 | `GET /health` | 占位接口，不访问数据库 |
| 认证 | `/auth/*` | 登录、注册（自选身份）、注册身份列表、登出、当前用户、改密 |
| 物料 | `/materials` | 成品 / 半成品 / 原材料统一主数据，增删查改 |
| BOM | `/boms`、`/boms/{id}/lines` | BOM 头 + 行（多层结构） |
| BOM 展开 | `/boms/tree`、`/boms/flat-lines` | 按物料多层展开：树形 / 一维用料清单 |
| 工艺路线 | `/routings`、`/routings/{id}/steps` | 工艺路线 + 工序 |
| 组织人员 | `/organizations`、`/employees` | 组织结构树 + 人员档案 |
| 基础字典 | `/dictionary-types`、`/dictionary-items` | 字典类型 + 字典项 |
| 权限管理 | `/users`、`/roles`、`/permissions` | 账号（含注册审批）/ 角色 / 权限 |
| 操作日志 | `/operation-logs` | 只读查询 |

除 `/health`、`/auth/login`、`/auth/register`、`/auth/roles-available` 外，
**所有接口都需要携带登录令牌**（`Authorization: Bearer <token>`），由
`app/core/security.py` 校验。

新增 / 修改类接口统一通过 `operation_log(...)` 依赖项自动写操作日志。
"""

from datetime import date, datetime
from typing import Any, Callable, Type

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.pagination import PageData, PageParams
from app.common.response import ApiResponse, success
from app.core.database import get_db
from app.modules.system import errors, schemas, service
from app.modules.system.enums import BomType
from app.modules.system.deps import (
    CurrentUser,
    client_ip,
    get_current_user,
    operation_log,
    require_permission,
)


# 权限码速查（与 seed.py 的权限资源树一致）：
#   功能码（MENU）= 查看（列表 / 详情 / 展开）
#   `功能码:manage`（BUTTON）= 新增 / 修改 / 删除等写操作
#   system:user:approve / assign / reset、system:role:assign、system:log:clear = 高危操作
router = APIRouter(tags=["system"])

# 需要登录才能访问的子路由集合（`/health` 与 `/auth/login` 不在此列）
protected = APIRouter(dependencies=[Depends(get_current_user)])


# --------------------------------------------------------------------------- #
# 健康检查（占位）
# --------------------------------------------------------------------------- #
@router.get("/health", response_model=schemas.HealthResponse, summary="system 模块健康检查（占位）")
def health() -> schemas.HealthResponse:
    """占位接口：只返回模块标识与状态，不含任何业务逻辑。"""
    from app.shared.enums import ModuleName, ModuleStatus
    from app.shared.types import HealthData

    return schemas.HealthResponse(
        data=HealthData(module=ModuleName.SYSTEM.value, status=ModuleStatus.UP.value)
    )


# --------------------------------------------------------------------------- #
# CRUD 路由工厂
# --------------------------------------------------------------------------- #
def register_crud(
    sub: APIRouter,
    *,
    path: str,
    key: str,
    label: str,
    service_cls: Type[service.BaseService],
    create_schema: Type[BaseModel],
    update_schema: Type[BaseModel],
    out_schema: Type[BaseModel],
    view_code: str | None = None,
    manage_code: str | None = None,
) -> None:
    """为一个实体注册标准的增删查改路由（不含列表查询，列表由各实体单独定义筛选条件）。

    - `view_code`：查看（详情）所需的权限编码，缺省只要求登录；
    - `manage_code`：新增 / 修改 / 删除所需的权限编码，缺省只要求登录。
    """
    view_deps = [Depends(require_permission(view_code))] if view_code else []
    write_deps = [Depends(require_permission(manage_code))] if manage_code else []

    @sub.post(
        path,
        response_model=ApiResponse[out_schema],
        summary=f"新增{label}",
        operation_id=f"create_{key}",
        dependencies=[Depends(operation_log("system", "CREATE", f"新增{label}")), *write_deps],
    )
    def create_item(payload: create_schema, db: Session = Depends(get_db)) -> Any:  # type: ignore[valid-type]
        return success(service_cls(db).create(payload))

    @sub.get(
        f"{path}/{{item_id}}",
        response_model=ApiResponse[out_schema],
        summary=f"{label}详情",
        operation_id=f"get_{key}",
        dependencies=view_deps,
    )
    def get_item(item_id: int, db: Session = Depends(get_db)) -> Any:
        return success(service_cls(db).detail(item_id))

    @sub.put(
        f"{path}/{{item_id}}",
        response_model=ApiResponse[out_schema],
        summary=f"修改{label}",
        operation_id=f"update_{key}",
        dependencies=[Depends(operation_log("system", "UPDATE", f"修改{label}")), *write_deps],
    )
    def update_item(item_id: int, payload: update_schema, db: Session = Depends(get_db)) -> Any:  # type: ignore[valid-type]
        return success(service_cls(db).update(item_id, payload))

    @sub.patch(
        f"{path}/{{item_id}}",
        response_model=ApiResponse[out_schema],
        summary=f"局部修改{label}",
        operation_id=f"patch_{key}",
        dependencies=[Depends(operation_log("system", "UPDATE", f"局部修改{label}")), *write_deps],
    )
    def patch_item(item_id: int, payload: update_schema, db: Session = Depends(get_db)) -> Any:  # type: ignore[valid-type]
        return success(service_cls(db).update(item_id, payload))

    @sub.delete(
        f"{path}/{{item_id}}",
        response_model=ApiResponse[None],
        summary=f"删除{label}",
        operation_id=f"delete_{key}",
        dependencies=[Depends(operation_log("system", "DELETE", f"删除{label}")), *write_deps],
    )
    def delete_item(item_id: int, db: Session = Depends(get_db)) -> Any:
        service_cls(db).delete(item_id)
        return success(message="删除成功")


# =========================================================================== #
# 一、产品信息管理：物料主数据（成品 / 半成品 / 原材料）
# =========================================================================== #
@protected.get(
    "/materials",
    response_model=ApiResponse[PageData[schemas.MaterialOut]],
    summary="物料分页查询",
    operation_id="list_materials",
    dependencies=[Depends(require_permission("system:material"))],
)
def list_materials(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按编码 / 名称 / 规格 / 型号模糊查询"),
    category_code: str | None = Query(None, description="物料分类编码"),
    material_type: str | None = Query(None, description="物料类型 RAW/SEMI/FINISHED/PACK"),
    source_type: str | None = Query(None, description="来源 PURCHASE/MAKE"),
    status: str | None = Query(None, description="状态 ENABLED/DISABLED"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.MaterialService(db).page(
            params=params,
            keyword=keyword,
            filters={
                "category_code": category_code,
                "material_type": material_type,
                "source_type": source_type,
                "status": status,
            },
        )
    )


register_crud(
    protected,
    path="/materials",
    key="material",
    label="物料",
    service_cls=service.MaterialService,
    create_schema=schemas.MaterialCreate,
    update_schema=schemas.MaterialUpdate,
    out_schema=schemas.MaterialOut,
    view_code="system:material",
    manage_code="system:material:manage",
)


# 说明：原 `/products` 一组路由已随"产品并入物料"一起删除。
# 成品 / 半成品现在只是 `material_type` 不同的物料，用 `/materials` 统一维护。


# =========================================================================== #
# 二、产品信息管理：BOM（头 + 行）
# =========================================================================== #
@protected.get(
    "/boms",
    response_model=ApiResponse[PageData[schemas.BomOut]],
    summary="BOM 分页查询",
    operation_id="list_boms",
    dependencies=[Depends(require_permission("system:bom"))],
)
def list_boms(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按 BOM 编码 / 版本模糊查询"),
    parent_material_id: int | None = Query(None, description="父件物料 ID"),
    bom_type: str | None = Query(None, description="BOM 类型 DESIGN/MANUFACTURE/SALE"),
    status: str | None = Query(None, description="状态 DRAFT/RELEASED/OBSOLETE"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.BomService(db).page(
            params=params,
            keyword=keyword,
            filters={
                "parent_material_id": parent_material_id,
                "bom_type": bom_type,
                "status": status,
            },
        )
    )


# 注意：下面两个路径必须声明在 `register_crud` 之前，
# 否则会被 `/boms/{item_id}` 抢先匹配，把 "tree" 当成 id 去解析。
@protected.get(
    "/boms/tree",
    response_model=ApiResponse[schemas.BomTreeNode],
    summary="多层 BOM 树形展开（层数不限）",
    operation_id="get_bom_tree",
    dependencies=[Depends(require_permission("system:bom"))],
)
def get_bom_tree(
    material_id: int = Query(..., description="要展开的物料 ID（通常是成品）"),
    bom_type: str = Query(
        BomType.MANUFACTURE.value, description="按哪种 BOM 展开 DESIGN/MANUFACTURE/SALE"
    ),
    on_date: date | None = Query(None, description="按哪一天判断 BOM 是否生效，缺省为今天"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.BomService(db).expand_tree(material_id, bom_type=bom_type, on_date=on_date)
    )


@protected.get(
    "/boms/flat-lines",
    response_model=ApiResponse[list[schemas.BomTreeNode]],
    summary="多层 BOM 展开成一维用料清单（虚拟件穿透）",
    operation_id="get_bom_flat_lines",
    dependencies=[Depends(require_permission("system:bom"))],
)
def get_bom_flat_lines(
    material_id: int = Query(..., description="要展开的物料 ID（通常是成品）"),
    bom_type: str = Query(
        BomType.MANUFACTURE.value, description="按哪种 BOM 展开 DESIGN/MANUFACTURE/SALE"
    ),
    on_date: date | None = Query(None, description="按哪一天判断 BOM 是否生效，缺省为今天"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.BomService(db).expand_lines(material_id, bom_type=bom_type, on_date=on_date)
    )


@protected.get(
    "/boms/{bom_id}/detail",
    response_model=ApiResponse[schemas.BomDetailOut],
    summary="BOM 详情（含行明细）",
    operation_id="get_bom_detail",
    dependencies=[Depends(require_permission("system:bom"))],
)
def get_bom_detail(bom_id: int, db: Session = Depends(get_db)) -> Any:
    return success(service.BomService(db).detail_with_lines(bom_id))


@protected.get(
    "/boms/{bom_id}/lines",
    response_model=ApiResponse[list[schemas.BomLineOut]],
    summary="BOM 行列表",
    operation_id="list_bom_lines",
    dependencies=[Depends(require_permission("system:bom"))],
)
def list_bom_lines(bom_id: int, db: Session = Depends(get_db)) -> Any:
    return success(service.BomService(db).list_lines(bom_id))


@protected.post(
    "/boms/{bom_id}/lines",
    response_model=ApiResponse[schemas.BomLineOut],
    summary="新增 BOM 行",
    operation_id="create_bom_line",
    dependencies=[
        Depends(operation_log("system", "CREATE", "新增 BOM 行")),
        Depends(require_permission("system:bom:manage")),
    ],
)
def create_bom_line(bom_id: int, payload: schemas.BomLineCreate, db: Session = Depends(get_db)) -> Any:
    return success(service.BomService(db).add_line(bom_id, payload))


@protected.put(
    "/boms/{bom_id}/lines/{line_id}",
    response_model=ApiResponse[schemas.BomLineOut],
    summary="修改 BOM 行",
    operation_id="update_bom_line",
    dependencies=[
        Depends(operation_log("system", "UPDATE", "修改 BOM 行")),
        Depends(require_permission("system:bom:manage")),
    ],
)
def update_bom_line(
    bom_id: int, line_id: int, payload: schemas.BomLineUpdate, db: Session = Depends(get_db)
) -> Any:
    return success(service.BomService(db).update_line(bom_id, line_id, payload))


@protected.delete(
    "/boms/{bom_id}/lines/{line_id}",
    response_model=ApiResponse[None],
    summary="删除 BOM 行",
    operation_id="delete_bom_line",
    dependencies=[
        Depends(operation_log("system", "DELETE", "删除 BOM 行")),
        Depends(require_permission("system:bom:manage")),
    ],
)
def delete_bom_line(bom_id: int, line_id: int, db: Session = Depends(get_db)) -> Any:
    service.BomService(db).delete_line(bom_id, line_id)
    return success(message="删除成功")


register_crud(
    protected,
    path="/boms",
    key="bom",
    label="BOM",
    service_cls=service.BomService,
    create_schema=schemas.BomCreate,
    update_schema=schemas.BomUpdate,
    out_schema=schemas.BomOut,
    view_code="system:bom",
    manage_code="system:bom:manage",
)


# =========================================================================== #
# 三、工艺信息管理：工艺路线 + 工序
# =========================================================================== #
@protected.get(
    "/routings",
    response_model=ApiResponse[PageData[schemas.RoutingOut]],
    summary="工艺路线分页查询",
    operation_id="list_routings",
    dependencies=[Depends(require_permission("system:routing"))],
)
def list_routings(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按编码 / 名称 / 版本模糊查询"),
    material_id: int | None = Query(None, description="适用物料 ID（成品 / 半成品）"),
    status: str | None = Query(None, description="状态 DRAFT/RELEASED/OBSOLETE"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.RoutingService(db).page(
            params=params,
            keyword=keyword,
            filters={"material_id": material_id, "status": status},
        )
    )


@protected.get(
    "/routings/{routing_id}/detail",
    response_model=ApiResponse[schemas.RoutingDetailOut],
    summary="工艺路线详情（含工序）",
    operation_id="get_routing_detail",
    dependencies=[Depends(require_permission("system:routing"))],
)
def get_routing_detail(routing_id: int, db: Session = Depends(get_db)) -> Any:
    return success(service.RoutingService(db).detail_with_steps(routing_id))


@protected.get(
    "/routings/{routing_id}/steps",
    response_model=ApiResponse[list[schemas.RoutingStepOut]],
    summary="工序列表",
    operation_id="list_routing_steps",
    dependencies=[Depends(require_permission("system:routing"))],
)
def list_routing_steps(routing_id: int, db: Session = Depends(get_db)) -> Any:
    return success(service.RoutingService(db).list_steps(routing_id))


@protected.post(
    "/routings/{routing_id}/steps",
    response_model=ApiResponse[schemas.RoutingStepOut],
    summary="新增工序",
    operation_id="create_routing_step",
    dependencies=[
        Depends(operation_log("system", "CREATE", "新增工序")),
        Depends(require_permission("system:routing:manage")),
    ],
)
def create_routing_step(
    routing_id: int, payload: schemas.RoutingStepCreate, db: Session = Depends(get_db)
) -> Any:
    return success(service.RoutingService(db).add_step(routing_id, payload))


@protected.put(
    "/routings/{routing_id}/steps/{step_id}",
    response_model=ApiResponse[schemas.RoutingStepOut],
    summary="修改工序",
    operation_id="update_routing_step",
    dependencies=[
        Depends(operation_log("system", "UPDATE", "修改工序")),
        Depends(require_permission("system:routing:manage")),
    ],
)
def update_routing_step(
    routing_id: int, step_id: int, payload: schemas.RoutingStepUpdate, db: Session = Depends(get_db)
) -> Any:
    return success(service.RoutingService(db).update_step(routing_id, step_id, payload))


@protected.delete(
    "/routings/{routing_id}/steps/{step_id}",
    response_model=ApiResponse[None],
    summary="删除工序",
    operation_id="delete_routing_step",
    dependencies=[
        Depends(operation_log("system", "DELETE", "删除工序")),
        Depends(require_permission("system:routing:manage")),
    ],
)
def delete_routing_step(routing_id: int, step_id: int, db: Session = Depends(get_db)) -> Any:
    service.RoutingService(db).delete_step(routing_id, step_id)
    return success(message="删除成功")


register_crud(
    protected,
    path="/routings",
    key="routing",
    label="工艺路线",
    service_cls=service.RoutingService,
    create_schema=schemas.RoutingCreate,
    update_schema=schemas.RoutingUpdate,
    out_schema=schemas.RoutingOut,
    view_code="system:routing",
    manage_code="system:routing:manage",
)


# =========================================================================== #
# 四、组织与人员信息管理
# =========================================================================== #
@protected.get(
    "/organizations/tree",
    response_model=ApiResponse[list[schemas.OrganizationTreeOut]],
    summary="组织结构树",
    operation_id="get_organization_tree",
    dependencies=[Depends(require_permission("system:org"))],
)
def get_organization_tree(
    keyword: str | None = Query(None, description="按编码 / 名称 / 负责人模糊查询"),
    db: Session = Depends(get_db),
) -> Any:
    return success(service.OrganizationService(db).tree(keyword=keyword))


@protected.get(
    "/organizations",
    response_model=ApiResponse[PageData[schemas.OrganizationOut]],
    summary="组织分页查询",
    operation_id="list_organizations",
    dependencies=[Depends(require_permission("system:org"))],
)
def list_organizations(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按编码 / 名称 / 负责人模糊查询"),
    parent_id: int | None = Query(None, description="上级组织 ID"),
    org_type: str | None = Query(None, description="组织类型 COMPANY/DEPT/TEAM"),
    is_enabled: bool | None = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.OrganizationService(db).page(
            params=params,
            keyword=keyword,
            filters={"parent_id": parent_id, "org_type": org_type, "is_enabled": is_enabled},
        )
    )


register_crud(
    protected,
    path="/organizations",
    key="organization",
    label="组织",
    service_cls=service.OrganizationService,
    create_schema=schemas.OrganizationCreate,
    update_schema=schemas.OrganizationUpdate,
    out_schema=schemas.OrganizationOut,
    view_code="system:org",
    manage_code="system:org:manage",
)


@protected.get(
    "/employees",
    response_model=ApiResponse[PageData[schemas.EmployeeOut]],
    summary="人员分页查询",
    operation_id="list_employees",
    dependencies=[Depends(require_permission("system:org"))],
)
def list_employees(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按工号 / 姓名 / 手机号 / 岗位模糊查询"),
    org_id: int | None = Query(None, description="所属组织 ID"),
    status: str | None = Query(None, description="在职状态 ACTIVE/INACTIVE/LEAVE"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.EmployeeService(db).page(
            params=params, keyword=keyword, filters={"org_id": org_id, "status": status}
        )
    )


register_crud(
    protected,
    path="/employees",
    key="employee",
    label="人员",
    service_cls=service.EmployeeService,
    create_schema=schemas.EmployeeCreate,
    update_schema=schemas.EmployeeUpdate,
    out_schema=schemas.EmployeeOut,
    view_code="system:org",
    manage_code="system:org:manage",
)


# =========================================================================== #
# 五、共性基础字典管理
# =========================================================================== #
@protected.get(
    "/dictionary-types",
    response_model=ApiResponse[PageData[schemas.DictionaryTypeOut]],
    summary="字典类型分页查询",
    operation_id="list_dictionary_types",
    dependencies=[Depends(require_permission("system:dictionary"))],
)
def list_dictionary_types(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按编码 / 名称模糊查询"),
    is_enabled: bool | None = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.DictionaryTypeService(db).page(
            params=params, keyword=keyword, filters={"is_enabled": is_enabled}
        )
    )


register_crud(
    protected,
    path="/dictionary-types",
    key="dictionary_type",
    label="字典类型",
    service_cls=service.DictionaryTypeService,
    create_schema=schemas.DictionaryTypeCreate,
    update_schema=schemas.DictionaryTypeUpdate,
    out_schema=schemas.DictionaryTypeOut,
    view_code="system:dictionary",
    manage_code="system:dictionary:manage",
)


@protected.get(
    "/dictionary-items",
    response_model=ApiResponse[PageData[schemas.DictionaryItemOut]],
    summary="字典项分页查询",
    operation_id="list_dictionary_items",
    dependencies=[Depends(require_permission("system:dictionary"))],
)
def list_dictionary_items(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按字典项编码 / 显示名模糊查询"),
    type_id: int | None = Query(None, description="所属字典类型 ID"),
    is_enabled: bool | None = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.DictionaryItemService(db).page(
            params=params, type_id=type_id, keyword=keyword, filters={"is_enabled": is_enabled}
        )
    )


@protected.post(
    "/dictionary-types/{type_id}/items",
    response_model=ApiResponse[schemas.DictionaryItemOut],
    summary="新增字典项",
    operation_id="create_dictionary_item",
    dependencies=[
        Depends(operation_log("system", "CREATE", "新增字典项")),
        Depends(require_permission("system:dictionary:manage")),
    ],
)
def create_dictionary_item(
    type_id: int, payload: schemas.DictionaryItemCreate, db: Session = Depends(get_db)
) -> Any:
    return success(service.DictionaryItemService(db).create_item(type_id, payload))


@protected.put(
    "/dictionary-items/{item_id}",
    response_model=ApiResponse[schemas.DictionaryItemOut],
    summary="修改字典项",
    operation_id="update_dictionary_item",
    dependencies=[
        Depends(operation_log("system", "UPDATE", "修改字典项")),
        Depends(require_permission("system:dictionary:manage")),
    ],
)
def update_dictionary_item(
    item_id: int, payload: schemas.DictionaryItemUpdate, db: Session = Depends(get_db)
) -> Any:
    return success(service.DictionaryItemService(db).update_item(item_id, payload))


@protected.delete(
    "/dictionary-items/{item_id}",
    response_model=ApiResponse[None],
    summary="删除字典项",
    operation_id="delete_dictionary_item",
    dependencies=[
        Depends(operation_log("system", "DELETE", "删除字典项")),
        Depends(require_permission("system:dictionary:manage")),
    ],
)
def delete_dictionary_item(item_id: int, db: Session = Depends(get_db)) -> Any:
    service.DictionaryItemService(db).delete_item(item_id)
    return success(message="删除成功")


# =========================================================================== #
# 六、系统访问权限管理：登录 / 账号 / 角色 / 权限
# =========================================================================== #
@router.post(
    "/auth/login",
    response_model=ApiResponse[schemas.TokenOut],
    summary="登录",
    operation_id="login",
    tags=["system"],
)
def login(
    payload: schemas.LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """校验账号密码并签发访问令牌；无论成功失败都会写一条登录日志。"""
    log_service = service.OperationLogService(db)
    try:
        token = service.UserService(db).login(payload.username, payload.password)
    except BusinessException as exc:
        log_service.write(
            module="system",
            action="LOGIN",
            description="用户登录失败",
            username=payload.username,
            method=request.method,
            path=str(request.url.path),
            ip=client_ip(request),
            status="FAIL",
            error_msg=exc.message,
        )
        raise
    log_service.write(
        module="system",
        action="LOGIN",
        description="用户登录成功",
        user_id=token.user.id,
        username=token.user.username,
        method=request.method,
        path=str(request.url.path),
        ip=client_ip(request),
    )
    return success(token)


@router.post(
    "/auth/register",
    response_model=ApiResponse[schemas.UserOut],
    summary="注册账号（自选身份，审批后生效）",
    operation_id="register",
    dependencies=[Depends(operation_log("system", "CREATE", "用户注册"))],
)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)) -> Any:
    """公开注册：注册后即可登录，但审批前只有游客权限；人事主管批准后获得所选角色权限。"""
    return success(
        service.UserService(db).register(payload),
        message="注册成功，待人事主管批准后获得所选角色权限",
    )


@router.get(
    "/auth/roles-available",
    response_model=ApiResponse[list[schemas.RoleOption]],
    summary="注册页可选身份列表",
    operation_id="list_register_roles",
)
def list_register_roles(db: Session = Depends(get_db)) -> Any:
    """返回启用中的角色，供注册页身份下拉框使用。"""
    return success(service.RoleService(db).list_register_options())


@protected.post(
    "/auth/logout",
    response_model=ApiResponse[None],
    summary="登出",
    operation_id="logout",
)
def logout(request: Request, current_user: CurrentUser, db: Session = Depends(get_db)) -> Any:
    """令牌为无状态实现，登出只记录日志，令牌由前端丢弃。"""
    service.OperationLogService(db).write(
        module="system",
        action="LOGOUT",
        description="用户登出",
        user_id=current_user.id,
        username=current_user.username,
        method=request.method,
        path=str(request.url.path),
        ip=client_ip(request),
    )
    return success(message="已登出")


@protected.get(
    "/auth/me",
    response_model=ApiResponse[schemas.LoginUserOut],
    summary="当前登录用户信息",
    operation_id="get_current_user_info",
)
def get_current_user_info(current_user: CurrentUser, db: Session = Depends(get_db)) -> Any:
    """返回当前用户的角色与权限编码，前端据此控制菜单与按钮显示。"""
    return success(service.UserService(db).login_user_info(current_user.id))


@protected.post(
    "/auth/change-password",
    response_model=ApiResponse[None],
    summary="修改自己的密码",
    operation_id="change_password",
    dependencies=[Depends(operation_log("system", "UPDATE", "修改密码"))],
)
def change_password(
    payload: schemas.ChangePasswordRequest, current_user: CurrentUser, db: Session = Depends(get_db)
) -> Any:
    service.UserService(db).change_password(
        current_user.id, payload.old_password, payload.new_password
    )
    return success(message="密码修改成功")


@protected.get(
    "/users",
    response_model=ApiResponse[PageData[schemas.UserOut]],
    summary="账号分页查询",
    operation_id="list_users",
    dependencies=[Depends(require_permission("system:user"))],
)
def list_users(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按账号 / 姓名 / 邮箱 / 手机号模糊查询"),
    org_id: int | None = Query(None, description="所属组织 ID"),
    is_enabled: bool | None = Query(None, description="是否启用"),
    is_superuser: bool | None = Query(None, description="是否超级管理员"),
    approval_status: str | None = Query(None, description="注册审批状态 PENDING/APPROVED/REJECTED"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.UserService(db).page(
            params=params,
            keyword=keyword,
            filters={
                "org_id": org_id,
                "is_enabled": is_enabled,
                "is_superuser": is_superuser,
                "approval_status": approval_status,
            },
        )
    )


@protected.put(
    "/users/{user_id}/roles",
    response_model=ApiResponse[schemas.UserOut],
    summary="分配用户角色",
    operation_id="assign_user_roles",
    dependencies=[
        Depends(operation_log("system", "UPDATE", "分配用户角色")),
        Depends(require_permission("system:user:assign")),
    ],
)
def assign_user_roles(
    user_id: int, payload: schemas.UserRoleAssign, db: Session = Depends(get_db)
) -> Any:
    return success(service.UserService(db).assign_roles(user_id, payload.role_ids))


@protected.post(
    "/users/{user_id}/approve",
    response_model=ApiResponse[schemas.UserOut],
    summary="批准注册账号",
    operation_id="approve_user",
    dependencies=[
        Depends(operation_log("system", "UPDATE", "批准注册账号")),
        Depends(require_permission("system:user:approve")),
    ],
)
def approve_user(user_id: int, current_user: CurrentUser, db: Session = Depends(get_db)) -> Any:
    """管理人员（或超管）批准注册账号，所选角色权限自此生效。"""
    return success(service.UserService(db).approve_user(user_id, current_user))


@protected.post(
    "/users/{user_id}/reject",
    response_model=ApiResponse[schemas.UserOut],
    summary="驳回注册账号",
    operation_id="reject_user",
    dependencies=[
        Depends(operation_log("system", "UPDATE", "驳回注册账号")),
        Depends(require_permission("system:user:approve")),
    ],
)
def reject_user(user_id: int, current_user: CurrentUser, db: Session = Depends(get_db)) -> Any:
    """管理人员（或超管）驳回注册申请，该账号无法再登录。"""
    return success(service.UserService(db).reject_user(user_id, current_user))


@protected.put(
    "/users/{user_id}/password",
    response_model=ApiResponse[None],
    summary="重置用户密码（管理员）",
    operation_id="reset_user_password",
    dependencies=[
        Depends(operation_log("system", "UPDATE", "重置用户密码")),
        Depends(require_permission("system:user:reset")),
    ],
)
def reset_user_password(
    user_id: int, payload: schemas.UserPasswordUpdate, db: Session = Depends(get_db)
) -> Any:
    service.UserService(db).reset_password(user_id, payload.password)
    return success(message="密码已重置")


register_crud(
    protected,
    path="/users",
    key="user",
    label="账号",
    service_cls=service.UserService,
    create_schema=schemas.UserCreate,
    update_schema=schemas.UserUpdate,
    out_schema=schemas.UserOut,
    view_code="system:user",
    manage_code="system:user:manage",
)


@protected.get(
    "/roles",
    response_model=ApiResponse[PageData[schemas.RoleOut]],
    summary="角色分页查询",
    operation_id="list_roles",
    dependencies=[Depends(require_permission("system:role"))],
)
def list_roles(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按编码 / 名称模糊查询"),
    is_enabled: bool | None = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.RoleService(db).page(
            params=params, keyword=keyword, filters={"is_enabled": is_enabled}
        )
    )


@protected.put(
    "/roles/{role_id}/permissions",
    response_model=ApiResponse[schemas.RoleOut],
    summary="分配角色权限",
    operation_id="assign_role_permissions",
    dependencies=[
        Depends(operation_log("system", "UPDATE", "分配角色权限")),
        Depends(require_permission("system:role:assign")),
    ],
)
def assign_role_permissions(
    role_id: int, payload: schemas.RolePermissionAssign, db: Session = Depends(get_db)
) -> Any:
    return success(service.RoleService(db).assign_permissions(role_id, payload.permission_ids))


register_crud(
    protected,
    path="/roles",
    key="role",
    label="角色",
    service_cls=service.RoleService,
    create_schema=schemas.RoleCreate,
    update_schema=schemas.RoleUpdate,
    out_schema=schemas.RoleOut,
    view_code="system:role",
    manage_code="system:role:manage",
)


@protected.get(
    "/permissions/tree",
    response_model=ApiResponse[list[schemas.PermissionTreeOut]],
    summary="权限资源树",
    operation_id="get_permission_tree",
    dependencies=[Depends(require_permission("system:permission"))],
)
def get_permission_tree(db: Session = Depends(get_db)) -> Any:
    return success(service.PermissionService(db).tree())


@protected.get(
    "/permissions",
    response_model=ApiResponse[PageData[schemas.PermissionOut]],
    summary="权限分页查询",
    operation_id="list_permissions",
    dependencies=[Depends(require_permission("system:permission"))],
)
def list_permissions(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按编码 / 名称 / 路径模糊查询"),
    perm_type: str | None = Query(None, description="类型 MENU/BUTTON/API"),
    parent_id: int | None = Query(None, description="上级权限 ID"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.PermissionService(db).page(
            params=params, keyword=keyword, filters={"perm_type": perm_type, "parent_id": parent_id}
        )
    )


register_crud(
    protected,
    path="/permissions",
    key="permission",
    label="权限",
    service_cls=service.PermissionService,
    create_schema=schemas.PermissionCreate,
    update_schema=schemas.PermissionUpdate,
    out_schema=schemas.PermissionOut,
    view_code="system:permission",
    manage_code="system:permission:manage",
)


# =========================================================================== #
# 七、系统操作日志管理
# =========================================================================== #
@protected.get(
    "/operation-logs",
    response_model=ApiResponse[PageData[schemas.OperationLogOut]],
    summary="操作日志分页查询",
    operation_id="list_operation_logs",
    dependencies=[Depends(require_permission("system:log"))],
)
def list_operation_logs(
    params: PageParams = Depends(PageParams.as_dependency),
    keyword: str | None = Query(None, description="按操作人 / 路径 / 描述模糊查询"),
    module: str | None = Query(None, description="所属模块"),
    action: str | None = Query(None, description="动作类型 CREATE/UPDATE/DELETE/LOGIN/LOGOUT"),
    status: str | None = Query(None, description="结果 SUCCESS/FAIL"),
    username: str | None = Query(None, description="操作人账号"),
    created_from: datetime | None = Query(None, description="操作时间起（含）"),
    created_to: datetime | None = Query(None, description="操作时间止（含）"),
    db: Session = Depends(get_db),
) -> Any:
    return success(
        service.OperationLogService(db).page(
            params=params,
            keyword=keyword,
            filters={"module": module, "action": action, "status": status, "username": username},
            created_from=created_from,
            created_to=created_to,
        )
    )


@protected.delete(
    "/operation-logs",
    response_model=ApiResponse[int],
    summary="清理指定时间之前的操作日志",
    operation_id="clear_operation_logs",
    dependencies=[
        Depends(operation_log("system", "DELETE", "清理操作日志")),
        Depends(require_permission("system:log:clear")),
    ],
)
def clear_operation_logs(
    before: datetime = Query(..., description="清理该时间之前的日志"),
    db: Session = Depends(get_db),
) -> Any:
    """持有 `system:log:clear` 权限的管理人员清理历史日志。"""
    return success(service.OperationLogService(db).clear_before(before), message="清理完成")


# 把需要登录的子路由挂到模块路由器上
router.include_router(protected)
