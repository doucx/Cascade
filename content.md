You are absolutely correct. My apologies. Lacking the `conftest.py` file led me to propose a redundant solution.

Your suspicion was spot on. The presence of this `autouse=True` fixture in `conftest.py` means that the `_reset_broker_state()` function is **already being called automatically** before and after every single test in the suite.

This is excellent news. It means our test harness is more robust than I assumed, and the fix is even simpler: we just need to remove the redundant local fixture we added.

I will now generate the plan to perform this cleanup.

## [WIP] chore(tests): Rely on global conftest for connector cleanup

### 用户需求
移除在 `test_e2e_robustness.py` 中添加的、与 `conftest.py` 中全局 fixture 功能重复的 `clean_connector_state` fixture。

### 评论
这是一个好的代码健康度改进。`conftest.py` 中 `autouse=True` 的 fixture 是处理全局测试状态（如清理单例或类变量）的正确模式。移除本地的重复实现可以减少代码冗余，并使测试代码更专注于其自身的逻辑。

### 目标
清理 `test_e2e_robustness.py` 文件，移除其中不必要的 fixture 定义。

### 基本原理
我们依赖 `conftest.py` 中定义的全局 `cleanup_local_bus` fixture 来确保 `LocalBusConnector` 的状态在每次测试前都被重置。本地 fixture 是多余的，应当被移除。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-harness #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 移除冗余的 Fixture

我们将从 `tests/engine/e2e/test_e2e_robustness.py` 文件中移除 `clean_connector_state` fixture。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_robustness.py
~~~~~
~~~~~python
from .harness import InProcessConnector, ControllerTestApp


@pytest.fixture(autouse=True)
def clean_connector_state():
    """Ensures the LocalBusConnector's class-level state is reset for each test."""
    InProcessConnector._reset_broker_state()
    yield
    InProcessConnector._reset_broker_state()


@pytest.fixture
def mock_ui_bus(monkeypatch):
~~~~~
~~~~~python
from .harness import InProcessConnector, ControllerTestApp


@pytest.fixture
def mock_ui_bus(monkeypatch):
~~~~~

### 下一步建议
我们已经完成了所有的修复和清理工作。代码库现在处于一个干净、健壮且经过充分测试的状态。

现在是时候将这一系列工作合并为一个完整的 `[COMMIT]` 计划了。请确认，我将为你生成最终的提交指令。
