好的，已经完成了测试架构的重构。现在我们将这些更改作为一个完整的逻辑单元提交到 Git 仓库。

## [COMMIT] refactor(tests): 集中化共享 Fixture 并实现全局状态清理

### 用户需求

将分散在各处的共享测试 Fixture（`bus_and_spy`）和清理逻辑（`cleanup_local_bus`）整合到根目录的 `conftest.py` 中，消除 DRY 违规并确保测试隔离性。

### 评论

这次重构完成了 `Monorepo Testing Architecture` 规范的落地。通过将全局逻辑移至根注册中心，我们显著降低了维护成本，并为未来编写更健壮的测试奠定了基础。

### 目标

1.  将 `conftest.py` 的修改提交到仓库。
2.  记录删除冗余 `conftest.py` 文件的操作。

### 基本原理

在之前的 `[WIP]` 计划中，我们已经执行了文件系统层面的修改。现在，我们通过 Git 提交将这些更改持久化，并提供详尽的提交信息，以便于后续审计和追踪。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/fixtures #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将修改后的根 `conftest.py` 以及被删除的文件路径添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
conftest.py
packages/cascade-runtime/tests/conftest.py
tests/e2e/runtime/conftest.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): centralize shared fixtures and implement global state cleanup

This commit consolidates shared pytest fixtures into the root 'conftest.py' to adhere to the Monorepo Testing Architecture Specification and eliminate DRY violations.

Changes:
- Moved 'bus_and_spy' fixture from package-specific conftests to the root registry.
- Promoted 'cleanup_local_bus' to a global 'autouse' fixture to ensure reliable state isolation across all tests (E2E and unit).
- Removed redundant 'conftest.py' files in 'packages/cascade-runtime/tests/' and 'tests/e2e/runtime/'.

This centralization simplifies test maintenance and ensures a consistent event-driven testing environment project-wide.
~~~~~

### 下一步建议

-   **验证**: 建议运行 `pytest --reactor-backend=python` 来验证全量测试是否通过。
-   **持续重构**: 随着项目的增长，应定期审查 `cascade-test-utils` 中的 Helper 函数，看是否有通用的逻辑可以进一步抽象为 Fixture。
