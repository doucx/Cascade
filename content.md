好的，既然测试已经全部通过，这意味着“cascade-graph 绞杀计划”的核心目标已经达成。我们成功地将逻辑图生成的职责收敛到了编译器，将对象模型收敛到了运行时，并且通过一个兼容层保持了现有代码的稳定性。

现在我将生成一个 `[COMMIT]` 计划，用于物理删除已废弃的包并提交所有更改。

## [COMMIT] refactor(arch): 完成 cascade-graph 绞杀并清理废弃包

### 用户需求
完成“绞杀计划”的最后一步：物理删除 `packages/cascade-graph` 目录，并提交所有相关的架构迁移和重构工作。

### 评论
通过这次重构，我们显著简化了 Monorepo 的包结构。现在：
1.  **编译器 (cascade-compiler)** 负责将 DSL 转换为逻辑 IR。
2.  **运行时 (cascade-runtime)** 拥有自己的图模型 (`model.py`)，不再依赖外部包进行图构建。
3.  **分层一致性**：`BlueprintHasher` 移至 Runtime 层，解决了 Reflection 层的向上依赖问题。

### 目标
1.  物理删除 `packages/cascade-graph`。
2.  提交所有文件的移动、修改以及对 `pyproject.toml` 的更新。

### 基本原理
按照计划，在所有集成测试通过后，废弃的包应该被立即移除，以保持代码库的整洁和 SSoT（单一事实来源）。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/compiler #scope/core #ai/instruct #task/domain/architecture #task/object/cascade-graph #task/action/termination #task/state/end #task/status/completed

---

### Script

#### Acts 1: 物理删除 cascade-graph 包

由于所有逻辑和测试都已迁移至 `cascade-runtime`，我们现在可以安全地删除整个目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-graph
~~~~~

#### Acts 2: 提交所有变更

我们将所有修改过的包和根目录配置文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(arch): terminate cascade-graph and unify graph model in runtime

Completed Operation Graph-Strangler:
1. Moved core object models (Graph, Node, Edge) from cascade-graph to cascade-runtime.
2. Migrated 'BlueprintHasher' from cascade-reflection to cascade-runtime to fix layering violation.
3. Implemented a compatibility 'build_graph' layer in cascade-runtime that uses the new Compiler+Adapter path.
4. Refactored IRToRuntimeAdapter to correctly handle nested list/dict dependencies.
5. Updated all global references from 'cascade.graph' to 'cascade.runtime.graph'.
6. Migrated all unit and integration tests from cascade-graph to cascade-runtime/tests/legacy_graph.
7. Physically removed the packages/cascade-graph directory and updated workspace configurations.

This change consolidates logical graph generation into the compiler and aligns the runtime with a self-contained object model.
~~~~~

### 下一步建议
- **监控 CI**: 观察 CI 环境中的长期运行测试，确保没有遗漏的路径引用。
- **文档更新**: 检查并更新任何涉及包结构的文档或架构图，反映 `cascade-graph` 已不存在的事实。
- **依赖审计**: 在下一次 `uv lock` 时，确认 `cascade-graph` 已完全从依赖树中消失。
