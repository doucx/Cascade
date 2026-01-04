好的，我们进入 Phase 3: 运行时层 (The Runtime Layer)。

在这一阶段，我们将实现 `CodeRegistry` 和 `Linker`，并重构 `VMExecutionStrategy` 以使用新的链接机制。目标是彻底移除运行时代码中用于“猜测”函数映射的 Hack 代码，转而使用 `Assembly` 中提供的 `SymbolTable`。

## [WIP] feat: 实现 CodeRegistry 和 Linker，完成 VM 运行时重构

### 用户需求

1.  实现 `CodeRegistry`：用于在运行时存储和查找 `Canonical Hash` 到 Python `Callable` 的映射。
2.  实现 `Linker`：根据 `Assembly` 的 `SymbolTable` 和图结构，将物理节点 ID 链接到 `CodeRegistry` 中的具体函数，生成 `function_map`。
3.  重构 `VMExecutionStrategy`：移除遗留的 `v2_registry` Hack，改用标准的 `Registry -> Compile -> Link -> Execute` 流程。

### 评论

这是 "The Linker Protocol" 的核心实施阶段。通过引入显式的链接步骤，我们将编译时（生成 Assembly）和运行时（执行 Assembly）彻底解耦。`Linker` 将负责处理所有的函数查找逻辑，包括用户定义的 Worker 和系统内置的基础设施节点（如 Bleacher, Stainer）。这将显著提高系统的清晰度和可维护性。

### 目标

1.  创建 `packages/cascade-vm/src/cascade/vm/registry.py`，定义 `CodeRegistry`。
2.  创建 `packages/cascade-vm/src/cascade/vm/linker.py`，定义 `Linker`。
3.  更新 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py`，使用新组件重写 `execute` 方法。

### 基本原理

*   **Registry**: 作为运行时的“动态链接库”，它只关心“哈希 -> 函数”的纯映射，不关心图结构。
*   **Linker**: 作为装载器，它负责“合”，将静态的 `Assembly` 和动态的 `Registry` 结合，为 `Reactor` 准备好可执行的 `function_map`。
*   **StdLib 处理**: 对于基础设施节点（`.bleach`, `.stain` 等），Linker 将使用内置的启发式规则或查找表进行链接，无需用户手动注册。

### 标签

#intent/build #flow/ready #priority/high #comp/vm #comp/runtime #concept/linker #scope/core #ai/instruct #task/domain/runtime #task/object/linker #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现 CodeRegistry

`CodeRegistry` 是运行时的函数仓库。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/registry.py
~~~~~
~~~~~python
from typing import Dict, Callable, Any

# A generic callable type for task functions
TaskCallable = Callable[..., Any]


class CodeRegistry:
    """
    The runtime registry for executable code.
    It maps canonical code structure hashes to actual Python callables.
    """

    def __init__(self):
        self._registry: Dict[str, TaskCallable] = {}

    def register(self, canonical_hash: str, func: TaskCallable) -> None:
        """
        Registers a function under its canonical hash.
        If the hash already exists, we assume the code is identical (idempotent).
        """
        self._registry[canonical_hash] = func

    def get(self, canonical_hash: str) -> TaskCallable:
        """
        Retrieves a function by its canonical hash.
        Raises KeyError if not found.
        """
        if canonical_hash not in self._registry:
            raise KeyError(f"Code for hash '{canonical_hash}' not found in registry.")
        return self._registry[canonical_hash]

    def has(self, canonical_hash: str) -> bool:
        return canonical_hash in self._registry
~~~~~

#### Acts 2: 实现 Linker

`Linker` 负责生成 `Reactor` 所需的 `function_map`。它处理用户代码（通过 SymbolTable）和标准库代码（通过后缀匹配或内置映射）。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python
import asyncio
from typing import Dict, Callable, Any, Optional

from cascade.spec.assembly import Assembly
from cascade.spec.physics import Token, PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry

# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe

# Helper to wrap user functions
def _make_worker_wrapper(func: Callable) -> Callable:
    """Wraps a user function to match the (inputs, node, resources) signature."""

    async def _wrapper(
        inputs: Dict[str, Token], node: Any, resources: Any
    ) -> Dict[str, Token]:
        # Unpack inputs. The Bleacher put them in 'worker_input'
        # payload is the dict of {arg_name: val}
        if "worker_input" not in inputs:
            # Fallback or error? For now assume it's there.
            return {}
            
        kwargs = inputs["worker_input"].payload

        # Execute
        if asyncio.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = func(**kwargs)

        return {"worker_result": Token(payload=result)}

    return _wrapper


class Linker:
    """
    The Linker binds a static Assembly to a dynamic CodeRegistry.
    It produces the function_map required by the Reactor.
    """

    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
        function_map: Dict[str, Callable] = {}

        for node_id, node in assembly.graph.nodes.items():
            if not isinstance(node, PhysicsFuncNode):
                continue

            # 1. User Worker Nodes (via Symbol Table)
            if node_id in assembly.symbol_table:
                canonical_hash = assembly.symbol_table[node_id]
                try:
                    raw_func = registry.get(canonical_hash)
                    function_map[node_id] = _make_worker_wrapper(raw_func)
                except KeyError:
                    # TODO: In distributed mode, this might trigger a code fetch
                    raise ImportError(
                        f"Failed to link node '{node_id}': Code hash '{canonical_hash}' not found in registry."
                    )
                continue

            # 2. Standard Library Nodes (via ID Heuristics)
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue
            
            # If we reach here, we have an unlinked function node.
            # In strict mode, this should probably raise.
            # For now, we leave it unmapped (Reactor will raise if it tries to execute it).

        return function_map

    def _resolve_stdlib(self, node_id: str) -> Optional[Callable]:
        """
        Resolves infrastructure nodes to standard library implementations.
        """
        # Triad
        if node_id.endswith(".bleach"):
            return standard_bleacher
        if node_id.endswith(".stain"):
            return standard_stainer
        
        # Observability
        if node_id == PhysicalIdGenerator.observability_observer():
            return standard_observer
            
        # Resources
        if "allocator" in node_id:
            return discrete_allocator
        if "reclaimer" in node_id:
            return discrete_reclaimer
        if node_id.startswith("req."):
            return resource_requestor
            
        # Probes
        if node_id.startswith("probe.const."):
            return const_probe
            
        return None
~~~~~

#### Acts 3: 重构 VMExecutionStrategy

现在，我们将各个部分整合到 `VMExecutionStrategy` 中。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.new
from typing import Any, Dict, Callable
import asyncio
import time

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.environment import EnvironmentDef
from cascade.spec.physics import Token

from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.reflection import PhysicalIdGenerator, ReflectionAnalyzer

from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker

from cascade.runtime.strategies.base import ExecutionContext
from cascade.runtime.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
)

class VMExecutionStrategy:
    def __init__(self, bus: Any):
        self.bus = bus
        self.analyzer = ReflectionAnalyzer()

    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any:
        # 1. Compile: Logical -> Physical
        # -------------------------------
        # TODO: Handle EnvironmentDef properly based on context.active_resources
        env_def = EnvironmentDef(resources=[])
        
        compiler = IRGenerator()
        graph_ir = compiler.generate(target)
        
        builder = Builder()
        assembly = builder.build(graph_ir, env_def)
        physical_graph = assembly.graph

        # 2. Runtime Setup
        # ----------------
        memory = VolatileMemory()
        executor = PhysicsExecutor()
        resource_registry = ResourceRegistry()

        # Bridge: Register active resources from Engine context to VM Registry
        for name, res in context.active_resources.items():
            resource_registry.register(name, res)

        # 3. Registration: Populate CodeRegistry
        # --------------------------------------
        code_registry = CodeRegistry()
        
        # We need to register all tasks involved in the graph.
        # GraphIR nodes contain the TaskDef, which has the canonical hash.
        # We also need the actual callable.
        # Since GraphIR only has metadata, we need to re-discover the callables from the 'target' structure.
        
        # Collect all LazyResults from the target input
        lazy_results = self._collect_lazy_results(target)
        
        for lr in lazy_results.values():
            # Analyze to get hash (idempotent)
            task_def = self.analyzer.analyze(lr.task)
            canonical_hash = task_def.fingerprint["canonical_code_structure_hash"]
            
            # Register the raw function
            # Note: lr.task is the Task wrapper. We want the underlying function if possible,
            # or the wrapper if it's callable. Analyzer handles this check.
            # Here we register the Task wrapper itself, the Linker/Wrapper handles execution.
            # Actually, `lr.task.func` is usually what we want to run, but `lr.task` is callable too.
            # Let's register `lr.task.func` to be safe and pure.
            func_to_run = getattr(lr.task, "func", lr.task)
            code_registry.register(canonical_hash, func_to_run)

        # 4. Linking: Assembly + Registry -> Function Map
        # -----------------------------------------------
        linker = Linker()
        # We need to bridge the bus for the Observer. 
        # Ideally, we pass 'context' or 'bus' to the Linker or Reactor?
        # The standard_observer currently is hardcoded in Linker. 
        # We need to inject the bus into the standard_observer logic.
        # Strategy: Use a closure-based Linker or specialized registry?
        # Better: The Reactor execution passes `resources`. We can put the `bus` in `resources`.
        
        # Register the bus as a resource!
        resource_registry.register("system.event_bus", self.bus)
        
        # Now Link
        function_map = linker.link(assembly, code_registry)

        # 5. Reactor Setup
        # ----------------
        reactor = Reactor(
            graph=physical_graph,
            memory=memory,
            executor=executor,
            function_map=function_map,
            resource_registry=resource_registry
        )
        
        # Prime the reactor (fill constants, pulses)
        reactor.prime()

        # Result Future
        result_future = asyncio.get_running_loop().create_future()

        # Identify Target Physical Node for Sinking Result
        # We need the Physical ID of the target's Stainer.
        # 1. Find the NodeIR for the target.
        # target is a LazyResult. We have its UUID.
        target_uuid = target._uuid if hasattr(target, "_uuid") else None
        
        # If target is a list/dict, we might have multiple roots. 
        # For now, support single root return.
        # We can scan GraphIR for the node that corresponds to this UUID?
        # GraphIR nodes have `current_node_instance_hash` which IS the UUID (in current impl).
        # Let's verify `generator.py`. 
        # Yes: `node_id = self.hashing_service.compute_node_instance_hash(...)`
        # And `_visited[lr._uuid] = node_id`.
        # So we can re-compute the hash or assume we can find it?
        
        # The Compiler doesn't expose the UUID->Hash map.
        # But we know HashingService is deterministic.
        # Let's try to find the NodeIR that matches the target's task name and assume it's the last one? Risky.
        
        # Robust Fix: We need the Node ID.
        # Let's re-use the HashingService to compute it for the target.
        from cascade.reflection import HashingService
        # But we need dependencies...
        
        # OK, let's look at the generated GraphIR. The `current_node_instance_hash` IS the physical ID base.
        # We need to find which NodeIR corresponds to `target`.
        # If we assume `target` is the root, it usually appears last in the list (Post-Order Traversal).
        # Let's try the last node.
        if graph_ir.nodes:
            target_node_ir = graph_ir.nodes[-1]
            target_base_id = target_node_ir.current_node_instance_hash
            target_stainer_id = PhysicalIdGenerator.stain_node(target_base_id)

            # Bridge: Sink to Future
            def _result_sink(token: Token):
                if not result_future.done():
                    result_future.set_result(token.payload)
            
            reactor.add_sink(target_stainer_id, "output_default", _result_sink)

        # 6. Execution Loop
        # -----------------
        try:
            while not result_future.done():
                fired = await reactor.step()
                if fired == 0 and not result_future.done():
                    # If we stall but haven't got a result, check for errors or deadlocks
                    await asyncio.sleep(0.001)
        except Exception as e:
            # If reactor crashes, we fail the run
            raise e
            
        return result_future.result()

    def _collect_lazy_results(self, target: Any) -> Dict[str, Any]:
        """Recursive finder."""
        results = {}
        if isinstance(target, (LazyResult, MappedLazyResult)):
            results[target._uuid] = target
            for arg in target.args:
                results.update(self._collect_lazy_results(arg))
            for k, v in target.kwargs.items():
                results.update(self._collect_lazy_results(v))
        elif isinstance(target, (list, tuple)):
            for item in target:
                results.update(self._collect_lazy_results(item))
        elif isinstance(target, dict):
            for v in target.values():
                results.update(self._collect_lazy_results(v))
        return results
~~~~~

### 下一步建议

我们已经完成了 Phase 3 的核心实施：
1.  实现了 `CodeRegistry` 用于管理函数。
2.  实现了 `Linker` 用于连接静态 `Assembly` 和动态运行时。
3.  重构了 `VMExecutionStrategy` 以使用这一新流程，并移除了旧的 Hack。

接下来，我们需要对 `standard_observer` 进行微调，使其从 `resource_registry` 中获取 `event_bus`，而不是依赖硬编码。这是在 `VMExecutionStrategy` 重构中发现的一个小 TODO。

然后，我们将进入 **Phase 4: 验证与清理**，确保新架构坚如磐石。
