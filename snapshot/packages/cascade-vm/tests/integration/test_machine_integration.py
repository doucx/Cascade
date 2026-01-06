import asyncio
from typing import List, Any

import pytest

from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.nodes import Token
from cascade.runtime.storage import InMemoryObjectStore
from cascade.sdk import task as cs_task
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.linker import Linker
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import LocalComputeService, ComputeRequest
from cascade.vm.resource_registry import ResourceRegistry


@pytest.mark.asyncio
async def test_machine_end_to_end_integration():
    """
    This is the "gold standard" test for the Singularity architecture.
    It verifies that a task requiring asynchronous execution (a user function)
    can be dispatched to the ComputeService, and its result can be correctly
    routed back into the synchronous Reactor to trigger another downstream task
    also executed via the ComputeService.
    """
    # --- 1. Define Test Workflow (using SDK) ---
    # A shared list to capture the side-effect of the sink task
    results: List[Any] = []

    @cs_task
    async def async_add(a: int, b: int) -> int:
        await asyncio.sleep(0.01)  # Simulate I/O
        return a + b

    @cs_task
    def sink_task(value: int) -> None:
        # This sync task will also be run by the ComputeService in a thread pool.
        results.append(value)

    # The workflow: async_add(1, 2) -> sink_task(...)
    workflow = sink_task(async_add(1, 2))

    # --- 2. Compile the Workflow ---
    ir_generator = IRGenerator()
    graph_ir = ir_generator.generate(workflow)

    # Define an empty environment for this simple case
    environment = EnvironmentDef(resources=[])

    builder = Builder()
    assembly = builder.build(graph_ir, environment)

    # --- 3. Setup VM Components ---
    # Code Registry for the compute service
    code_registry = CodeRegistry()

    # The IR generator processes dependencies first (post-order traversal)
    add_node_ir = graph_ir.nodes[0]
    sink_node_ir = graph_ir.nodes[1]

    code_registry.register(
        add_node_ir.task.fingerprint["canonical_code_structure_hash"], async_add.func
    )
    code_registry.register(
        sink_node_ir.task.fingerprint["canonical_code_structure_hash"], sink_task.func
    )

    # Linker for the reactor kernel
    linker = Linker()
    function_map = linker.link(assembly, code_registry)

    # Memory and Queues
    memory = VolatileMemory()
    compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
    ingress_queue: asyncio.Queue[tuple[str, Token]] = asyncio.Queue()

    # Core Services
    object_store = InMemoryObjectStore()
    resource_registry = ResourceRegistry()
    resource_registry.register("system.compute_queue", compute_queue)
    resource_registry.register("system.object_store", object_store)

    # The Reactor (Physics Kernel)
    reactor = Reactor(
        graph=assembly.graph,
        memory=memory,
        function_map=function_map,
        resource_registry=resource_registry,
        ingress_queue=ingress_queue,
    )
    reactor.prime()

    # The Compute Service (Async Plane)
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
    )

    # The Machine (Coordinator)
    machine = Machine(
        reactor=reactor,
        compute_service=compute_service,
        ingress_queue=ingress_queue,
    )

    # --- 4. Run and Assert ---
    await machine.run()

    # Assert that the sink task was called with the correct result
    assert results == [3]