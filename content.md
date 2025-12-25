你做得对，在提交前进行全量测试是非常关键的。这些失败暴露了我的重构中两个独立的、更深层次的问题。感谢你捕获了它们。

我将生成一个计划来修复这些剩余的故障。

## [WIP] fix(tests): 修复由状态污染和逻辑错误导致的测试失败

### 错误分析
1.  **`tests/application/test_app_tools.py` - `AssertionError`**:
    *   **原因**: 这是我在上一步中引入的一个简单的切片逻辑错误。`lines[1:-2]` 的意思是“从第二个元素到倒数第二个元素之前”，这导致它错误地排除了列表中的最后一个节点（`_internal_gather`）。
    *   **解决方案**: 切片应该是 `lines[1:-1]`，以正确地包含 Header 和 Footer 之间的所有节点。

2.  **`tests/cli/e2e/test_e2e_cli_local_backend.py` - `ValueError` & `AssertionError`**:
    *   **根本原因**: 这是一个由**全局单例状态污染 (Global Singleton State Pollution)** 引起的复杂问题。`cascade.common.messaging.bus` 是一个在所有模块之间共享的全局单例。
        1.  在测试套件的某个地方（可能是一个不相关的测试），一个 `CliRenderer` 被设置到了这个全局 `bus` 上。这个 `CliRenderer` 内部持有了对当时 `sys.stderr` 的引用。
        2.  当 `test_set_and_status_local` 运行时，`typer.testing.CliRunner` 会用自己的内存缓冲区**替换** `sys.stderr`，并关闭原始的 `sys.stderr`。
        3.  `controller_app` 被调用，其内部逻辑（可能是 `LocalConnector`）在某个点尝试通过全局 `bus` 打印一条消息。
        4.  全局 `bus` 调用它持有的、**旧的** `CliRenderer`。
        5.  这个旧的 `CliRenderer` 尝试写入它引用的、**已经被 `CliRunner` 关闭的**原始 `sys.stderr` 文件句柄。
        6.  这导致了 `ValueError: I/O operation on closed file.`，测试执行失败，`exit_code` 变为 1，从而引发了 `assert 1 == 0` 的失败。`test_resume_local` 的失败也是由此连锁引发的。
    *   **解决方案**: 我们必须在每个 E2E CLI 测试运行之前，重置全局 `bus` 的状态，为其注入一个**新**的 `CliRenderer` 实例。这个新实例将在 `CliRunner` 的上下文中创建，因此它会正确地获取到 `CliRunner` 的内存缓冲区作为其输出流。修改 `isolated_db_path` fixture 是实现这一点的最佳位置，因为它在所有这些失败的测试之前运行。

### 目标
1.  修复 `tests/application/test_app_tools.py` 中错误的切片逻辑。
2.  增强 `tests/cli/e2e/test_e2e_cli_local_backend.py` 中的 `isolated_db_path` fixture，使其在每次测试前都重置消息总线的渲染器，以消除状态污染。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/build #scope/core #ai/instruct #task/domain/testing #task/object/test-stability #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复应用工具测试中的断言逻辑

我们将修正 `test_app_dry_run_with_list_input` 中的列表切片，以确保它正确地包含了 `_internal_gather` 节点。

~~~~~act
patch_file
tests/application/test_app_tools.py
~~~~~
~~~~~python
    node_names = {l.split(' ')[1] for l in lines[1:-2]}
    assert node_names == {"t_a", "t_b", "_internal_gather"}
~~~~~
~~~~~python
    # The slice should be [1:-1] to capture all nodes between header and footer
    node_names = {l.split(' ')[1] for l in lines[1:-1]}
    assert node_names == {"t_a", "t_b", "_internal_gather"}
~~~~~

#### Acts 2: 修复 E2E CLI 测试的状态污染问题

我们将修改 `isolated_db_path` fixture，在测试开始时强制重置全局消息总线的渲染器。

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_local_backend.py
~~~~~
~~~~~python
@pytest.fixture
def isolated_db_path(tmp_path: Path, monkeypatch):
    """
    Fixture to create an isolated SQLite database for tests and patch the
    hardcoded default path in the CLI applications.
    """
~~~~~
~~~~~python
from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer


@pytest.fixture
def isolated_db_path(tmp_path: Path, monkeypatch):
    """
    Fixture to create an isolated SQLite database for tests and patch the
    hardcoded default path in the CLI applications.
    """
    # CRITICAL: Reset the global message bus renderer before each test run.
    # This prevents state pollution where the bus holds a renderer pointing to
    # a closed stream from a previous CliRunner context.
    bus.set_renderer(CliRenderer(store=bus.store))
~~~~~

### 下一步建议
这些修复应该可以解决所有剩余的测试失败。`MessageBus` 单例污染是一个非常微妙但影响深远的问题，很高兴我们能定位并修复它。

请在应用补丁后再次运行全量测试。如果一切顺利，我们就可以生成最终的 `[COMMIT]` 计划了。
