简要回答：
已完成 `EdgeType` 枚举的重构。本次提交消除了图模型中对硬编码字符串的所有依赖，提升了系统的类型安全和可维护性。

## [COMMIT] refactor(graph): 引入 EdgeType 枚举以消除魔法字符串

### 用户需求
将引入 `EdgeType` 枚举的重构提交，消除 `GraphBuilder`, `Engine`, `Resolver` 和 `Visualize` 中对特殊边类型硬编码字符串（如 `_condition`, `_implicit_dependency`）的依赖。

### 评论
这个重构是提高 `Cascade` 核心稳定性的关键一步。通过将边的语义意图（数据、条件、约束、隐式依赖）显式化为枚举类型，我们极大地增强了代码的可读性，并降低了未来因字符串拼写错误或约定变更而导致系统逻辑崩溃的风险。

### 目标
提交所有与 `EdgeType` 相关的更改，并将宏观任务标记为完成。

### 基本原理
此变更属于代码重构范畴，通过替换魔法字符串为类型安全的枚举，提高了核心模型的质量。它是对现有实现债的清理，也是未来复杂功能（如分布式执行中的序列化）的必要前置条件。

### 标签
#intent/refine #flow/ready #priority/medium #comp/graph #comp/runtime #concept/state #scope/dx #ai/delegate #task/domain/graph #task/object/edgemodel #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交 EdgeType 重构的所有变更

将所有被修改的文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
src/cascade/graph/model.py
src/cascade/graph/build.py
src/cascade/runtime/engine.py
src/cascade/runtime/resolvers.py
src/cascade/tools/visualize.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(graph): Replace magic strings with EdgeType enum

This refactors the core graph model to eliminate reliance on hardcoded string conventions for special edge types, improving type safety and maintainability.

- **`graph.model`**: Introduces `EdgeType` enum (`DATA`, `CONDITION`, `CONSTRAINT`, `IMPLICIT`) and adds it to the `Edge` dataclass.
- **`graph.build`**: Updates edge creation logic to use `EdgeType` instead of string conventions (`_condition`, implicit dependency, dynamic constraints via prefixing `arg_name`).
- **`runtime.engine`**: Updates the `_should_skip` logic to use `EdgeType.CONDITION` and `EdgeType.DATA/IMPLICIT` for skip cascading checks.
- **`runtime.resolvers`**: `ArgumentResolver` now filters non-data edges explicitly using `EdgeType.DATA`. `ConstraintResolver` now correctly identifies dynamic constraints using `EdgeType.CONSTRAINT`.
- **`tools.visualize`**: Updates visualization rendering logic to interpret edges based on their `EdgeType`.
~~~~~

### 下一步建议

现在核心图模型已经稳定且类型安全。然而，在 `src/cascade/graph/serialize.py` 中，我们存在一个已知技术债务：图序列化对 `EdgeType` 缺乏支持，并且无法正确重建包含 `Router` 元数据的边。

我建议下一个任务是 **改进图序列化机制**：
1.  更新 `serialize.py`，确保 `EdgeType` 能够被正确序列化和反序列化。
2.  解决 `Router` 相关的序列化问题，确保边缘元数据的无损往返（尽管完全重建 `Router` 对象本身很复杂，但我们可以确保图结构和边缘类型是完整的）。

如果你同意，我将生成执行此序列化改进的计划。
