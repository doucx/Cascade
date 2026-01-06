简要回答：
好的，我将执行 **Phase 1: Standardization & Purification**。这将包括移除 legacy 的 Probe 组件，创建新的物理出口组件 `standard_egress`，并更新 `Linker` 以注册新组件并解绑旧组件。

## [WIP] refactor: 实施 Phase 1 - 标准库清洗与物理出口创建

### 用户需求
根据 [实施路线图：Cascade VM 物理内核集成](01KE9G5EW4TP5YPNWZ548Y52YS) 的第一阶段要求：
1.  **移除 Probe 组件**：删除 `packages/cascade-std/src/cascade/std/probe` 目录。
2.  **创建物理出口 (Egress IC)**：实现 `standard_egress`，作为物理层向外部策略层传递数据的唯一合法通道。
3.  **更新 Linker**：在 VM 链接器中移除对 Probe 的映射，并添加对 Egress 的支持。

### 评论
这是一个关键的架构清理步骤。
*   移除 Probe 标志着我们正式放弃“在物理层内进行 I/O 采样”的旧模式，转向“预物质化”模式。
*   引入 `standard_egress` 建立了符合物理公理的、明确的系统边界。
*   **注意**：在完成此步骤后，当前的编译器（尚未经过 Phase 2 改造）生成的包含 `F_probe` 的图在运行时将会因为找不到链接函数而失败。这是预期的中间状态，将在下一阶段（Phase 2）通过更新编译器来解决。

### 目标
完成标准库的净化，建立新的物理出口机制。

### 基本原理
*   **移除 Probe**: 为了满足“计算同质性公理”，所有环境采样都应被视为计算任务，或由策略层预先处理。
*   **Standard Egress**: 为了满足“边界显式化公理”，数据离开物理图必须通过显式的、可观测的节点，而不是隐式的回调。
*   **Linker Update**: 保持运行时与标准库的一致性。

### 标签
#intent/refine #intent/build #flow/ready #priority/high #comp/runtime #concept/physics #scope/core #ai/instruct
#task/domain/vm #task/object/standard-lib #task/action/purification #task/state/begin

---

### Script

#### Acts 1: 创建物理出口组件 (Egress IC)

我们首先创建 `egress.py`，它定义了将 Token 从物理图导出到 `system.egress_queue` 的逻辑。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/system/egress.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def standard_egress(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    """
    Standard Egress IC (Physical Exit).
    
    This node acts as a 'Black Hole' in the physical graph. It consumes a Token
    and teleports it to the 'system.egress_queue', allowing the Strategy layer
    to observe the result.
    
    Ports:
        - in: The token to export.
    """
    # 1. Get the Egress Queue from system resources
    # This must be registered by the Strategy during startup.
    queue = resources.get("system.egress_queue")
    
    # 2. Consume the token
    # Phase 3.3 of the roadmap defines the input port as 'in'.
    token = inputs.get("in")
    
    if token:
        # 3. Export
        # We wrap the token with the node ID so the Strategy knows which egress node it came from.
        # This allows handling multiple egress points (e.g. for different task results).
        queue.put_nowait((node.id, token))
    
    # 4. Return empty (Evaporate)
    # No tokens are returned to the graph. The energy leaves the system here.
    return {}
~~~~~

#### Acts 2: 更新 Linker 逻辑

接着，我们需要修改 `linker.py`。我们要移除对已废弃 Probe 组件的引用，并添加对新 Egress 组件的映射规则。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
~~~~~
~~~~~python.new
# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
        # Probes
        if node_id.startswith("probe.const."):
            return const_probe

        return None
~~~~~
~~~~~python.new
        # System / Egress
        if node_id.startswith("egress."):
            return standard_egress

        return None
~~~~~

#### Acts 3: 移除 Probe 组件

最后，我们执行破坏性操作，彻底删除 `cascade.std.probe` 包。这是一个不可逆的操作，标志着旧架构的终结。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-std/src/cascade/std/probe
~~~~~

### 下一步建议

Phase 1 已完成。目前系统处于一个中间状态：VM 已经去除了对 Probe 的支持，但 Compiler 仍然会为常量参数生成 `F_probe` 节点。

下一步必须立即执行 **Phase 2: Compiler Backend Optimization**，修改 `ParameterWiringPolicy`，使其不再生成 `F_probe`，而是生成直接连接到 `Bleacher` 的 `D_const` 结构，从而修复“链接断裂”并完成架构升级。
