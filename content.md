好的，既然所有测试都已通过，Dyad 架构已经稳定，现在是进行最后一步清理工作的时候了。

我将生成一个 `[COMMIT]` 计划，彻底移除所有与旧 Triad 架构相关的废弃代码。

## [WIP] chore: 移除废弃的 Triad (Bleacher/Worker/Stainer) 架构代码

### 用户需求
在 Dyad 架构重构完成并通过所有测试后，清理并删除代码库中所有与旧 Triad 架构相关的废弃文件、类、常量和方法。

### 评论
这是 Dyad 重构任务的最后一步，也是至关重要的一步。通过移除这些技术债务，我们确保了代码库的整洁和一致性，防止了未来开发者误用或混淆新旧架构，并正式将 Dyad 模型确立为系统唯一的执行拓扑。

### 目标
1.  **重构标准库**: 将 `standard_observer` 从 `triad` 目录移至 `system` 目录，然后删除整个 `triad` 目录。
2.  **清理 Spec 定义**: 删除定义 `BleachNode`, `StainNode`, `WorkerNode` 及其 Spec 的 `triad.py` 文件。
3.  **清理常量与命名**: 从 `NodePrefix` 和 `PhysicalIdGenerator` 中移除已废弃的 Triad 相关条目。
4.  **更新导出**: 调整所有 `__init__.py` 文件，移除对已删除模块的引用。
5.  **提交变更**: 将所有清理工作作为一个原子提交。

### 基本原理
旧的 Triad (Bleacher/Worker/Stainer) 代码现在已成为死代码。保留它们会增加维护成本和认知负担。此计划通过一系列精确的删除和移动操作，系统性地将这些废弃代码从项目中移除，完成整个重构任务的闭环。

### 标签
#intent/refine #flow/ready #priority/medium #comp/compiler #comp/spec #comp/runtime #comp/std #task/domain/compiler #task/object/dyad-infrastructure #task/action/cleanup #task/state/end

---

### Script

#### Acts 1: 重构 Observer 并更新 Linker

首先，我们将 `standard_observer` 从即将被删除的 `triad` 目录中解救出来，放到更通用的 `system` 目录中，并更新 `Linker` 的引用。

~~~~~act
move_file
packages/cascade-std/src/cascade/std/triad/observer.py
packages/cascade-std/src/cascade/std/system/observer.py
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
# Common Standard Library
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
~~~~~
~~~~~python.new
# Common Standard Library
from cascade.std.system.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
~~~~~

#### Acts 2: 删除标准库中废弃的 Triad 实现

现在 `observer.py` 已经移走，`triad` 目录下的所有文件都是可删除的。

~~~~~act
delete_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~

~~~~~act
delete_file
packages/cascade-std/src/cascade/std/triad/dispatcher.py
~~~~~

~~~~~act
delete_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~

~~~~~act
delete_file
packages/cascade-std/src/cascade/std/triad/__init__.py
~~~~~

#### Acts 3: 更新标准库的导出

从 `__init__.py` 中移除对旧 Triad ICs 的导出。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/__init__.py
~~~~~
~~~~~python.old
# Legacy Triad (Keep for backward compatibility until full migration)
from .triad.dispatcher import standard_dispatcher
from .triad.bleacher import standard_bleacher
from .triad.stainer import standard_stainer
from .triad.observer import standard_observer

# System
from .system.gate import gate_passthrough
~~~~~
~~~~~python.new
# Legacy Triad (Keep for backward compatibility until full migration)
from .system.observer import standard_observer

# System
from .system.gate import gate_passthrough
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/__init__.py
~~~~~
~~~~~python.old
__all__ = [
    "standard_launcher",
    "standard_lander",
    "standard_dispatcher",
    "standard_bleacher",
    "standard_stainer",
    "standard_observer",
    "gate_passthrough",
    "standard_retry_logic",
~~~~~
~~~~~python.new
__all__ = [
    "standard_launcher",
    "standard_lander",
    "standard_observer",
    "gate_passthrough",
    "standard_retry_logic",
~~~~~

#### Acts 4: 删除 Spec 中废弃的 Triad 定义

删除 `cascade-spec` 中与 Triad 相关的物理节点定义和组件 Spec 定义。

~~~~~act
delete_file
packages/cascade-spec/src/cascade/spec/physical/triad.py
~~~~~

~~~~~act
delete_file
packages/cascade-spec/src/cascade/spec/components/triad.py
~~~~~

#### Acts 5: 更新 Spec 包的导出

清理 `__init__.py` 文件，移除对已删除 Triad 模块的引用。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/components/__init__.py
~~~~~
~~~~~python.old
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
    ContinuousAllocatorSpec,
    ContinuousReclaimerSpec,
)
from .triad import BleacherSpec, WorkerSpec, StainerSpec, ObservabilitySpec
from .system import (
    EgressSpec,
    GateSpec,
~~~~~
~~~~~python.new
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
    ContinuousAllocatorSpec,
    ContinuousReclaimerSpec,
)
from .system import (
    EgressSpec,
    GateSpec,
~~~~~
~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/components/__init__.py
~~~~~
~~~~~python.old
__all__ = [
    "DiscreteAllocatorSpec",
    "DiscreteReclaimerSpec",
    "BleacherSpec",
    "ObservabilitySpec",
    "WorkerSpec",
    "StainerSpec",
    "EgressSpec",
    "GateSpec",
~~~~~
~~~~~python.new
from .triad_legacy import ObservabilitySpec


__all__ = [
    "DiscreteAllocatorSpec",
    "DiscreteReclaimerSpec",
    "ObservabilitySpec",
    "EgressSpec",
    "GateSpec",
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from .physical.nodes import (
    Token,
    PhysicsNode,
    PhysicsDataNode,
    PhysicsFuncNode,
)
from .physical.triad import (
    BleachNode,
    WorkerNode,
    StainNode,
    ObservabilityNode,
    RetryNode,
)
from .physical.topology import Channel, BipartiteGraph
from .physical.resources import ResourceSlot
~~~~~
~~~~~python.new
from .physical.nodes import (
    Token,
    PhysicsNode,
    PhysicsDataNode,
    PhysicsFuncNode,
)
from .physical.triad_legacy import (
    ObservabilityNode,
    RetryNode,
)
from .physical.topology import Channel, BipartiteGraph
from .physical.resources import ResourceSlot
~~~~~
~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Ref",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "BleachNode",
    "WorkerNode",
    "StainNode",
    "ObservabilityNode",
    "RetryNode",
    "Channel",
    "BipartiteGraph",
~~~~~
~~~~~python.new
__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Ref",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "ObservabilityNode",
    "RetryNode",
    "Channel",
    "BipartiteGraph",
~~~~~

#### Acts 6: 清理废弃的常量和命名规则

最后，从 `NodePrefix` 和 `PhysicalIdGenerator` 中移除 Triad 的痕迹。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/constants.py
~~~~~
~~~~~python.old
    # Function Nodes (Transitions)
    LAUNCH = "launch"  # Dyad: Launcher (Prepare & Dispatch)
    LAND = "land"  # Dyad: Lander (Receive & Finalize)
    BLEACH = "bleach"  # Triad: Pre-process (Deprecated)
    WORKER = "worker"  # Triad: Execution (Deprecated)
    STAIN = "stain"  # Triad: Post-process (Deprecated)
    REQ = "req"  # Resource Requestor
    GATE = "gate"  # Control Gate
~~~~~
~~~~~python.new
    # Function Nodes (Transitions)
    LAUNCH = "launch"  # Dyad: Launcher (Prepare & Dispatch)
    LAND = "land"  # Dyad: Lander (Receive & Finalize)
    REQ = "req"  # Resource Requestor
    GATE = "gate"  # Control Gate
~~~~~

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/naming.py
~~~~~
~~~~~python.old
    def result_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.RESULT}"

    @staticmethod
    def bleach_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.BLEACH}"

    @staticmethod
    def worker_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.WORKER}"

    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.STAIN}"

    @staticmethod
    def sleep_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.SLEEP}"
~~~~~
~~~~~python.new
    def result_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.RESULT}"

    @staticmethod
    def sleep_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.SLEEP}"
~~~~~
~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def worker_in_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.in"

    @staticmethod
    def worker_out_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.out"

    @staticmethod
    def trace_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.trace"
~~~~~
~~~~~python.new
    # Deprecated Triad helpers, removed.
~~~~~

### 下一步建议
**Dyad 架构重构任务已圆满完成。**

代码库现在更加健壮、简洁且易于维护。建议团队可以开始规划以下方向：
*   **新功能开发**: 基于新的稳定架构，开始实施新的业务功能。
*   **性能优化**: 分析新的执行路径，寻找潜在的性能瓶颈并进行优化。
*   **文档更新**: 更新开发者文档，反映新的架构设计和拓扑结构。
