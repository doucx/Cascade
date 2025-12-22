好的，我们立即开始最后一阶段的核心架构重构。

此计划将完成架构建议书中的最终目标：创建一个 `cascade-library` 包，将所有具体的 Provider 实现从 `cascade-sdk` 中剥离出来，使 SDK 本身成为一个纯粹、轻量级的核心。

## [WIP] refactor(arch): Decouple providers into a dedicated cascade-library package

### 用户需求
创建 `cascade-library` 包，并将所有内置的 Provider（如 `http`, `sql`, `io` 等）从 `cascade-sdk` 中迁移过去，完成语义化重构的最后一步。

### 评论
这是实现“小核心，大生态”设计哲学的关键一步。通过将具体的 Provider 实现移入一个独立的“标准库”包，`cascade-sdk` 的职责变得极其纯粹：它只提供定义工作流的语言核心（`@task`, `cs.run`）和扩展机制（Provider 注册表）。这使得核心 SDK 更加稳定，同时让 Provider 生态可以独立版本和演进。

### 目标
1.  创建 `packages/cascade-library` 的目录结构及其 `pyproject.toml` 文件。
2.  将所有与 Provider 相关的配置（`optional-dependencies`, `entry-points`）从 `cascade-sdk` 迁移到 `cascade-library`。
3.  将所有 Provider 的实现文件（`http.py`, `io.py` 等）从 `cascade-sdk` 移动到 `cascade-library`。
4.  更新根 `pyproject.toml`，将 `cascade-library` 添加为工作区成员和顶层依赖。
5.  重新安装工作区依赖并运行测试，以验证重构的正确性。

### 基本原理
此操作将“接口”与“实现”进行了最终分离。`cascade-sdk` 保留了 Provider 的注册机制和核心协议（接口），而 `cascade-library` 则提供了这些接口的一系列官方实现。用户未来可以选择只安装 `cascade-sdk` 核心，并按需安装或开发自己的 Provider 库，这极大地增强了 Cascade 的模块化和可扩展性。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/package-structure #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: 创建 `cascade-library` 包并迁移配置
我们首先创建新包的目录和 `pyproject.toml`。这个配置文件将包含从 `cascade-sdk` 迁移过来的 `optional-dependencies` 和 `entry-points`。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-library/src/cascade/providers
~~~~~

~~~~~act
write_file
packages/cascade-library/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-library"
version = "0.1.0"
description = "Standard library of providers for the Cascade ecosystem."
requires-python = ">=3.8"
dependencies = [
  "cascade-sdk"
]

[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer[all]"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
redis = ["cascade-engine[redis]"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
  "aiobotocore",
  "cascade-engine[redis]",
]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
wait = "cascade.providers.time:TimeWaitProvider"
recv = "cascade.providers.signal:RecvProvider"
template = "cascade.providers.template:TemplateProvider"
"http.get" = "cascade.providers.http:HttpGetProvider"
"http.post" = "cascade.providers.http:HttpPostProvider"
"http.put" = "cascade.providers.http:HttpPutProvider"
"http.delete" = "cascade.providers.http:HttpDeleteProvider"
"http.request" = "cascade.providers.http:HttpRequestProvider"
subflow = "cascade.providers.subflow:SubflowProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
lookup = "cascade.providers.config:LookupProvider"
"read.text" = "cascade.providers.io:ReadTextProvider"
"read.bytes" = "cascade.providers.io:ReadBytesProvider"
"write.text" = "cascade.providers.io:WriteTextProvider"
"write.bytes" = "cascade.providers.io:WriteBytesProvider"
"fs.exists" = "cascade.providers.io:FsExistsProvider"
"io.local.read_text" = "cascade.providers.io:IoLocalReadTextProvider"
"io.local.read_bytes" = "cascade.providers.io:IoLocalReadBytesProvider"
"io.local.write_text" = "cascade.providers.io:IoLocalWriteTextProvider"
"io.local.write_bytes" = "cascade.providers.io:IoLocalWriteBytesProvider"
"io.local.exists" = "cascade.providers.io:IoLocalExistsProvider"
"io.s3.read_text" = "cascade.providers.s3:S3ReadTextProvider"
"io.s3.read_bytes" = "cascade.providers.s3:S3ReadBytesProvider"
"io.s3.write_text" = "cascade.providers.s3:S3WriteTextProvider"
"io.s3.write_bytes" = "cascade.providers.s3:S3WriteBytesProvider"
"io.stdout.write" = "cascade.providers.stdio:StdOutWriteProvider"
"io.stdin.read_line" = "cascade.providers.stdio:StdInReadLineProvider"
dict = "cascade.providers.helpers:DictProvider"
format = "cascade.providers.helpers:FormatProvider"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-sdk = { workspace = true }
cascade-engine = { workspace = true }
~~~~~

#### Acts 2: 移动 Provider 实现文件
我们将所有具体的 provider python 文件从 `sdk` 移动到 `library`。

~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/config.py
packages/cascade-library/src/cascade/providers/config.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/helpers.py
packages/cascade-library/src/cascade/providers/helpers.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/http.py
packages/cascade-library/src/cascade/providers/http.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/io.py
packages/cascade-library/src/cascade/providers/io.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/s3.py
packages/cascade-library/src/cascade/providers/s3.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/shell.py
packages/cascade-library/src/cascade/providers/shell.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/signal.py
packages/cascade-library/src/cascade/providers/signal.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/sql.py
packages/cascade-library/src/cascade/providers/sql.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/stdio.py
packages/cascade-library/src/cascade/providers/stdio.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/subflow.py
packages/cascade-library/src/cascade/providers/subflow.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/template.py
packages/cascade-library/src/cascade/providers/template.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/src/cascade/providers/time.py
packages/cascade-library/src/cascade/providers/time.py
~~~~~

#### Acts 3: 清理 `cascade-sdk` 的配置文件
现在我们从 `cascade-sdk` 的 `pyproject.toml` 中移除已经迁移走的配置项。

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~
[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer[all]"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
redis = ["cascade-engine[redis]"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
  "aiobotocore",
  "cascade-engine[redis]",
]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
wait = "cascade.providers.time:TimeWaitProvider"
recv = "cascade.providers.signal:RecvProvider"
template = "cascade.providers.template:TemplateProvider"
"http.get" = "cascade.providers.http:HttpGetProvider"
"http.post" = "cascade.providers.http:HttpPostProvider"
"http.put" = "cascade.providers.http:HttpPutProvider"
"http.delete" = "cascade.providers.http:HttpDeleteProvider"
"http.request" = "cascade.providers.http:HttpRequestProvider"
subflow = "cascade.providers.subflow:SubflowProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
lookup = "cascade.providers.config:LookupProvider"
"read.text" = "cascade.providers.io:ReadTextProvider"
"read.bytes" = "cascade.providers.io:ReadBytesProvider"
"write.text" = "cascade.providers.io:WriteTextProvider"
"write.bytes" = "cascade.providers.io:WriteBytesProvider"
"fs.exists" = "cascade.providers.io:FsExistsProvider"
"io.local.read_text" = "cascade.providers.io:IoLocalReadTextProvider"
"io.local.read_bytes" = "cascade.providers.io:IoLocalReadBytesProvider"
"io.local.write_text" = "cascade.providers.io:IoLocalWriteTextProvider"
"io.local.write_bytes" = "cascade.providers.io:IoLocalWriteBytesProvider"
"io.local.exists" = "cascade.providers.io:IoLocalExistsProvider"
"io.s3.read_text" = "cascade.providers.s3:S3ReadTextProvider"
"io.s3.read_bytes" = "cascade.providers.s3:S3ReadBytesProvider"
"io.s3.write_text" = "cascade.providers.s3:S3WriteTextProvider"
"io.s3.write_bytes" = "cascade.providers.s3:S3WriteBytesProvider"
"io.stdout.write" = "cascade.providers.stdio:StdOutWriteProvider"
"io.stdin.read_line" = "cascade.providers.stdio:StdInReadLineProvider"
dict = "cascade.providers.helpers:DictProvider"
format = "cascade.providers.helpers:FormatProvider"
~~~~~
~~~~~
[project.optional-dependencies]
# Providers and their dependencies are now in cascade-library
all = []
~~~~~

#### Acts 4: 更新工作区配置
最后，我们将新包注册到 monorepo 的根配置中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~
dependencies = [
    "cascade-spec",
    "cascade-engine",
    "cascade-sdk",
]
~~~~~
~~~~~
dependencies = [
    "cascade-spec",
    "cascade-engine",
    "cascade-sdk",
    "cascade-graph",
    "cascade-library",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-provider-ipfs = { workspace = true }
~~~~~
~~~~~
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-provider-ipfs = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
]
~~~~~
~~~~~
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
]
~~~~~
