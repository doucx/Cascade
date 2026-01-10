好的，我们来为这个新功能创建健壮的单元测试。

我将生成一个计划，该计划会创建一个新的测试文件，并使用 `pytest` 的 `monkeypatch` 和参数化功能来全面验证 `Engine` 的策略选择逻辑。

## [WIP] test: 为 Engine 的策略选择逻辑添加单元测试

### 错误分析
无错误，此为新功能的测试实现。

### 用户需求
为 `Engine` 根据 `CASCADE_BACKEND` 环境变量选择默认执行策略的功能创建单元测试。

### 评论
为配置驱动的行为（如通过环境变量切换功能）编写单元测试至关重要。这可以确保：
1.  **功能正确性**：我们验证了代码确实按预期响应环境变量。
2.  **防止回归**：未来的代码变更不会意外地破坏这个切换机制。
3.  **文档化**：测试本身就是关于该功能如何工作的清晰文档。

### 目标
1.  创建新的目录结构 `packages/cascade-runtime/tests/unit/host/`。
2.  在上述目录中创建一个新的测试文件 `test_engine_init.py`。
3.  实现一个参数化的测试，覆盖 `CASCADE_BACKEND` 环境变量的所有相关情况（`vm`, `graph`, 未设置, 其他值）。
4.  实现一个测试，验证当 `strategy` 被显式传入 `Engine` 时，它会覆盖环境变量的设置。

### 基本原理
我们将使用 `pytest` 的核心功能来编写简洁而强大的测试：
-   **`monkeypatch` Fixture**: 这是在测试期间安全地修改（和自动恢复）环境变量的标准方法。我们将用它来模拟 `os.getenv` 的不同返回值。
-   **`@pytest.mark.parametrize`**: 这个装饰器让我们能用同一套测试逻辑来运行多个不同的输入和预期输出组合，从而有效地测试所有分支，同时保持代码的 DRY (Don't Repeat Yourself)。
-   **`unittest.mock.MagicMock`**: 我们将使用 `MagicMock` 来创建 `Engine` 所需的依赖项（`solver`, `executor`, `bus`），确保我们的测试是轻量级的单元测试，只关注 `Engine` 的初始化逻辑，而不依赖于这些组件的实际实现。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/runtime #concept/config #scope/dx #ai/instruct #task/domain/testing #task/object/engine-strategy #task/action/test #task/state/continue

---

### Script

#### Acts 1: 创建测试目录

首先，我们使用 `mkdir -p` 来确保测试文件所需的目录结构存在。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-runtime/tests/unit/host/
~~~~~

#### Acts 2: 编写测试文件

现在，我们创建 `test_engine_init.py` 文件。它将包含两个核心测试：一个用于验证基于环境变量的策略选择，另一个用于验证显式策略的优先级。

~~~~~act
write_file
packages/cascade-runtime/tests/unit/host/test_engine_init.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock

from cascade.runtime.host.instance import Engine
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.execution.graph.strategy import GraphExecutionStrategy


# Fixtures for Engine dependencies
@pytest.fixture
def mock_solver():
    return MagicMock()


@pytest.fixture
def mock_executor():
    return MagicMock()


@pytest.fixture
def mock_bus():
    return MagicMock()


@pytest.mark.parametrize(
    "backend_env, expected_strategy_type",
    [
        ("vm", VMExecutionStrategy),
        ("VM", VMExecutionStrategy),  # Test case-insensitivity
        ("graph", GraphExecutionStrategy),
        ("GRAPH", GraphExecutionStrategy),
        ("other", GraphExecutionStrategy),  # Test fallback for unknown values
        (None, GraphExecutionStrategy),  # Test unset env var defaults to graph
    ],
)
def test_engine_selects_strategy_from_env(
    monkeypatch,
    mock_solver,
    mock_executor,
    mock_bus,
    backend_env,
    expected_strategy_type,
):
    """
    Tests that the Engine correctly selects the default execution strategy
    based on the CASCADE_BACKEND environment variable.
    """

    if backend_env is None:
        monkeypatch.delenv("CASCADE_BACKEND", raising=False)
    else:
        monkeypatch.setenv("CASCADE_BACKEND", backend_env)

    # We pass strategy=None to trigger the default selection logic
    engine = Engine(
        solver=mock_solver,
        executor=mock_executor,
        bus=mock_bus,
        strategy=None,
    )

    assert isinstance(engine.strategy, expected_strategy_type)


def test_engine_uses_explicit_strategy_over_env(
    monkeypatch, mock_solver, mock_executor, mock_bus
):
    """
    Tests that an explicitly provided strategy always takes precedence
    over the environment variable.
    """
    # Set env to a value that would normally select GraphExecutionStrategy
    monkeypatch.setenv("CASCADE_BACKEND", "graph")

    # But explicitly provide the VM strategy
    explicit_strategy = VMExecutionStrategy(executor=mock_executor, bus=mock_bus)

    engine = Engine(
        solver=mock_solver,
        executor=mock_executor,
        bus=mock_bus,
        strategy=explicit_strategy,
    )

    assert engine.strategy is explicit_strategy
    assert isinstance(engine.strategy, VMExecutionStrategy)
~~~~~

### 下一步建议

测试已经创建完毕。现在请运行 `pytest packages/cascade-runtime/tests/unit/host/test_engine_init.py` 来验证我们刚刚实现的 `CASCADE_BACKEND` 功能是正确且健壮的。

如果测试通过，我们可以将这个任务标记为完成，并生成一个 `[COMMIT]` 计划来提交这些变更。
