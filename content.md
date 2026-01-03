好的，已切换回 Quipu 模式。

根据我们的分析，我将生成一个计划，在项目根目录创建 `conftest.py` 文件，并实现支持后端切换的参数化 Fixture。

## [WIP] feat(test): 添加全局参数化夹具以支持多后端 Reactor 测试

### 用户需求
根据路线图“任务 3.1”，创建一个全局共享的、参数化的 Pytest Fixture，以便未来的测试可以针对不同的 Reactor 后端（Python/Rust）运行。

### 评论
这是为“双引擎共生”架构建立测试基石的关键一步。通过在根目录创建 `conftest.py`，我们建立了一个统一的测试基础设施入口。这个参数化的 `reactor_backend_factory` 夹具将使我们能够用同一套测试来验证 Python 和未来 Rust 实现的行为一致性，完美践行了“一套测试，双重验证”的核心目标。

### 目标
1.  在项目根目录 `/home/doucx/Documents/Projects/Cascade/` 创建一个新的 `conftest.py` 文件。
2.  实现 `pytest_addoption` 钩子，添加一个 `--reactor-backend` 命令行选项，默认为 `python`。
3.  创建一个 `reactor_backend_factory` 会话级 Fixture。
4.  该 Fixture 将根据命令行选项返回 `cascade.vm.reactor.Reactor` 类。
5.  当请求 `rust` 后端时，该 Fixture 将使用 `pytest.skip` 跳过测试，因为 Rust 实现尚不可用。

### 基本原理
将 `conftest.py` 放置在项目根目录，可以确保 Pytest 在运行时能发现它，并将其中的 Fixture 应用于 `packages/` 目录下的所有测试文件。这是一种标准的、符合 Pytest 惯例的共享测试基础设施的方式。使用 `scope="session"` 可以确保 Fixture 在整个测试会话中只被创建一次，提高了效率。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/parameterized-fixture #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建全局共享的 conftest.py

我们将在项目根目录创建 `conftest.py`，并定义命令行选项和参数化的 Fixture。

~~~~~act
write_file
conftest.py
~~~~~
~~~~~python
import pytest
from typing import Callable, Type
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
        # When the Rust implementation is ready, it will be imported and returned here.
        # For now, we skip any tests that request it.
        pytest.skip(
            "Rust reactor backend is not yet implemented. Skipping test."
        )
    else:
        pytest.fail(
            f"Invalid reactor backend specified: '{backend}'. "
            "Choose from 'python' or 'rust'."
        )

~~~~~

### 下一步建议

我们已经成功地创建了全局共享的测试 Fixture。为了验证它是否按预期工作，并为后续的测试提供一个参考示例，我建议修改一个现有的测试用例来使用这个新的 `reactor_backend_factory`。

`packages/cascade-vm/tests/unit/test_reactor.py` 中的 `test_event_driven_ping_pong` 测试是一个很好的候选者，因为它使用了 `EventDrivenRunner`，而我们之前已经重构了 `EventDrivenRunner` 来接受一个 `reactor_factory`。

我将生成一个计划来应用这个修改。
