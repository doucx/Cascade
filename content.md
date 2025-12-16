好的，继续进行收尾工作：公开新的异常类，并修改控制流测试以验证新的异常类型。

## [WIP] refactor(runtime/tests): 导入新异常并更新控制流测试断言

### 目标
1.  在 `src/cascade/runtime/__init__.py` 中公开 `DependencyMissingError`。
2.  更新 `tests/runtime/test_control_flow.py`，将所有因跳过导致的 `KeyError` 断言替换为 `DependencyMissingError` 断言。

### 基本原理
确保新的错误处理机制被集成测试正确覆盖。新的异常提供了更丰富的上下文，测试现在可以针对这些语义信息进行断言。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/tests #concept/exceptions #scope/core #ai/instruct #task/domain/runtime #task/object/exception-handling #task/action/integrate #task/state/continue

---

### Script

#### Acts 1: 在 `src/cascade/runtime/__init__.py` 中导入新异常

~~~~~act
write_file
src/cascade/runtime/__init__.py
~~~~~
~~~~~python
from .bus import MessageBus
from .engine import Engine
from .subscribers import HumanReadableLogSubscriber
from .events import Event
from .exceptions import DependencyMissingError
from .resource_manager import ResourceManager
from .protocols import ExecutionPlan, Solver, Executor, CachePolicy

__all__ = [
    "MessageBus",
    "Engine",
    "HumanReadableLogSubscriber",
    "Event",
    "DependencyMissingError",
    "ResourceManager",
    "ExecutionPlan",
    "Solver",
    "Executor",
    "CachePolicy",
]
~~~~~

#### Acts 2: 修复 `src/cascade/__init__.py` 中的导入

我们还需要在顶层的 `__init__.py` 中公开这个异常，以便用户可以直接通过 `cascade.DependencyMissingError` 访问它。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json
from .spec.constraint import with_constraints

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "visualize",
    "cli",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "override_resource",
]
~~~~~
~~~~~python
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json
from .spec.constraint import with_constraints
from .runtime.exceptions import DependencyMissingError

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "visualize",
    "cli",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "DependencyMissingError",
]
~~~~~

#### Acts 3: 更新 `tests/runtime/test_control_flow.py` 中的断言

将硬编码的 `KeyError` 断言替换为新的 `DependencyMissingError`。

~~~~~act
patch_file
tests/runtime/test_control_flow.py
~~~~~
~~~~~python
    flow = action().run_if(condition())

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(KeyError):
        await engine.run(flow)
~~~~~
~~~~~python
    flow = action().run_if(condition())

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
        await engine.run(flow)
~~~~~

~~~~~act
patch_file
tests/runtime/test_control_flow.py
~~~~~
~~~~~python
    res_a = step_a().run_if(condition())
    res_b = step_b(res_a)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(KeyError):
        await engine.run(res_b)
~~~~~
~~~~~python
    res_a = step_a().run_if(condition())
    res_b = step_b(res_a)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
        await engine.run(res_b)
~~~~~

### 下一步建议
我们现在应该运行完整的测试套件来验证所有架构、测试和异常的更改。如果测试通过，我们将生成一个最终的 `[COMMIT]` 计划。
