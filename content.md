简要回答

好的，我们立即为刚刚创建的 `IRGenerator` 编写单元测试。这将遵循 TDD 的最佳实践，确保我们的 Frontend 在一开始就具有坚实的质量基础，并能验证其最核心的功能。

## [WIP] test(compiler): 为 IRGenerator 添加单元测试

### 用户需求
为 `IRGenerator` 创建一个单元测试，验证它能正确地将一个简单的、带有字面量参数的 `LazyResult` (如 `add(1, 2)`) 转换为一个结构正确的 `GraphIR`。

### 评论
这是我们新编译器 Frontend 的第一个质量门。通过这个测试，我们将锁定 `IRGenerator` 的基础行为：
1.  **单节点图生成**: 验证对于单个任务，确实只生成一个 `NodeIR`。
2.  **任务定义分析**: 确保 `ReflectionAnalyzer` 被正确调用，并将 `TaskDef` 附加到 `NodeIR` 上。
3.  **参数扁平化**: 验证位置参数 `(1, 2)` 被正确地转换为了 `inputs` 字典 `{"0": 1, "1": 2}`。

这个测试的通过将为后续更复杂的测试（如依赖关系解析）提供信心。

### 目标
1.  创建测试文件 `packages/cascade-compiler/tests/unit/frontend/test_generator.py`。
2.  在文件中定义一个简单的 `@task` 函数 `add` 作为测试素材。
3.  编写一个测试用例 `test_generate_simple_task`，调用 `IRGenerator` 处理 `add(1, 2)`。
4.  断言生成的 `GraphIR` 结构和内容符合预期。

### 基本原理
我们遵循测试驱动开发（TDD）的原则。在实现了 `IRGenerator` 的核心功能后，我们必须立即编写测试来验证和保护这些功能。这不仅可以防止未来的代码修改破坏现有行为（回归），还能为其他开发者提供一个清晰的、可执行的 `IRGenerator` 使用示例。

### 标签
#intent/tooling #flow/draft #priority/high #comp/compiler #comp/tests #scope/dx #ai/instruct #task/domain/compiler #task/object/frontend #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 Frontend 单元测试

我们将创建一个新的测试文件，并添加一个测试用例来验证 `IRGenerator` 的基本功能。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python
import pytest

from cascade.spec.task import task
from cascade.spec.ir.models import GraphIR
from cascade.compiler.frontend.generator import IRGenerator


# --- Test Fixtures ---

@task
def add(a: int, b: int) -> int:
    """A simple task for testing."""
    return a + b


@task
def process_data(data: dict) -> str:
    """A task with more complex literal arguments."""
    return str(data.get("key"))


# --- Test Cases ---


def test_generate_simple_task():
    """
    Tests that a single LazyResult with literal arguments is converted
    into a valid GraphIR with a single NodeIR.
    """
    # Arrange
    generator = IRGenerator()
    target = add(1, 2)

    # Act
    graph_ir = generator.generate(target)

    # Assert
    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 1

    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "add"
    assert node_ir.task.name == "add"
    assert "current_code_structure_hash" in node_ir.task.fingerprint

    # Verify that positional arguments are correctly mapped to string keys
    assert node_ir.inputs == {"0": 1, "1": 2}
    assert node_ir.constraints == {}


def test_generate_task_with_kwargs():
    """
    Tests that a single LazyResult with literal keyword arguments is
    correctly converted.
    """
    # Arrange
    generator = IRGenerator()
    target = process_data(data={"key": "value"})

    # Act
    graph_ir = generator.generate(target)

    # Assert
    assert len(graph_ir.nodes) == 1
    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "process_data"
    assert node_ir.inputs == {"data": {"key": "value"}}
~~~~~

### 下一步建议
我们已经验证了最简单的场景。下一步是测试 `IRGenerator` 的核心职责之一：**依赖解析**。我建议编写一个新的测试用例，`test_generate_task_with_dependency`，它将使用类似 `add(add(1, 2), 3)` 的结构，并断言：
1.  生成了两个 `NodeIR`。
2.  `GraphIR` 中的节点顺序是正确的（依赖项在前）。
3.  上游节点的 `inputs` 是下游节点的 ID 引用。
