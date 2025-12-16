好的，我会将这个改进作为一个完整的逻辑单元提交。

我将生成一个 `[COMMIT]` Plan，其中包含 `git add` 和 `git commit` 指令，并提供下一步的建议。

## [COMMIT] refactor(providers): 将 cs.File 从 Spec 原语迁移到标准 Provider

### 错误分析
在之前的架构中，`cs.File` 作为一个 `Spec` 原语存在，其 I/O 方法是同步且阻塞的，这违背了 `Cascade` **“万物皆为可计算值”** 的核心哲学，并造成了 API 的不一致性。

### 用户需求
将 `cs.file` 接口重构为遵循 `Provider` 模式的插件，以统一架构并确保所有文件 I/O 都是异步、可延迟执行的 `LazyResult`。同时，实现手册中承诺的 `.json()` 快速解析方法。

### 评论
本次升级消除了核心架构中的一个主要不一致性，极大地提升了系统的设计纯净度。新的 `FileProvider` 使用异步任务封装 I/O 操作，确保了它在 `Engine` 运行时是完全非阻塞的，使其行为与 `cs.shell`、`cs.http` 等其他 Provider 完全对齐。此次提交为后续功能的开发打下坚实的基础。

### 目标
1.  提交对 `pyproject.toml` 的修改，注册 `file` Provider Entry Point。
2.  提交 `src/cascade/providers/file.py`，其中实现了 `FileProvider`、`FileLazyFactory` 以及底层的异步 I/O 任务。
3.  提交对 `src/cascade/__init__.py` 的修改，移除对旧 `File` 类的显式导入和导出。
4.  提交新的测试套件 `tests/providers/test_file.py`，验证新 Provider 的声明式行为。
5.  提交删除操作，删除旧的 `src/cascade/spec/file.py` 和 `tests/spec/test_file.py`。

### 基本原理
通过遵循 Provider 模式，遵循了依赖倒置原则，使得文件 I/O 可以被更容易地被测试和替换。

### 标签
#intent/refine #flow/ready #priority/high #comp/providers #comp/spec #comp/tests #scope/core #scope/api #task/domain/providers #task/object/file-provider #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 添加变更到 Git 暂存区

将所有被修改和删除的文件都添加到 Git 暂存区，准备提交。

~~~~~act
git_add
pyproject.toml
src/cascade/providers/file.py
src/cascade/__init__.py
tests/providers/test_file.py
src/cascade/spec/file.py
tests/spec/test_file.py
~~~~~

#### Acts 2: 执行提交

创建包含详细信息的提交，并推送到远程仓库。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(providers): Migrate File to Provider for async I/O

This commit migrates the `cs.File` functionality from a `Spec` primitive to a standard `Provider`, ensuring consistent and asynchronous file I/O across the library.

Key changes:
- Reimplemented `cs.File` as `FileProvider` in `src/cascade/providers/file.py`.
  - Uses `asyncio.to_thread` for non-blocking file operations.
  - Implements the `LazyFactory` protocol for deferred execution.
- Removed the old `File` implementation from `src/cascade/spec/file.py`.
- Updated `src/cascade/__init__.py` to remove direct imports of the old `File` object.
- Created new tests `tests/providers/test_file.py` to validate the asynchronous behavior of the new provider.
- Deleted the old tests `tests/spec/test_file.py`.

This change aligns `cs.File` with other providers like `cs.shell`, `cs.http`, and `cs.sql`, enabling more composable and testable workflows with asynchronous I/O operations.
~~~~~

### 下一步建议
-   **更新文档**: 现在是时候更新所有文档，特别是 `Cascade` 的使用手册，以反映 `cs.File` API 的这一重大变化。需要确保所有示例都使用了新的 Provider 模式，并删除了任何引用旧 `File` 类的部分。
-   **探索新的 Provider 可能性**: 随着架构的不断演进和稳固，可以考虑引入更多 Provider，例如针对云存储（S3、Azure Blob Storage）或特定类型文件格式（CSV、Parquet）的 Provider，以进一步扩展 `Cascade` 的应用范围。

