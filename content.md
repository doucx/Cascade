简要回答
我们正在 **Phase 6** 的冲刺阶段。这次我们将一次性编写 `Backend` 和 `VM` 的所有剩余测试，覆盖 **Dynamic Params** 和 **Map Execution** 的所有场景。这会让我们进入一个巨大的 RED 状态，然后通过扩展 Spec、Compiler 和 VM 来一举完成功能对齐。

## [WIP] test(compiler+vm): 全面覆盖 Map 与 Params 的执行逻辑

### 用户需求
1.  在 `test_backend.py` 中添加 `Param` 节点的测试。
2.  在 `test_backend.py` 中添加 `Map` 节点的测试（预期生成 `MapCall`）。
3.  在 `test_vm_*.py` 中添加 `MapCall` 的执行测试（迭代、收集结果）。

### 评论
为了不破坏“架构完整性”，我们在 Spec 层面引入 `MapCall` 指令是必然的。Map 不是普通的函数调用，它是数据并行。VM 需要像 CPU 的 SIMD 指令一样处理它（或者在软件层面循环）。

### 目标
定义 `Map` 和 `Param` 在 Blueprint 和 VM 中的行为。

### 基本原理
Map 节点在 Graph 中是单个节点，但在 VM 中它应该是一条能够展开的指令。

### 标签
#intent/test #flow/ready #priority/high #comp/tests #comp/compiler #comp/vm #task/domain/core #task/object/map-execution #task/action/test #task/state/continue

---

### Script

#### Acts 1: 扩充 `test_backend.py`

我们添加对 Map 和 Param 编译的验证。注意：我们假设 Spec 中会新增 `MapCall`。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~
~~~~~python.old
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.blueprint import Blueprint, Call, Register, Literal, JumpIfFalse

from cascade.compiler.backend import Backend
~~~~~
~~~~~python.new
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.blueprint import Blueprint, Call, Register, Literal, JumpIfFalse, MapCall

from cascade.compiler.backend import Backend
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~
~~~~~python.old
    # Check 2: Action
    assert isinstance(instr_2, Call)
    assert instr_2.task_name == "action"
~~~~~
~~~~~python.new
    # Check 2: Action
    assert isinstance(instr_2, Call)
    assert instr_2.task_name == "action"


def test_compile_map_node_generates_map_call():
    """
    Case 4: Map Node (A -> Map(B)).
    Verify that Backend generates a MapCall instruction when NodeIR has meta['is_map'].
    """
    # Node B is a map over task "process"
    node_b = NodeIR(
        id="B", 
        definition=_create_dummy_task_def("process"),
        inputs={"scale": 2}, # Constant input
        meta={"is_map": True}
    )
    
    # Dynamic input from A (a list)
    node_a = NodeIR(id="A", definition=_create_dummy_task_def("list_gen"))
    edge = EdgeIR(source_id="A", target_id="B", target_arg="items")
    
    ir = GraphIR(nodes=[node_a, node_b], edges=[edge])
    plan = [["A"], ["B"]]
    
    blueprint = Backend.compile(ir, plan)
    
    # Should have 2 instructions: Call(list_gen) -> MapCall(process)
    assert len(blueprint.instructions) == 2
    instr_map = blueprint.instructions[1]
    
    assert isinstance(instr_map, MapCall)
    assert instr_map.task_name == "process"
    
    # Verify inputs: 'items' comes from Register, 'scale' is Literal
    assert isinstance(instr_map.kwargs["items"], Register)
    assert isinstance(instr_map.kwargs["scale"], Literal)
~~~~~

#### Acts 2: 创建新的 VM Map 测试 `test_vm_map.py`

这个测试验证 VM 能否执行 `MapCall`。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_vm_map.py
~~~~~
~~~~~python
import pytest
import asyncio
from cascade.spec.blueprint import Blueprint, Call, MapCall, Register, Literal
from cascade.vm import VirtualMachine

# --- Helpers ---

def double(x):
    return x * 2

async def async_double(x):
    await asyncio.sleep(0.01)
    return x * 2

def add(a, b):
    return a + b

# --- Tests ---

@pytest.mark.asyncio
async def test_vm_map_execution_sync():
    """
    Case 1: Sync MapCall.
    Verify VM iterates over list input and collects results.
    """
    # Instruction: results = map(double, x=[1, 2, 3])
    instr = MapCall(
        func=double,
        output=Register(0),
        args=[],
        kwargs={"x": Literal([1, 2, 3])},
        task_name="map_double"
    )
    
    bp = Blueprint(instructions=[instr], register_count=1)
    vm = VirtualMachine()
    
    results = await vm.execute(bp)
    assert results == [2, 4, 6]


@pytest.mark.asyncio
async def test_vm_map_execution_async():
    """
    Case 2: Async MapCall.
    Verify VM awaits all coroutines.
    """
    instr = MapCall(
        func=async_double,
        output=Register(0),
        kwargs={"x": Literal([10, 20])},
        task_name="map_async"
    )
    
    bp = Blueprint(instructions=[instr], register_count=1)
    vm = VirtualMachine()
    
    results = await vm.execute(bp)
    assert results == [20, 40]


@pytest.mark.asyncio
async def test_vm_map_multiple_iterables():
    """
    Case 3: Map with multiple iterables (zip behavior).
    map(add, a=[1, 2], b=[10, 20]) -> [11, 22]
    """
    instr = MapCall(
        func=add,
        output=Register(0),
        kwargs={
            "a": Literal([1, 2]),
            "b": Literal([10, 20])
        },
        task_name="map_add"
    )
    
    bp = Blueprint(instructions=[instr], register_count=1)
    vm = VirtualMachine()
    
    results = await vm.execute(bp)
    assert results == [11, 22]
~~~~~

### 下一步建议
测试现在会失败（RED），因为 `MapCall` 尚未定义。我们需要：
1.  **Spec**: 在 `blueprint.py` 中添加 `MapCall`。
2.  **Backend**: 更新 `backend.py`，当检测到 `is_map` 时生成 `MapCall`。
3.  **VM**: 更新 `machine.py`，实现 `MapCall` 的执行逻辑（包括 zip 输入、并发执行和结果收集）。
