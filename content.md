You are absolutely correct. My previous refactoring, while architecturally sound, failed to update the test suite, causing these failures. Thank you for providing the test summary; it allows me to precisely correct the issue.

The errors confirm that our change to enforce dependency injection in the `Engine` was successful. Now, we must bring the tests into alignment with this new, stricter contract.

## [WIP] fix(tests): 更新测试用例以适应 Engine 的依赖注入构造器

### 错误分析
我之前对 `cascade.runtime.Engine` 的 `__init__` 方法进行了重构，移除了其内部对 `NativeSolver`, `LocalExecutor` 和 `MessageBus` 的默认实例化，强制调用者必须提供这些依赖。

这个改动导致了测试失败，因为许多现有的测试用例仍然使用旧的、无参数的 `Engine()` 或只提供部分参数的 `Engine(bus=...)` 方式来实例化引擎，这违反了新的构造函数签名，从而引发 `TypeError`。

### 用户需求
修复因 `Engine` 构造器变更而导致的所有测试失败。

### 评论
这是重构过程中一个常见且健康的步骤：核心组件的改进必然要求其客户端（包括测试用例）进行适配。通过修复这些测试，我们不仅能让测试套件重新变绿，更重要的是，我们确保了测试代码本身也遵循了新的、更清晰的依赖注入模式，提高了测试的明确性和可维护性。

### 目标
1.  修改 `tests/providers/test_sql.py`，为 `db_engine` fixture 中的 `Engine` 实例化提供默认的 `solver`, `executor`, 和 `bus`。
2.  修改 `tests/integration/test_end_to_end.py`，为 `Engine` 的实例化补充 `solver` 和 `executor` 参数。
3.  修改 `tests/integration/test_resource_scheduling.py` 中的所有 `Engine` 实例化，为其提供所有必需的依赖。

### 基本原理
我将逐一修改所有失败的测试文件。对于每个文件，我将在顶部添加必要的 `import` 语句来引入 `NativeSolver`, `LocalExecutor`, 和 `MessageBus`。然后，我将定位到每一个 `Engine(...)` 的调用点，并使用这些导入的默认组件来填充新的、必需的 `solver`, `executor`, 和 `bus` 参数。这将使测试代码与 `Engine` 的新接口保持一致，从而解决 `TypeError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_sql.py` 中的 `Engine` 实例化

我将首先修复 `db_engine` fixture，为其提供所有必需的组件。

~~~~~act
patch_file
tests/providers/test_sql.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from sqlalchemy import create_engine
~~~~~
~~~~~python
import pytest
import cascade as cs
from sqlalchemy import create_engine

from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~

~~~~~act
patch_file
tests/providers/test_sql.py
~~~~~
~~~~~python
@pytest.fixture(scope="module")
def db_engine():
    """Provides a Cascade Engine with the sqlite_db resource pre-registered."""
    engine = cs.Engine()
    engine.register(sqlite_db)
    return engine
~~~~~
~~~~~python
@pytest.fixture(scope="module")
def db_engine():
    """Provides a Cascade Engine with the sqlite_db resource pre-registered."""
    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    engine.register(sqlite_db)
    return engine
~~~~~

#### Acts 2: 修复 `test_end_to_end.py` 中的 `Engine` 实例化

接下来，我将修复端到端测试，为 `Engine` 补充 `solver` 和 `executor`。

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.engine import Engine
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python
    # We use the event_bus for engine events, which is internal.
    # The subscriber will translate these to calls on the mocked messaging_bus.
    event_bus = cs.runtime.MessageBus()
    cs.runtime.HumanReadableLogSubscriber(event_bus)
    engine = Engine(bus=event_bus)

    result = asyncio.run(engine.run(final_greeting))
~~~~~
~~~~~python
    # We use the event_bus for engine events, which is internal.
    # The subscriber will translate these to calls on the mocked messaging_bus.
    event_bus = cs.runtime.MessageBus()
    cs.runtime.HumanReadableLogSubscriber(event_bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=event_bus)

    result = asyncio.run(engine.run(final_greeting))
~~~~~

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python
    event_bus = cs.runtime.MessageBus()
    cs.runtime.HumanReadableLogSubscriber(event_bus)
    engine = Engine(bus=event_bus)

    with pytest.raises(ValueError, match="Something went wrong"):
~~~~~
~~~~~python
    event_bus = cs.runtime.MessageBus()
    cs.runtime.HumanReadableLogSubscriber(event_bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=event_bus)

    with pytest.raises(ValueError, match="Something went wrong"):
~~~~~

#### Acts 3: 修复 `test_resource_scheduling.py` 中的 `Engine` 实例化

最后，我将修复资源调度测试中的所有 `Engine` 调用。

~~~~~act
patch_file
tests/integration/test_resource_scheduling.py
~~~~~
~~~~~python
import pytest
import asyncio
import time
import cascade as cs
from cascade.runtime.engine import Engine
~~~~~
~~~~~python
import pytest
import asyncio
import time
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~

~~~~~act
patch_file
tests/integration/test_resource_scheduling.py
~~~~~
~~~~~python
    start_time = time.time()

    # Run with limited capacity: only 1 slot available
    # Because both tasks need 1 slot, they must run one after another.
    # FIX: Use Engine directly to avoid nested event loop error in tests
    engine = Engine(system_resources={"slots": 1})
    result = await engine.run(workflow)

    duration = time.time() - start_time
~~~~~
~~~~~python
    start_time = time.time()

    # Run with limited capacity: only 1 slot available
    # Because both tasks need 1 slot, they must run one after another.
    # FIX: Use Engine directly to avoid nested event loop error in tests
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        system_resources={"slots": 1},
    )
    result = await engine.run(workflow)

    duration = time.time() - start_time
~~~~~

~~~~~act
patch_file
tests/integration/test_resource_scheduling.py
~~~~~
~~~~~python
    job = cpu_heavy_task().with_constraints(cpu=needs)

    # We set system capacity to 4.
    engine = Engine(system_resources={"cpu": 4})
    result = await engine.run(job)

    assert result == "Done"
~~~~~
~~~~~python
    job = cpu_heavy_task().with_constraints(cpu=needs)

    # We set system capacity to 4.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        system_resources={"cpu": 4},
    )
    result = await engine.run(job)

    assert result == "Done"
~~~~~

~~~~~act
patch_file
tests/integration/test_resource_scheduling.py
~~~~~
~~~~~python
    job = massive_job().with_constraints(memory_gb=64)

    # System only has 16GB
    engine = Engine(system_resources={"memory_gb": 16})

    with pytest.raises(ValueError, match="exceeds total system capacity"):
        await engine.run(job)
~~~~~
~~~~~python
    job = massive_job().with_constraints(memory_gb=64)

    # System only has 16GB
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        system_resources={"memory_gb": 16},
    )

    with pytest.raises(ValueError, match="exceeds total system capacity"):
        await engine.run(job)
~~~~~

### 下一步建议
这些修复应该能让测试套件重新通过。一旦确认，我们就可以继续进行**阶段二**的下一步：重构 `Engine.run` 的核心编排逻辑，将特定于本地执行的细节剥离并下沉到 `LocalExecutor` 中。
