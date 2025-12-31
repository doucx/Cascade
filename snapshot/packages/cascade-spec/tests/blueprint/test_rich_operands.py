import pytest
from dataclasses import is_dataclass
from cascade.spec.blueprint import Call, Register, Literal, ContextOperand, ResourceOperand, Operand

def test_resource_operand_structure():
    """
    验证 ResourceOperand 的存在和结构。
    它用于在指令层面表示 'cs.inject("db")'，推迟解析到运行时。
    """
    try:
        # 对应 code: cs.inject("db_connection")
        op = ResourceOperand(name="db_connection")
    except NameError:
        pytest.fail("ResourceOperand class is not defined in cascade.spec.blueprint")

    assert is_dataclass(op)
    assert isinstance(op, Operand)
    assert op.name == "db_connection"

def test_context_operand_structure():
    """
    验证 ContextOperand 的存在和结构。
    它用于直接从运行时上下文（如 params, env）中加载数据，
    这对应 'cs.Param("env_name")' 的编译结果。
    """
    try:
        # 对应 code: cs.Param("env_name")
        op = ContextOperand(scope="params", key="env_name")
    except NameError:
        pytest.fail("ContextOperand class is not defined in cascade.spec.blueprint")

    assert is_dataclass(op)
    assert isinstance(op, Operand)
    assert op.scope == "params"
    assert op.key == "env_name"

def test_call_instruction_accepts_polymorphic_operands():
    """
    验证 Call 指令的 args/kwargs 可以混合接受 Literal, Register 以及新的 Operand 类型。
    """
    # 构造混合参数列表
    mixed_args = [
        Literal(1),                      # 常量
        Register(0),                     # 运行时中间结果
        ResourceOperand("db"),           # 依赖注入
        ContextOperand("params", "key")  # 全局参数
    ]
    
    try:
        instr = Call(
            output=Register(1),
            task_name="test_task",
            args=mixed_args,
            kwargs={"ctx": ContextOperand("env", "HOME")},
            structure_hash="hash_abc"
        )
    except TypeError as e:
        pytest.fail(f"Call instruction failed to accept polymorphic operands: {e}")
    
    # 验证类型保持
    assert isinstance(instr.args[2], ResourceOperand)
    assert isinstance(instr.args[3], ContextOperand)
    assert isinstance(instr.kwargs["ctx"], ContextOperand)