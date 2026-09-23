"""system 模块 FastAPI 依赖项：当前登录用户、权限校验、操作日志记录。

这些依赖项属于"系统访问权限管理"能力的一部分，由 system 模块实现；
其它模块**不要各自造一套**，请从 `app.modules.system.contract` 导入：

```python
from app.modules.system.contract import CurrentUser, operation_log, require_permission

@router.post("/orders", dependencies=[operation_log("sales", "CREATE", "新增销售订单")])
def create_order(current_user: CurrentUser): ...
```
"""

import json
import time
from typing import Annotated, Any, Callable, Iterator, Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.core import security
from app.core.database import get_db
from app.modules.system import errors, models
from app.modules.system.service import OperationLogService, UserService

# 请求体日志最多保留的字符数
_MAX_LOG_PARAMS_LENGTH = 2000
# 需要脱敏的请求体字段
_SENSITIVE_KEYS = ("password", "new_password", "old_password", "token", "secret")


def _extract_token(request: Request) -> str:
    """从 `Authorization: Bearer <token>` 头中取出令牌。"""
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def get_optional_current_user(
    request: Request, db: Session = Depends(get_db)
) -> Optional[models.User]:
    """解析令牌并返回当前用户；未登录或令牌失效时返回 None（不抛异常）。"""
    token = _extract_token(request)
    if not token:
        return None
    payload = security.decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    user = UserService(db).repo.get(int(payload["sub"]))
    if user is None or not user.is_enabled:
        return None
    return user


def get_current_user(user: Optional[models.User] = Depends(get_optional_current_user)) -> models.User:
    """必须登录的依赖项；未登录抛 1104。"""
    if user is None:
        raise BusinessException(errors.CODE_UNAUTHORIZED, "未登录或登录已过期")
    return user


# 供业务路由直接注入使用：`current_user: CurrentUser`
CurrentUser = Annotated[models.User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[Optional[models.User], Depends(get_optional_current_user)]


def require_permission(permission_code: str) -> Callable[..., models.User]:
    """生成"需要指定权限编码"的依赖项。

    超级管理员默认拥有全部权限；其余用户取角色关联的权限编码集合做判断。
    """

    def _dependency(
        db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
    ) -> models.User:
        if user.is_superuser:
            return user
        codes = UserService(db).login_user_info(user.id).permissions
        if permission_code not in codes:
            raise BusinessException(
                errors.CODE_FORBIDDEN, f"无访问权限（缺少权限：{permission_code}）"
            )
        return user

    return _dependency


def _sanitize(payload: Any) -> Any:
    """递归脱敏请求体中的密码、令牌等字段。"""
    if isinstance(payload, dict):
        return {
            key: ("***" if any(word in key.lower() for word in _SENSITIVE_KEYS) else _sanitize(value))
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_sanitize(item) for item in payload]
    return payload


async def _read_request_params(request: Request) -> Optional[str]:
    """读取请求体并脱敏，超长时截断；GET 等无请求体的方法返回 None。"""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    raw = await request.body()
    if not raw:
        return None
    try:
        text = json.dumps(_sanitize(json.loads(raw)), ensure_ascii=False)
    except (ValueError, UnicodeDecodeError):
        text = raw.decode("utf-8", errors="ignore")
    return text[:_MAX_LOG_PARAMS_LENGTH]


def operation_log(module: str, action: str, description: str) -> Callable[..., Iterator[None]]:
    """生成"自动记录操作日志"的依赖项。

    用法：`dependencies=[operation_log("system", "CREATE", "新增物料")]`
    成功与失败都会记录；失败时先回滚再写日志，避免脏事务影响日志落库。
    """

    async def _dependency(request: Request, db: Session = Depends(get_db)) -> Any:
        started = time.perf_counter()
        params = await _read_request_params(request)
        status, error_msg = "SUCCESS", None
        try:
            yield
        except BusinessException as exc:
            status, error_msg = "FAIL", exc.message
            raise
        except Exception as exc:  # noqa: BLE001 - 失败原因需要落库
            status, error_msg = "FAIL", str(exc)
            raise
        finally:
            if status == "FAIL":
                db.rollback()
            try:
                user = get_optional_current_user(request, db)
                OperationLogService(db).write(
                    module=module,
                    action=action,
                    description=description,
                    user_id=user.id if user else None,
                    username=user.username if user else None,
                    method=request.method,
                    path=str(request.url.path),
                    ip=request.client.host if request.client else None,
                    request_params=params,
                    status=status,
                    error_msg=error_msg,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            except Exception:  # noqa: BLE001 - 日志失败不能影响主流程
                db.rollback()

    return _dependency


def client_ip(request: Request) -> Optional[str]:
    """取客户端 IP（记录登录日志用）。"""
    return request.client.host if request.client else None
