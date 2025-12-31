import pytest
from cascade.compiler.backend import Backend
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, InjectionIR
from cascade.spec.blueprint import ResourceOperand, Call
from cascade.spec.fingerprint import Fingerprint

class MockPolicy:
    def __init__(self, retry=None, resources=None):
        self.retry = retry
        self.resources = resources or {}

def _create_dummy_task_def(name):
    fp = Fingerprint.from_dict({"current_code_structure_hash": "h"})
    return TaskDef(name=name, args=[], fingerprint=fp)

def test_backend_compiles_injection_to_resource_operand():
    """
    验证 Backend 将 NodeIR 中的 InjectionIR 转换为 Call 指令中的 ResourceOperand。
    """
    # 1. 手动构造包含 InjectionIR 的 GraphIR
    task_def = _create_dummy_task_def("db_task")
    node = NodeIR(
        current_node_instance_hash="n1", 
        definition=task_def,
        kwargs={
            "conn": InjectionIR(resource_name="postgres_prod") # Expectation
        }
    )
    
    graph = GraphIR(nodes=[node], edges=[])
    plan = [["n1"]]

    # 2. Compile
    blueprint = Backend.compile(graph, plan)
    
    # 3. Assert
    instr = blueprint.instructions[0]
    assert isinstance(instr, Call)
    
    operand = instr.kwargs["conn"]
    assert isinstance(operand, ResourceOperand)
    assert operand.name == "postgres_prod"

def test_backend_transfers_policy_to_instruction():
    """
    验证 Backend 将 NodeIR.policy 转移到 Call.policy。
    """
    task_def = _create_dummy_task_def("retry_task")
    
    # 模拟 IR 携带的策略
    policy_data = MockPolicy(resources={"cpu": 4})
    node = NodeIR(current_node_instance_hash="n1", definition=task_def, policy=policy_data) # Expectation: policy field on NodeIR
    
    graph = GraphIR(nodes=[node], edges=[])
    plan = [["n1"]]

    blueprint = Backend.compile(graph, plan)
    instr = blueprint.instructions[0]
    
    assert instr.policy is not None
    assert instr.policy.resources["cpu"] == 4