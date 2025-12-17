Of course. My apologies for the oversight. The test failures clearly indicate I did not apply the required changes comprehensively across the entire test suite. I will now correct all remaining failures in a single, systematic pass.

## [WIP] fix(tests): Update entire test suite for Engine DI constructor

### 错误分析
The previous refactoring of `cascade.runtime.Engine` enforced a strict dependency injection pattern for its constructor, requiring `solver`, `executor`, and `bus` instances to be provided upon initialization. My last fix was incomplete, leaving numerous test files that still used the old `Engine()` instantiation method. This resulted in 33 `TypeError` failures across the test suite, as reported.

### 用户需求
Fix all 33 failing tests by updating their `Engine` instantiation calls to conform to the new constructor signature.

### 评论
This is the final and necessary cleanup step to stabilize the codebase after the architectural refactoring of the `Engine`. Completing this will ensure our test suite is not only passing but also adheres to the improved design principles we've introduced, making future tests clearer and more maintainable.

### 目标
Systematically patch all failing test files to provide the required `solver`, `executor`, and `bus` arguments when creating an `Engine` instance, thereby resolving all `TypeError` exceptions and making the test suite pass.

### 基本原理
I will execute a series of `patch_file` operations guided by the test failure summary. For each failing file, I will first ensure the necessary `NativeSolver`, `LocalExecutor`, and `MessageBus` classes are imported. Then, I will replace every outdated `Engine()` or `Engine(bus=...)` call with the correct, fully-formed constructor: `Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=...)`. This methodical approach will cover all failing cases and bring the entire test suite into alignment with the refactored `Engine`.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Fix Provider Tests (`test_config.py`, `test_file.py`, `test_http.py`, `test_sql.py`)

I'll start with the provider tests, which all follow a similar pattern.

~~~~~act
patch_file
tests/providers/test_config.py
~~~~~
~~~~~python
import pytest
import cascade as cs
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~act
patch_file
tests/providers/test_config.py
~~~~~
~~~~~python
    loaded_data = cs.load_yaml(dummy_config_file)

    engine = cs.Engine()
    result = await engine.run(loaded_data)

    assert isinstance(result, dict)
~~~~~
~~~~~python
    loaded_data = cs.load_yaml(dummy_config_file)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(loaded_data)

    assert isinstance(result, dict)
~~~~~
~~~~~act
patch_file
tests/providers/test_config.py
~~~~~
~~~~~python
    # 2. Explicitly look up the value
    version = cs.lookup(source=config_source, key="project.version")

    engine = cs.Engine()
    result = await engine.run(version)

    assert result == "1.0.0"
~~~~~
~~~~~python
    # 2. Explicitly look up the value
    version = cs.lookup(source=config_source, key="project.version")

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(version)

    assert result == "1.0.0"
~~~~~
~~~~~act
patch_file
tests/providers/test_config.py
~~~~~
~~~~~python
    source = provide_dict()
    value = cs.lookup(source=source, key="a.b")

    engine = cs.Engine()
    result = await engine.run(value)
    assert result == 10
~~~~~
~~~~~python
    source = provide_dict()
    value = cs.lookup(source=source, key="a.b")

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(value)
    assert result == 10
~~~~~
~~~~~act
patch_file
tests/providers/test_config.py
~~~~~
~~~~~python
    source = provide_dict()
    # "b" does not exist in the root dict, should raise KeyError
    missing_value = cs.lookup(source=source, key="b")

    engine = cs.Engine()
    with pytest.raises(KeyError):
        await engine.run(missing_value)
~~~~~
~~~~~python
    source = provide_dict()
    # "b" does not exist in the root dict, should raise KeyError
    missing_value = cs.lookup(source=source, key="b")

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    with pytest.raises(KeyError):
        await engine.run(missing_value)
~~~~~
~~~~~act
patch_file
tests/providers/test_config.py
~~~~~
~~~~~python
    # Attempting to look up "nonexistent" on it should raise TypeError.
    invalid_lookup = cs.lookup(source=source, key="a.nonexistent")

    engine = cs.Engine()
    with pytest.raises(TypeError, match="Cannot access segment"):
        await engine.run(invalid_lookup)
~~~~~
~~~~~python
    # Attempting to look up "nonexistent" on it should raise TypeError.
    invalid_lookup = cs.lookup(source=source, key="a.nonexistent")

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    with pytest.raises(TypeError, match="Cannot access segment"):
        await engine.run(invalid_lookup)
~~~~~
~~~~~act
patch_file
tests/providers/test_file.py
~~~~~
~~~~~python
import pytest
import cascade as cs
import json
~~~~~
~~~~~python
import pytest
import cascade as cs
import json
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~act
patch_file
tests/providers/test_file.py
~~~~~
~~~~~python
    # cs.file returns the factory, read_text() returns the LazyResult
    read_result = cs.file(dummy_file).read_text()

    engine = cs.Engine()
    result = await engine.run(read_result)

    assert "status" in result
~~~~~
~~~~~python
    # cs.file returns the factory, read_text() returns the LazyResult
    read_result = cs.file(dummy_file).read_text()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert "status" in result
~~~~~
~~~~~act
patch_file
tests/providers/test_file.py
~~~~~
~~~~~python
    read_result = cs.file(binary_file).read_bytes()

    engine = cs.Engine()
    result = await engine.run(read_result)

    assert result == b"\x01\x02\x03\x04"
~~~~~
~~~~~python
    read_result = cs.file(binary_file).read_bytes()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert result == b"\x01\x02\x03\x04"
~~~~~
~~~~~act
patch_file
tests/providers/test_file.py
~~~~~
~~~~~python
    exist_result = cs.file(dummy_file).exists()

    engine = cs.Engine()
    result = await engine.run(exist_result)

    assert result is True
~~~~~
~~~~~python
    exist_result = cs.file(dummy_file).exists()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(exist_result)

    assert result is True
~~~~~
~~~~~act
patch_file
tests/providers/test_file.py
~~~~~
~~~~~python
    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.file(path).exists()

    engine = cs.Engine()
    result = await engine.run(exist_result)

    assert result is False
~~~~~
~~~~~python
    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.file(path).exists()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(exist_result)

    assert result is False
~~~~~
~~~~~act
patch_file
tests/providers/test_file.py
~~~~~
~~~~~python
    json_result = cs.file(dummy_file).json()

    engine = cs.Engine()
    result = await engine.run(json_result)

    assert isinstance(result, dict)
~~~~~
~~~~~python
    json_result = cs.file(dummy_file).json()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(json_result)

    assert isinstance(result, dict)
~~~~~
~~~~~act
patch_file
tests/providers/test_file.py
~~~~~
~~~~~python
    # cs.file receives the LazyResult path
    read_result = cs.file(path_result).read_text()

    engine = cs.Engine()
    result = await engine.run(read_result)

    assert result == "dynamic content"
~~~~~
~~~~~python
    # cs.file receives the LazyResult path
    read_result = cs.file(path_result).read_text()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert result == "dynamic content"
~~~~~
~~~~~act
patch_file
tests/providers/test_http.py
~~~~~
~~~~~python
import pytest
import cascade as cs
import aiohttp
~~~~~
~~~~~python
import pytest
import cascade as cs
import aiohttp
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~act
patch_file
tests/providers/test_http.py
~~~~~
~~~~~python
    # 3. Run and Assert
    # Since we are already in an async test loop, we use the Engine directly
    # instead of cs.run() which tries to create a new loop via asyncio.run()
    engine = cs.Engine()
    result = await engine.run(final_result)
    assert result == "cascade"
~~~~~
~~~~~python
    # 3. Run and Assert
    # Since we are already in an async test loop, we use the Engine directly
    # instead of cs.run() which tries to create a new loop via asyncio.run()
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(final_result)
    assert result == "cascade"
~~~~~
~~~~~act
patch_file
tests/providers/test_http.py
~~~~~
~~~~~python
    final_status = get_status(api_response)

    # 3. Run and Assert
    engine = cs.Engine()
    result = await engine.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
~~~~~
~~~~~python
    final_status = get_status(api_response)

    # 3. Run and Assert
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
~~~~~
~~~~~act
patch_file
tests/providers/test_sql.py
~~~~~
~~~~~python
    target = cs.sql("SELECT 1", db="non_existent_db")

    engine = cs.Engine()
    # We don't register anything

    # Should fail during execution when trying to resolve the Inject object
~~~~~
~~~~~python
    target = cs.sql("SELECT 1", db="non_existent_db")

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    # We don't register anything

    # Should fail during execution when trying to resolve the Inject object
~~~~~

#### Acts 2: Fix Runtime Tests (`test_control_flow.py`, `test_input_execution.py`, `test_map.py`, `test_retry.py`, `test_router_pruning.py`)

These tests often already have a `MessageBus`, so I just need to add the `solver` and `executor`.

~~~~~act
patch_file
tests/runtime/test_control_flow.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~act
patch_file
tests/runtime/test_control_flow.py
~~~~~
~~~~~python
    flow = action().run_if(condition())

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(flow)
    assert result == "executed"
~~~~~
~~~~~python
    flow = action().run_if(condition())

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(flow)
    assert result == "executed"
~~~~~
~~~~~act
patch_file
tests/runtime/test_control_flow.py
~~~~~
~~~~~python
    flow = action().run_if(condition())

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
~~~~~
~~~~~python
    flow = action().run_if(condition())

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
~~~~~
~~~~~act
patch_file
tests/runtime/test_control_flow.py
~~~~~
~~~~~python
    res_b = step_b(res_a)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
~~~~~
~~~~~python
    res_b = step_b(res_a)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
~~~~~
~~~~~act
patch_file
tests/runtime/test_input_execution.py
~~~~~
~~~~~python
import pytest
import cascade as cs
# 注意：在实现阶段需要确保这些模块存在
# from cascade.context import get_current_context
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
# 注意：在实现阶段需要确保这些模块存在
# from cascade.context import get_current_context
~~~~~
~~~~~act
patch_file
tests/runtime/test_input_execution.py
~~~~~
~~~~~python
        
    workflow = double(p)
    
    engine = cs.Engine()
    
    # 执行，传入 params
    # 这里的关键是 Engine 需要将 {"count": 10} 传递给 _get_param_value 任务
~~~~~
~~~~~python
        
    workflow = double(p)
    
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    
    # 执行，传入 params
    # 这里的关键是 Engine 需要将 {"count": 10} 传递给 _get_param_value 任务
~~~~~
~~~~~act
patch_file
tests/runtime/test_input_execution.py
~~~~~
~~~~~python
    monkeypatch.setenv("TEST_VAR", "cascade_value")
    
    e = cs.Env("TEST_VAR")
    
    engine = cs.Engine()
    result = await engine.run(e)
    
    assert result == "cascade_value"
~~~~~
~~~~~python
    monkeypatch.setenv("TEST_VAR", "cascade_value")
    
    e = cs.Env("TEST_VAR")
    
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(e)
    
    assert result == "cascade_value"
~~~~~
~~~~~act
patch_file
tests/runtime/test_map.py
~~~~~
~~~~~python
import pytest
import cascade as cs
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~act
patch_file
tests/runtime/test_map.py
~~~~~
~~~~~python
    # 2. Reduce the results -> 12
    total = sum_all(numbers=mapped_results)

    engine = cs.Engine()
    result = await engine.run(total)
    assert result == 12
~~~~~
~~~~~python
    # 2. Reduce the results -> 12
    total = sum_all(numbers=mapped_results)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(total)
    assert result == 12
~~~~~
~~~~~act
patch_file
tests/runtime/test_map.py
~~~~~
~~~~~python
    mapped_results = double.map(x=inputs)
    total = sum_all(numbers=mapped_results)

    engine = cs.Engine()
    result = await engine.run(total)
    assert result == 0
~~~~~
~~~~~python
    mapped_results = double.map(x=inputs)
    total = sum_all(numbers=mapped_results)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(total)
    assert result == 0
~~~~~
~~~~~act
patch_file
tests/runtime/test_map.py
~~~~~
~~~~~python
    # 3. Sum -> 12
    total = sum_all(numbers=doubled)

    engine = cs.Engine()
    result = await engine.run(total)
    assert result == 12
~~~~~
~~~~~python
    # 3. Sum -> 12
    total = sum_all(numbers=doubled)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(total)
    assert result == 12
~~~~~
~~~~~act
patch_file
tests/runtime/test_map.py
~~~~~
~~~~~python
    # Should produce [11, 22, 33]
    mapped = add.map(a=list_a, b=list_b)
    total = sum_all(numbers=mapped)

    engine = cs.Engine()
    result = await engine.run(total)
    assert result == 66
~~~~~
~~~~~python
    # Should produce [11, 22, 33]
    mapped = add.map(a=list_a, b=list_b)
    total = sum_all(numbers=mapped)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(total)
    assert result == 66
~~~~~
~~~~~act
patch_file
tests/runtime/test_map.py
~~~~~
~~~~~python
    list_b = [10, 20, 30]  # Mismatched

    mapped = add.map(a=list_a, b=list_b)

    engine = cs.Engine()
    with pytest.raises(ValueError, match="mismatched lengths"):
        await engine.run(mapped)
~~~~~
~~~~~python
    list_b = [10, 20, 30]  # Mismatched

    mapped = add.map(a=list_a, b=list_b)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    with pytest.raises(ValueError, match="mismatched lengths"):
        await engine.run(mapped)
~~~~~
~~~~~act
patch_file
tests/runtime/test_retry.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event, TaskRetrying, TaskExecutionFinished
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event, TaskRetrying, TaskExecutionFinished
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~act
patch_file
tests/runtime/test_retry.py
~~~~~
~~~~~python
    task_with_retry = flaky_task().with_retry(max_attempts=3, delay=0.01)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(task_with_retry)
~~~~~
~~~~~python
    task_with_retry = flaky_task().with_retry(max_attempts=3, delay=0.01)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(task_with_retry)
~~~~~
~~~~~act
patch_file
tests/runtime/test_retry.py
~~~~~
~~~~~python
    task_with_retry = always_fail().with_retry(max_attempts=2, delay=0.01)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(ValueError, match="Always fail"):
        await engine.run(task_with_retry)
~~~~~
~~~~~python
    task_with_retry = always_fail().with_retry(max_attempts=2, delay=0.01)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    with pytest.raises(ValueError, match="Always fail"):
        await engine.run(task_with_retry)
~~~~~
~~~~~act
patch_file
tests/runtime/test_router_pruning.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~act
patch_file
tests/runtime/test_router_pruning.py
~~~~~
~~~~~python
    workflow = consumer(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(workflow)
    assert result == "A"
~~~~~
~~~~~python
    workflow = consumer(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(workflow)
    assert result == "A"
~~~~~
~~~~~act
patch_file
tests/runtime/test_router_pruning.py
~~~~~
~~~~~python
    workflow = consumer(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(workflow)
    assert result == "A(SHARED)"
~~~~~
~~~~~python
    workflow = consumer(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(workflow)
    assert result == "A(SHARED)"
~~~~~

#### Acts 3: Fix Spec and Tools Tests (`test_resource.py`, `test_preview.py`)

Finally, I'll fix the remaining spec and tools tests.

~~~~~act
patch_file
tests/spec/test_resource.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.events import ResourceAcquired, ResourceReleased, Event
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.events import ResourceAcquired, ResourceReleased, Event
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~act
patch_file
tests/spec/test_resource.py
~~~~~
~~~~~python
def test_di_end_to_end():
    """Tests the full lifecycle: registration, injection, execution, teardown."""
    import asyncio

    engine = cs.Engine()
    engine.register(config)
    engine.register(db_connection)
~~~~~
~~~~~python
def test_di_end_to_end():
    """Tests the full lifecycle: registration, injection, execution, teardown."""
    import asyncio

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    engine.register(config)
    engine.register(db_connection)
~~~~~
~~~~~act
patch_file
tests/spec/test_resource.py
~~~~~
~~~~~python
    events = []
    bus = cs.MessageBus()
    bus.subscribe(Event, events.append)

    engine = cs.Engine(bus=bus)
    engine.register(config)
    engine.register(db_connection)
~~~~~
~~~~~python
    events = []
    bus = cs.MessageBus()
    bus.subscribe(Event, events.append)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    engine.register(config)
    engine.register(db_connection)
~~~~~
~~~~~act
patch_file
tests/spec/test_resource.py
~~~~~
~~~~~python
        print("TEARDOWN: mock_db_connection")

    engine = cs.Engine()
    engine.register(config)
    engine.register(db_connection)  # Register the original
~~~~~
~~~~~python
        print("TEARDOWN: mock_db_connection")

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    engine.register(config)
    engine.register(db_connection)  # Register the original
~~~~~
~~~~~act
patch_file
tests/tools/test_preview.py
~~~~~
~~~~~python
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.tools.preview import _analyze_plan, DryRunConsoleSubscriber
from cascade.tools.events import (
    PlanNodeInspected,
~~~~~
~~~~~python
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.tools.preview import _analyze_plan, DryRunConsoleSubscriber
from cascade.tools.events import (
    PlanNodeInspected,
~~~~~

### 下一步建议
这次的修复是全面性的，应该能够解决所有报告的 `TypeError`。在确认测试通过后，我们将完全准备好继续**阶段二**的下一个核心任务：重构 `Engine.run` 的内部逻辑，并将执行细节下沉到 `LocalExecutor` 中。
