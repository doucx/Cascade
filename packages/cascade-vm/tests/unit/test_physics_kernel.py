import pytest
from typing import Dict, Any

from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel.core import PhysicsKernel


# --- Kernel Function Mocks ---


def kernel_identity(
    inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: Any
) -> Dict[str, Ref]:
    # Simple pass-through: input 'in' -> output 'out'
    return {"out": inputs["in"]}


def kernel_resource_access(
    inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: ResourceRegistry
) -> Dict[str, Ref]:
    # Validates that we can access resources
    config = resources.get("config")
    # Return a synthetic Ref based on config (just for testing logic)
    return {"out": Ref(uri=f"mem://config-{config['version']}")}


def kernel_fail(
    inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: Any
) -> Dict[str, Ref]:
    raise RuntimeError("Kernel Crash")


# --- Tests ---


@pytest.fixture
def resources():
    r = ResourceRegistry()
    r.register("config", {"version": "1.0"})
    return r


@pytest.fixture
def kernel(resources):
    func_map = {
        "node_ident": kernel_identity,
        "node_res": kernel_resource_access,
        "node_fail": kernel_fail,
    }
    return PhysicsKernel(func_map, resources)


def test_kernel_identity_execution(kernel):
    node = PhysicsFuncNode(id="node_ident", name="Identity")
    input_ref = Ref(uri="mem://input-123")

    inputs = {"in": input_ref}
    outputs = kernel.execute(node, inputs)

    assert outputs["out"] == input_ref


def test_kernel_resource_access(kernel):
    node = PhysicsFuncNode(id="node_res", name="ResourceUser")

    outputs = kernel.execute(node, {})

    assert outputs["out"].uri == "mem://config-1.0"


def test_kernel_missing_mapping(kernel):
    node = PhysicsFuncNode(id="node_unknown", name="Unknown")

    with pytest.raises(ValueError, match="No kernel function mapped"):
        kernel.execute(node, {})


def test_kernel_exception_propagation(kernel):
    node = PhysicsFuncNode(id="node_fail", name="FailNode")

    with pytest.raises(RuntimeError, match="Kernel Crash"):
        kernel.execute(node, {})
