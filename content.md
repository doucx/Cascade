好的，我们开始执行路线图的第一步。

这是一个基础性的重构，旨在统一概念，将 `SqliteConnector` 演进为更通用的 `LocalConnector`，为后续实现 UDS 事件流等功能奠定清晰的语义基础。

## [WIP] refactor: 将 sqlite 后端重构为统一的 local 后端

### 用户需求
执行“路线图：实现统一的 `local` 后端与实时 `watch` 功能”中的第一步，即“[概念统一] 重构与重命名”。这包括：
1.  将 `cascade-connector-sqlite` 包重命名为 `cascade-connector-local`。
2.  将 `SqliteConnector` 类重命名为 `LocalConnector`。
3.  在所有 CLI 工具中，将 `--backend sqlite` 标志更新为 `--backend local`。
4.  更新所有相关的配置和测试用例以反映这些变更。

### 评论
这是一个至关重要的第一步。通过在添加新功能前统一概念模型，我们确保了代码库和用户界面的清晰度和一致性。将关注点从具体的“SQLite”实现转移到更抽象的“本地、零依赖”后端角色，是架构演进的正确方向。

### 目标
1.  **目录与包重命名**: 将 `packages/cascade-connector-sqlite` 完整地重命名为 `packages/cascade-connector-local`。
2.  **配置更新**: 修改所有 `pyproject.toml` 文件，将对 `cascade-connector-sqlite` 的引用更新为 `cascade-connector-local`。
3.  **代码重构**: 在代码库中，将 `SqliteConnector` 类及其引用全部重构为 `LocalConnector`。
4.  **CLI 接口变更**: 在 `cs-controller` 和 `cs-observer` 中，将用户可见的后端选项从 `'sqlite'` 更改为 `'local'`。
5.  **测试同步**: 重命名并更新相关的测试文件，确保测试套件在重构后依然能够通过。

### 基本原理
此计划遵循路线图中的指导原则：将一个实体的稳定身份（本地、零依赖的连接器）与其当前实现（SQLite）解耦。通过在项目早期进行这种概念上的统一，可以降低未来扩展的复杂性，并为新功能的加入（如 UDS）提供一个清晰的语义入口。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/engine #comp/tests #concept/config #scope/dx #ai/instruct #task/domain/storage #task/object/local-backend #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重命名核心连接器包

首先，我们将 `sqlite` 连接器包的整个目录重命名为 `local`，以反映其新的角色。

~~~~~act
move_file
packages/cascade-connector-sqlite
packages/cascade-connector-local
~~~~~

#### Acts 2: 更新包元数据及工作区配置

重命名目录后，我们需要更新 `pyproject.toml` 文件以匹配新的包名和依赖关系。

首先，更新包自身的 `pyproject.toml`。

~~~~~act
patch_file
packages/cascade-connector-local/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "cascade-connector-sqlite"
version = "0.1.0"
description = "A zero-dependency SQLite connector for Cascade."
~~~~~
~~~~~toml
[project]
name = "cascade-connector-local"
version = "0.1.0"
description = "A zero-dependency local connector for Cascade (SQLite, UDS)."
~~~~~

然后，更新根 `pyproject.toml` 中的工作区引用。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
cascade-connector-sqlite = { workspace = true }
~~~~~
~~~~~toml
cascade-connector-local = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
    "packages/cascade-connector-sqlite",
~~~~~
~~~~~toml
    "packages/cascade-connector-local",
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
  "cascade-connector-sqlite",
~~~~~
~~~~~toml
  "cascade-connector-local",
~~~~~

#### Acts 3: 重构连接器模块和类

现在，我们在新的包内部重命名模块和类，从 `SqliteConnector` 迁移到 `LocalConnector`。

~~~~~act
move_file
packages/cascade-connector-local/src/cascade/connectors/sqlite
packages/cascade-connector-local/src/cascade/connectors/local
~~~~~

更新 `__init__.py` 文件以导出新的类名。

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-engine) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .connector import SqliteConnector

__all__ = ["SqliteConnector"]
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-engine) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .connector import LocalConnector

__all__ = ["LocalConnector"]
~~~~~

在 `connector.py` 中重命名主类和辅助类。

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python
class _SqliteSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "SqliteConnector", task: asyncio.Task):
        self._parent = parent
        self._task = task

    async def unsubscribe(self) -> None:
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        if self._task in self._parent._background_tasks:
            self._parent._background_tasks.remove(self._task)
        if not self._parent._use_polling:
            try:
                Path(self._parent.uds_path).unlink(missing_ok=True)
            except OSError:
                pass


class SqliteConnector(Connector):
    def __init__(
        self,
        db_path: str = "~/.cascade/control.db",
~~~~~
~~~~~python
class _LocalSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "LocalConnector", task: asyncio.Task):
        self._parent = parent
        self._task = task

    async def unsubscribe(self) -> None:
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        if self._task in self._parent._background_tasks:
            self._parent._background_tasks.remove(self._task)
        if not self._parent._use_polling:
            try:
                Path(self._parent.uds_path).unlink(missing_ok=True)
            except OSError:
                pass


class LocalConnector(Connector):
    def __init__(
        self,
        db_path: str = "~/.cascade/control.db",
~~~~~

#### Acts 4: 更新 `cs-controller` CLI

修改 `cs-controller` 以使用新的 `local` 后端标识和 `LocalConnector` 类。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
from cascade.connectors.mqtt import MqttConnector
from cascade.connectors.sqlite import SqliteConnector
from cascade.spec.protocols import Connector
~~~~~
~~~~~python
from cascade.connectors.mqtt import MqttConnector
from cascade.connectors.local import LocalConnector
from cascade.spec.protocols import Connector
~~~~~

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
def _get_connector(backend: str, hostname: str, port: int) -> Connector:
    if backend == "sqlite":
        return SqliteConnector()
    elif backend == "mqtt":
~~~~~
~~~~~python
def _get_connector(backend: str, hostname: str, port: int) -> Connector:
    if backend == "local":
        return LocalConnector()
    elif backend == "mqtt":
~~~~~

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'sqlite')."
    ),
~~~~~
~~~~~python
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'local')."
    ),
~~~~~

#### Acts 5: 更新 `cs-observer` CLI

对 `cs-observer` 执行相同的更新。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'sqlite')."
    ),
~~~~~
~~~~~python
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'local')."
    ),
~~~~~

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
async def _get_status(backend: str, hostname: str, port: int):
    """Core logic for the status command."""
    if backend == "sqlite":
        await _get_status_sqlite()
        return
~~~~~
~~~~~python
async def _get_status(backend: str, hostname: str, port: int):
    """Core logic for the status command."""
    if backend == "local":
        await _get_status_sqlite()
        return
~~~~~

#### Acts 6: 更新并重构测试用例

最后，我们重命名并更新相关的端到端测试，以确保它们与新的 `local` 后端保持一致。

~~~~~act
move_file
tests/cli/e2e/test_e2e_cli_sqlite_backend.py
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~
~~~~~python
from cascade.cli.controller.app import app as controller_app
from cascade.cli.observer.app import app as observer_app
from cascade.connectors.sqlite import SqliteConnector
~~~~~
~~~~~python
from cascade.cli.controller.app import app as controller_app
from cascade.cli.observer.app import app as observer_app
from cascade.connectors.local import LocalConnector
~~~~~

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~
~~~~~python
    # Patch 1: The default path in the SqliteConnector constructor, used by cs-controller
    # We patch the class itself to replace the default __init__ behavior.
    original_init = SqliteConnector.__init__

    def patched_init(self, db_path=str(db_path), **kwargs):
        # We force our test db_path, ignoring whatever might be passed.
        original_init(self, db_path=str(db_path), **kwargs)

    monkeypatch.setattr(
        "cascade.cli.controller.app.SqliteConnector",
        lambda *args, **kwargs: SqliteConnector(db_path=str(db_path)),
    )
~~~~~
~~~~~python
    # Patch 1: The default path in the LocalConnector constructor, used by cs-controller
    # We patch the class itself to replace the default __init__ behavior.
    original_init = LocalConnector.__init__

    def patched_init(self, db_path=str(db_path), **kwargs):
        # We force our test db_path, ignoring whatever might be passed.
        original_init(self, db_path=str(db_path), **kwargs)

    monkeypatch.setattr(
        "cascade.cli.controller.app.LocalConnector",
        lambda *args, **kwargs: LocalConnector(db_path=str(db_path)),
    )
~~~~~

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~
~~~~~python
def test_set_and_status_sqlite(isolated_db_path: Path):
~~~~~
~~~~~python
def test_set_and_status_local(isolated_db_path: Path):
~~~~~

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~
~~~~~python
    result_set = runner.invoke(
        controller_app,
        ["set-limit", "--scope", "global", "--rate", "10/s", "--backend", "sqlite"],
    )
    assert result_set.exit_code == 0
    assert isolated_db_path.exists()

    # 2. Check the status
    result_status = runner.invoke(observer_app, ["status", "--backend", "sqlite"])
~~~~~
~~~~~python
    result_set = runner.invoke(
        controller_app,
        ["set-limit", "--scope", "global", "--rate", "10/s", "--backend", "local"],
    )
    assert result_set.exit_code == 0
    assert isolated_db_path.exists()

    # 2. Check the status
    result_status = runner.invoke(observer_app, ["status", "--backend", "local"])
~~~~~

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~
~~~~~python
def test_resume_sqlite(isolated_db_path: Path):
~~~~~
~~~~~python
def test_resume_local(isolated_db_path: Path):
~~~~~

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~
~~~~~python
            "5",
            "--backend",
            "sqlite",
        ],
    )
    assert isolated_db_path.exists()

    # 2. Resume the scope
    result_resume = runner.invoke(
        controller_app, ["resume", "task:api", "--backend", "sqlite"]
    )
    assert result_resume.exit_code == 0

    # 3. Check the status and verify it's gone
    result_status = runner.invoke(observer_app, ["status", "--backend", "sqlite"])
~~~~~
~~~~~python
            "5",
            "--backend",
            "local",
        ],
    )
    assert isolated_db_path.exists()

    # 2. Resume the scope
    result_resume = runner.invoke(
        controller_app, ["resume", "task:api", "--backend", "local"]
    )
    assert result_resume.exit_code == 0

    # 3. Check the status and verify it's gone
    result_status = runner.invoke(observer_app, ["status", "--backend", "local"])
~~~~~

现在处理引擎的 E2E 测试。

~~~~~act
move_file
tests/engine/e2e/test_e2e_sqlite_connector.py
tests/engine/e2e/test_e2e_local_connector.py
~~~~~

~~~~~act
patch_file
tests/engine/e2e/test_e2e_local_connector.py
~~~~~
~~~~~python
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.connectors.sqlite.connector import SqliteConnector, POLL_INTERVAL
~~~~~
~~~~~python
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.connectors.local.connector import LocalConnector, POLL_INTERVAL
~~~~~

~~~~~act
patch_file
tests/engine/e2e/test_e2e_local_connector.py
~~~~~
~~~~~python
@pytest.fixture
def controller_connector(unique_paths):
    """Provides a connector instance to act as the 'controller' CLI."""
    db_path, uds_path = unique_paths
    return SqliteConnector(db_path=db_path, uds_path=uds_path)
~~~~~
~~~~~python
@pytest.fixture
def controller_connector(unique_paths):
    """Provides a connector instance to act as the 'controller' CLI."""
    db_path, uds_path = unique_paths
    return LocalConnector(db_path=db_path, uds_path=uds_path)
~~~~~

~~~~~act
patch_file
tests/engine/e2e/test_e2e_local_connector.py
~~~~~
~~~~~python
@pytest.fixture
def engine(unique_paths, bus_and_spy):
    """Provides a fully configured Engine using the SqliteConnector."""
    db_path, uds_path = unique_paths
    bus, _ = bus_and_spy
    connector = SqliteConnector(db_path=db_path, uds_path=uds_path)

    class TimedMockExecutor(LocalExecutor):
~~~~~
~~~~~python
@pytest.fixture
def engine(unique_paths, bus_and_spy):
    """Provides a fully configured Engine using the LocalConnector."""
    db_path, uds_path = unique_paths
    bus, _ = bus_and_spy
    connector = LocalConnector(db_path=db_path, uds_path=uds_path)

    class TimedMockExecutor(LocalExecutor):
~~~~~

### 下一步建议

我们已经成功完成了第一步的重构和重命名。现在整个代码库在概念上已经统一，`local` 成为了官方指定的零依赖后端标识。

根据路线图，下一步是 **步骤 2: [核心机制] 实现基于 UDS 的 Telemetry 事件服务器**。这将为 `Engine` 赋予广播实时事件的能力，是实现 `cs-observer watch --backend local` 功能的核心。如果你准备好了，我将开始制定实现 `UdsTelemetryServer` 的计划。
