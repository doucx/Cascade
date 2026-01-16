好的，我们来执行 Step 3.5，修复 Linker 以适配 Dyad 架构。

## [WIP] feat(vm): 适配 Linker 以支持 Dyad 架构

### 用户需求
执行 Dyad 架构重构的 Step 3.5，更新 `cascade-vm` 包中的 `Linker`，使其能够识别并正确链接 `LauncherNode` 和 `LanderNode` 到它们在标准库中的实现 (`standard_launcher`, `standard_lander`)。

### 评论
这是连接编译器输出和虚拟机执行的关键一步。此更改使新编译的 Dyad 架构图谱 (`Assembly`) 能够被虚拟机正确解释和执行。通过移除旧的、基于 `symbol_table` 的 `dispatcher` 链接逻辑，`Linker` 的职责变得更加清晰：它只负责链接物理节点到其固定的内核实现，而用户代码的查找则完全由 `ComputeService` 负责。

### 目标
1.  修改 `cascade-vm` 的 `Linker` 实现。
2.  将以 `.launch` 结尾的节点 ID 映射到 `standard_launcher`。
3.  将以 `.land` 结尾的节点 ID 映射到 `standard_lander`。
4.  移除所有与 Triad (`.bleach`, `.stain`) 和旧 `dispatcher` 相关的链接逻辑。

### 基本原理
`Linker` 的核心职责是将 `Assembly` 中定义的物理功能节点 (`PhysicsFuncNode`) 映射到可执行的 Python 函数（内核IC）。在 Dyad 架构中，所有由 `Expander` 生成的功能节点（`Launcher`, `Lander` 以及资源、系统节点）都有一个固定的、由标准库提供的实现。我们通过修改 `Linker` 的 ID 识别规则，就能将新的节点类型正确地链接到它们的实现上，从而完成整个执行链路的闭环。

### 标签
#intent/refine #flow/ready #priority/critical #comp/runtime #concept/executor #task/domain/vm #task/object/linker #task/action/adapt #task/state/continue

---

### Script

#### Acts 1: 重写 Linker 以适配 Dyad 架构

我们将完全重写 `linker.py` 文件，更新其导入、核心链接逻辑和标准库解析规则，以全面支持 Dyad 架构。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python
from typing import Dict, Callable, Optional

from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.physical.constants import NodePrefix
from .registry import CodeRegistry

# Dyad Implementations
from cascade.std.dyad.launcher import standard_launcher
from cascade.std.dyad.lander import standard_lander

# Common Standard Library
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
from cascade.std.system.gate import gate_passthrough
from cascade.std.system.time import standard_sleep


class LinkerError(RuntimeError):
    pass


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
        # Phase 1: Integrity Validation
        self._verify_integrity(assembly, registry)

        # Phase 2: Function Mapping
        function_map: Dict[str, Callable] = {}
        for node_id, node in assembly.graph.nodes.items():
            if not isinstance(node, PhysicsFuncNode):
                continue

            # In the Dyad architecture, all physical function nodes map to a
            # standard library IC. User code is invoked by the ComputeService,
            # not linked directly into the kernel. The Linker's role is to
            # resolve the system-level ICs based on naming conventions.
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue

        return function_map

    def _verify_integrity(self, assembly: Assembly, registry: CodeRegistry) -> None:
        missing_hashes = {
            code_hash
            for code_hash in assembly.symbol_table.values()
            if not registry.has(code_hash)
        }

        if missing_hashes:
            missing_list = "\n - ".join(sorted(list(missing_hashes)))
            raise LinkerError(
                f"Linker integrity check failed. The following code hashes "
                f"are required by the assembly but were not found in the CodeRegistry:\n"
                f" - {missing_list}"
            )

    def _resolve_stdlib(self, node_id: str) -> Optional[Callable]:
        # Dyad Primitives
        if node_id.endswith(f".{NodePrefix.LAUNCH}"):
            return standard_launcher
        if node_id.endswith(f".{NodePrefix.LAND}"):
            return standard_lander

        # System & Time
        if node_id.endswith(f".{NodePrefix.SLEEP}"):
            return standard_sleep
        if node_id == PhysicalIdGenerator.observability_observer():
            return standard_observer
        if node_id.startswith(f"{NodePrefix.EGRESS}."):
            return standard_egress

        # Resources
        if "allocator" in node_id:
            return discrete_allocator
        if "reclaimer" in node_id:
            return discrete_reclaimer
        if node_id.startswith(f"{NodePrefix.REQ}."):
            return resource_requestor
        if f"{NodePrefix.GATE}.wakeup" in node_id:
            return gate_passthrough

        return None
~~~~~

### 下一步建议
我们已经完成了 Phase 3 的所有核心步骤：
1.  **3.1**: 更新了 `cascade-spec` 和 `cascade-reflection` 的基础定义。
2.  **3.2 & 3.3**: 重构了 `cascade-compiler` 的 `SubGraph` 模型和 `Expander`。
3.  **3.4**: 适配了 `cascade-compiler` 的 `Wiring Policies`。
4.  **3.5**: 修复了 `cascade-vm` 的 `Linker`。

**编译器和运行时现在在逻辑上已经对齐到 Dyad 架构。**

下一步是 **Phase 4: 验证与清理**。
首要任务是运行测试套件，识别并修复所有因物理拓扑结构变更而失败的测试用例。这很可能会暴露一些我们未预见到的边界情况或逻辑错误。
