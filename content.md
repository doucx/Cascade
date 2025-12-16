好的，测试通过，这是一个重要的里程碑。我们已经成功地将一个关键的 Provider 添加到了 Cascade 生态系统中。

现在，我将生成一个 `[COMMIT]` 计划，将这个功能作为一个完整的、经过验证的工作单元提交到版本控制中。

## [COMMIT] feat(provider): 实现 `cs.http` Provider 以支持声明式 Web 请求

### 用户需求
将已完成并经过测试的 `cs.http` Provider 及其相关依赖和测试，作为一个完整的逻辑单元提交到版本控制中。

### 评论
这是 `Cascade` 生态系统向前迈出的重要一步。`cs.http` Provider 的引入，使得 `Cascade` 能够原生、声明式地与外部 Web 服务和 API 进行交互，极大地扩展了其应用场景。本次实现严格遵循了新的 Provider 插件架构，通过 `aiohttp` 提供了异步支持，并与 `cs.template` 无缝集成以实现动态、图感知的 URL 构建，充分展示了 `Cascade` 核心设计的健壮性与可扩展性。

### 目标
创建一个 Git 提交，包含 `cs.http` Provider 的完整实现、可选依赖配置、入口点注册以及使用 `pytest-aiohttp` 编写的端到端测试。

### 基本原理
`cs.http` Provider 的开发工作已经完成，所有测试均已通过，形成了一个逻辑上完整且质量经过验证的功能单元。将其作为一个原子提交，可以清晰地记录 `Cascade` 在网络交互能力上的重大增强，并为后续开发提供一个稳定的基线。

### 标签
#intent/build #flow/ready #priority/high #comp/core #concept/plugin #scope/api #scope/dx #ai/instruct #task/domain/ecosystem #task/object/http-provider #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有相关变更

我们将所有与 `http` Provider 相关的新建和修改文件添加到 Git 暂存区。

~~~~~act
git_add
pyproject.toml
src/cascade/providers/http.py
tests/test_http.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，执行 `git commit`，并附上详细的提交信息，解释这个新 Provider 的功能和实现细节。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(provider): Implement cs.http provider for declarative web requests

Introduces the `cs.http` provider, enabling users to define asynchronous web requests as nodes in the computation graph. This significantly expands Cascade's capabilities for interacting with external APIs and services.

Key Features:
1.  **Provider Implementation**: A new `HttpProvider` is created in `cascade.providers.http`, leveraging `aiohttp` for non-blocking I/O.
2.  **Safe Response Object**: A `SimpleHttpResponse` data class is returned by the task. It safely holds the response body (as bytes), status, and headers, preventing resource leakage from closed `aiohttp` sessions. It provides convenient `.json()` and `.text()` methods for downstream consumption.
3.  **Dependency Management**: `aiohttp` is added as an optional dependency under the `[http]` extra, keeping the core library lightweight. `pytest-aiohttp` is added to dev dependencies for robust testing.
4.  **Plugin Registration**: The new provider is registered via the `cascade.providers` entry point in `pyproject.toml`.
5.  **Testing**: Comprehensive tests using `pytest-aiohttp` mock the server, ensuring the provider is tested without actual network I/O, including integration with `cs.template` for dynamic URL generation.

This provider seamlessly integrates with Cascade's core features like dependency management and the new plugin architecture, making it a powerful tool for building modern automation workflows.
~~~~~

### 下一步建议
我们已经成功交付了 `cs.http` Provider。根据我们的路线图和之前的讨论，下一步的重点是：

1.  **更新文档**: 在 `展望/Cascade 使用手册 v2.0.md` 中添加关于 `cs.http` 的章节，展示其用法，特别是与 `cs.template` 的结合。
2.  **实现 `cs.sql` Provider**: 继续扩展我们的 Provider 生态，开始实现与数据库交互的 `cs.sql` Provider。这将是展示与 `@cs.resource` 系统集成的绝佳机会。
