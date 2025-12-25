好的，我们已经成功完成了测试目录结构的重构，解决了 Fixture 发现问题，并优化了测试的隔离性。现在是时候将这些改进作为一个完整的逻辑单元提交了。

我将生成一个 `[COMMIT]` 计划，将所有更改添加到 Git 暂存区并创建一个详细的提交。

## [COMMIT] refactor(tests): Co-locate tests with packages and optimize structure

### 用户需求
用户要求将之前的所有更改（包括测试目录重构、Fixture 修复和结构优化）作为一个完整的提交记录。

### 评论
这次重构不仅改善了项目的物理布局，还通过修正 Pytest 发现机制和增强测试隔离性，显著提升了测试套件的健壮性和可维护性。现在的结构符合现代 Python “代码与测试共存”的最佳实践，为每个包的独立开发和分发打下了坚实基础。

### 目标
1. 将所有修改后的文件添加到 Git 暂存区。
2. 创建一个详尽的、符合 Conventional Commits 规范的提交。

### 基本原理
我们使用 `git_add .` 来捕获所有的结构性变更（包括目录移动、新文件的创建和现有文件的修改）。提交信息将详细说明此次重构的动机、采取的行动以及解决的关键问题。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #comp/build #scope/dx #ai/instruct #task/domain/testing #task/object/git-commit #task/action/commit #task/state/end #task/status/completed

---
### Script

#### Acts 1: 提交变更

我们将所有更改添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
.
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): Co-locate tests with packages and optimize structure

This commit performs a major overhaul of the testing infrastructure to align with modern Python "code-co-location" best practices.

Key Changes:
- Relocated package-specific tests from the top-level 'tests/' directory into 'packages/*/tests/'.
- Implemented localized 'conftest.py' files within each package to fix Pytest fixture discovery issues (notably 'bus_and_spy').
- Moved the 'cleanup_local_bus' autouse fixture to 'packages/cascade-engine/tests/e2e/conftest.py' to ensure proper test isolation and prevent state leakage between E2E tests.
- Flattened the redundant 'tests/e2e/e2e/' directory structure into 'tests/e2e/'.
- Fixed a NameError and harness configuration in 'test_e2e_robustness.py' where the controller and engine were not sharing a connector instance.

Results:
- Improved modularity: Packages are now self-contained with their own tests and fixtures.
- Enhanced DX: Related code and tests are physically closer, reducing cognitive load.
- Stable CI: Eliminated race conditions and fixture failures caused by the previous directory mismatch.
~~~~~

### 下一步建议
- **CI 验证**: 建议在远程 CI 环境中运行一次完整的测试，以确保环境差异不会影响测试的发现。
- **文档更新**: 如果有开发者文档描述了如何运行测试，可能需要更新相关指令，建议使用 `pytest packages/` 或针对特定包运行。
