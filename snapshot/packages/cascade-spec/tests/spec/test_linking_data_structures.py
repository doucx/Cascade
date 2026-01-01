import pytest

# 这些导入在 RED 阶段可能会失败，或者在实例化时报错
from cascade.spec.blueprint import Call, MapCall, Register


def test_call_instruction_has_structure_hash():
    """
    验证 Call 指令包含 structure_hash 字段。
    这是链接阶段查找函数实现的键。
    """
    try:
        # 尝试用 kwargs 实例化，如果字段不存在会报错
        # output 使用 dummy Register
        Call(
            output=Register(0),
            task_name="t",
            structure_hash="hash_123",
        )
    except TypeError as e:
        if "unexpected keyword argument 'structure_hash'" in str(e):
            pytest.fail("Call instruction missing 'structure_hash' field")
        raise e


def test_map_call_instruction_has_structure_hash():
    """
    验证 MapCall 指令也包含 structure_hash 字段。
    """
    try:
        MapCall(
            output=Register(0),
            task_name="t",
            structure_hash="hash_123",
        )
    except TypeError as e:
        if "unexpected keyword argument 'structure_hash'" in str(e):
            pytest.fail("MapCall instruction missing 'structure_hash' field")
        raise e


def test_compilation_result_structure():
    """
    验证 CompilationResult 类的存在及其结构。
    它负责在 Frontend 和 Runtime 之间传递 IR 和 Symbol Table。
    """
    # 尝试导入 CompilationResult (目前不存在)
    try:
        from cascade.spec.compiler_result import CompilationResult
    except ImportError:
        pytest.fail("Could not import cascade.spec.compiler_result.CompilationResult")

    # 验证字段 (运行时检查)
    # 我们传入 None 作为占位符，仅检查字段是否存在
    try:
        res = CompilationResult(ir=None, symbol_table={})
    except TypeError as e:
        pytest.fail(f"CompilationResult instantiation failed: {e}")

    assert hasattr(res, "ir")
    assert hasattr(res, "symbol_table")
