from typing import Any, Dict
import asyncio

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
            resource_registry=resource_registry,
        )

        # Prime the reactor (fill constants, pulses)
        reactor.prime()

        # Result Future
        result_future = asyncio.get_running_loop().create_future()

        # Identify Target Physical Node for Sinking Result
        # We need the Physical ID of the target's Stainer.
        # 1. Find the NodeIR for the target.
        # target is a LazyResult. We have its UUID.
        # target_uuid = target._uuid if hasattr(target, "_uuid") else None

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
        # Use a visited set to handle cycles (though LR graph should be DAG) and avoid redundant work
        results = {}
        self._visit(target, results, set())
        return results

    def _visit(self, obj: Any, results: Dict[str, Any], visited: set) -> None:
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            if obj._uuid in visited:
                return
            visited.add(obj._uuid)
            results[obj._uuid] = obj

            # 1. Data Dependencies (Args/Kwargs)
            if hasattr(obj, "args"):
                for arg in obj.args:
                    self._visit(arg, results, visited)
            if hasattr(obj, "kwargs"):
                for v in obj.kwargs.values():
                    self._visit(v, results, visited)
            if hasattr(obj, "mapping_kwargs"):
                for v in obj.mapping_kwargs.values():
                    self._visit(v, results, visited)

            # 2. Control Dependencies
            if obj._condition:
                self._visit(obj._condition, results, visited)
            
            for dep in obj._dependencies:
                self._visit(dep, results, visited)

            # 3. Constraint Dependencies (Dynamic resource amounts)
            if obj._constraints:
                for req in obj._constraints.requirements.values():
                    self._visit(req, results, visited)

            # 4. Jump/Router Dependencies (Recursion/Branching)
            if hasattr(obj, "_jump_selector") and obj._jump_selector:
                selector = obj._jump_selector
                for route_lr in selector.routes.values():
                    if route_lr:
                        self._visit(route_lr, results, visited)

        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._visit(item, results, visited)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._visit(v, results, visited)
