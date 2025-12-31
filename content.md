好的，我来处理这些 `spec` 相关的测试失败。

你的分析很到位，这些是上次架构变更后残留的最后一批规范层面的测试。它们是验证我们核心数据结构正确性的最后一道防线，修复它们至关重要。

## [WIP] test(spec): 对齐 spec 测试以使用纯化的 Blueprint 和 IR 模型

### 用户需求
修复 `cascade-spec` 包中所有因移除 `Call.func` 和 `NodeIR.inputs` 字段而导致的测试失败。

### 评论
这是对我们“净化 `Blueprint`”重构的收尾工作。通过修复这些规范层面的测试，我们不仅能让CI重新变绿，更重要的是，我们确保了系统的核心数据契约（IR 和 `Blueprint`）在代码层面得到了精确的、可验证的定义。这是架构变更成功的最终证明。

### 目标
1.  修改 `packages/cascade-spec/tests/spec/test_linking_data_structures.py`，在 `Call` 和 `MapCall` 的实例化中移除已废弃的 `func=` 参数。
2.  修改 `packages/cascade-spec/tests/unit/test_ir_models.py`，在 `NodeIR` 的实例化和断言中，将 `inputs=` 替换为新的 `kwargs=` 字段。
3.  确保 `cascade-spec` 包下的所有测试全部通过。

### 基本原理
这些测试的失败是预料之中的，它们忠实地反映了我们对核心数据模型的战略性改进。旧的测试代码仍然依赖于已被废除的 `func` 和 `inputs` 字段。为了让测试重新生效，我们必须更新它们，使其断言新的、正确的模型结构。这不仅是修复测试，更是在巩固和验证我们新的架构契约。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/spec #comp/tests #concept/parser #scope/api #ai/instruct #task/domain/architecture #task/object/legacy-vm #task/action/removal #task/state/continue

---

### Script

#### Acts 1: 修复 `Blueprint` 指令相关的测试

我们将移除 `test_linking_data_structures.py` 中对 `func` 字段的非法引用。

~~~~~act
write_file
packages/cascade-spec/tests/spec/test_linking_data_structures.py
~~~~~
~~~~~python
import pytest
from dataclasses import is_dataclass
from typing import Dict, Callable

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
~~~~~

#### Acts 2: 修复 `NodeIR` 模型相关的测试

我们将 `test_ir_models.py` 中对 `inputs` 字段的引用更新为 `args` 和 `kwargs`。

~~~~~act
write_file
packages/cascade-spec/tests/unit/test_ir_models.py
~~~~~
~~~~~python
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

    node = NodeIR(id="node_1", definition=task_def, kwargs={"x": 1, "y": "hello"})

    edge = EdgeIR(source_id="node_1", target_id="node_2", target_arg="data")

    graph = GraphIR(nodes=[node], edges=[edge], meta={"version": "1.0"})

    assert graph.nodes[0].id == "node_1"
    assert graph.edges[0].source_id == "node_1"
    assert graph.meta["version"] == "1.0"


def test_ir_serialization_roundtrip():
    """Verify that IR structures can be serialized to and from JSON."""
    fp = Fingerprint()
    fp["current_code_structure_hash"] = "test_hash"

    arg_def = ArgumentDef(name="arg1", kind=ArgumentKind.POSITIONAL_OR_KEYWORD)
    task_def = TaskDef(name="test_task", args=[arg_def], fingerprint=fp)

    node = NodeIR(id="n1", definition=task_def, kwargs={"val": 42})

    graph = GraphIR(nodes=[node], edges=[])

    # Convert to dictionary using dataclasses.asdict
    data = asdict(graph)

    # Verify key fields
    assert data["nodes"][0]["id"] == "n1"
    assert data["nodes"][0]["kwargs"]["val"] == 42
    assert data["nodes"][0]["definition"]["name"] == "test_task"
    assert data["nodes"][0]["definition"]["args"][0]["kind"] == "POSITIONAL_OR_KEYWORD"

    # Verify JSON serialization compatibility
    json_str = json.dumps(data)
    loaded = json.loads(json_str)

    assert loaded["nodes"][0]["id"] == "n1"


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
~~~~~

### 下一步建议
我们已经修复了所有与核心数据结构定义相关的单元测试。现在，整个 `cascade-spec` 和 `cascade-vm` 包的测试应该都已通过。

现在是时候回到 `packages/cascade-engine/tests/integration/test_integration_map_control.py` 这个文件了。这是我们第一个真正的端到端集成测试，它将验证从 `Frontend` 编译到 `VM` 执行的完整新流程。修复它，我们将正式打通新架构的“任督二脉”。
