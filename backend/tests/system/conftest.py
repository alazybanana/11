"""system 模块测试夹具。

本机没有 MySQL，这里用 **SQLite 内存库**覆盖 `get_db` 依赖，
在不改动任何业务代码的前提下跑通完整链路（含登录鉴权与操作日志）。

覆盖方式说明：`app.dependency_overrides[get_db]` 按函数对象替换，
`router.py` / `deps.py` 导入的是同一个 `get_db` 对象，因此替换对所有接口生效。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.system import models  # noqa: F401  确保模型注册到 Base.metadata

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


@pytest.fixture()
def session_factory() -> Iterator[Any]:
    """为每个用例创建独立的内存 SQLite 库，并预置一个超级管理员账号。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )

    with factory() as seed:
        seed.add(
            models.User(
                username=ADMIN_USERNAME,
                password_hash=hash_password(ADMIN_PASSWORD),
                real_name="超级管理员",
                is_superuser=True,
                is_enabled=True,
            )
        )
        seed.commit()

    yield factory

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(session_factory: Any) -> Iterator[TestClient]:
    """把所有请求的数据库会话指向内存 SQLite 的 TestClient。"""

    def _override_get_db() -> Iterator[Session]:
        db: Session = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    """用预置的超级管理员登录，返回可直接用于请求的鉴权头。"""
    response = client.post(
        "/api/v1/system/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    body = response.json()
    assert body["code"] == 0, body
    return {"Authorization": f"Bearer {body['data']['access_token']}"}
