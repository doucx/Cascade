好的，任务已完成。我们将这次对测试用例的更新作为一个完整的工作单元提交到 Git 仓库。

## [COMMIT] test: 更新 visualizer 测试以适配 Dyad 架构

### 用户需求
将修复后的 `test_visualizer.py` 提交到版本控制系统。

### 评论
这次提交确保了编译器组件的可视化测试套件能够正确反映当前的 Dyad（二连体）架构。这是保持测试作为系统“真理来源”的重要步骤。

### 目标
1.  将 `packages/cascade-compiler/tests/unit/utils/test_visualizer.py` 的更改添加到暂存区。
2.  创建一个清晰、符合规范的提交记录。

### 基本原理
通过同步测试和实现，我们消除了因架构演进带来的虚假失败，保证了 CI/CD 流程的顺畅。使用 `[COMMIT]` 计划来执行 Git 操作是 Quipu 协议的标准流程。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #comp/compiler #scope/dx #ai/instruct #task/domain/testing #task/object/visualizer #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将修改后的测试文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-compiler/tests/unit/utils/test_visualizer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
test(compiler): update visualizer tests to match Dyad architecture

The 'test_visualizer.py' was failing because it was using outdated 'Triad' node definitions (Bleacher/Worker/Stainer) and asserting against incorrect colors.

- Rewrote the test to use 'Dyad' nodes (LauncherNode/LanderNode).
- Added assertions for the correct heuristic colors defined in 'GraphDumper':
  - LauncherNode (The Starter): #c8e6c9
  - Result DataNode (Landing Pad): #f3e5f5
  - LanderNode (The Finisher): #ffccbc
- Verified that observability channels correctly render as dashed lines.
~~~~~

### 下一步建议
- **回归测试**: 建议在提交后运行整个 `packages/cascade-compiler/` 的测试套件，确保没有其他由于架构变动导致的隐性失败。
- **架构文档同步**: 如果有相关的架构设计 Markdown 文档，可能也需要同步更新其中的拓扑图示例。
