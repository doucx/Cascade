简要回答：
好的，我将严格遵循“正规军”方案，一次性编写涵盖 `Spec`, `Compiler`, `Engine` 三个层面的测试用例，以验证基于 `structure_hash` 的安全链接机制。这些测试在当前代码库中必然失败，从而将系统置于明确的 **RED** 状态。

## [WIP] test: 添加基于 structure_hash 的安全链接的完整测试套件 (RED 阶段)

### 用户需求
实现基于 `structure_hash` 的安全链接机制的测试层。这是“焦土政策”重构中 Compiler-Runtime 架构的关键一环，旨在确保编译期生成的指令（骨架）能在运行期通过哈希指纹正确链接到内存中的函数对象（血肉）。

### 评论
当前系统 `Backend` 生成的 `Blueprint` 中 `func` 为 `None`，且 `VMExecutionStrategy` 尚未实现链接逻辑。本次提交的测试用例将暴露这些缺失，具体表现为：
1.  **Spec 层**: `Call`/`MapCall` 指令缺少 `structure_hash` 字段；`CompilationResult` 类不存在。
2.  **Compiler 层**: `Frontend` 不返回 `symbol_table`；`Backend` 不填充 `structure_hash`。
3.  **Engine 层**: VM 执行时因 `func` 为 `None` 而崩溃。

### 目标
1.  创建 `packages/cascade-spec/tests/spec/test_linking_data_structures.py` 以验证数据结构契约。
2.  创建 `packages/cascade-compiler/tests/unit/test_compiler_linking.py` 以验证编译器层面的元数据传递。
3.  创建 `packages/cascade-engine/tests/integration/test_vm_linking.py` 以验证运行时的链接与执行。

### 基本原理
遵循 TDD 原则，先编写断言“正确行为”的测试。由于相关数据结构和逻辑尚未实现，这些测试的失败将明确指导后续的实现工作。我们采用长命名规范（`current_code_structure_hash`）来消除概念歧义。

### 标签
#intent/tooling #flow/draft #priority/high #comp/spec #comp/compiler #comp/runtime #task/domain/core #task/object/linking #task/action/test-creation #task/state/begin

---

### Script

#### Acts 1: 创建 Spec 层测试 (验证数据结构)

我们将验证 `Blueprint` 指令集是否包含链接所需的哈希字段，以及是否存在承载链接信息的 `CompilationResult` 结构。

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
            func=None, 
            output=Register(0), 
            task_name="t", 
            structure_hash="hash_123"
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
            func=None, 
            output=Register(0), 
            task_name="t", 
            structure_hash="hash_123"
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

#### Acts 2: 创建 Compiler 层测试 (验证元数据流转)

我们将验证 `Frontend` 是否正确生成符号表（Symbol Table），以及 `Backend` 是否将哈希值正确写入指令。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/test_compiler_linking.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.task import task
from cascade.compiler.frontend import Frontend
from cascade.compiler.backend import Backend
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.blueprint import Call

def test_frontend_returns_compilation_result_with_symbol_table():
    """
    验证 Frontend.compile 返回的是 CompilationResult 对象，
    并且包含正确的 symbol_table。
    """
    @task
    def my_func(): pass

    # RED 阶段：Frontend.compile 目前返回 GraphIR，没有 symbol_table 属性
    result = Frontend.compile(my_func())
    
    # 检查类型 (不直接 import 类以避免 ImportError 阻断测试运行，依靠鸭子类型或类名检查)
    assert type(result).__name__ == "CompilationResult", \
        f"Expected CompilationResult, got {type(result).__name__}"

    assert hasattr(result, "symbol_table"), "Result missing symbol_table"
    assert hasattr(result, "ir"), "Result missing ir"
    
    # 验证 Symbol Table 内容
    symbol_table = result.symbol_table
    assert len(symbol_table) == 1
    
    # 获取唯一的 key (structure_hash)
    hash_key = list(symbol_table.keys())[0]
    
    # 验证 value 是原始函数
    assert symbol_table[hash_key] == my_func.func

def test_backend_populates_structure_hash_in_blueprint():
    """
    验证 Backend 在生成 Blueprint 时，从 NodeIR 的 definition 中读取
    current_code_structure_hash 并写入指令。
    """
    # 构造一个带有 structure_hash 的 NodeIR
    expected_hash = "test_hash_123"
    fp = Fingerprint.from_dict({"current_code_structure_hash": expected_hash})
    task_def = TaskDef(name="test_task", args=[], fingerprint=fp)
    node = NodeIR(id="n1", definition=task_def, inputs={})
    
    graph = GraphIR(nodes=[node], edges=[])
    plan = [["n1"]]
    
    # Backend.compile 应该读取这个 hash 并放入 Blueprint
    blueprint = Backend.compile(graph, plan)
    
    assert len(blueprint.instructions) == 1
    instr = blueprint.instructions[0]
    assert isinstance(instr, Call)
    
    # RED 阶段失败点：instr 没有 structure_hash 属性
    if not hasattr(instr, "structure_hash"):
        pytest.fail("Instruction generated by Backend missing 'structure_hash' attribute")
        
    assert instr.structure_hash == expected_hash
~~~~~

#### Acts 3: 创建 Engine 层测试 (验证运行时链接)

我们将创建一个端到端的集成测试，验证 `VMExecutionStrategy` 是否利用编译器提供的信息成功完成了链接并执行任务。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_vm_linking.py
~~~~~
~~~~~python
import pytest
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
import cascade as cs

@pytest.mark.asyncio
async def test_vm_strategy_performs_linking_and_execution():
    """
    端到端集成测试：
    1. 定义任务
    2. Engine (use_vm=True) 调用 Frontend 编译 -> 得到 Symbol Table
    3. Engine 调用 Backend 编译 -> 得到带 Hash 的 Blueprint (func=None)
    4. Engine 执行 Link 过程 -> 填充 Blueprint 的 func
    5. VM 执行成功
    
    RED 阶段预期：
    由于 Link 逻辑未实现，VM 尝试执行 func=None 的指令，抛出 TypeError。
    """
    @cs.task
    def echo(x):
        return x

    workflow = echo("hello_world")
    
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )
    
    # 使用 VM 执行
    try:
        result = await engine.run(workflow, use_vm=True)
    except TypeError as e:
        if "'NoneType' object is not callable" in str(e):
            # 这是我们预期的失败，证明 Link 没发生
            pytest.fail("VM crashed because function was not linked (func is None)")
        raise e
    except AttributeError as e:
        # 可能是 CompilationResult 还没实现导致的属性错误
        pytest.fail(f"Execution failed likely due to missing linking infrastructure: {e}")
    
    assert result == "hello_world"
~~~~~

### 下一步建议
一旦测试文件创建完成，我们将运行这些测试确认它们全部失败（RED）。随后，我们将按照路线图逐一实现 Spec、Compiler 和 Engine 的相关逻辑，直到测试全部变绿（GREEN）。
