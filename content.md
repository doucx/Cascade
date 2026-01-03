## [WIP] fix(test): 修复集成测试中的 worker 匹配逻辑

### 错误分析
集成测试 `test_source_node_is_triggered_by_pulse` 失败，因为测试中的 `mock_worker` 函数使用了 `node.id.startswith(...)` 来识别要执行的逻辑任务。这是一个错误的假设，因为物理节点的 `id` 是一个哈希值，与逻辑任务名无关。正确的、稳定的标识符是 `node.name`，它被编译器设置为 `Exec(LogicalTaskName)`。

### 用户需求
修改 `packages/cascade-vm/tests/integration/test_source_node_execution.py` 中的 `mock_worker` 函数，使其使用 `node.name` 来进行条件判断，而不是 `node.id`。

### 评论
这个修复遵循了“依赖稳定接口而非实现细节”的最佳实践。将匹配逻辑从不稳定的哈希 `id` 切换到语义化的 `name` 属性，使我们的测试代码更加健壮、可读，并且能够抵抗未来对哈希算法的任何修改。

### 目标
1.  定位 `test_source_node_execution.py` 中的 `mock_worker` 函数。
2.  将其中的 `if node.id.startswith("source_task"):` 修改为 `if "source_task" in node.name:`。

### 基本原理
`cascade-compiler` 的 `Expander` 在创建 `WorkerNode` 时，会将其 `name` 属性设置为一个包含逻辑任务名的、可预测的字符串（例如 `"Exec(source_task)"`）。这个 `name` 属性是专门为调试和可读性设计的，是比哈希 `id` 更合适的语义标识符。通过在测试中利用这个稳定的 `name` 属性，我们可以确保 `mock_worker` 能够准确地路由到正确的业务逻辑，从而修复测试断言。

### 标签
#intent/fix #flow/ready #priority/high #comp/vm #comp/tests #task/domain/testing #task/object/test-robustness #task/action/refactor #task-state/continue

---

### Script

#### Acts 1: 修复测试中的 `mock_worker`

我们将使用 `patch_file` 精确地修改 `mock_worker` 函数的条件判断逻辑。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    trace_from_bleacher = worker_input_token.trace

    result = "Unexpected worker call"
    if node.id.startswith("source_task"):
        result = source_task.func()

    # The Stainer will merge this into the final trace
~~~~~
~~~~~python.new
def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    trace_from_bleacher = worker_input_token.trace

    result = "Unexpected worker call"
    # Use the stable semantic name for routing, not the volatile hash-based id
    if "source_task" in node.name:
        result = source_task.func()

    # The Stainer will merge this into the final trace
~~~~~

### 下一步建议
我们已经修复了集成测试中最后一个已知的逻辑错误。现在，测试应该能够成功通过了。

一旦确认测试通过，就意味着我们对编译器和 VM 的所有重构工作都已完成并通过了验证。这将是一个完美的时机，来创建一个 `[COMMIT]` 计划，将我们过去所有相关的修改（脉冲模型、探测器模型、标准库修复、测试修复）作为一个完整的、原子性的工作单元进行提交。

如果你同意，我将在你确认测试通过后，立即为你生成这个 `[COMMIT]` 计划。
