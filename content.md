## [WIP] 战略分析表明，测试超时的根本原因是 `VMExecutionStrategy` 在等待结果时，没有监控 `Machine` 的状态。如果 `Machine` 因为异常或误判空闲而提前退出，Strategy 就会陷入无限等待（直到测试超时）。

此外，当前的实现中存在架构异味：策略层直接操作物理图结构（Egress Grafting）。

为了解决这些问题，我将执行以下操作：
1.  **增强等待逻辑**: 使用 `asyncio.wait` 同时监听 `egress_queue` 和 `machine_task`。如果 `machine_task` 在没产生结果的情况下结束，立即抛出异常并报告 `Machine` 的状态。
2.  **重构 Egress 注入**: 将“手术”逻辑封装到私有方法 `_graft_egress` 中，提高代码可读性。
3.  **修复 ID 查找**: 更加健壮地处理 Target Node ID 的查找，不再隐式依赖 `IRGenerator` 的内部状态，而是显式地处理。

## 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/execution #scope/core #task/domain/runtime #task/object/vm-strategy #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 VMExecutionStrategy 以增强鲁棒性

我们将重写 `vm.py`，重点改进 `execute` 方法中的等待逻辑和错误处理。

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
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import Channel, BipartiteGraph

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
        # We instantiate a fresh IRGenerator per execution if needed, 
        # but the class is lightweight enough to be reused if we reset it.
        # However, for thread safety and clean state, it's better to create new ones 
        # or rely on its statelessness. The current IRGenerator is stateful.
        self.ir_generator_factory = IRGenerator

    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any:
        run_id = context.run_id
        logger.info(f"VM Strategy starting for run_id={run_id}")

        async with AsyncExitStack() as stack:
            # --- Phase 3.1: Pre-flight (Environment Preparation) ---
            object_store = InMemoryObjectStore()
            code_registry = CodeRegistry()
            resource_registry = ResourceRegistry()

            ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
            egress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
            compute_queue = asyncio.Queue()

            compute_service = LocalComputeService(
                store=object_store,
                registry=code_registry,
                inbound_queue=compute_queue,
                outbound_queue=ingress_queue,
            )
            
            resource_registry.register("system.object_store", object_store)
            resource_registry.register("system.compute_queue", compute_queue)
            resource_registry.register("system.egress_queue", egress_queue)
            resource_registry.register("system.event_bus", self.bus)

            # --- Phase 3.2: Compile & Materialize ---
            logger.debug("Compiling logical graph to physical assembly...")
            
            ir_gen = self.ir_generator_factory()
            graph_ir = ir_gen.generate(target)
            
            env_def = EnvironmentDef(resources=[]) 
            assembly = self.builder.build(graph_ir, env_def)
            physical_graph = assembly.graph

            self._register_tasks(target, code_registry, ir_gen)
            self._materialize_constants(physical_graph, object_store)

            # --- Phase 3.3: Physical Surgery (Egress Grafting) ---
            # Use the IRGenerator instance that generated the IR to find the ID
            target_node_id = self._resolve_target_node_id(target, ir_gen)
            if target_node_id:
                self._graft_egress(physical_graph, target_node_id, target._uuid if hasattr(target, '_uuid') else "root")
            else:
                # If target is a literal, we can just return it.
                return target

            # --- Phase 3.4: Link & Launch ---
            logger.debug("Linking physical graph...")
            function_map = self.linker.link(assembly, code_registry)
            
            memory = VolatileMemory()
            reactor = Reactor(
                graph=physical_graph,
                memory=memory,
                function_map=function_map,
                resource_registry=resource_registry,
                ingress_queue=ingress_queue
            )
            
            genesis_trace = {
                "rid": run_id,
                "params": context.params
            }
            reactor.prime(genesis_trace=genesis_trace)

            machine = Machine(reactor, compute_service, ingress_queue)
            machine_task = asyncio.create_task(machine.run())
            # Ensure we cancel the machine if we exit the block
            stack.push_async_callback(self._stop_machine, machine_task)

            # --- Phase 3.5: Reaping (Result Collection) ---
            logger.info("Machine launched. Waiting for result...")
            
            # Create a task for getting the result
            result_task = asyncio.create_task(egress_queue.get())
            
            # Wait for either result or machine exit
            done, pending = await asyncio.wait(
                [result_task, machine_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            if result_task in done:
                source_id, result_token = result_task.result()
                result_ref = result_token.payload
                
                if isinstance(result_ref, Ref):
                    final_result = object_store.get(result_ref)
                else:
                    final_result = result_ref
                
                return final_result
            else:
                # Machine exited without producing a result
                # Check if machine failed
                try:
                    machine_task.result() # Will raise if machine crashed
                except Exception as e:
                    raise RuntimeError(f"Machine crashed: {e}") from e
                
                raise RuntimeError("Machine stopped unexpectedly without producing a result (Idle?).")

    async def _stop_machine(self, task: asyncio.Task):
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _materialize_constants(self, graph: BipartiteGraph, store: InMemoryObjectStore):
        for node in graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                payload = node.initial_payload
                if payload is not None and not isinstance(payload, Ref):
                    meta = {}
                    if isinstance(payload, (int, float, bool, str)) and len(str(payload)) < 256:
                        meta["scalar_value"] = payload
                    
                    ref = store.put(payload, metadata=meta)
                    node.initial_payload = ref
                    logger.debug(f"Materialized constant for node {node.id} -> {ref.uri}")

    def _resolve_target_node_id(self, target: Any, ir_gen: IRGenerator) -> Optional[str]:
        if isinstance(target, (LazyResult, MappedLazyResult)):
            return ir_gen._visited.get(target._uuid)
        return None

    def _graft_egress(self, graph: BipartiteGraph, target_node_id: str, target_uuid: str):
        stain_id = PhysicalIdGenerator.stain_node(target_node_id)
        egress_id = f"egress.{target_uuid}"
        
        f_egress = PhysicsFuncNode(
            id=egress_id,
            name="Egress",
            input_ports={"in": PortDef("in", PortRole.DATA, "Token")},
            output_ports={},
        )
        graph.nodes[egress_id] = f_egress

        channel = Channel(
            source_node_id=stain_id,
            source_port="output_default",
            target_node_id=egress_id,
            target_port="in"
        )
        graph.channels.append(channel)
        logger.debug(f"Surgically grafted egress {egress_id} to {stain_id}")

    def _register_tasks(self, target: Any, registry: CodeRegistry, ir_gen: IRGenerator):
        lazy_results = self._collect_lazy_results(target)
        visited_map = ir_gen._visited
        nodes_map = ir_gen.nodes

        for uuid, lr in lazy_results.items():
            if uuid not in visited_map:
                continue
            
            node_id = visited_map[uuid]
            node_ir = nodes_map.get(node_id)
            
            if node_ir:
                canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
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
我们已经增强了 `VMExecutionStrategy` 的错误报告和鲁棒性。现在应该再次运行测试。如果测试失败，我们将得到一个明确的 `RuntimeError`，而不是含糊的 Timeout，这将极大帮助我们定位问题。

建议执行 `pytest packages/cascade-runtime/tests/integration/test_vm_strategy.py`。
