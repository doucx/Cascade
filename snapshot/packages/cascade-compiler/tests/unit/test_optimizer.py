import pytest

# These are defined in Phase 1, so they should import correctly.
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint

from cascade.compiler.optimizer import Optimizer, ExecutionPlan
from cascade.compiler.exceptions import CycleDetectedError


def _create_dummy_node_ir(node_id: str) -> NodeIR:
    """Helper to create a minimal NodeIR for topology tests."""
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_for_{node_id}"})
    task_def = TaskDef(name=node_id, args=[], fingerprint=fp)
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)


def test_optimizer_detects_cycle():
    """
    Case 1: Cycle Detection
    Verify that the optimizer raises CycleDetectedError for a graph with a loop.
    """
    node_a = _create_dummy_node_ir("A")
    node_b = _create_dummy_node_ir("B")

    # A -> B -> A
    cyclic_ir = GraphIR(
        nodes=[node_a, node_b],
        edges=[
            EdgeIR(
                source_node_instance_hash="A",
                target_node_instance_hash="B",
                target_arg="data",
            ),
            EdgeIR(
                source_node_instance_hash="B",
                target_node_instance_hash="A",
                target_arg="data",
            ),
        ],
    )

    with pytest.raises(CycleDetectedError):
        Optimizer.optimize(cyclic_ir)


def test_optimizer_schedules_diamond_graph():
    """
    Case 2: Topological Sort of a diamond dependency graph.
    A -> B, A -> C, B -> D, C -> D
    """
    node_a = _create_dummy_node_ir("A")
    node_b = _create_dummy_node_ir("B")
    node_c = _create_dummy_node_ir("C")
    node_d = _create_dummy_node_ir("D")

    diamond_ir = GraphIR(
        nodes=[node_a, node_b, node_c, node_d],
        edges=[
            EdgeIR(
                source_node_instance_hash="A",
                target_node_instance_hash="B",
                target_arg="a_val",
            ),
            EdgeIR(
                source_node_instance_hash="A",
                target_node_instance_hash="C",
                target_arg="a_val",
            ),
            EdgeIR(
                source_node_instance_hash="B",
                target_node_instance_hash="D",
                target_arg="b_val",
            ),
            EdgeIR(
                source_node_instance_hash="C",
                target_node_instance_hash="D",
                target_arg="c_val",
            ),
        ],
    )

    plan: ExecutionPlan = Optimizer.optimize(diamond_ir)

    # Expected plan is 3 stages
    assert len(plan) == 3

    # Stage 0: Must contain only A
    assert plan[0] == ["A"]

    # Stage 1: Must contain B and C (order is not guaranteed)
    assert set(plan[1]) == {"B", "C"}

    # Stage 2: Must contain only D
    assert plan[2] == ["D"]
