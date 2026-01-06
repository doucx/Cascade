简要回答：
分析完成。这是一个预料之中的架构不匹配错误。测试失败的根源在于，我们的测试工具 `EventDrivenRunner` 还没有实现“常量物质化”这一关键步骤，导致它将原始数据（如整数 `10`）直接注入了物理层，而新的 `ComputeService` 严格要求只处理 `Ref` 对象。

我将修复 `EventDrivenRunner` 来模拟正确的行为。

## [WIP] fix: 在测试工具中实现常量物质化以对齐引用架构

### 错误分析
1.  **核心错误**: `AttributeError: 'int' object has no attribute 'uri'`。
    *   **位置**: `ComputeService._process_request` 中，在尝试解引用（`store.get(ref)`）时发生。
    *   **原因**: `ref` 变量本应是一个 `Ref` 对象，但实际上它是一个整数（`10`）。
2.  **根源**:
    *   在 Phase 2 中，我们修改了编译器，使其生成带有原始字面量（`initial_payload=10`）的 `D_const` 节点。
    *   根据路线图，将这些原始字面量转换为 `Ref` 对象是 **策略层 (Strategy)** 的职责。
    *   我们当前的测试工具 `EventDrivenRunner` 扮演了一个简化的策略角色，但它的 `prime()` 方法只是简单地将 `initial_payload` 直接包装进 `Token`，没有执行“物质化”步骤。
    *   因此，一个 `Token(payload=10)` 被创建并最终传递给了 `ComputeService`，导致了架构冲突。
3.  **下游影响**: 第二个错误 `TypeError: unsupported operand type(s) for *: 'AttributeError' and 'AttributeError'` 是第一个错误的直接后果。`add_one` 任务失败并返回了一个 `AttributeError` 异常对象，这个异常对象被作为输入传递给了 `square` 任务，导致了类型错误。

### 用户需求
修复测试套件，使其能够正确地测试新的、基于全引用的物理执行流程。

### 评论
这个失败是积极的，因为它精确地暴露了测试基础设施与我们正在构建的目标架构之间的差距。通过修复 `EventDrivenRunner`，我们不仅能让测试通过，还能使其成为 `CascadeVMStrategy` 未来实现的一个更精确、更高保真的模型。

### 目标
修改 `EventDrivenRunner.prime()` 方法，在启动 VM 之前，扫描图中所有的 `PhysicsDataNode`，并将其 `initial_payload` 中的所有原始值通过 `object_store` 转换为 `Ref` 对象。

### 基本原理
遵循“边界显式化公理”和路线图 Phase 3.2 的规定。原始数据在进入物理图之前必须被“预物质化”。测试工具作为物理图的“加载器”，必须履行这一职责。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #comp/vm #concept/physics #ai/instruct
#task/domain/vm #task-object/test-harness #task-action/alignment #task/state/continue

---

### Script

#### Acts 1: 更新 `EventDrivenRunner` 以支持常量物质化

我们将修改 `harness.py`，首先添加必要的 `Ref` 导入，然后重写 `prime` 方法以实现物质化逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
import asyncio
import logging
import uuid
from typing import Dict, Any, Callable, TypeVar, Optional, List, Tuple

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
~~~~~
~~~~~python.new
import asyncio
import logging
import uuid
from typing import Dict, Any, Callable, TypeVar, Optional, List, Tuple

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.object import Ref
from cascade.vm.reactor import Reactor
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    def prime(self):
        self.reactor.prime(genesis_trace={"rid": self.run_id})
~~~~~
~~~~~python.new
    def prime(self):
        # Phase 3.2 - Constant Materialization
        # The runner, acting as the Strategy, scans the graph for any initial payloads
        # and converts them to Refs before priming the reactor.
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                payload = node.initial_payload
                if payload is not None and not isinstance(payload, Ref):
                    # Materialize the raw value into the object store
                    node.initial_payload = self.object_store.put(payload)

        self.reactor.prime(genesis_trace={"rid": self.run_id})
~~~~~

### 下一步建议
我们已经修复了测试工具，使其与目标架构的核心原则（全引用）保持一致。现在，`test_ref_architecture` 应该能够成功通过，从而验证我们 Phase 1 和 Phase 2 的工作是正确且完整的。

一旦测试通过，我们就可以满怀信心地开始实施 **Phase 3: 策略层重构**，即创建生产级的 `CascadeVMStrategy`。
