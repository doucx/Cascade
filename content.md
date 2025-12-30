好的，我们已经成功重构了 `sql` 和 `ipfs` 提供者的核心逻辑，并修正了受影响的单元测试，使其完全符合 Cascade 的核心架构契约。现在，我将生成一个 `[COMMIT]` 计划来永久化这些变更。

## [COMMIT] refactor(providers): unify LazyFactory to return Task objects

### 用户需求
统一 `LazyFactory` 协议的实现，确保所有内置提供者（如 `cs.sql` 和 `cs.ipfs`）都返回功能完备的 `Task` 对象，从而满足类型检查要求并提供一致的 DSL 组合能力。

### 评论
这是一个关键的架构对齐步骤。它不仅消除了 `pyright` 报告的类型错误，更重要的是消除了系统中的“二等公民”任务。现在，内置提供者与用户自定义任务在行为上完全一致，都支持 `.map()` 等高级组合操作。

### 目标
1.  提交 `sql.py` 和 `ipfs/provider.py` 的重构代码。
2.  提交 `test_sql.py` 和 `test_ipfs.py` 的修正测试。
3.  确保所有变更已作为一个逻辑单元被 Git 跟踪。

### 基本原理
我们通过以下行动达成了目标：
*   **提供者重构**：移除了中间工厂函数，直接返回被 `@task` 装饰的任务对象。
*   **API 显式化**：将 SQL 资源的注入从魔术字符串改为显式的 `cs.inject()`，提高了代码的透明度。
*   **测试适配**：修正了测试中对 `Task` API 的错误假设，并解决了异步测试环境下的 fixture 兼容性问题。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/tests #scope/api #scope/dx #ai/refine #task/domain/architecture #task/object/provider-contract #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将把重构后的提供者源码和修正后的测试文件添加到 Git 暂存区，并创建一个详细的提交。

~~~~~act
git_add
packages/cascade-library/src/cascade/providers/sql.py
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/provider.py
packages/cascade-library/tests/test_sql.py
packages/cascade-provider-ipfs/tests/test_ipfs.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(providers): unify LazyFactory to return Task objects

This commit resolves a core architectural inconsistency where some providers (SQL, IPFS) returned plain functions instead of 'Task' objects, violating the 'LazyFactory' protocol and breaking DSL consistency.

Key Changes:
- Refactored 'sql.py' to return the '@task' decorated '_sql_task' directly.
- Updated 'cs.sql' API to require explicit connection injection via 'cs.inject()'.
- Rewrote IPFS provider to use atomic, self-contained tasks for 'cat' and 'add' operations.
- Updated 'test_sql.py' to reflect the correct separation of responsibilities between 'Task' (template) and 'LazyResult' (instance).
- Fixed 'test_ipfs.py' by correctly implementing async fixtures as 'async def'.

These changes ensure that all built-in providers now support the full range of Task features, including '.map()' and policy chaining, providing a unified and predictable experience for developers.
~~~~~

### 下一步建议
我们已经完成了“提供者契约”这一裂痕的修复。接下来，我建议处理：

- **### 2. `ResourceDefinition` 类型的职责混乱**：这涉及 `cascade/spec/resource.py` 的重构，以及 `Engine` 和 `ResourceContainer` 如何处理资源提供者的逻辑，这将进一步稳固系统的资源管理基石。
