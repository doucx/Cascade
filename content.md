好的，遵照指令。我们开始执行重构方案的第一阶段：清理与依赖注入。

我将生成一个计划，使用 `write_file` 彻底重写 `cascade/runtime/strategies/vm.py` 文件，为其建立全新的、符合“宏观流程编排器”角色的类结构和依赖注入。

## [WIP] refactor(engine): 重构 VMExecutionStrategy 以适应物理模型

### 用户需求
根据我们制定的详细重构方案，开始第一阶段：清理 `VMExecutionStrategy` 类，并为其注入新的、与物理引擎兼容的依赖。

### 评论
这是将 `VMExecutionStrategy` 从一个过时的原型转变为现代化“宏观流程编排器”的关键第一步。通过彻底重写该文件，我们能建立一个清晰、稳固的结构基础，为后续实现核心的异步协调和拓扑加载逻辑做好准备。此举也正式标志着我们向纯粹的、解耦的物理执行模型迈进。

### 目标
1.  使用 `write_file` 彻底覆盖 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py`。
2.  在文件中导入所有必需的新组件，包括 `Frontend`, `Backend`, `Reactor`, `PhysicsExecutor` 等。
3.  定义新的 `VMExecutionStrategy` 类，其 `__init__` 方法仅接收 `MessageBus` 等高层级依赖。
4.  为 `execute` 和 `_load_topology` 方法创建符合新方案签名的占位符 (stubs)。

### 基本原理
旧的 `VMExecutionStrategy` 与我们新的 `Reactor` 物理模型在架构上完全不兼容。与其进行复杂的增量式修补，不如直接用一个全新的、设计正确的骨架来替换它。`write_file` 是执行此种结构性重塑的最直接、最无歧义的操作。这个新骨架将显式地声明其对编译器和 VM 组件的依赖，为实现“编译-组装-配置-运行”的宏观编排流程奠定基础。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/refactor #task/state/begin

---
### Script

#### Acts 1: 重写 VMExecutionStrategy 类结构

我们将使用 `write_file` 操作，用一个全新的、符合新架构设计的类骨架替换 `vm.py` 的全部内容。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python
import asyncio
from contextlib import ExitStack
from typing import Any, Dict

# --- 核心 VM 和编译器组件 ---
from cascade.compiler import Frontend, Backend
from cascade.vm import Reactor, PhysicsExecutor
from cascade.spec.topology import BipartiteGraph, ChannelKind
from cascade.spec.physics import FuncNode, DataNode, EmitterNode, Token, Port
from cascade.vm.reactor.model import Channel as ReactorChannel


# --- 运行时和规格 ---
from cascade.runtime.bus import MessageBus
from cascade.spec.protocols import StateBackend


class VMExecutionStrategy:
    """
    Orchestrates the new physics-based VM execution by acting as a
    macro-orchestrator for the compiler and the Reactor.
    """

    def __init__(
        self,
        bus: MessageBus,
        # Note: ResourceManager and ConstraintManager are now owned by the Reactor/VM,
        # so this strategy no longer needs to manage them directly.
    ):
        self.bus = bus
        self.frontend = Frontend()
        self.backend = Backend()

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        """
        The main entry point for the VM execution strategy.
        This method will be implemented in the next phase.
        """
        # Placeholder for the orchestration logic.
        raise NotImplementedError("VMExecutionStrategy.execute is not yet implemented.")

    def _load_topology(self, reactor: Reactor, topology: BipartiteGraph):
        """
        Translates the static BipartiteGraph spec into live, interconnected
        physics objects within the Reactor.
        This method will be implemented in the next phase.
        """
        # Placeholder for the topology loading logic.
        raise NotImplementedError(
            "VMExecutionStrategy._load_topology is not yet implemented."
        )
~~~~~

### 下一步建议
我们已经成功地为 `VMExecutionStrategy` 建立了新的结构基础。下一步，我将根据方案的 **阶段 2 和 3**，着手实现 `execute` 方法中的核心编排逻辑和 `_load_topology` 辅助方法。

准备好后，请告诉我继续。
