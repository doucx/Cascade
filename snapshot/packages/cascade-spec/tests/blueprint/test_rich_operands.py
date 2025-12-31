import pytest
from dataclasses import is_dataclass
from cascade.spec.blueprint import Call, Register, Literal, ContextOperand, ResourceOperand

def test_resource_operand_structure():
    """
    验证 ResourceOperand 的存在和结构。
    用于替代运行时魔法 ArgumentResolver，显式表达 'cs.inject'。
    """
    try:
        # 对应 code: cs.inject("db_connection")
        op = ResourceOperand(name="db_connection")
    except NameError:
        pytest.fail("ResourceOperand class is not defined in cascade.spec.blueprint")

    assert is_dataclass(op)
    assert op.name == "db_connection"

def test_context_operand_structure():
    """
    验证 ContextOperand 的存在和结构。
    用于直接从 params/context 中加载数据，对应 'cs.Param' 的优化编译。
    """
    try:
        # 对应 code: cs.Param("env_name")
        op = ContextOperand(scope="params", key="env_name")
    except NameError:
        pytest.fail("ContextOperand class is not defined in cascade.spec.blueprint")

    assert is_dataclass(op)
    assert op.scope == "params"
    assert op.key == "env_name"

def test_call_instruction_accepts_polymorphic_operands():
    """
    验证 Call 指令的 args/kwargs 可以接受新的 Operand 类型。
    """
    instr = Call(
        output=Register(0),
        task_name="test_task",
        args=[
            Literal(1), 
            ResourceOperand("db"), 
            ContextOperand("params", "timeout")
        ],
        kwargs={},
        structure_hash="hash_abc"
    )
    
    assert isinstance(instr.args[1], ResourceOperand)
    assert isinstance(instr.args[2], ContextOperand)