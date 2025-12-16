好的，资源约束模型的元数据层已完成，现在我们创建一个原子化的提交。

## [COMMIT] feat(core): Add resource constraint model to Node and LazyResult

### 用户需求
引入资源感知调度的基础结构，允许任务声明资源需求（如 CPU, GPU, 内存）。

### 评论
该任务是实现高级调度和健壮性管理的关键一步。通过在 `LazyResult` 上暴露 `.with_constraints()` API 并将约束元数据化到 `Node` 模型中，我们严格遵循了洋葱架构，将约束的规格定义与未来的调度实现逻辑解耦。这是一个逻辑上完整的、可提交的工作单元。

### 目标
将所有关于资源约束的修改和新增的测试文件提交到一个原子化的 Git Commit 中。

### 基本原理
资源约束元数据是核心工作流管理所需的持久化信息。在完成其定义和传递后，应立即提交以确保工作单元的完整性。后续的序列化支持和调度逻辑将依赖于这些已固化的模型。

### 标签
#intent/build #flow/ready #priority/high #comp/core #concept/solver #task/domain/core #task/object/resource-constraint #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 暂存所有与资源约束相关的修改和新增文件

~~~~~act
git_add
src/cascade/spec/constraint.py
src/cascade/spec/task.py
src/cascade/graph/model.py
src/cascade/graph/build.py
src/cascade/__init__.py
tests/spec/test_constraint.py
~~~~~

#### Acts 2: 提交变更

创建一个详细的 Git Commit，描述本次功能增强。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Add resource constraint model to Node and LazyResult

This commit introduces the necessary metadata structures to support resource-aware scheduling in future advanced solvers (like CSPSolver).

Key changes:
1. `ResourceConstraint` spec is defined, allowing tasks to declare requirements (e.g., `gpu_count`, `memory_gb`).
2. `LazyResult` gains `.with_constraints(**kwargs)` for declarative setup.
3. `GraphBuilder` and `Node` model are updated to propagate and store this metadata on the computation graph node.
4. Exported `cs.with_constraints` as a helper function.

The execution logic remains unchanged, as resource scheduling will be implemented in a future adapter/solver.
~~~~~

### 下一步建议
资源约束模型现已在图结构中稳定。下一步，我们需要更新图序列化模块 (`src/cascade/graph/serialize.py`)，使其能够正确地序列化和反序列化新的 `ResourceConstraint` 对象，从而保证图的持久化是无损的。
