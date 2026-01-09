## [WIP] fix: Update imports after migration

### 用户需求

修复因代码迁移导致的 `ImportError`、`ModuleNotFoundError` 和 `AttributeError`。具体包括：
1.  更新测试文件中的导入路径，使其指向 `cascade-execution-graph` 包中的新位置。
2.  确保新包的 `__init__.py` 文件正确导出了必要的类（如 `StaticGraphError`）。

### 评论

这是迁移工作后的标准清理步骤。由于我们将代码物理移动到了新的包结构中，所有引用旧路径的代码（主要是测试代码）都需要更新。此外，为了保持模块的封装性，我们需要在新的 `__init__.py` 文件中显式导出公共 API。

### 目标

1.  修复 `test_engine_control_flow.py`：从 `cascade.execution.graph.errors` 导入 `DependencyMissingError`。
2.  修复 `test_solver_csp.py`：更新 monkeypatch 的目标模块路径。
3.  更新 `cascade.execution.graph.model.__init__.py`：导出 `StaticGraphError`。
4.  修复 `test_static_integrity.py`：从正确的模块导入 `StaticGraphError`。

### 基本原理

通过显式更新测试中的导入路径，我们解耦了测试对旧 `runtime` 结构的依赖，验证了新包结构的正确性。在 `__init__.py` 中导出异常类是 Python 包开发的最佳实践，它简化了使用者的导入语句。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #comp/build #scope/core #ai/instruct #task/domain/runtime #task/object/imports #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_engine_control_flow.py`

更新导入路径，不再依赖 `cascade` 顶层包导出 `DependencyMissingError`，而是直接从其新家导入。

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~python.old
import pytest
import cascade as cs
from cascade.runtime import EventBus
from cascade.runtime.host.instance import Engine
from cascade.runtime.services.observability.events import TaskSkipped
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.test_utils.helpers import SpySubscriber
~~~~~
~~~~~python.new
import pytest
import cascade as cs
from cascade.runtime import EventBus
from cascade.runtime.host.instance import Engine
from cascade.runtime.services.observability.events import TaskSkipped
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.execution.graph.errors import DependencyMissingError
from cascade.test_utils.helpers import SpySubscriber
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~python.old
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
        await engine.run(flow)

    # Verify Skip Event using the new helper
~~~~~
~~~~~python.new
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(DependencyMissingError):
        await engine.run(flow)

    # Verify Skip Event using the new helper
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~python.old
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
        await engine.run(res_b)

    skip_events = spy.events_of_type(TaskSkipped)
~~~~~
~~~~~python.new
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(DependencyMissingError):
        await engine.run(res_b)

    skip_events = spy.events_of_type(TaskSkipped)
~~~~~

#### Acts 2: 修复 `test_solver_csp.py`

更新动态导入的路径以匹配新的包结构。

~~~~~act
patch_file
packages/cascade-runtime/tests/unit/test_solver_csp.py
~~~~~
~~~~~python.old
def test_csp_solver_missing_dependency(monkeypatch):
    import cascade.runtime.kernel.solvers.csp as csp_module

    # Simulate missing dependency by setting constraint to None
~~~~~
~~~~~python.new
def test_csp_solver_missing_dependency(monkeypatch):
    import cascade.execution.graph.solvers.csp as csp_module

    # Simulate missing dependency by setting constraint to None
~~~~~

#### Acts 3: 导出 `StaticGraphError`

在 `cascade-execution-graph` 的模型包中导出异常类，以便其他模块可以导入它。

~~~~~act
write_file
packages/cascade-execution-graph/src/cascade/execution/graph/model/__init__.py
~~~~~
~~~~~python
from .exceptions import StaticGraphError, CascadeGraphError

__all__ = ["StaticGraphError", "CascadeGraphError"]
~~~~~

#### Acts 4: 修复 `test_static_integrity.py`

更新导入语句以反映 `StaticGraphError` 的新位置（现在可以通过包导入了）。

~~~~~act
patch_file
packages/cascade-runtime/tests/legacy_graph/integration/test_static_integrity.py
~~~~~
~~~~~python.old
import pytest
import cascade as cs
from cascade.execution.graph.model import StaticGraphError
from cascade.runtime import Engine, EventBus
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver
~~~~~
~~~~~python.new
import pytest
import cascade as cs
from cascade.execution.graph.model.exceptions import StaticGraphError
from cascade.runtime import Engine, EventBus
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver
~~~~~

### 下一步建议

执行完这些修复后，请再次运行测试套件。如果一切顺利，这些测试应该能够通过。
之后，我们可以继续 Phase 3: Engine Decoupling，开始修改 `Engine` 以移除对图执行策略的硬编码依赖。
