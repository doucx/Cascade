import asyncio
import logging
from typing import Any, Optional, Dict, Set

from cascade.spec.runtime.strategies import ExecutionStrategy, ExecutionContext
from cascade.spec.runtime.interfaces import Executor
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.assembly import CompilationArtifact
from cascade.spec.physical.object import Ref
from cascade.spec.ir.graph import GraphIR
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult

from cascade.vm.compute import BridgedComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.vm.registry import CodeRegistry
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.memory import VolatileMemory
from cascade.vm.linker import Linker
from cascade.bus.core import EventBus

from cascade.compiler.frontend import IRGenerator, GenerationResult
from cascade.compiler.backend import Builder

logger = logging.getLogger(__name__)


class RuntimeHarness:
    def __init__(
        self,
        context: ExecutionContext,
        executor: Executor,
        bus: EventBus,
        code_registry: CodeRegistry,
    ):
        self.context = context
        self.bus = bus

        # 1. Physical Buses (Queues)
        # VM <- Outside (Compute results, Timer events, User inputs)
        self.ingress_queue: asyncio.Queue = asyncio.Queue()
        # VM -> Outside (User Results)
        self.egress_queue: asyncio.Queue = asyncio.Queue()
        # VM -> Compute Service
        self.compute_queue: asyncio.Queue = asyncio.Queue()
        # VM -> Time Service
        self.chronos_queue: asyncio.Queue = asyncio.Queue()

        # 2. Signaling
        self.wakeup_event = asyncio.Event()

        # 3. Peripheral Services (Sidecars)
        # The BridgedComputeService adapts the VM's ComputeRequest protocol
        # to the Runtime's Executor protocol.
        self.compute_service = BridgedComputeService(
            executor=executor,
            store=context.object_store,
            registry=code_registry,
            inbound_queue=self.compute_queue,
            outbound_queue=self.ingress_queue,
            context=context,
            wakeup_event=self.wakeup_event,
        )

        self.chronos_service = ChronosService(
            inbound_queue=self.chronos_queue,
            outbound_queue=self.ingress_queue,
            wakeup_event=self.wakeup_event,
        )

        # 4. Resource Registry (The Environment)
        # Registers system-level resources that Kernel ICs (like egress, sleep) depend on.
        self.resource_registry = ResourceRegistry()
        self._register_system_resources()

    def _register_system_resources(self):
        self.resource_registry.register("system.egress_queue", self.egress_queue)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register(
            "system.object_store", self.context.object_store
        )
        self.resource_registry.register("system.event_bus", self.bus)


class VMExecutionStrategy(ExecutionStrategy):
    def __init__(self, executor: Executor, bus: EventBus):
        self.executor = executor
        self.bus = bus
        self.compiler_frontend = IRGenerator()
        self.compiler_backend = Builder()
        self.linker = Linker()

    async def execute(self, target: Any, context: ExecutionContext) -> Any:
        logger.info("VMStrategy: Starting execution cycle.")

        # --- Phase 1: Compilation ---
        logger.debug("VMStrategy: Compiling logical graph...")
        graph_ir_result = self.compiler_frontend.generate(target)
        graph_ir = graph_ir_result.ir

        # Build environment definition from IR requirements
        env_def = self._scan_resources(graph_ir)

        artifact = self.compiler_backend.build(graph_ir, environment=env_def)
        logger.debug("VMStrategy: Compilation complete.")

        # --- Phase 2: Linking ---
        logger.debug("VMStrategy: Linking code...")
        code_registry = self._link_code(graph_ir, graph_ir_result)

        # --- Phase 3: Bootstrap ---
        logger.debug("VMStrategy: Bootstrapping machine...")
        harness = RuntimeHarness(context, self.executor, self.bus, code_registry)

        function_map = self.linker.link(artifact.assembly, code_registry)
        kernel = PhysicsKernel(function_map, harness.resource_registry)

        memory = VolatileMemory()
        reactor = Reactor(
            graph=artifact.assembly.graph,
            memory=memory,
            kernel=kernel,
            ingress_queue=harness.ingress_queue,
        )
        machine = Machine(
            reactor=reactor,
            compute_service=harness.compute_service,
            chronos_service=harness.chronos_service,
            wakeup_event=harness.wakeup_event,
        )

        # --- Phase 4: Ignition ---
        logger.debug("VMStrategy: Igniting reactor...")
        self._materialize_constants(artifact, context)
        reactor.prime(genesis_trace={"rid": context.run_id})

        # --- Phase 5: Run Loop & Harvesting ---
        logger.debug("VMStrategy: Running...")
        machine_task = asyncio.create_task(machine.run())

        try:
            return await self._run_and_harvest(
                target, artifact, harness, machine_task, context
            )
        except Exception as e:
            logger.error(f"VM execution failed: {e}")
            raise
        finally:
            # Ensure machine is stopped
            if not machine_task.done():
                reactor.shutdown_event.set()
                # Use a shield or separate wait to ensure cancellation doesn't block forever
                try:
                    await asyncio.wait_for(machine_task, timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass

    def _scan_resources(self, graph_ir: GraphIR) -> EnvironmentDef:
        required_resources: Set[str] = set()
        for node in graph_ir.nodes:
            if node.constraints:
                required_resources.update(node.constraints.keys())

        # For now, we assume all resources are 'discrete' with default capacity.
        # In the future, this could be enriched by a global ResourceManager config.
        resources = [
            ResourceDef(name=r, type="discrete", capacity=100)
            for r in required_resources
        ]
        return EnvironmentDef(resources=resources)

    def _link_code(self, graph_ir: GraphIR, result: GenerationResult) -> CodeRegistry:
        registry = CodeRegistry()
        for node_ir in graph_ir.nodes:
            # Only task nodes need code linking (not map nodes, params, etc. if handled purely by graph)
            # Actually, map nodes might have a factory.
            # The frontend provides 'executables' keyed by instance hash.
            instance_hash = node_ir.current_node_instance_hash
            canonical_hash = node_ir.task.fingerprint.get(
                "canonical_code_structure_hash"
            )

            if canonical_hash and instance_hash in result.executables:
                func = result.executables[instance_hash]
                if not registry.has(canonical_hash):
                    registry.register(canonical_hash, func)

        return registry

    def _materialize_constants(
        self, artifact: CompilationArtifact, context: ExecutionContext
    ) -> None:
        for node in artifact.assembly.graph.nodes.values():
            if (
                isinstance(node, PhysicsDataNode)
                and node.initial_tokens > 0
                and node.id.startswith("const.")
            ):
                payload = node.initial_payload
                # If payload is already a Ref, we assume it's valid.
                if isinstance(payload, Ref):
                    continue

                # Materialize raw value
                meta = {}
                # Scalar Hoisting: If it's a simple type, hoist it to metadata
                # so the Kernel (e.g. allocators) can read it without I/O.
                if (
                    isinstance(payload, (int, float, bool, str))
                    and len(str(payload)) < 256
                ):
                    meta["scalar_value"] = payload

                ref = context.object_store.put(payload, metadata=meta)
                node.initial_payload = ref

    async def _run_and_harvest(
        self,
        target: Any,
        artifact: CompilationArtifact,
        harness: RuntimeHarness,
        machine_task: asyncio.Task,
        context: ExecutionContext,
    ) -> Any:
        # 1. Identify Target Egress Nodes
        # We need to map Physical Egress ID -> Logical Target Component

        # Targets can be: Single Object, List, Tuple, Dict
        # We need to reconstruct the structure with results.

        # Flatten the target structure to find all LazyResults we need to wait for
        # Map: Logical UUID -> (Physical Egress ID, Placeholder Setter)
        # But here we just need to collect them.

        target_map: Dict[str, str] = {}  # UUID -> Egress Node ID

        def _register_target(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                # Look up physical egress ID in manifest
                # The manifest keys exit_points by logical UUID
                if obj._uuid in artifact.manifest.exit_points:
                    target_map[obj._uuid] = artifact.manifest.exit_points[obj._uuid]
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _register_target(item)
            elif isinstance(obj, dict):
                for item in obj.values():
                    _register_target(item)

        _register_target(target)

        if not target_map:
            # Edge case: No targets (e.g. empty list). Wait for machine stop?
            # Or just return empty structure.
            # But the machine might still be running side effects.
            # For robustness, we wait for drain if no targets.
            logger.warning("No targets identified for harvesting.")
            # For now, return target as is (it might be a literal)
            return target

        # 2. Harvesting Loop
        collected_results: Dict[str, Any] = {}  # UUID -> Result Value
        pending_uuids = set(target_map.keys())

        # Reverse map for quick lookup: Egress ID -> UUID
        egress_to_uuid = {v: k for k, v in target_map.items()}

        # Task management: We hold the egress reading task across loop iterations
        # if it hasn't completed yet.
        egress_task: Optional[asyncio.Task] = None

        try:
            while pending_uuids:
                if egress_task is None:
                    egress_task = asyncio.create_task(harness.egress_queue.get())

                # Wait for either a result OR the machine stopping
                done, pending = await asyncio.wait(
                    [egress_task, machine_task], return_when=asyncio.FIRST_COMPLETED
                )

                if machine_task in done:
                    # Machine stopped before we got all results
                    try:
                        machine_task.result()
                    except Exception as e:
                        raise RuntimeError(
                            f"Machine crashed during execution: {e}"
                        ) from e

                    raise RuntimeError(
                        f"Machine stopped prematurely. Pending targets: {pending_uuids}"
                    )

                if egress_task in done:
                    # We have a result token
                    egress_id, token = await egress_task
                    egress_task = None  # Reset for next iteration

                    if egress_id in egress_to_uuid:
                        uuid = egress_to_uuid[egress_id]

                        # 3. Dereference Result
                        val = token.payload
                        if isinstance(val, Ref):
                            val = context.object_store.get(val)

                        # 4. Check for Error (Exception Propagation)
                        if isinstance(val, Exception):
                            raise val

                        collected_results[uuid] = val
                        if uuid in pending_uuids:
                            pending_uuids.remove(uuid)
        finally:
            # Cleanup: Cancel pending egress read if we are exiting (e.g. on error)
            if egress_task and not egress_task.done():
                egress_task.cancel()
                try:
                    await egress_task
                except asyncio.CancelledError:
                    pass

        # 5. Reassemble Result Structure
        def _reassemble(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return collected_results[obj._uuid]
            elif isinstance(obj, list):
                return [_reassemble(x) for x in obj]
            elif isinstance(obj, tuple):
                return tuple(_reassemble(x) for x in obj)
            elif isinstance(obj, dict):
                return {k: _reassemble(v) for k, v in obj.items()}
            return obj

        return _reassemble(target)
