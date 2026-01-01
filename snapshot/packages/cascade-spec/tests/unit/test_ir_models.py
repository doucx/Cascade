import json
from dataclasses import asdict

import pytest

from cascade.spec.ir.models import (
    GraphIR,
    NodeIR,
    EdgeIR,
    TaskDef,
    ArgumentDef,
    ArgumentKind,
    Instruction,
    Call,
    Return,
)
from cascade.spec.fingerprint import Fingerprint


def test_ir_structures_exist():
    """Verify that GraphIR, NodeIR, and EdgeIR can be instantiated."""
    # This test will fail until the models are created.
    fp = Fingerprint()
    fp["current_code_structure_hash"] = "test_hash"

    task_def = TaskDef(name="test_task", args=[], fingerprint=fp)

    node = NodeIR(
        current_node_instance_hash="node_1",
        definition=task_def,
        kwargs={"x": 1, "y": "hello"},
    )

    edge = EdgeIR(
        source_node_instance_hash="node_1",
        target_node_instance_hash="node_2",
        target_arg="data",
    )

    graph = GraphIR(nodes=[node], edges=[edge], meta={"version": "1.0"})

    assert graph.nodes[0].current_node_instance_hash == "node_1"
    assert graph.edges[0].source_node_instance_hash == "node_1"
    assert graph.meta["version"] == "1.0"


def test_ir_serialization_roundtrip():
    """Verify that IR structures can be serialized to and from JSON."""
    fp = Fingerprint()
    fp["current_code_structure_hash"] = "test_hash"

    arg_def = ArgumentDef(name="arg1", kind=ArgumentKind.POSITIONAL_OR_KEYWORD)
    task_def = TaskDef(name="test_task", args=[arg_def], fingerprint=fp)

    node = NodeIR(
        current_node_instance_hash="n1", definition=task_def, kwargs={"val": 42}
    )

    graph = GraphIR(nodes=[node], edges=[])

    # Convert to dictionary using dataclasses.asdict
    data = asdict(graph)

    # Verify key fields
    assert data["nodes"][0]["current_node_instance_hash"] == "n1"
    assert data["nodes"][0]["kwargs"]["val"] == 42
    assert data["nodes"][0]["definition"]["name"] == "test_task"
    assert data["nodes"][0]["definition"]["args"][0]["kind"] == "POSITIONAL_OR_KEYWORD"

    # Verify JSON serialization compatibility
    json_str = json.dumps(data)
    loaded = json.loads(json_str)

    assert loaded["nodes"][0]["current_node_instance_hash"] == "n1"


def test_instruction_serialization():
    """Verify that Instruction dataclasses can be instantiated and serialized."""
    # This test covers the second part of Phase 0's implementation goal.
    call_instruction = Call(
        id="instr_1",
        task_name="my_task",
        args=[1, "hello"],
        output_register="r0",
    )
    return_instruction = Return(id="instr_2", source_register="r0")

    program: list[Instruction] = [call_instruction, return_instruction]

    # This crude serialization check is enough to drive the implementation.
    # We are not using asdict because Instruction is a base class.
    # A real implementation would need a polymorphic serializer.
    serialized = [
        {"type": "Call", "id": i.id, "task": i.task_name}
        if isinstance(i, Call)
        else {"type": "Return", "id": i.id, "source": i.source_register}
        for i in program
    ]

    json_str = json.dumps(serialized)
    loaded = json.loads(json_str)

    assert len(loaded) == 2
    assert loaded[0]["type"] == "Call"
    assert loaded[1]["source"] == "r0"
