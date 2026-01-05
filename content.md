太棒了。测试全绿标志着这次“手术”取得了圆满成功。我们成功地在没有破坏系统核心功能的前提下，完成了极其复杂的架构分层重构。

现在，我将生成一个 `[COMMIT]` 计划，将这些具有里程碑意义的变更正式提交。

## [COMMIT] refactor: 实现架构分层重构与语义对齐

### 用户需求
将 `cascade-spec` 和 `cascade-runtime` 的目录结构重组，以及 `cascade-sdk` 的配套修复作为一次完整的逻辑工作单元进行提交。

### 评论
这次重构彻底消除了历史债务，为 Cascade 迈向 V3 奠定了坚实的本体论基础。通过将 Spec 明确划分为 DSL、IR、Physical 和 Runtime，系统现在的分层非常清晰，极大地提升了可维护性和未来的扩展能力。

### 目标
1.  将所有重构涉及的文件变更添加到 Git 暂存区。
2.  创建一个详尽的提交说明，记录此次破坏性重构的逻辑和动机。

### 基本原理
按照 Quipu 协议，在确认所有逻辑变更正确且测试通过后，通过一个独立的计划来执行提交操作。这确保了版本历史的整洁和可追溯性。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/spec #comp/runtime #comp/sdk #comp/build
#ai/delegate
#task/domain/architecture #task/object/monorepo #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交架构重构变更

我们将添加受影响的包目录，并提交更改。

~~~~~act
git_add
packages/cascade-spec
packages/cascade-runtime
packages/cascade-sdk
pyproject.toml
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: large-scale directory restructuring and semantic alignment

This is a milestone refactoring that implements the V3 architectural blueprint:

1.  cascade-spec: Restructured into distinct layers:
    - dsl/: Fluent interface, tasks, resources, and inputs.
    - ir/: Intermediate Representation (Graph models, Fingerprinting).
    - physical/: Petri-net based topology, nodes (Bleach/Worker/Stain), and assembly.
    - runtime/: Execution interfaces and telemetry protocols.

2.  cascade-runtime (formerly cascade-engine):
    - Established host/, io/, kernel/, services/, and legacy/ modules.
    - Moved executors and caching into io/.
    - Moved solvers into kernel/.
    - Refactored EventBus and Constraints into services/.

3.  cascade-sdk: Updated the central _IMPORT_MAP to reflect the new module paths, restoring public API integrity.

All core tests passed. This change establishes the "Single Source of Truth" for the new layered architecture.
~~~~~

### 下一步建议
- **清理残留**: 现在物理移动已完成，建议执行一次全局搜索，确保没有过时的字符串注释或文档片段指向旧的路径。
- **CI 验证**: 将分支推送到远程仓库，观察在干净环境下的全量集成测试表现。
- **文档同步**: 接下来需要更新 `.stitcher.yaml` 文件中的文档说明，以匹配新的 FQN（Stitcher 的 `refactor apply` 应该已经处理了一部分，但建议进行人工审计）。

