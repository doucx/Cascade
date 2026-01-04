好的，我明白了。上一轮的重构只修改了 `cascade-engine` 的核心 `src` 文件，导致所有依赖它的测试文件和其他包都出现了导入错误。

我将根据你提供的错误日志和文件内容，修复我当前权限范围内所有文件的导入问题。

**根本原因**:
*   **重命名**: `cascade.runtime.MessageBus` 已被重构为 `cascade.runtime.EventBus`。
*   **路径变更**: `cascade.runtime.bus` 模块已移动到 `cascade.runtime.event_bus`。
*   **API 变更**: `cascade.runtime` 的 `__init__.py` 不再导出 `MessageBus`，而是导出 `EventBus`。

**修复策略**:
1.  **修复直接依赖**: 我将修改所有在当前上下文（XML 文件列表）中直接导入旧 `MessageBus` 的测试文件，将导入路径和类名更新为 `EventBus`。
2.  **识别并报告间接依赖**: 部分测试的失败是由于它们依赖的其他**源文件**（如 `cascade.app` 或 `cascade.sdk`）尚未更新。根据协议，我无权修改当前上下文之外的文件。我将在计划的“下一步建议”中明确列出这些文件，以便我们可以在下一阶段修复它们。

以下是修复我当前权限范围内文件的计划。

## [WIP] fix(tests): 更新测试文件以使用重构后的 EventBus

### 错误分析

上一轮重构将 `cascade-engine` 内的 `MessageBus` 重命名为 `EventBus`，并移动了其源文件。测试套件的执行结果证实，这一变更导致了整个代码库中大范围的 `ModuleNotFoundError` 和 `ImportError`。

本次修复的目标是解决这些导入错误。然而，分析显示错误分为两类：
1.  **直接错误**: 测试文件本身直接导入了旧的 `MessageBus`。这些错误在我当前的权限范围内，可以被修复。
2.  **间接错误**: 测试文件导入了其他模块（如 `cascade.app` 或 `cascade.testing`），而这些模块内部又依赖于旧的 `MessageBus`。这些源文件不在我当前的操作上下文中，因此无法修改。

本计划将专注于修复第一类“直接错误”。

### 用户需求

修复因 `MessageBus` -> `EventBus` 重构而导致的测试失败。

### 评论

这是一个必要的跟进修复。通过修正测试文件，我们能逐步恢复测试套件的健康状态，并验证核心重构的正确性。明确指出无法修复的间接依赖，可以为下一步工作提供清晰的路线图。

### 目标

1.  在所有提供的测试文件中，将 `from cascade.runtime.bus import MessageBus` 或 `from cascade.runtime import MessageBus` 的导入语句更新为 `from cascade.runtime import EventBus`。
2.  在上述文件中，将所有 `MessageBus()` 的实例化操作更新为 `EventBus()`。

### 基本原理

通过一系列精确的 `patch_file` 操作，我们将逐一修正受影响的测试文件。优先使用 `from cascade.runtime import EventBus`，因为它更简洁，并依赖于 `runtime` 模块正确暴露的公共 API。对于无法修复的间接错误，我们将在“下一步建议”中进行详细说明，以保持工作流程的透明和连贯。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/architecture #task/object/message-bus #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `cascade-engine` 的测试配置

首先修复 `cascade-engine` 包自身的 `conftest.py`。

~~~~~act
patch_file
packages/cascade-engine/tests/conftest.py
~~~~~
~~~~~python.old
import pytest
from cascade.runtime.bus import MessageBus
from cascade.testing import SpySubscriber


@pytest.fixture
def bus_and_spy():
    bus = MessageBus()
    spy = SpySubscriber(bus)
    return bus, spy
~~~~~
~~~~~python.new
import pytest
from cascade.runtime import EventBus
from cascade.testing import SpySubscriber


@pytest.fixture
def bus_and_spy():
    bus = EventBus()
    spy = SpySubscriber(bus)
    return bus, spy
~~~~~

#### Acts 2: 修复 `cascade-graph` 的集成测试

接下来处理 `cascade-graph` 包的测试文件。

~~~~~act
patch_file
packages/cascade-graph/tests/integration/test_static_integrity.py
~~~~~
~~~~~python.old
import pytest
import cascade as cs
from cascade.graph import StaticGraphError
from cascade.runtime import Engine, MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~python.new
import pytest
import cascade as cs
from cascade.graph import StaticGraphError
from cascade.runtime import Engine, EventBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/integration/test_static_integrity.py
~~~~~
~~~~~python.old
    workflow = task_a_violating()

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # This test will FAIL initially because the LocalExecutor does not yet
~~~~~
~~~~~python.new
    workflow = task_a_violating()

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())

    # This test will FAIL initially because the LocalExecutor does not yet
~~~~~

#### Acts 3: 修复 `cascade-library` 的集成测试

处理 `cascade-library` 包中的多个测试文件。

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_helpers.py
~~~~~
~~~~~python.old
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~
~~~~~python.new
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime import EventBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_helpers.py
~~~~~
~~~~~python.old
    workflow = cs.dict(static_key="static", dynamic_key=get_val())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    assert result == {"static_key": "static", "dynamic_key": "dynamic_value"}
~~~~~
~~~~~python.new
    workflow = cs.dict(static_key="static", dynamic_key=get_val())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)

    assert result == {"static_key": "static", "dynamic_key": "dynamic_value"}
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_helpers.py
~~~~~
~~~~~python.old
    workflow = cs.format("Hello, {name}!", name=get_name())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    assert result == "Hello, World!"
~~~~~
~~~~~python.new
    workflow = cs.format("Hello, {name}!", name=get_name())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)

    assert result == "Hello, World!"
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_helpers.py
~~~~~
~~~~~python.old
    workflow = cs.format("Positional: {}, {}", get_first(), get_second())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    assert result == "Positional: first, second"
~~~~~
~~~~~python.new
    workflow = cs.format("Positional: {}, {}", get_first(), get_second())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)

    assert result == "Positional: first, second"
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_signal_provider.py
~~~~~
~~~~~python.old
import asyncio
import time
import pytest
import cascade as cs

from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~
~~~~~python.new
import asyncio
import time
import pytest
import cascade as cs

from cascade.runtime import Engine, EventBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_signal_provider.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine(local_connector):
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        connector=local_connector,
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine(local_connector):
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),
        connector=local_connector,
    )
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_time_provider.py
~~~~~
~~~~~python.old
import time
import pytest
import cascade as cs

from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~
~~~~~python.new
import time
import pytest
import cascade as cs

from cascade.runtime import Engine, EventBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_time_provider.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine():
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine():
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),
    )
~~~~~

#### Acts 4: 修复 `cascade-provider-ipfs` 的集成测试

最后，处理 `cascade-provider-ipfs` 包的测试文件。

~~~~~act
patch_file
packages/cascade-provider-ipfs/tests/integration/test_ipfs.py
~~~~~
~~~~~python.old
import pytest
import cascade as cs
from aiohttp import web
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~
~~~~~python.new
import pytest
import cascade as cs
from aiohttp import web
from cascade.runtime.engine import Engine
from cascade.runtime import EventBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~

~~~~~act
patch_file
packages/cascade-provider-ipfs/tests/integration/test_ipfs.py
~~~~~
~~~~~python.old
    workflow = cs.ipfs.cat(cid=TEST_CID, api_base_url=mock_ipfs_server)

    # Run the workflow
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    # Assert the result
~~~~~
~~~~~python.new
    workflow = cs.ipfs.cat(cid=TEST_CID, api_base_url=mock_ipfs_server)

    # Run the workflow
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)

    # Assert the result
~~~~~

~~~~~act
patch_file
packages/cascade-provider-ipfs/tests/integration/test_ipfs.py
~~~~~
~~~~~python.old
    workflow = cs.ipfs.add(path=str(test_file), api_base_url=mock_ipfs_server)

    # Run
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    # Assert we got the hash from the JSON response
~~~~~
~~~~~python.new
    workflow = cs.ipfs.add(path=str(test_file), api_base_url=mock_ipfs_server)

    # Run
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)

    # Assert we got the hash from the JSON response
~~~~~

### 下一步建议

我们已经修复了权限范围内的所有直接导入错误。然而，测试套件仍会因为间接依赖而失败。为了完全解决问题，下一步需要修改以下核心源文件，将它们对 `MessageBus` 的引用更新为 `EventBus`：

*   `packages/cascade-application/src/cascade/app/__init__.py`
*   `packages/cascade-sdk/src/cascade/testing.py`
*   `packages/cascade-sdk/src/cascade/sdk.py`
*   `packages/cascade-library/src/cascade/providers/subflow.py`

请在下一个指令中提供这些文件的上下文，以便我完成整个重构任务。
