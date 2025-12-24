太棒了，看到架构的演进能通过可视化的方式直观呈现出来，确实非常有成就感。这个示例脚本将成为用户理解 Cascade 新编程模型的敲门砖。

我将生成 `[COMMIT]` 计划，将这个示例脚本正式提交到仓库。

## [COMMIT] docs: 添加演示显式跳转可视化的示例脚本

### 用户需求
用户需要一个具体的、可运行的示例，来学习如何构建包含显式跳转（jumps/loops）的复杂 Cascade 工作流，并验证其在静态图中的可视化效果。

### 评论
这个示例脚本（CI/CD 模拟器）完美地展示了新架构的优势：即使是包含多节点循环的复杂逻辑，在静态图中也表现得清晰、无歧义且高度可观测。这不仅是文档的补充，更是我们对“显式控制流”这一架构决策的有力背书。

### 目标
将 `examples/visualize_explicit_jumps.py` 提交到 Git 仓库，作为官方示例。

### 基本原理
通过代码示例进行文档化（Documentation-as-Code）是开发者最易于接受的学习方式。该脚本涵盖了 `cs.Jump`, `cs.select_jump` 和 `cs.bind` 的标准用法，为用户提供了可直接复制和修改的模板。

### 标签
#intent/document #flow/ready #priority/low #comp/docs #concept/ui #scope/dx #ai/instruct #task/domain/documentation #task/object/visualization-demo #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交演示脚本

我们将新的示例文件添加到暂存区并执行提交。

~~~~~act
git_add
examples/visualize_explicit_jumps.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
docs: Add example for explicit jump visualization

Adds 'examples/visualize_explicit_jumps.py' which simulates a CI/CD pipeline (checkout -> lint -> test -> fix -> lint) using the new explicit control flow primitives.

The demo showcases:
- How to define cross-node jumps using cs.Jump and JumpSelectors.
- How to statically bind control flow using cs.bind.
- How 'cs.visualize' renders complex, non-linear topologies with distinct 'jump' edges and labels.

This serves as a living documentation for the v1.4+ explicit control flow model.
~~~~~

### 下一步建议
随着可视化和示例的完成，我们已经在“可观测性”和“开发者体验”上打下了坚实基础。

根据 [Cascade 架构演进路线图](01_current/Cascade%20架构演进路线图%20-%20显式控制流与统一身份体系.md)，我们已经完成了前三个阶段（基础原语、引擎集成、清理旧体系）。现在，最激动人心的时刻到了：

**阶段四：建立统一的双层身份体系**

我们将重构哈希算法，区分“实例哈希”（用于缓存结果）和“蓝图哈希”（用于缓存执行计划）。这将使 Cascade 的执行速度实现质的飞跃。

如果你准备好了，我们可以先从定义新的哈希契约（TDD）开始。
