Of course. The test failure is a direct and expected consequence of our previous refactoring, and it highlights a subtle but important detail about the `dry_run` tool's purpose.

Your analysis is spot on. I will fix the test and then prepare for the next step of writing the new smoke tests.

## [WIP] fix: Correct dry_run event to filter non-literal inputs

### 错误分析
测试 `test_dry_run_emits_correct_events_linear` 失败的根本原因是：我们对 `GraphBuilder` 的重构非常成功，它现在会**完整地**保留任务的所有输入结构（包括 `LazyResult` 对象）在 `node.literal_inputs` 字段中。

*   **旧行为**: `GraphBuilder` 会分离出字面量和 `LazyResult` 依赖。
*   **新行为**: `step_b` 的 `literal_inputs` 现在是 `{'0': <LazyResult of step_a>, 'y': 10}`，这在图构建层面是完全正确的。
*   **测试断言的缺陷**: 测试用例是基于旧行为编写的，它错误地断言 `literal_inputs` **只应包含**真正的字面量 (`{'y': 10}`)。

**解决方案**:
失败的不是 `GraphBuilder`，而是 `dry_run` 工具的事件生成逻辑。`dry_run` 的目的是向用户展示**静态**信息。将 `LazyResult` 对象放入发给 `dry_run` 订阅者的事件中，既不清晰也非其本意。

因此，正确的修复是修改 `_analyze_plan` 函数，在创建 `PlanNodeInspected` 事件时，明确地从 `node.literal_inputs` 中过滤掉 `LazyResult` 实例，只保留真正的字面量。这会让 `dry_run` 的行为符合预期，并使测试通过。

### 用户需求
1.  修复 `test_preview.py` 中因 `GraphBuilder` 行为变更而失败的测试。
2.  确保 `dry_run` 工具的输出（通过 `PlanNodeInspected` 事件）只包含静态的、在构建时已知的字面量输入，以保持其可读性。
3.  为下一步编写新的冒烟测试做准备，探查相关文件。

### 目标
1.  修改 `cascade-py/src/cascade/tools/preview.py` 中的 `_analyze_plan` 函数。
2.  在创建 `PlanNodeInspected` 事件时，过滤 `node.literal_inputs` 字典，移除所有 `LazyResult` 或 `MappedLazyResult` 的值。
3.  读取 `test_build.py` 和 `helpers.py` 为编写新的测试做准备。

### 基本原理
通过在事件生成的源头进行过滤，我们确保了 `dry_run` 工具的契约（只报告字面量）得以维持，而无需使测试去适应一个对用户不友好的、包含内部对象的事件负载。这是一种关注点分离的体现：`GraphBuilder` 负责构建一个精确的内部图表示，而 `dry_run` 工具则负责将这个表示翻译成对人类有用的、简化的信息。

### 标签
#intent/fix #flow/ready #priority/high #comp/py #concept/dx #scope/ux #ai/instruct #task/domain/core #task/object/graph-builder #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `preview.py` 的事件生成逻辑

我们将修改 `_analyze_plan` 函数，确保 `PlanNodeInspected` 事件的 `literal_inputs` 字段只包含真正的字面量。

~~~~~act
patch_file
packages/cascade-py/src/cascade/tools/preview.py
~~~~~
~~~~~python
        for node in stage:
            bus.publish(
                PlanNodeInspected(
                    run_id=target._uuid,
                    index=current_index,
                    total_nodes=total_steps,
                    node_id=node.id,
                    node_name=node.name,
                    literal_inputs=node.literal_inputs,
                )
            )
            current_index += 1
~~~~~
~~~~~python
        for node in stage:
            # Filter out non-literal dependencies from the inputs for cleaner output
            from cascade.spec.lazy_types import LazyResult, MappedLazyResult
            
            literals = {
                k: v for k, v in node.literal_inputs.items() 
                if not isinstance(v, (LazyResult, MappedLazyResult))
            }
            
            bus.publish(
                PlanNodeInspected(
                    run_id=target._uuid,
                    index=current_index,
                    total_nodes=total_steps,
                    node_id=node.id,
                    node_name=node.name,
                    literal_inputs=literals,
                )
            )
            current_index += 1
~~~~~

#### Acts 2: 准备新的冒烟测试

现在，为了编写一个能够验证我们新架构（深度依赖、`cs.dict`、`cs.format`）的测试，我需要先了解一下现有图构建测试的结构和新提供者的 API。

首先，查看现有的图构建测试文件。

~~~~~act
read_file
tests/cascade-runtime/graph/test_build.py
~~~~~

然后，确认一下我刚刚创建的 `helpers` 提供者的具体实现。

~~~~~act
read_file
packages/cascade-py/src/cascade/providers/helpers.py
~~~~~

### 下一步建议
在分析完上述文件后，我将创建一个新的 `[WIP]` 计划，其中包含：
1.  一个新的测试文件 `tests/cascade-py/providers/test_helpers.py` 来测试 `cs.dict` 和 `cs.format`。
2.  在 `tests/cascade-runtime/graph/test_build.py` 中增加一个新的测试用例，专门验证 `GraphBuilder` 对嵌套在列表和字典中的 `LazyResult` 的深度依赖发现能力。
