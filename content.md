简要回答

好的，我们继续遵循 TDD 流程，为 `IRGenerator` 添加一个更复杂的测试用例，以验证其处理任务间依赖关系的能力。

## [WIP] test(compiler): 为 IRGenerator 添加依赖解析测试

### 用户需求
为 `IRGenerator` 添加一个新的单元测试，`test_generate_task_with_dependency`。该测试需要验证当一个 `LazyResult` (下游) 依赖于另一个 `LazyResult` (上游) 时，`IRGenerator` 能够：
1.  正确生成代表两个任务的 `NodeIR`。
2.  在 `GraphIR` 中保持正确的拓扑顺序（上游节点在前）。
3.  在下游节点的 `inputs` 中，使用上游节点的 ID 字符串作为引用。

### 评论
这是对 `IRGenerator` 核心能力的第二次关键验证。第一个测试验证了它能处理“点”，这个测试将验证它能处理“线”。通过断言 ID 引用，我们确保了 `LazyResult` 对象图被正确地“扁平化”为 `GraphIR`，为 Backend 的处理做好了准备。

### 目标
1.  在 `packages/cascade-compiler/tests/unit/frontend/test_generator.py` 文件中追加一个新的测试用例。
2.  构造一个依赖场景，例如 `add(add(1, 2), 3)`。
3.  断言生成的 `GraphIR` 包含两个节点，并且下游节点的输入正确引用了上游节点的 ID。

### 基本原理
一个健壮的编译器前端必须能够正确解析依赖关系，这是构建任何非平凡工作流的基础。通过在 TDD 流程的早期阶段就锁定此行为，我们可以确保在后续添加更复杂功能（如 Map/Router）时，不会破坏这一核心逻辑。

### 标签
#intent/tooling #flow/draft #priority/high #comp/compiler #comp/tests #scope/dx #ai/instruct #task/domain/compiler #task/object/frontend #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 添加依赖解析测试用例

我们将通过 `patch_file` 向现有的测试文件追加新的测试用例。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
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
~~~~~python.new
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


def test_generate_task_with_dependency():
    """
    Tests that a LazyResult depending on another is converted into two
    NodeIRs with a correct ID reference.
    """
    # Arrange
    generator = IRGenerator()
    upstream_lr = add(1, 2)
    downstream_lr = add(upstream_lr, 3)

    # Act
    graph_ir = generator.generate(downstream_lr)

    # Assert
    assert len(graph_ir.nodes) == 2

    # The generator produces a topologically sorted list due to post-order traversal
    upstream_node = graph_ir.nodes[0]
    downstream_node = graph_ir.nodes[1]

    # Verify upstream node is correct
    assert upstream_node.name == "add"
    assert upstream_node.inputs == {"0": 1, "1": 2}

    # Verify downstream node correctly references the upstream node's ID
    assert downstream_node.name == "add"
    assert downstream_node.inputs == {"0": upstream_node.id, "1": 3}
~~~~~

### 下一步建议
我们已经成功验证了 Frontend 的基础和依赖解析能力。现在可以安全地进入 **Act 3: 移植引擎 (Lobotomizing the Engine)**。我们将开始对 `cascade-engine` 进行核心替换手术，使其调用我们新构建的、经过测试的 `IRGenerator`。
