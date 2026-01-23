好的，我们已经完成了代码的适配工作。现在，我将生成一个 `[COMMIT]` 计划，将这些更改作为一个逻辑单元提交。

这标志着我们对 Cascade 参数传递链路基础重构的全面完成，涵盖了规约、编译器以及新旧两种运行时执行器。

## [COMMIT] fix(execution-graph): align IRToRuntimeAdapter with new NodeIR spec

### 用户需求
完成对 `cascade-execution-graph` 适配器的修改，并创建 Git 提交。

### 评论
通过这次提交，我们确保了 Cascade 系统内部新旧组件在核心 IR 数据规约上达到了完全的一致性。这消除了最后一个潜在的不一致点，为运行全量测试套件铺平了道路。

### 目标
1.  将修改后的 `adapter.py` 暂存到 Git。
2.  创建一个语义清晰、符合规范的提交消息。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules` 协议，我们将文件修改与提交操作分离开来。这是一个 `[COMMIT]` 计划，仅包含 Git 相关的 `act` 指令。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/ir #scope/core #ai/instruct #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将 `adapter.py` 添加到暂存区，并记录这次关键的兼容性修复。

~~~~~act
git_add
packages/cascade-execution-graph/src/cascade/execution/graph/model/adapter.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(execution-graph): align IRToRuntimeAdapter with new NodeIR spec

Updated IRToRuntimeAdapter to read from 'args' and 'kwargs' instead of the deprecated 'inputs' field in NodeIR. 

This ensures that the legacy graph-based execution strategy remains compatible with the core compiler's refined IR generation logic. The fix utilizes a unified input view within the adapter to correctly reconstruct dependency edges and parameter bindings without information loss.
~~~~~

### 下一步建议
- **全量回归**: 现在整个参数链路已经重构并适配完毕，建议立即运行全量测试：`pytest`。
- **环境验证**: 在通过测试后，建议在典型的 DSL 场景（如带 `*args/**kwargs` 的任务流）下进行一次冒烟测试，确保高层次的语义表达依然正确。
