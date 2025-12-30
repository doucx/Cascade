好的，我们开始 "Phase 2: Compiler Optimizer" 的 TDD 流程。

我将生成一个计划，创建 `Optimizer` 的 RED 状态测试。这包括定义一个新的异常类型 `CycleDetectedError` 和编写两个核心测试用例：一个用于验证循环依赖的检测，另一个用于验证菱形依赖图的正确拓扑排序。

## [WIP] test(compiler): 为 Optimizer 创建 RED 状态测试

### 用户需求
根据 TDD 重构路线图的 "Phase 2"，我们需要为新的 `Optimizer` 组件创建初始的、失败的（RED 状态）测试用例。这些测试用例需要定义 `Optimizer` 的核心契约：能够对 `GraphIR` 进行拓扑排序，并能在遇到循环依赖时抛出特定的错误。

### 评论
这是编译器开发的关键一步。`Optimizer` 负责将无序的 `GraphIR` 转换为可执行的计划，并在此过程中执行静态验证（如循环检测）。预先定义这些测试，可以确保我们实现的算法是正确且健壮的，并明确了 `Optimizer` 的输入（`GraphIR`）和输出（`ExecutionPlan` 或 `CycleDetectedError`）接口。

### 目标
1.  在 `cascade.compiler` 中创建 `exceptions.py` 文件并定义 `CycleDetectedError`。
2.  创建新的测试文件 `packages/cascade-compiler/tests/test_optimizer.py`。
3.  在该测试文件中，添加一个测试用例，断言当输入一个循环 `GraphIR` 时会抛出 `CycleDetectedError`。
4.  添加第二个测试用例，断言当输入一个菱形依赖 `GraphIR` 时，会生成一个逻辑上正确的拓扑排序计划。

### 基本原理
我们严格遵循 TDD 流程。通过 `write_file` 创建新的测试和异常类，我们为 `Optimizer` 组件设定了明确的开发目标。`pytest.xfail` 标记的使用表明我们预期这些测试会因为 `Optimizer` 尚未实现而失败，这正是 TDD 流程中 "RED" 阶段的标志。

### 标签
#intent/tooling #flow/ready #priority/high #comp/compiler #concept/ir #scope/core #ai/instruct #task/domain/refactor #task/object/compiler-optimizer #task/action/define #task/state/continue

---

### Script

#### Acts 1: 定义编译器异常

我们需要一个特定的异常来表示循环依赖，以便测试可以精确捕获它。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/exceptions.py
~~~~~
~~~~~python
class CompilerError(Exception):
    """Base class for compiler-related errors."""
    pass

class CycleDetectedError(CompilerError):
    """Raised when a cycle is detected in the dependency graph."""
    pass
~~~~~

#### Acts 2: 更新 `__init__.py` 导出异常

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .frontend import Frontend

__all__ = ["Frontend"]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .frontend import Frontend
from .exceptions import CompilerError, CycleDetectedError

__all__ = ["Frontend", "CompilerError", "CycleDetectedError"]
~~~~~

#### Acts 3: 创建 Optimizer 的 RED 测试文件

这个测试文件定义了 `Optimizer` 必须满足的两个核心行为。

~~~~~act
write_file
packages/cascade-compiler/tests/test_optimizer.py
~~~~~
~~~~~python
import pytest
from typing import List

# These are defined in Phase 1, so they should import correctly.
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint

# NOTE: The Optimizer and its specific exception are not yet implemented.
# We expect an ImportError, which will cause the tests to fail (RED state).
try:
    from cascade.compiler.optimizer import Optimizer, ExecutionPlan
    from cascade.compiler.exceptions import CycleDetectedError
except ImportError:
    # Define a placeholder for type hinting if the import fails
    ExecutionPlan = List[List[str]]


def _create_dummy_node_ir(node_id: str) -> NodeIR:
    """Helper to create a minimal NodeIR for topology tests."""
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_for_{node_id}"})
    task_def = TaskDef(name=node_id, args=[], fingerprint=fp)
    return NodeIR(id=node_id, definition=task_def)


@pytest.mark.xfail(reason="Optimizer not implemented", raises=(ImportError, NameError))
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
            EdgeIR(source_id="A", target_id="B", target_arg="data"),
            EdgeIR(source_id="B", target_id="A", target_arg="data"),
        ],
    )

    with pytest.raises(CycleDetectedError):
        Optimizer.optimize(cyclic_ir)


@pytest.mark.xfail(reason="Optimizer not implemented", raises=(ImportError, NameError))
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
            EdgeIR(source_id="A", target_id="B", target_arg="a_val"),
            EdgeIR(source_id="A", target_id="C", target_arg="a_val"),
            EdgeIR(source_id="B", target_id="D", target_arg="b_val"),
            EdgeIR(source_id="C", target_id="D", target_arg="c_val"),
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
~~~~~
