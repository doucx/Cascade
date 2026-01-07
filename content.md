好的，我将审查所有 `conftest.py` 文件，识别 DRY 违规，并根据 `Monorepo Testing Architecture Specification` 原则将共享的 Fixture 整合到根目录的 `conftest.py` 中。

审查发现，`bus_and_spy` Fixture 在 `packages/cascade-runtime/tests/conftest.py` 和 `tests/e2e/runtime/conftest.py` 中被重复定义，这是一个明显的 DRY 违规。此外，位于 E2E 测试中的 `cleanup_local_bus` Fixture 对于确保所有测试的隔离性至关重要，将其提升为全局 Fixture 可以使整个项目受益。

`cascade-connector-mqtt` 中的 `conftest.py` 是高度特化的，用于 Mock `aiomqtt` 库，它只对该包有意义，因此保留在原位是正确的。

我将生成一个计划来执行这项重构。

## [WIP] refactor: 集中化共享 pytest Fixture 以消除 DRY 违规

### 用户需求

审查项目中的 `conftest.py` 文件，找出因重复定义 Fixture 导致的 DRY（Don't Repeat Yourself）违规，并将这些共享的 Fixture 整合到项目根目录的 `conftest.py` 文件中。

### 评论

这是一个非常重要的架构改进。通过将跨包共享的 Fixture（如 `bus_and_spy`）和全局性的辅助 Fixture（如 `cleanup_local_bus`）集中到根 `conftest.py`，我们严格遵循了 `Monorepo Testing Architecture` 规范。这不仅消除了代码冗余，还提高了可维护性，并确保了测试环境的一致性和稳定性。

### 目标

1.  将 `bus_and_spy` Fixture 的定义统一移动到根 `conftest.py` 文件中。
2.  将用于状态清理的 `cleanup_local_bus` Fixture 提升到根 `conftest.py`，并设为 `autouse`，以确保在所有测试会话中自动应用。
3.  删除 `packages/cascade-runtime/tests/conftest.py` 和 `tests/e2e/runtime/conftest.py` 这两个因 Fixture 移出而变为空或冗余的文件。
4.  保留 `packages/cascade-connector-mqtt/tests/unit/conftest.py`，因为它包含的是特定于包的 Mock 逻辑，不属于共享范畴。

### 基本原理

根据 `Monorepo Testing Architecture` 规范，根 `conftest.py` 是整个项目的“全局 Fixture 注册中心”。所有跨包共享的、通用的测试基础设施都应在此处定义。

-   `bus_and_spy` Fixture 提供了 `EventBus` 和 `SpySubscriber`，这是多个包（如 `cascade-runtime` 和 E2E 测试）进行事件相关测试时都会用到的核心工具，因此是典型的共享 Fixture。
-   `cleanup_local_bus` Fixture 用于在测试之间重置内存消息代理的状态，这对于防止 E2E 测试中的状态泄漏至关重要。将其提升为全局自动应用的 Fixture，可以从根本上解决测试隔离性问题，增强测试套件的健壮性。

通过此重构，我们将使测试架构更清晰、更符合 DRY 原则。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/fixtures #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 整合共享 Fixture 到根 `conftest.py`

我们将 `bus_and_spy` 和 `cleanup_local_bus` 添加到根 `conftest.py` 文件中，并包含所有必需的导入。

~~~~~act
patch_file
conftest.py
~~~~~
~~~~~python.old
import pytest
from typing import Type
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol


def pytest_addoption(parser):
    """Adds a command-line option to select the reactor backend."""
    parser.addoption(
        "--reactor-backend",
        action="store",
        default="python",
        help="Select reactor backend to test: python or rust",
    )


@pytest.fixture(scope="session")
def reactor_backend_factory(
    request,
) -> Type[ReactorProtocol]:
    """
    A session-scoped fixture that provides the Reactor class
    based on the --reactor-backend command-line option.
    """
    backend = request.config.getoption("--reactor-backend")

    if backend == "python":
        # Return the Python implementation
        return Reactor
    elif backend == "rust":
        # Import the high-performance Rust implementation
        from cascade_vm_rs import RustReactor

        return RustReactor
    else:
        pytest.fail(
            f"Invalid reactor backend specified: '{backend}'. "
            "Choose from 'python' or 'rust'."
        )
~~~~~
~~~~~python.new
import pytest
from typing import Type
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol

# Imports for new global fixtures
from cascade.runtime import EventBus
from cascade.test_utils.helpers import SpySubscriber

# Attempt to import LocalBusConnector for global cleanup
try:
    from cascade.connectors.local.bus import LocalBusConnector
except ImportError:
    LocalBusConnector = None


def pytest_addoption(parser):
    """Adds a command-line option to select the reactor backend."""
    parser.addoption(
        "--reactor-backend",
        action="store",
        default="python",
        help="Select reactor backend to test: python or rust",
    )


@pytest.fixture(scope="session")
def reactor_backend_factory(
    request,
) -> Type[ReactorProtocol]:
    """
    A session-scoped fixture that provides the Reactor class
    based on the --reactor-backend command-line option.
    """
    backend = request.config.getoption("--reactor-backend")

    if backend == "python":
        # Return the Python implementation
        return Reactor
    elif backend == "rust":
        # Import the high-performance Rust implementation
        from cascade_vm_rs import RustReactor

        return RustReactor
    else:
        pytest.fail(
            f"Invalid reactor backend specified: '{backend}'. "
            "Choose from 'python' or 'rust'."
        )


@pytest.fixture(autouse=True)
def cleanup_local_bus():
    """
    Ensures that the memory broker state is completely cleared between tests.
    This prevents state leakage (retained messages/subscriptions) which
    causes unpredictable failures in E2E tests.
    """
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
    yield
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()


@pytest.fixture
def bus_and_spy():
    """Provides a runtime EventBus instance and an attached SpySubscriber."""
    bus = EventBus()
    spy = SpySubscriber(bus)
    return bus, spy
~~~~~

#### Acts 2: 删除冗余的 `conftest.py` 文件

现在共享 Fixture 已被移至根目录，原来的 `conftest.py` 文件变得多余，应当被删除以保持整洁。

删除 `cascade-runtime` 包中的 `conftest.py`。

~~~~~act
delete_file
packages/cascade-runtime/tests/conftest.py
~~~~~

删除 E2E 测试目录中的 `conftest.py`。

~~~~~act
delete_file
tests/e2e/runtime/conftest.py
~~~~~

### 下一步建议

重构完成后，强烈建议完整运行一次测试套件，以确保：
1.  所有测试都能正确发现并使用位于根 `conftest.py` 中的全局 Fixture。
2.  `cleanup_local_bus` Fixture 的自动应用没有引入任何副作用。
3.  整个测试流程依然稳定可靠。

你可以通过运行 `pytest` 命令来验证这一点。
