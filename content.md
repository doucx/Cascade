简要回答

好的，我将开始实施阶段三的策略层重构。这将涉及在 `VMExecutionStrategy` 中实现完整的“加载器”逻辑，包括环境准备、编译、物质化、外科手术式的图修改、以及启动基于物理内核的 `Reactor` 和 `Machine`。

## [WIP] feat(runtime): 实现 CascadeVMStrategy 及其加载与执行逻辑

### 用户需求
实现 `cascade-runtime` 中的 `VMExecutionStrategy` 类。它是连接逻辑世界（DSL/Engine）与物理世界（VM/Reactor）的胶水层，负责将逻辑图编译为物理图，进行数据“物质化”处理，并驱动物理引擎执行任务。

### 评论
这是 Cascade 3.3 架构转型的核心一步。通过这个策略类，我们正式启用了“双速引擎”模型：同步的物理内核负责调度，异步的计算服务负责执行。这也标志着系统从传统的解释器模式向仿真器模式的转变。

### 目标
1.  在 `packages/cascade-runtime/src/cascade/runtime/legacy/strategies/vm.py` 中实现完整的 `VMExecutionStrategy`。
2.  实现 **Pre-flight**：初始化对象存储 (`InMemoryObjectStore`) 和计算服务 (`LocalComputeService`)。
3.  实现 **Compile & Materialize**：调用编译器生成物理图，并将所有常量数据转换为引用 (`Ref`) 存入对象存储。
4.  实现 **Physical Surgery**：动态创建 `Egress` 节点并将其“缝合”到目标任务的输出端，以便捕获结果。
5.  实现 **Link & Launch**：组装 `ResourceRegistry`, `Linker`, `Reactor`, `Machine` 并启动执行。
6.  实现 **Reaping**：从出口队列回收结果并返回给 Engine。

### 基本原理
为了保证物理内核的纯粹性（不处理 I/O，不持有大对象），策略层必须承担“加载器”的重任。它必须在物理图启动前，将所有静态数据“预物质化”为存储中的引用，并将所有 Python 函数注册到计算服务的注册表中。此外，通过显式地将 `Egress` 节点嫁接到图中，我们避免了在该层使用隐式的回调或 Probe，符合“边界显式化公理”。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/execution #scope/core #task/domain/runtime #task/object/vm-strategy #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 实现 VMExecutionStrategy

我们在 `vm.py` 中填入具体的实现逻辑。代码将涵盖从编译到结果回收的完整生命周期。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/vm.py
~~~~~
~~~~~python
import asyncio
import logging
from typing import Any, Dict, Optional, Tuple, Set, List
from contextlib import AsyncExitStack

from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.spec.runtime import ExecutionContext
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import Channel

from cascade.reflection import ReflectionAnalyzer, HashingService, PhysicalIdGenerator
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder

from cascade.runtime.storage.memory import InMemoryObjectStore
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker
from cascade.vm.reactor import Reactor
from cascade.vm.machine import Machine
from cascade.vm.memory import VolatileMemory
from cascade.vm.compute.service import LocalComputeService

logger = logging.getLogger(__name__)


class VMExecutionStrategy:
    def __init__(self, bus: Any):
        self.bus = bus
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()
        self.linker = Linker()
        self.builder = Builder()
        self.ir_generator = IRGenerator()

    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any:
        run_id = context.run_id
        logger.info(f"VM Strategy starting for run_id={run_id}")

        async with AsyncExitStack() as stack:
            # --- Phase 3.1: Pre-flight (Environment Preparation) ---
            # 1. Storage Initialization
            object_store = InMemoryObjectStore()

            # 2. Code Registry & Resource Registry
            code_registry = CodeRegistry()
            resource_registry = ResourceRegistry()

            # 3. Queues
            # Ingress: Results coming back from Compute Service -> Reactor
            ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
            # Egress: Final results leaving Reactor -> Strategy
            egress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
            # Compute: Requests from Reactor -> Compute Service
            compute_queue = asyncio.Queue()

            # 4. Compute Service
            compute_service = LocalComputeService(
                store=object_store,
                registry=code_registry,
                inbound_queue=compute_queue,
                outbound_queue=ingress_queue,
            )
            # Register system resources for the kernel/std-lib nodes to use
            resource_registry.register("system.object_store", object_store)
            resource_registry.register("system.compute_queue", compute_queue)
            resource_registry.register("system.egress_queue", egress_queue)
            resource_registry.register("system.event_bus", self.bus)

            # --- Phase 3.2: Compile & Materialize ---
            logger.debug("Compiling logical graph to physical assembly...")
            
            # A. Generate GraphIR
            # We treat the target as the root. IRGenerator expects the object itself.
            graph_ir = self.ir_generator.generate(target)
            
            # B. Build Physical Assembly
            # For now, we use a default empty environment definition.
            # In the future, this can be derived from context.active_resources or config.
            env_def = EnvironmentDef(resources=[]) 
            assembly = self.builder.build(graph_ir, env_def)
            physical_graph = assembly.graph

            # C. Register User Code
            # We need to map the canonical hashes in the assembly to actual Python callables.
            # We traverse the target's logical structure to find the Tasks and register them.
            # NOTE: This assumes that all code needed is reachable from 'target'.
            self._register_tasks(target, code_registry)

            # D. Constant Materialization (Scalar Hoisting)
            # Iterate over all DataNodes in the physical graph.
            # If they hold raw data (initial_tokens > 0), materialize it into the store.
            for node in physical_graph.nodes.values():
                if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                    payload = node.initial_payload
                    # If payload is already a Ref or None, skip
                    if payload is not None and not isinstance(payload, Ref):
                        # Scalar Hoisting Heuristic
                        meta = {}
                        if isinstance(payload, (int, float, bool, str)) and len(str(payload)) < 256:
                            meta["scalar_value"] = payload
                        
                        # Store and replace payload with Ref
                        ref = object_store.put(payload, metadata=meta)
                        node.initial_payload = ref
                        logger.debug(f"Materialized constant for node {node.id} -> {ref.uri}")

            # --- Phase 3.3: Physical Surgery (Egress Grafting) ---
            # We need to find the physical output node for our target.
            # 1. Identify Target Node ID
            # If target is a LazyResult, we compute its instance hash.
            target_uuid = None
            if isinstance(target, (LazyResult, MappedLazyResult)):
                # We need to re-compute the hash or extract it if cached.
                # Since IRGenerator visits it, we can rely on the fact that HashingService 
                # produces deterministic IDs.
                # However, IRGenerator returns a GraphIR, not a map of UUID->Hash.
                # We assume the HashingService used by IRGenerator is the same.
                # To be safe, we re-calculate it or rely on the IRGenerator if we could modify it.
                # For now, let's re-calculate using HashingService manually.
                # Note: This might be expensive for huge graphs, but safe for now.
                # Wait, IRGenerator logic is complex. 
                # Alternative: The IRGenerator stores visited nodes in `_visited`.
                # But we don't have access to the instance used inside `execute`.
                # Let's rely on the strategy's hashing service.
                
                # We need a dependency map for the hasher. This is tricky without full traversal.
                # SIMPLIFICATION: We assume the target is the last node added to IRGenerator? No.
                # ROBUST APPROACH: We trust the HashingService to be idempotent given the same inputs.
                # But we need the dependency map.
                
                # Let's use the IRGenerator's internal state if we can, or just use a helper.
                # Actually, in this Strategy, we can just use the IRGenerator instance we have.
                # But `generate` returns GraphIR.
                
                # Let's assume we can map back. The Assembly doesn't link logical UUIDs.
                # Temporary Hack/Solution: Use the IRGenerator's _visited map? No, it's private.
                
                # Let's re-traverse to build the map needed for hashing.
                # Or, better: Modify IRGenerator to return the root ID? 
                # For this implementation, I will perform a minimal traversal to get the ID.
                # Actually, `self.ir_generator` state is reset on init? No, it accumulates state in `nodes` and `_visited`.
                # So if we reuse `self.ir_generator`, we can access `_visited`.
                target_node_id = self.ir_generator._visited.get(target._uuid)
                if not target_node_id:
                     # Should not happen if generate was just called
                    raise RuntimeError("Target node ID not found after IR generation.")
            else:
                # Literal target? VM Strategy usually expects LazyResult.
                # If it's a literal, we just return it immediately?
                return target

            # 2. Find the Stain Node
            stain_id = PhysicalIdGenerator.stain_node(target_node_id)
            
            # 3. Create Egress Node
            egress_id = f"egress.{target._uuid}"
            f_egress = PhysicsFuncNode(
                id=egress_id,
                name="Egress",
                input_ports={"in": PortDef("in", PortRole.DATA, "Token")},
                output_ports={},
            )
            physical_graph.nodes[egress_id] = f_egress

            # 4. Stitch Connection (Stain -> Egress)
            # Stain output is 'output_default'
            channel = Channel(
                source_node_id=stain_id,
                source_port="output_default",
                target_node_id=egress_id,
                target_port="in"
            )
            physical_graph.channels.append(channel)
            logger.debug(f"Surgically grafted egress {egress_id} to {stain_id}")

            # --- Phase 3.4: Link & Launch ---
            logger.debug("Linking physical graph...")
            
            # A. Link Functions
            function_map = self.linker.link(assembly, code_registry)
            
            # B. Initialize Memory & Reactor
            memory = VolatileMemory()
            reactor = Reactor(
                graph=physical_graph,
                memory=memory,
                function_map=function_map,
                resource_registry=resource_registry,
                ingress_queue=ingress_queue
            )
            
            # C. Prime Reactor (Genesis Trace)
            # We inject run parameters into the genesis trace
            genesis_trace = {
                "rid": run_id,
                "params": context.params
            }
            reactor.prime(genesis_trace=genesis_trace)

            # D. Start Machine
            machine = Machine(reactor, compute_service, ingress_queue)
            machine_task = asyncio.create_task(machine.run())
            stack.push_async_callback(self._stop_machine, machine_task)

            # --- Phase 3.5: Reaping (Result Collection) ---
            logger.info("Machine launched. Waiting for result...")
            
            try:
                # Wait for the result token in the egress queue
                source_id, result_token = await egress_queue.get()
                
                # Extract Ref and Dereference
                result_ref = result_token.payload
                
                # Handle potential errors encoded in metadata (Phase 3.3/4 logic)
                # For now, we assume success if it reached egress.
                # (Standard Stainer logic would route errors to output_error, which we didn't connect to egress yet.
                #  We assume success path for now. Error path surgery is a future refinement).
                
                if isinstance(result_ref, Ref):
                    final_result = object_store.get(result_ref)
                else:
                    # Should be a Ref, but handle raw just in case
                    final_result = result_ref
                
                return final_result

            finally:
                # Clean shutdown handled by AsyncExitStack callbacks
                pass

    async def _stop_machine(self, task: asyncio.Task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def _register_tasks(self, target: Any, registry: CodeRegistry):
        """
        Traverses the logical target to find all Tasks and registers them.
        """
        lazy_results = self._collect_lazy_results(target)
        
        # We also need to map UUIDs to Nodes to compute hashes correctly.
        # This duplicates some work from IRGenerator, but is necessary 
        # because we need the *Task Object* (the function), which IRGenerator doesn't expose easily.
        
        # For this version, we assume IRGenerator has populated self.ir_generator.nodes 
        # which maps ID -> NodeIR. 
        # And `lazy_results` maps UUID -> LazyResult.
        # We need to bridge UUID -> ID -> NodeIR -> Canonical Hash -> Task Function.
        
        visited_map = self.ir_generator._visited # uuid -> node_id
        nodes_map = self.ir_generator.nodes # node_id -> NodeIR

        for uuid, lr in lazy_results.items():
            if uuid not in visited_map:
                continue
            
            node_id = visited_map[uuid]
            node_ir = nodes_map.get(node_id)
            
            if node_ir:
                canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
                # Register the raw function
                if not registry.has(canonical_hash):
                    registry.register(canonical_hash, lr.task.func)

    def _collect_lazy_results(self, target: Any) -> Dict[str, Any]:
        results = {}
        stack = [target]
        processed_uuids = set()

        while stack:
            current = stack.pop()

            if isinstance(current, (LazyResult, MappedLazyResult)):
                if current._uuid in processed_uuids:
                    continue
                processed_uuids.add(current._uuid)
                results[current._uuid] = current

                if current._condition:
                    stack.append(current._condition)
                if hasattr(current, "_dependencies"):
                    stack.extend(current._dependencies)

                if isinstance(current, LazyResult):
                    stack.extend(current.args)
                    stack.extend(current.kwargs.values())
                elif isinstance(current, MappedLazyResult):
                    stack.extend(current.mapping_kwargs.values())

            elif isinstance(current, (list, tuple)):
                stack.extend(current)
            elif isinstance(current, dict):
                stack.extend(current.values())

        return results
~~~~~

### 下一步建议
我们已经实现了 `VMExecutionStrategy` 的核心逻辑。根据计划，下一步是确保 `Linker` 和 `PhysicalIdGenerator` 等依赖项都已就绪（虽然我们的分析表明它们应该已经是好的，但集成测试是最终的检验标准）。

现在的当务之急是运行测试。我们应该启用并运行 `tests/integration/test_vm_strategy.py`，看看这个新引擎是否能真正转起来。如果测试失败，我们将根据报错进行修复。如果成功，我们可以继续完善其功能，比如支持 `params` 上下文注入或更复杂的流控制。

建议执行 `pytest packages/cascade-runtime/tests/integration/test_vm_strategy.py`。
