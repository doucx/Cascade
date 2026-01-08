好的，迁移工作已顺利完成。代码已通过重构实现了对 `httpx` 的支持，且测试用例中的环境依赖问题也已修复。

我现在将生成一个 `[COMMIT]` 计划，将这些更改作为一个完整的逻辑单元提交到版本库中。

## [COMMIT] refactor(library): migrate http provider from aiohttp to httpx

### 用户需求
提交将 `cascade-library` 的 HTTP 实现从 `aiohttp` 迁移到 `httpx` 的所有相关更改。

### 评论
这是一次重要的技术栈更新。通过引入 `httpx`，我们不仅获得了更现代的异步 API 和更严谨的超时处理，还为未来支持 HTTP/2 奠定了基础。同时，通过保持 `HttpResponse` 接口的稳定性，我们成功实现了底层驱动的“热插拔”，而未破坏现有的任务编排语义。

### 目标
1.  将 `pyproject.toml`、`http.py` 及其测试文件的修改提交到 Git。

### 基本原理
遵循物理修改与提交隔离的原则。由于之前的 `write_file` 和 `patch_file` 操作已完成且验证通过（或已通过测试修正），现在进行原子化的提交。

### 标签
#intent/refine #flow/ready #priority/medium #comp/runtime #task/domain/io #task/object/http-provider #task/action/migration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交更改

我们将所有涉及迁移的文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/cascade-library/pyproject.toml
packages/cascade-library/src/cascade/providers/http.py
packages/cascade-library/tests/integration/test_http.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(library): migrate http provider from aiohttp to httpx

This commit replaces the core HTTP engine in cascade-library with httpx.

Key changes:
- Updated pyproject.toml to use httpx in [http] and [all] extras.
- Rewrote cascade.providers.http to use httpx.AsyncClient.
- Maintained backward compatibility for user-facing tasks by preserving the HttpResponse dataclass interface.
- Improved multipart file handling using httpx's native support.
- Updated integration tests to ensure compatibility while keeping aiohttp as a test-only dependency for mock servers.

Benefits include better API ergonomics, mandatory timeouts by default, and future-ready HTTP/2 support.
~~~~~

### 下一步建议
- **性能监控**: 在实际的高并发工作流中观察 `httpx` 的内存占用和响应速度。
- **扩展迁移**: 考虑将 `cascade-provider-ipfs` 也迁移到 `httpx`，以统一整个生态系统的 HTTP 客户端实现。
- **HTTP/2 开启**: 如果上游服务支持，可以在 `AsyncClient` 中显式开启 HTTP/2 支持。
