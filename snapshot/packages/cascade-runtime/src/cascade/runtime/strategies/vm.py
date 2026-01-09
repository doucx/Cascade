import asyncio
import logging
from typing import Any, Dict, Optional, cast

from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.object import Ref

from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder

from cascade.reflection import TaskAnalyzer

from cascade.vm.registry import CodeRegistry
from cascade.vm.harness import EventDrivenRunner

from cascade.runtime.services.observability.bus import EventBus
from cascade.runtime.strategies import ExecutionContext

logger = logging.getLogger(__name__)


class VMExecutionStrategy:
    def __init__(
        self,
        bus: EventBus,
        environment: Optional[EnvironmentDef] = None,
    ):
        self.bus = bus
        self.environment = environment or EnvironmentDef(resources=[])
        # Compiler components
        self.ir_generator = IRGenerator()
        self.builder = Builder()

    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any:
        run_id = context.run_id
        logger.info(f"VMStrategy starting execution for run_id={run_id}")

        # 1. Compile: LazyResult -> GraphIR
        # The IRGenerator treats the target as the root(s)
        gen_result = self.ir_generator.generate(target)
        graph_ir = gen_result.ir
        
        # 2. Build: GraphIR -> Assembly (Physical Graph)
        # We use the environment definition passed in init (or default)
        artifact = self.builder.build(graph_ir, self.environment)
        assembly = artifact.assembly
        manifest = artifact.manifest

        # 3. Link: Populate CodeRegistry
        # We need to map the Canonical Code Hashes (from IR/Assembly) to the actual Callables (from GenerationResult)
        code_registry = CodeRegistry()
        
        # Iterate over all nodes in the IR to match hashes with executables
        for node_ir in graph_ir.nodes:
            # Only nodes that carry code need registration
            if node_ir.current_node_instance_hash in gen_result.executables:
                executable = gen_result.executables[node_ir.current_node_instance_hash]
                # The canonical hash is in the TaskDef fingerprint
                canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
                
                # Register idempotent-ly
                if not code_registry.has(canonical_hash):
                    code_registry.register(canonical_hash, executable)

        # 4. Instantiate VM Runner
        runner = EventDrivenRunner.from_assembly(assembly, code_registry)
        
        # Inject Run ID into the runner (it generates its own usually, but we want to trace it)
        runner.run_id = run_id
        
        # Bridge Telemetry: Subscribe the Engine's bus to the VM's events
        # Note: EventDrivenRunner has its own internal EventBus. We bridge them.
        # Simple bridge: forward all events.
        # In a production system we might filter or transform.
        runner.event_bus.subscribe(
            cast(Any, object),  # Subscribe to root Event class (duck typing for now as classes might differ in import path context)
            lambda event: self.bus.publish(event)
        )

        # 5. Execute
        try:
            await runner.start_loop()
            runner.prime()

            # Determine the logical ID of the target to find its exit point
            target_logical_id: str
            if isinstance(target, (LazyResult, MappedLazyResult)):
                target_logical_id = target._uuid
            else:
                # If target is a list or literal, IRGenerator handles it, 
                # but 'target' object itself won't be in the manifest as a single root.
                # For MVP, we assume target is a single LazyResult.
                # If it's a list, we'd need to wait for all of them.
                raise NotImplementedError("VMStrategy currently supports single LazyResult targets only.")

            # Find the Physical Egress Node ID from the Manifest
            if target_logical_id not in manifest.exit_points:
                raise RuntimeError(
                    f"Target {target_logical_id} has no compiled exit point in the manifest. "
                    "Did the compiler generate an Egress node?"
                )
            
            egress_node_id = manifest.exit_points[target_logical_id]

            # Wait for the target task to complete execution
            # We wait for the logical task's completion event.
            # The EventDrivenRunner emits events using the *base* physical ID (typically the instance hash).
            # The manifest maps logical_id -> physical_base_id.
            target_physical_base = manifest.logical_to_physical_map[target_logical_id]
            
            logger.info(f"Waiting for completion of task {target_physical_base}...")
            await runner.run_until_complete(target_physical_base)

            # 6. Extract Result
            # The result should now be waiting in the Egress Data Node.
            # We peek directly into the VM's volatile memory.
            try:
                result_token = runner.memory.take(egress_node_id)
                # The token payload is a Ref (Reference to ObjectStore)
                result_ref = result_token.payload
                
                if isinstance(result_ref, Ref):
                    final_result = runner.object_store.get(result_ref)
                else:
                    # Scalar hoisting might have happened (if implemented), or raw value for simple types
                    final_result = result_ref
                    
                return final_result

            except Exception as e:
                logger.error(f"Failed to extract result from egress node {egress_node_id}: {e}")
                raise

        finally:
            await runner.stop_loop()