Excellent. The heavy lifting of the test suite refactoring is complete. Now it's time to create a clean, atomic commit that captures this significant improvement to the project's structure and maintainability.

I will generate the `[COMMIT]` plan.

## [COMMIT] refactor(tests): Align test suite structure with src architecture

### 用户需求
将已完成的测试套件重构工作（包括目录结构调整和文件拆分）作为一个单一的、逻辑完整的单元提交到版本控制中。

### 评论
这是一个里程碑式的提交。通过使测试套件的结构成为 `src` 目录“洋葱架构”的镜像，我们极大地提升了开发者体验（DX）和项目的长期可维护性。任何开发者现在都可以通过直觉快速定位到代码及其对应的测试，技术债务得到了有效偿还，为未来的功能开发扫清了障碍。

### 目标
创建一个 Git 提交，该提交包含所有新创建的、移动的和重命名的测试文件，并附有一个清晰、全面的提交信息，解释此次重构的动机和成果。

### 基本原理
整个测试套件的重构，从目录创建到文件拆分，共同构成了一个单一的架构目标：使测试与源码结构对齐。将这些变更合并到一个原子提交中，可以确保版本历史的清晰性，并代表一个完整的、逻辑上的改进。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/suite-structure #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有重构后的测试文件

我们将所有新的和移动后的测试文件添加到 Git 暂存区。`git add` 会自动处理文件的移动、创建和删除。

~~~~~act
git_add
~~~~~
~~~~~text
tests/spec/test_task.py
tests/spec/test_common.py
tests/spec/test_resource.py
tests/spec/test_routing.py
tests/spec/test_async.py
tests/spec/test_file.py
tests/graph/test_build.py
tests/runtime/test_control_flow.py
tests/runtime/test_map.py
tests/runtime/test_retry.py
tests/runtime/test_bus.py
tests/adapters/solvers/test_native.py
tests/adapters/executors/test_local.py
tests/adapters/caching/test_file_existence.py
tests/providers/test_http.py
tests/providers/test_sql.py
tests/providers/test_shell.py
tests/providers/test_template.py
tests/tools/test_preview.py
tests/integration/test_end_to_end.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，我们执行 `git commit`，附上详细的提交信息，记录下这次重要的重构工作。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): Align test suite structure with src architecture

Overhauls the entire `tests/` directory to mirror the "Onion Architecture" of the `src/cascade` source code. This resolves significant technical debt and improves developer experience.

Key Changes:

1.  **Mirrored Structure:** The flat test directory has been replaced with a nested structure that directly corresponds to `src/cascade`'s layers (e.g., `tests/spec`, `tests/graph`, `tests/runtime`, `tests/adapters`).

2.  **File Granularity:** Monolithic test files have been split into smaller, single-responsibility modules.
    -   `test_core_mvp.py` was split into `spec/test_task.py`, `spec/test_common.py`, and `graph/test_build.py`.
    -   `test_adapters.py` was split into `adapters/solvers/test_native.py` and `adapters/executors/test_local.py`.

3.  **Semantic Relocation:** All existing test files were moved to their new, logical locations (e.g., `test_http.py` -> `providers/test_http.py`).

This refactoring makes tests significantly easier to locate, understand, and maintain, ensuring the test suite can scale effectively with the growing complexity of the library.
~~~~~

### 下一步建议
我们已经成功地完成了对测试套件的重构和提交。现在，我们的基础非常稳固。

是时候解决我们在代码审查中发现的具体问题了。我建议我们首先处理最直接的问题：**清理 `src/cascade/providers/http.py` 文件中的冗余代码**。
