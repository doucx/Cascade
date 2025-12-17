这是一个非常核心的基础设施升级任务。将 I/O 操作统一到 `cs.io` 命名空间下不仅能提高 API 的一致性，也为后续扩展更多存储后端（如 S3, GCS, Azure Blob）奠定了清晰的结构基础。

我将生成一个计划，通过引入 `io.local.*` 和 `io.s3.*` 来实现这一目标，并更新项目配置以支持这些变更。

## [WIP] feat: 统一 I/O 命名空间至 cs.io 并添加 S3 支持

### 用户需求
1.  **命名空间统一**: 将现有的本地文件操作（原 `cs.read.*`, `cs.write.*`）映射到新的统一命名空间 `cs.io.local.*` 下，以规范 API。
2.  **S3 支持**: 引入 `cs.io.s3.*` Provider，支持对 AWS S3 对象存储的读写操作，作为 Cascade 扩展性的验证。
3.  **基础设施更新**: 更新 `pyproject.toml` 以注册新的 Provider 入口点并管理新的可选依赖（`aiobotocore`）。

### 评论
这个变更严格遵循了“提供者组合优于封装”的原则。S3 Provider 被设计为原子化的 `read` 和 `write` 操作，这意味着它们可以像本地文件操作一样被轻易地组合进任何工作流中。同时，通过继承现有的 `io` Provider 来实现 `io.local`，我们保持了代码的 DRY (Don't Repeat Yourself) 并确保了向后兼容性。

### 目标
1.  在 `src/cascade/providers/io.py` 中通过继承创建新的 `io.local.*` Provider 类。
2.  创建 `src/cascade/providers/s3.py`，实现基于 `aiobotocore` 的 S3 读写能力。
3.  更新 `pyproject.toml`，添加 `s3` 依赖组，并注册上述所有新 Provider。

### 基本原理
- **命名空间策略**: 使用 `.` 分隔的命名空间（如 `io.local.read_text`）配合 Cascade 的 `ProviderNamespace` 机制，可以自然地形成层级化的 API (`cs.io.local.read_text`)。
- **延迟加载**: S3 的依赖（`aiobotocore`）比较重，因此必须在 Provider 的 `create_factory` 方法中进行导入检查，确保未安装该依赖的用户不受影响。
- **兼容性**: 我们暂时保留旧的 `read.text` 等入口点，但在文档和新代码中推荐使用 `io.local`。

### 标签
#intent/build #flow/ready #priority/high #comp/providers #scope/api #task/domain/storage #task/object/io-provider #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 扩展本地 IO Provider 以支持新命名空间

我们在 `src/cascade/providers/io.py` 中定义新的 Provider 子类。它们继承自现有的实现，唯一的区别是 `name` 属性变更为 `io.local.*` 前缀。

~~~~~act
patch_file
src/cascade/providers/io.py
~~~~~
~~~~~python
class FsExistsProvider(Provider):
    name = "fs.exists"
    def create_factory(self) -> LazyFactory:
        return _exists_task
~~~~~
~~~~~python
class FsExistsProvider(Provider):
    name = "fs.exists"
    def create_factory(self) -> LazyFactory:
        return _exists_task

# --- New io.local.* Aliases ---

class IoLocalReadTextProvider(ReadTextProvider):
    name = "io.local.read_text"

class IoLocalReadBytesProvider(ReadBytesProvider):
    name = "io.local.read_bytes"

class IoLocalWriteTextProvider(WriteTextProvider):
    name = "io.local.write_text"

class IoLocalWriteBytesProvider(WriteBytesProvider):
    name = "io.local.write_bytes"

class IoLocalExistsProvider(FsExistsProvider):
    name = "io.local.exists"
~~~~~

#### Acts 2: 创建 S3 Provider

我们创建一个新的模块 `src/cascade/providers/s3.py`。它使用 `aiobotocore` 来实现异步的 S3 操作。为了保持原子性，Provider 不处理凭证逻辑，而是依赖 `botocore` 的标准凭证链（环境变量、配置文件、IAM 角色等）。

~~~~~act
write_file
src/cascade/providers/s3.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Optional
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider

try:
    import aiobotocore.session
except ImportError:
    aiobotocore = None


class S3ProviderBase(Provider):
    """Base class for S3 providers handling dependency checks."""
    
    def _check_dependency(self):
        if aiobotocore is None:
            raise ImportError(
                "The 'aiobotocore' library is required to use S3 providers. "
                "Please install it with: pip install cascade-py[s3]"
            )

# --- Tasks ---

@task(name="s3_read_text")
async def _s3_read_text(bucket: str, key: str, encoding: str = "utf-8") -> str:
    session = aiobotocore.session.get_session()
    async with session.create_client("s3") as client:
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            data = await stream.read()
            return data.decode(encoding)


@task(name="s3_read_bytes")
async def _s3_read_bytes(bucket: str, key: str) -> bytes:
    session = aiobotocore.session.get_session()
    async with session.create_client("s3") as client:
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            return await stream.read()


@task(name="s3_write_text")
async def _s3_write_text(bucket: str, key: str, content: str, encoding: str = "utf-8") -> None:
    data = content.encode(encoding)
    session = aiobotocore.session.get_session()
    async with session.create_client("s3") as client:
        await client.put_object(Bucket=bucket, Key=key, Body=data)


@task(name="s3_write_bytes")
async def _s3_write_bytes(bucket: str, key: str, content: bytes) -> None:
    session = aiobotocore.session.get_session()
    async with session.create_client("s3") as client:
        await client.put_object(Bucket=bucket, Key=key, Body=content)


# --- Providers ---

class S3ReadTextProvider(S3ProviderBase):
    name = "io.s3.read_text"
    
    def create_factory(self) -> LazyFactory:
        self._check_dependency()
        return _s3_read_text


class S3ReadBytesProvider(S3ProviderBase):
    name = "io.s3.read_bytes"
    
    def create_factory(self) -> LazyFactory:
        self._check_dependency()
        return _s3_read_bytes


class S3WriteTextProvider(S3ProviderBase):
    name = "io.s3.write_text"
    
    def create_factory(self) -> LazyFactory:
        self._check_dependency()
        return _s3_write_text


class S3WriteBytesProvider(S3ProviderBase):
    name = "io.s3.write_bytes"
    
    def create_factory(self) -> LazyFactory:
        self._check_dependency()
        return _s3_write_bytes
~~~~~

#### Acts 3: 注册 Provider 并更新依赖

更新 `pyproject.toml`，注册新的 `io.local.*` 和 `io.s3.*` 入口点，并添加 `aiobotocore` 到依赖列表。同时，为了方便测试，我们也将 `moto` 添加到 dev 依赖中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
  "pytest-aiohttp",
  "typer[all]",
  "mkdocs",
~~~~~
~~~~~toml
  "pytest-aiohttp",
  "moto[s3]",
  "typer[all]",
  "mkdocs",
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
config = ["PyYAML"]
csp_solver = ["python-constraint"]

# 新增一个 'all' 组，方便一键安装所有可选依赖
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
  "python-constraint",
]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
lookup = "cascade.providers.config:LookupProvider"
"read.text" = "cascade.providers.io:ReadTextProvider"
"read.bytes" = "cascade.providers.io:ReadBytesProvider"
"write.text" = "cascade.providers.io:WriteTextProvider"
"write.bytes" = "cascade.providers.io:WriteBytesProvider"
"fs.exists" = "cascade.providers.io:FsExistsProvider"
~~~~~
~~~~~toml
config = ["PyYAML"]
csp_solver = ["python-constraint"]
s3 = ["aiobotocore"]

# 新增一个 'all' 组，方便一键安装所有可选依赖
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
  "python-constraint",
  "aiobotocore",
]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
lookup = "cascade.providers.config:LookupProvider"
# Legacy aliases
"read.text" = "cascade.providers.io:ReadTextProvider"
"read.bytes" = "cascade.providers.io:ReadBytesProvider"
"write.text" = "cascade.providers.io:WriteTextProvider"
"write.bytes" = "cascade.providers.io:WriteBytesProvider"
"fs.exists" = "cascade.providers.io:FsExistsProvider"
# New cs.io.local namespace
"io.local.read_text" = "cascade.providers.io:IoLocalReadTextProvider"
"io.local.read_bytes" = "cascade.providers.io:IoLocalReadBytesProvider"
"io.local.write_text" = "cascade.providers.io:IoLocalWriteTextProvider"
"io.local.write_bytes" = "cascade.providers.io:IoLocalWriteBytesProvider"
"io.local.exists" = "cascade.providers.io:IoLocalExistsProvider"
# New cs.io.s3 namespace
"io.s3.read_text" = "cascade.providers.s3:S3ReadTextProvider"
"io.s3.read_bytes" = "cascade.providers.s3:S3ReadBytesProvider"
"io.s3.write_text" = "cascade.providers.s3:S3WriteTextProvider"
"io.s3.write_bytes" = "cascade.providers.s3:S3WriteBytesProvider"
~~~~~

### 下一步建议
实现 S3 Provider 的集成测试。由于 S3 依赖外部服务，我们将使用 `moto` 库来模拟 AWS 环境，确保测试可以在无网络、无凭证的环境下运行。这将验证我们新构建的 `cs.io.s3` 确实可用。
