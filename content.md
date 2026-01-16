我已经识别出 `cascade-sdk` 包中的循环依赖点。主要矛盾集中在 `cascade.sdk` 模块与 `cascade.tools.cli` 模块之间：`sdk` 模块在 `TYPE_CHECKING` 或延迟加载映射中引用了 `cli`，而 `cli` 模块的 `main` 函数又反向引用了 `sdk.run`。

通过将这些内部引用改为相对导入，我们可以确保 Python 解释器在加载子模块时不会反复触发父包的初始化逻辑。

## [WIP] refactor: 消除 cascade-sdk 包内的循环依赖，优化内部导入路径

### 用户需求
修复 `cascade-sdk` 包内 `sdk.py`、`tools/__init__.py` 和 `tools/cli.py` 之间的强耦合问题，将绝对导入改为相对导入。

### 评论
在 SDK 这种作为用户主要入口的包中，循环依赖不仅会导致初始化性能下降，还可能在某些复杂的环境下（如动态导入 provider）引发难以调试的 `AttributeError`。通过相对导入解耦是提升 SDK 健壮性的标准做法。

### 目标
1. 修复 `cascade.sdk` 模块中对同级模块（如 `control_flow`）和子包（如 `tools`）的绝对引用。
2. 修复 `cascade.tools.cli` 中对父级 `sdk` 模块的反向绝对引用。
3. 确保 `TYPE_CHECKING` 块中的类型定义不会在静态分析时触发不必要的包重载。

### 基本原理
相对导入（`.`, `..`）允许模块在不离开当前命名空间层级的情况下定位邻居。这在 `cascade-sdk` 这种具有扁平结构的包中非常有效，因为它避免了导入器重新去全局 `sys.path` 中搜索并重新评估 `cascade` 命名空间。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/sdk #task/object/sdk-package #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `cascade.sdk` 的内部引用

我们将 `sdk.py` 中 `TYPE_CHECKING` 块内指向本包其他模块的导入改为相对导入。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
if TYPE_CHECKING:
    from cascade.spec.dsl.task import task
    from cascade.spec.dsl.fluent import LazyResult
    from cascade.spec.dsl.routing import Router
    from cascade.spec.dsl.jump import Jump
    from cascade.spec.dsl.resources import resource, inject
    from cascade.spec.dsl.constraint import with_constraints
    from cascade.common.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.host.instance import Engine
    from cascade.bus.core import EventBus
    from cascade.bus.events import Event
    from cascade.execution.graph.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.execution.graph.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.runtime.interfaces import Connector, StateBackend

    from cascade.execution.graph.model.serialize import to_json, from_json
    from cascade.test_utils.helpers import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli

    # Dynamic Providers Stubs (for static analysis)
~~~~~
~~~~~python.new
if TYPE_CHECKING:
    from cascade.spec.dsl.task import task
    from cascade.spec.dsl.fluent import LazyResult
    from cascade.spec.dsl.routing import Router
    from cascade.spec.dsl.jump import Jump
    from cascade.spec.dsl.resources import resource, inject
    from cascade.spec.dsl.constraint import with_constraints
    from cascade.common.context import get_current_context

    from .control_flow import select_jump, bind

    from cascade.runtime.host.instance import Engine
    from cascade.bus.core import EventBus
    from cascade.bus.events import Event
    from cascade.execution.graph.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.execution.graph.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.runtime.interfaces import Connector, StateBackend

    from cascade.execution.graph.model.serialize import to_json, from_json
    from cascade.test_utils.helpers import override_resource, ControllerTestApp
    from .tools.cli import create_cli

    # Dynamic Providers Stubs (for static analysis)
~~~~~

#### Acts 2: 修复 `cascade.tools.cli` 的反向引用

这是循环依赖的核心触发点，我们将 `main` 函数中的绝对导入改为相对导入。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/cli.py
~~~~~
~~~~~python.old
    params: dict[str, ParamSpec] = {
        spec.name: spec for spec in all_specs if isinstance(spec, ParamSpec)
    }

    def main(**kwargs):
        from cascade.sdk import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")
~~~~~
~~~~~python.new
    params: dict[str, ParamSpec] = {
        spec.name: spec for spec in all_specs if isinstance(spec, ParamSpec)
    }

    def main(**kwargs):
        from ..sdk import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")
~~~~~

### 下一步建议
1. **运行 SDK 集成测试**: 运行 `packages/cascade-sdk/tests/integration/test_cli.py`。该测试会模拟 `create_cli` 的生成过程，如果循环依赖修复成功，测试应能正常启动而不会抛出 `ImportError`。
2. **清理 Runtime 耦合**: 准备修复 `cascade-runtime` 及其相关模块（8个文件）的耦合问题，那是报告中剩下的最后一个大项。
3. **验证类型提示**: 确保在 IDE（如 VS Code/Pyright）中，`cs.create_cli` 和 `cs.run` 的类型提示依然能正确跳转到定义位置。
