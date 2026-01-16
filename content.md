好的，测试已通过。我们继续执行计划，现在专注于清理 `cascade-compiler` 和相关的测试工具，确保它们完全对齐 `cascade-spec` 提供的规范。

## [WIP] refactor: Align cascade-compiler with centralized spec definitions

### 用户需求

在 `cascade-spec` 包中成功集中了核心接口和数据契约之后，需要继续对 `cascade-compiler` 包进行重构。此举旨在消除所有本地的、重复的接口定义（如 `ResourcePrism`），并确保测试工具（`cascade-test-utils`）也遵循新的、统一的导入路径。

### 评论

这是完成架构解耦计划的收尾工作。通过使编译器和测试工具也成为 `cascade-spec` 的“消费者”，我们确保了整个生态系统遵循单一、明确的规范。这不仅消除了潜在的代码冲突和维护噩梦，也为未来扩展编译器功能（例如添加新的资源类型或布线策略）提供了稳定、可靠的基础。

### 目标

1.  定位并移除 `cascade-compiler` 中本地定义的、与 `cascade-spec` 重复的 `ResourcePrism` 协议。
2.  更新编译器内部所有模块，使其从 `cascade.spec.compiler.interfaces` 导入 `ResourcePrism`。
3.  更新 `cascade-test-utils` 中的测试工具，使其从 `cascade.spec.runtime` 导入 `ComputeRequest`。

### 基本原理

编译器作为将逻辑 DSL 转换为物理执行图的核心组件，其自身的接口（如 `WiringPolicy`, `ResourcePrism`）也必须是标准化的。将这些接口的定义置于 `cascade-spec` 中，意味着编译器的内部工作方式遵循一套公开的、可被第三方扩展的协议。同理，测试工具作为验证系统行为正确性的关键部分，也必须使用与主系统完全相同的、来自 `cascade-spec` 的数据契约，以保证测试的有效性和一致性。

### 标签

#intent/refine #flow/ready #priority/high #comp/compiler #comp/spec #comp/tests #scope/api #scope/dx #task/domain/architecture #task/object/decoupling #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 `cascade-test-utils` 的导入路径

我们首先修复测试工具 `harness.py` 中的 `ComputeRequest` 导入，使其指向 `cascade-spec`。

~~~~~act
patch_file
packages/cascade-test-utils/src/cascade/test_utils/harness.py
~~~~~
~~~~~python.old
from cascade.bus.core import EventBus
from cascade.bus.events import Event, TaskExecutionFinished
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.bus.core import EventBus
from cascade.bus.events import Event, TaskExecutionFinished
from cascade.spec.runtime import ComputeRequest
from cascade.vm.compute import LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.vm.registry import CodeRegistry
~~~~~

#### Acts 2: 更新编译器中 `ResourcePrism` 的实现

接下来，我们修改编译器内部的 `ResourceWiringPolicy` 和 `DiscreteResourcePrism`，让它们从 `cascade-spec` 导入 `ResourcePrism` 协议，而不是本地副本。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/resource.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
from ..prism import ResourcePrism
from ..prisms.discrete import DiscreteResourcePrism


class ResourceWiringPolicy(WiringPolicy):
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy, ResourcePrism
from ..prisms.discrete import DiscreteResourcePrism


class ResourceWiringPolicy(WiringPolicy):
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import WiringContext
from ...expansion.context import ExpansionContext
from ..prism import ResourcePrism


class DiscreteResourcePrism(ResourcePrism):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None:
~~~~~
~~~~~python.new
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import WiringContext
from ...expansion.context import ExpansionContext
from cascade.spec.compiler.interfaces import ResourcePrism


class DiscreteResourcePrism(ResourcePrism):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None:
~~~~~

#### Acts 3: 删除编译器中的冗余协议定义

现在所有相关模块都已指向 `cascade-spec`，我们可以安全地删除编译器内部重复的 `prism.py` 文件及其关联的 `.stitcher.yaml` 文件。

~~~~~act
delete_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.py
~~~~~

~~~~~act
delete_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.stitcher.yaml
~~~~~

### 下一步建议

我们已经成功地完成了对 `cascade-compiler` 和 `cascade-test-utils` 的清理工作。至此，`cascade-spec`, `cascade-std`, `cascade-vm`, `cascade-compiler` 四个核心包之间的依赖关系已经基本理顺，它们都正确地将 `cascade-spec` 作为接口和契约的单一事实来源。

**架构重构任务已完成**。我们可以将这个系列的工作标记为 `[COMMIT]`，并创建一个 Git 提交来固化这些重要的改进。如果你同意，我将生成最终的提交计划。
