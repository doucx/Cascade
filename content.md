太好了，测试通过意味着我们的重构和修复已经达到了预期效果，系统现在既符合架构规范，也具备了更强的类型安全性。

我现在生成一个 `[COMMIT]` 计划，将所有的修改作为一个完整的逻辑单元提交。

## [COMMIT] refactor: resolve static analysis errors and migrate context module

### 用户需求
将之前完成的所有代码重构（包括 `context.py` 的迁移）和 Pyright 静态分析错误的修复进行正式提交。

### 评论
这次提交不仅解决了 7 个具体的类型错误，还通过将 `WorkflowContext` 移动到最基础的 `cascade-common` 包，从架构层面优化了项目的依赖结构，消除了潜在的循环依赖风险。这是一个高质量的维护性提交。

### 目标
1.  将所有修改过的文件添加到 Git 暂存区。
2.  创建一个包含详细说明的提交记录，涵盖重构和修复的核心内容。

### 基本原理
遵循 `[COMMIT]` 计划规范，本计划仅包含 Git 操作，以确保提交过程的原子性和可追溯性。提交信息采用 Conventional Commits 规范，清晰地描述了变更的性质和影响。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/graph #comp/spec #comp/common #comp/sdk #concept/dependency-management #scope/dx #ai/instruct #task/domain/testing #task/object/static-analysis #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有涉及的文件添加到暂存区。注意，`git add .` 会捕获文件的移动、删除和修改。

~~~~~act
git_add
packages/cascade-common/
packages/cascade-engine/
packages/cascade-graph/
packages/cascade-spec/
packages/cascade-python/
packages/cascade-sdk/
scripts/generate_stubs.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: resolve pyright errors and migrate context module

This commit resolves 7 static analysis errors reported by Pyright and
optimizes the project architecture by moving the context module.

Core Changes:
1.  Architecture Refactoring:
    - Moved 'context.py' from cascade-sdk to cascade-common.
    - This eliminates circular dependencies where low-level packages
      (cascade-graph) needed to access global workflow context.
    - Updated pyproject.toml dependencies for cascade-common and cascade-graph.
    - Updated all public (cascade-python) and internal import paths.

2.  Type Safety Fixes:
    - Unified 'Node' base class by adding 'has_complex_inputs' and 
      'mapping_factory' attributes, enabling safer property access.
    - Refined type narrowing in 'NodeProcessor' by replacing string-based 
      checks with 'isinstance' calls.
    - Hardened 'Fingerprint' class to automatically handle non-string values.
    - Fixed ResourceDefinition inference in Engine by using explicit 
      instantiation for internal connectors.

3.  Robustness:
    - Added defensive None checks in FlowManager to satisfy type narrowing.
    - Corrected lazy-loading maps and internal stubs generation scripts.

All tests passed across the affected packages.
~~~~~

### 下一步建议
- **CI 集成**: 建议在 CI 流程中加入 `pyright` 检查步骤，防止未来引入类似的类型错误。
- **文档更新**: 如果有开发者文档涉及到 `get_current_context` 的导入路径，请确保同步更新为 `cascade.common.context`。
