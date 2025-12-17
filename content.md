## [COMMIT] feat(io): Unify I/O namespace to `cs.io.local` and add S3 provider

### 用户需求
1.  将本地文件 I/O (read/write/exists) 统一到 `cs.io.local.*` 命名空间。
2.  引入 `cs.io.s3.*` Provider，支持异步 S3 读写操作，依赖 `aiobotocore`。

### 评论
这个提交代表了 Cascade 核心基础设施的一个重要里程碑。通过引入 `cs.io` 命名空间，我们为未来的多种存储后端（S3, GCS, etc.）定义了一个清晰且可扩展的抽象层。S3 Provider 的实现是高度原子化的，严格遵循了“提供者组合优于封装”的设计原则。对测试套件的多次修复，最终选择了最健壮的 `moto` 服务器模式和环境变量配置，确保了测试的稳定性和隔离性。

### 目标
提交所有关于 `cs.io` 命名空间统一、S3 Provider 文件创建和 `pyproject.toml` 配置的变更。

### 基本原理
完成的任务包括：
1.  创建 `src/cascade/providers/s3.py`，实现异步 S3 读写任务。
2.  修改 `src/cascade/providers/io.py`，添加 `io.local.*` 别名 Provider。
3.  更新 `pyproject.toml`，注册所有新的 Provider 入口点，并添加 `s3` 可选依赖。
4.  创建并稳定 `tests/providers/test_s3.py`，验证 S3 读写功能和依赖检查。

### 标签
#intent/build #flow/ready #priority/high #comp/providers #comp/tests #concept/executor #scope/api #scope/dx #task/domain/storage #task/object/io-provider #task/action/integration #task/state/end

---

### Script

#### Acts 1: 添加所有变更文件到 Git 暂存区

~~~~~act
git_add
pyproject.toml
src/cascade/providers/io.py
src/cascade/providers/s3.py
tests/providers/test_s3.py
~~~~~

#### Acts 2: 创建 Git Commit

~~~~~act
git_commit
~~~~~
~~~~~text
feat(io): Unify I/O namespace to `cs.io.local` and add S3 provider

This feature unifies all file I/O providers under the new `cs.io` namespace, providing a consistent abstraction layer for various storage backends.

Key changes:
1.  **Namespace Unification**: Existing local file providers (e.g., `read.text`) are aliased to `io.local.read_text`, laying the groundwork for deprecating the old names.
2.  **S3 Integration**: Introduced `io.s3.read_text` and `io.s3.write_text` (and byte variants) using `aiobotocore`, adding the first external storage backend.
3.  **Testing Infrastructure**: Added robust, isolated integration tests for the S3 provider using `moto` in server mode and configured via `AWS_ENDPOINT_URL_S3` environment variables, ensuring zero dependency on actual network calls or real credentials.

This completes Task 1.1 of the roadmap.
~~~~~

### 下一步建议
我们已经完成了路线图的第一阶段任务 1.1。现在可以着手进行**任务 1.2: `cs.http` 原子化网络提供者**。

这个任务的目标是完善 `cs.http` Provider，使其成为一个高度原子化、专注于网络传输的积木。目前 `src/cascade/providers/http.py` 中的实现已经存在，但需要确保它返回一个易于组合的 **数据类 (`SimpleHttpResponse`)**，而不是一个复杂的、难以序列化的 `aiohttp` 响应对象。这与路线图中的指导原则完全一致。
