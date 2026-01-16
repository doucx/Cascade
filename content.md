好的，我们已经完成了 `GraphDumper` 的重构，使其与 V3 的二元体（Dyad）物理架构保持了语义一致。现在我将生成一个提交计划来固化这些变更。

## [COMMIT] refactor(compiler): 同步 GraphDumper 与 V3 二元体架构

### 用户需求
固化对 `GraphDumper` 的重构，将其从基于旧 V2 启发式逻辑迁移到基于 V3 `NodePrefix` 和二元体类型的确定性着色逻辑。

### 评论
这是一个重要的维护步骤，确保了编译器的开发工具（可视化）不会与核心架构发生语义漂移。

### 目标
1. 将修改后的 `visualizer.py` 添加到暂存区。
2. 创建一个结构清晰的提交记录。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules` 协议，在独立的计划中执行 Git 提交操作，以确保变更的可追溯性和稳定性。

### 标签
#intent/refine #flow/ready #comp/compiler #scope/dx #ai/instruct #task/domain/compiler #task/object/visualizer #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交可视化工具的更新

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/utils/visualizer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(compiler): align GraphDumper with V3 Dyad architecture

The GraphDumper was previously using legacy V2 heuristics (e.g., searching for '.bleach' or '.stain' strings) for node coloring, which led to semantic drift in V3.

Key updates:
- Integrated `NodePrefix` and explicit `LauncherNode`/`LanderNode` checks for deterministic coloring.
- Launcher nodes are now Green (Initiators), Lander nodes are Orange (Finishers).
- System nodes like Egress (Pink), Constants (Light Blue), and Results (Purple) now have dedicated color mappings based on their physical prefixes.
- Improved identification of Resource Ledgers and Brokers.

This ensures that generated DOT diagrams accurately reflect the V3 physical topology.
~~~~~

### 下一步建议
- **架构审查**: 如果物理层引入了新的 `NodePrefix`（如未来可能增加的 `GATE` 细分），记得同步更新 `GraphDumper` 的映射表。
- **端到端验证**: 建议运行 `tests/compiler/test_builder.py` 相关的测试，确认在生成复杂图表时没有引入回归错误。
