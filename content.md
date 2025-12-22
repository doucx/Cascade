Excellent. The tests are passing, and all the necessary changes are in the working directory. It's time to create a clean, comprehensive commit for this significant new feature.

I will now generate the `[COMMIT]` plan.

## [COMMIT] feat(sdk): Introduce flow primitives cs.sequence and cs.pipeline

### 用户需求
引入 `cs.sequence` 和 `cs.pipeline` 两个高级流控制原语，以简化线性、顺序执行和链式数据处理工作流的定义，解决中间变量泛滥和控制流表达繁琐的问题。

### 评论
这是一个里程碑式的 API 增强。`cs.sequence` 和 `cs.pipeline` 极大地提升了 Cascade 的表达能力和人体工程学，使得编排常见的自动化脚本和数据处理流水线变得前所未有地直观和简洁。底层的实现（特别是上下文感知的跳过传播逻辑）不仅健壮，也为未来更高级的控制流模式奠定了坚实的基础。

### 目标
创建一个单一、原子化的 Git 提交，将 `cs.sequence` 和 `cs.pipeline` 的完整实现、相关的图模型变更、引擎执行逻辑修改、以及对应的测试用例全部纳入版本控制。

### 基本原理
该功能的所有代码实现和修复工作已经完成，并通过了完整的测试套件验证。现在需要将这些分散的修改整合为一个逻辑上完整的工作单元并提交，以正式地将该功能合并到代码库中。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #comp/spec #scope/api #scope/dx #ai/brainstorm #task/domain/sdk #task/object/flow-primitives #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 暂存所有与流控制原语相关的变更

我们将把所有修改过和新添加的文件都加入到 Git 的暂存区，为提交做准备。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/flow.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
packages/cascade-engine/src/cascade/runtime/strategies.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/hashing.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-sdk/src/cascade/__init__.py
packages/cascade-sdk/src/cascade/tools/visualize.py
packages/cascade-spec/src/cascade/graph/model.py
packages/cascade-spec/src/cascade/spec/lazy_types.py
packages/cascade-spec/src/cascade/spec/task.py
packages/cascade-library/src/cascade/flow.py
tests/engine/runtime/test_flow_primitives.py
~~~~~

#### Acts 2: 创建功能提交

现在，我们将创建一个内容详尽的 Git 提交，清晰地阐述本次变更的动机、实现和价值。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(sdk): Introduce flow primitives cs.sequence and cs.pipeline

Introduces two high-level flow control primitives to enhance expressiveness and reduce boilerplate in defining linear workflows. This addresses the common pain points of intermediate variable pollution and verbose control flow for simple sequential logic.

### `cs.sequence` for Sequential Execution

-   **Purpose**: Executes a list of tasks in a guaranteed order, ignoring their return values except for the last one.
-   **Use Case**: Ideal for imperative-style "do this, then do that" logic where data dependency is not the primary concern, such as logging, side-effects, or simple setup/teardown chains.
-   **Behavior**: If any task in the sequence fails or is skipped, the entire subsequent sequence is aborted gracefully.

```python
# Before
log_task = log_message("Starting...")
result = process_data().after(log_task)

# After
result = cs.sequence([
    log_message("Starting..."),
    process_data()
])
```

### `cs.pipeline` for Chained Data Processing

-   **Purpose**: Creates a data processing pipeline, similar to shell pipes (`|`), where the output of one step becomes the input of the next.
-   **Use Case**: Drastically simplifies data transformation workflows by eliminating the need to name every intermediate result.
-   **Behavior**: Supports tasks, regular functions, and lambdas. A step skipped via `.run_if(False)` will allow data to "penetrate" from the previous step to the next, enabling optional processing stages.

```python
# Before
data = read_file("data.json")
items = parse_json(data)
processed = process_items(items)

# After
processed = cs.pipeline(
    "data.json",
    [read_file, parse_json, process_items]
)
```

### Core Engine Changes

-   **`EdgeType.SEQUENCE`**: A new edge type was added to the graph model to represent non-data-transferring execution order.
-   **Context-Aware Skip Logic**: `FlowManager` and `ArgumentResolver` are now smarter. They inspect the `EdgeType` to correctly propagate skip events:
    -   `SEQUENCE` skips cause downstream abortion.
    -   `DATA` skips (in pipelines) allow data penetration.
-   **Graph Building**: The `GraphBuilder` was updated to correctly interpret these new primitives and construct the appropriate graph topology.
~~~~~

### 下一步建议
我们已经成功地引入了强大的新工具。为了最大化它们的价值，我建议：
1.  **编写专门的文档**: 在官方文档中为 `cs.sequence` 和 `cs.pipeline` 创建专门的章节，包含详细的用例和“食谱”。
2.  **探索 `cs.parallel`**: 作为一个自然的延伸，我们可以设计并实现一个 `cs.parallel` 原语，用于并行执行一组没有相互依赖的任务，进一步简化常见的并发模式。
