import asyncio
import time
from typing import Any, Dict, List, Callable, Optional, Union
from contextlib import ExitStack

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.environment import EnvironmentDef
from cascade.spec.physics import Token, PhysicsFuncNode
from cascade.spec.ports import PortName

from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.reflection import PhysicalIdGenerator, ReflectionAnalyzer

from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry

from cascade.runtime.strategies.base import ExecutionContext
from cascade.runtime.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    Event,
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

        # 3. Build Function Map (The "Linker")
        # ------------------------------------
        function_map: Dict[str, Callable] = {}
        
        # 3.1 Link User Functions (Workers)
        # We need to traverse the target again to find the actual callables
        # because GraphIR only contains metadata.
        # This is a temporary dependency walker until Compiler handles this.
        lazy_results_map = self._collect_lazy_results(target)
        
        # Link mapping: Physical Node ID -> Python Callable
        for lr_uuid, lr in lazy_results_map.items():
            # Calculate the canonical ID logic matching the Compiler
            # Note: This relies on IRGenerator and Builder being deterministic
            # and us finding the correct NodeIR match. 
            # For the prototype, we assume we can look up by logical ID if we had it,
            # but here we rely on the compiler's output structure.
            
            # WORKAROUND: We iterate the generated GraphIR to find the mapping 
            # between UUID and Canonical Hash.
            node_ir = next((n for n in graph_ir.nodes if n.task.name == lr.task.__name__), None) 
            # The above is risky if multiple tasks have same name. 
            # Correct approach: IRGenerator should expose a UUID map or we recreate logic.
            # For this prototype, we'll assume we can use the `current_node_instance_hash` 
            # if we replicate the hashing logic. 
            # Actually, `IRGenerator` generates IDs. We need that map.
            pass

        # REVISIT: The IRGenerator does not expose the map. 
        # Strategy: We will use a dynamic dispatch inside the worker implementation
        # or we rely on the fact that `IRGenerator` *returns* the target's Node ID.
        # But we need to link ALL nodes, not just the target.
        
        # Let's take a shortcut for the Prototype:
        # We will iterate the physical graph, find all ".worker" nodes, 
        # extract their logical ID prefix, and try to match it? No, physical IDs are hashes.
        
        # CORRECT STRATEGY FOR PROTOTYPE:
        # We will perform a parallel traversal or simply ask IRGenerator to generate again?
        # No, `IRGenerator` is stateful.
        
        # Let's rebuild the `executable_registry` using the v2.0 logic, 
        # which we know works and maps Hash -> Callable.
        from cascade.graph.build import build_graph
        from cascade.graph.registry import NodeRegistry
        
        v2_registry = NodeRegistry()
        _, _, executable_registry = build_graph(target, registry=v2_registry)

        for node_hash, func in executable_registry.items():
            worker_id = PhysicalIdGenerator.worker_node(node_hash)
            function_map[worker_id] = self._make_worker_wrapper(func)

        # 3.2 Link Infrastructure Functions (Bleacher, Stainer, Observer)
        for node in physical_graph.nodes.values():
            if node.id.endswith(".bleach"):
                function_map[node.id] = self._standard_bleacher
            elif node.id.endswith(".stain"):
                function_map[node.id] = self._standard_stainer
            elif node.id == PhysicalIdGenerator.observability_observer():
                function_map[node.id] = self._standard_observer
            elif "pulse" in node.id:
                # Pulse sources are DataNodes, no function needed
                pass
            elif "probe" in node.id:
                 function_map[node.id] = self._standard_probe

        # 4. Reactor & Bridge Setup
        # -------------------------
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

        # Identify Target Physical Node
        # We need the Node ID of the target.
        # IRGenerator.generate returns GraphIR. The last node added isn't necessarily target.
        # But `compiler.generate` returns GraphIR, and we don't know which one is target.
        # HACK: We re-compute the hash for the target using HashingService directly.
        from cascade.reflection import HashingService
        # This is tricky without the full dependency map.
        # Let's use the v2 executable_registry keys we just built!
        # The target's UUID is in `target._uuid`.
        # Wait, v2 `build_graph` returns `instance_map` which maps UUID -> Node.
        _, instance_map, _ = build_graph(target, registry=v2_registry)
        target_v2_node = instance_map[target._uuid]
        target_hash = target_v2_node.current_node_instance_hash
        
        target_stainer_id = PhysicalIdGenerator.stain_node(target_hash)

        # Bridge: Sink to Future
        def _result_sink(token: Token):
            if not result_future.done():
                result_future.set_result(token.payload)
        
        reactor.add_sink(target_stainer_id, "output_default", _result_sink)

        # 5. Execution Loop
        # -----------------
        try:
            while not result_future.done():
                fired = await reactor.step()
                if fired == 0 and not result_future.done():
                    # If we stall but haven't got a result, check for errors or deadlocks
                    # For prototype, just small sleep
                    await asyncio.sleep(0.001)
                    
                    # Optional: Check if total energy is 0 (Heat Death)
                    # if total_tokens == 0: break
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

    # --- Standard Triad Implementations (Micro-Kernel) ---

    def _make_worker_wrapper(self, func: Callable) -> Callable:
        """Wraps a user function to match the (inputs, node, resources) signature."""
        async def _wrapper(inputs: Dict[str, Token], node: Any, resources: Any) -> Dict[str, Token]:
            # Unpack inputs. The Bleacher put them in 'worker_input'
            # payload is the dict of {arg_name: val}
            kwargs = inputs["worker_input"].payload
            
            # Execute
            if asyncio.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)
                
            return {"worker_result": Token(payload=result)}
        return _wrapper

    async def _standard_bleacher(self, inputs: Dict[str, Token], node: Any, resources: Any) -> Dict[str, Token]:
        """
        F_pre: Joins all inputs and produces a single dict for the worker.
        Also emits start trace.
        """
        # 1. Collect Data Args
        # The node def has input ports. We assume all DATA inputs are arguments.
        # We need to look at the node definition to know which port maps to which arg?
        # Or we just take all inputs that are not special signals.
        worker_kwargs = {}
        start_ts = time.time()
        
        for port, token in inputs.items():
            if port in ["condition", PortName.PULSE] or port.startswith("wait_for_"):
                continue
            worker_kwargs[port] = token.payload
            
        # 2. Emit Start Trace
        # In a real impl, this goes to D_trace. 
        # For this prototype, we just pack it into trace_output
        trace = {"start_ts": start_ts, "node_id": node.id}
        
        # 3. Output
        return {
            "worker_input": Token(payload=worker_kwargs),
            "trace_output": Token(payload=trace),
            "obs_output": Token(payload={"event": "start", "ts": start_ts}) 
        }

    async def _standard_stainer(self, inputs: Dict[str, Token], node: Any, resources: Any) -> Dict[str, Token]:
        """
        F_post: Routes the result.
        """
        result = inputs["worker_result"].payload
        trace = inputs["trace_input"].payload
        
        # Simple default routing for now
        return {
            "output_default": Token(payload=result, trace=trace),
            "obs_output": Token(payload={"event": "end", "ts": time.time()})
        }
        
    async def _standard_observer(self, inputs: Dict[str, Token], node: Any, resources: Any) -> Dict[str, Token]:
        """
        F_obs: Bridges to the Engine EventBus.
        """
        raw_event = inputs["event_token"].payload
        # Determine Logical Node ID (strip suffix)
        # The trace or payload should contain the source node ID.
        # But here we simplified.
        
        # For the prototype, we simply map "start" -> TaskExecutionStarted
        # This is a bit lossy without the full Trace object, but proves the bridge works.
        
        if raw_event["event"] == "start":
            self.bus.publish(TaskExecutionStarted(task_id="vm-node", task_name="vm-task"))
        elif raw_event["event"] == "end":
             self.bus.publish(TaskExecutionFinished(task_id="vm-node", task_name="vm-task", status="Succeeded"))
             
        return {}

    async def _standard_probe(self, inputs: Dict[str, Token], node: Any, resources: Any) -> Dict[str, Token]:
        """F_probe: Identity pass-through for constants."""
        return {"out": inputs["value"]}
