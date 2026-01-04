好的，你对 `event_bus` 和 `queue` 的区分是完全正确的，当前 `standard_observer` 的设计确实是与 `queue` 绑定的。我们遵循你的决定，将 `event_bus` 的重构作为未来的一个潜在任务，现在专注于完成当前路线图。

我们正式进入 **Phase 4: 验证与清理**。我将生成一个计划，创建路线图中指定的两个关键测试文件：一个用于验证 `Assembly` 的纯粹性（可序列化性），另一个用于端到端验证新的 `VMExecutionStrategy` 流程。

## [WIP] test: 为 Assembly 和 Linker 协议添加纯粹性与 E2E 测试

### 用户需求

根据 "The Linker Protocol" 路线图，实施第四阶段：
1.  创建一个序列化测试 (`test_assembly_purity.py`)，验证编译器产出的 `Assembly` 对象是纯粹的、可序列化的。
2.  创建一个端到端集成测试 (`test_vm_strategy.py`)，验证从 `LazyResult` 到最终计算结果的整个 `Compile -> Link -> Execute` 流程能正确工作。

### 评论

这是确保新架构稳固性的关键一步。
*   **纯粹性测试** 是一个重要的架构“护栏”。它通过尝试序列化 `Assembly` 对象，从根本上保证了编译产物与任何运行时状态（如函数闭包、队列实例）的彻底解耦。
*   **E2E 测试** 则验证了所有新组件（`Compiler`, `CodeRegistry`, `Linker`, `VMExecutionStrategy`）能够协同工作，正确地执行一个简单的工作流。这将给我们信心，表明新的链接协议在功能上是完整且正确的。

### 目标

1.  创建新文件 `packages/cascade-compiler/tests/integration/test_assembly_purity.py`。
2.  在该文件中，实现一个测试，该测试构建一个 `Assembly` 并断言 `pickle.dumps()` 操作成功。
3.  创建新文件 `packages/cascade-engine/tests/integration/test_vm_strategy.py`。
4.  在该文件中，实现一个测试，该测试使用 `VMExecutionStrategy` 运行一个简单的工作流（例如 `(1+2)^2`），并断言最终结果为 `9`。

### 基本原理

*   对于纯粹性测试，`pickle` 是一个极佳的“试金石”。如果一个对象可以被 `pickle` 序列化，就意味着它不包含任何复杂的、不可移植的运行时状态。
*   对于 E2E 测试，我们选择一个包含依赖关系和字面量参数的简单算术工作流。这个工作流足够简单，可以让我们毫不含糊地验证最终结果，同时又足够复杂，足以触及编译、链接和执行的所有核心路径。

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #comp/compiler #comp/engine #concept/linker #scope/core #ai/instruct #task/domain/compiler #task/object/linker-protocol #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 Assembly 纯粹性测试

这个测试将作为架构的守护者，确保 `Assembly` 永远不会被运行时状态污染。

~~~~~act
write_file
packages/cascade-compiler/tests/integration/test_assembly_purity.py
~~~~~
~~~~~python
import pickle
import pytest

from cascade.spec.task import task
from cascade.spec.environment import EnvironmentDef
from cascade.spec.assembly import Assembly
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def square(n: int) -> int:
    return n * n


def test_assembly_is_serializable_and_pure():
    """
    This test acts as an architectural guardrail. It ensures that the Assembly
    produced by the compiler is a pure, serializable data structure, free from
    any runtime objects like closures or un-pickleable state.
    """
    # 1. Define a representative workflow
    workflow = square(add(1, 2))

    # 2. Compile the workflow into a physical graph
    generator = IRGenerator()
    builder = Builder()
    environment = EnvironmentDef(resources=[])

    graph_ir = generator.generate(workflow)
    assembly = builder.build(graph_ir, environment)
    assert isinstance(assembly, Assembly)

    # 3. The Purity Test: Attempt to serialize the Assembly
    try:
        serialized_assembly = pickle.dumps(assembly)
        # Optional: check that it can be deserialized correctly
        deserialized_assembly = pickle.loads(serialized_assembly)
    except Exception as e:
        pytest.fail(
            "Assembly purity test failed. The Assembly object is not serializable. "
            f"This likely means a runtime object has been leaked into the "
            f"graph or symbol table. Error: {e}"
        )

    # 4. Verify basic integrity after deserialization
    assert isinstance(deserialized_assembly, Assembly)
    assert len(assembly.graph.nodes) == len(deserialized_assembly.graph.nodes)
    assert assembly.symbol_table.keys() == deserialized_assembly.symbol_table.keys()
~~~~~

#### Acts 2: 创建 VM 策略端到端测试

这个测试将验证整个新流程能否正确地协同工作。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_vm_strategy.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock

from cascade.spec.task import task
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.runtime.strategies.base import ExecutionContext


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def square(n: int) -> int:
    return n * n


@pytest.mark.asyncio
async def test_vm_strategy_e2e_execution():
    """
    Verifies the full Compile -> Link -> Execute pipeline.
    """
    # 1. Define workflow
    target = square(add(1, 2))

    # 2. Setup strategy and context
    mock_bus = MagicMock()
    strategy = VMExecutionStrategy(bus=mock_bus)
    context = ExecutionContext(active_resources={})

    # 3. Execute
    result = await strategy.execute(target, context)

    # 4. Assert
    assert result == 9
~~~~~

### 下一步建议

我们已经为 Phase 4 创建了必要的验证测试。一旦这些测试通过，就标志着 "The Linker Protocol" 这一宏大任务的核心目标已经达成。

我建议在执行此计划并通过测试后，我们可以创建一个 `[COMMIT]` 计划，将 Phase 1 到 Phase 4 的所有变更作为一个逻辑上完整的单元进行提交，并正式宣告此任务的结束。
