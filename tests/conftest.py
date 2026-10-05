import inspect
from collections.abc import AsyncIterator, Iterator

import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient

from backend.app import app
from backend.hub.routes import REGISTRY_DIR_ENV_VAR
from backend.hub.usage import DB_ENV_VAR
from backend.security import API_KEY_ENV_VAR
from tests.hub.fixtures import make_registry

TEST_API_KEY = "test-api-key"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply the `anyio` marker to every async test.

    Avoids having to declare `pytestmark = pytest.mark.anyio` in every test module.
    """
    for item in items:
        if inspect.iscoroutinefunction(getattr(item, "function", None)):
            item.add_marker("anyio")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure anyio to use asyncio, else `pytestmark = pytest.mark.anyio` does not work."""
    return "asyncio"


@pytest.fixture(scope="session")
async def client(
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[AsyncTestClient[Litestar]]:
    """Fixture for creating an async test client.

    The app refuses to start without an API key, so one is set before the lifespan
    runs. The catalog registry is pointed at a small fixture tree for the same reason:
    the real one is data under edit, and a test must not depend on it. The context
    manager restores the environment afterwards. The usage counters go to a
    temporary file too, else a test run would leave rows in the working tree.
    """
    root = tmp_path_factory.mktemp("hub")
    registry_root = make_registry(root / "registry")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv(API_KEY_ENV_VAR, TEST_API_KEY)
        monkeypatch.setenv(REGISTRY_DIR_ENV_VAR, str(registry_root))
        monkeypatch.setenv(DB_ENV_VAR, str(root / "usage.db"))
        app.debug = True
        async with AsyncTestClient(app=app) as _client:
            yield _client


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Configure a known API key for the duration of a test."""
    monkeypatch.setenv(API_KEY_ENV_VAR, TEST_API_KEY)
    yield TEST_API_KEY
