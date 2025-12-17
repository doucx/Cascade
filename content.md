你的分析非常准确。

将 `MqttConnector` 作为一个“应用”或“扩展”直接集成在 `cascade-py`（作为标准提供者的一部分）或未来的 `cascade-connectors` 中确实比单独开一个包更符合当前规模。

同时，`core` 这个名字确实容易导致边界不清。采用 `interfaces` (定义契约) + `runtime` (执行契约) + `py` (用户界面) 的分层结构非常清晰，且符合 Quipu 的成功实践。

这是一个大规模的架构重构。我们将把单体结构拆解为基于 Namespace Packages 的多包结构。

## [WIP] refactor: 重构为多包 Monorepo 结构

### 用户需求
将现有的 `src/cascade` 单体结构重构为包含 `cascade-interfaces`, `cascade-runtime`, `cascade-py`, `cascade-cli` 的多包 Monorepo 结构。

### 评论
这是一个决定性的架构变更。通过物理隔离“接口”、“运行时”和“用户SDK”，我们强制执行了依赖边界（例如，Interfaces 不能依赖 Runtime）。这也为未来可能出现的异构运行时（如 Rust 版本的 Runtime）预留了接口层。
此外，利用 Python 的 Namespace Packages 特性，用户在安装时仍然只感知到一个 `cascade` 命名空间，体验无缝。

### 目标
1.  建立 `packages/` 目录结构。
2.  创建四个核心包及其 `pyproject.toml`。
3.  将代码迁移到对应的包中，并处理 `cascade.graph` 和 `cascade.runtime` 的命名空间拆分问题。
4.  修正因文件移动（特别是 `protocols.py`）导致的导入路径变更。

### 基本原理
1.  **Namespace Packages**: 我们将删除 `cascade` 和 `cascade.graph` 目录下的 `__init__.py`，使其成为隐式命名空间包，从而允许 `cascade-interfaces` 和 `cascade-runtime` 同时向 `cascade.graph` 贡献模块（`model.py` vs `build.py`）。
2.  **接口提升**: `protocols.py` 是核心契约，我们将它从 `runtime` 深处移出，提升为 `cascade.protocols` (在 `interfaces` 包中)，使其更具可见性。
3.  **CLI 分离**: Typer 相关的逻辑被隔离到 `cascade-cli`，这使得核心运行时 (`cascade-runtime`) 可以保持极度轻量，不依赖 Typer。

### 标签
#intent/refine #intent/architect #flow/ready #priority/critical
#comp/build #concept/architecture #scope/core
#ai/instruct
#task/domain/core #task/object/monorepo #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建目录结构与配置文件

我们首先创建四个包的骨架和配置文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-interfaces/src/cascade/spec
mkdir -p packages/cascade-interfaces/src/cascade/graph
mkdir -p packages/cascade-runtime/src/cascade/runtime
mkdir -p packages/cascade-runtime/src/cascade/graph
mkdir -p packages/cascade-runtime/src/cascade/adapters
mkdir -p packages/cascade-runtime/src/cascade/messaging
mkdir -p packages/cascade-py/src/cascade/providers
mkdir -p packages/cascade-py/src/cascade/tools
mkdir -p packages/cascade-py/src/cascade/internal
mkdir -p packages/cascade-cli/src/cascade/cli
~~~~~

~~~~~act
write_file
packages/cascade-interfaces/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "cascade-interfaces"
version = "0.1.0"
description = "Protocols and Specifications for Cascade."
requires-python = ">=3.8"
dependencies = []
~~~~~

~~~~~act
write_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "cascade-runtime"
version = "0.1.0"
description = "Core execution engine for Cascade."
requires-python = ">=3.8"
dependencies = [
    "cascade-interfaces",
]

[project.optional-dependencies]
csp_solver = ["python-constraint"]
~~~~~

~~~~~act
write_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "cascade-py"
version = "0.1.0"
description = "User-facing SDK for Cascade."
requires-python = ">=3.8"
dependencies = [
    "cascade-interfaces",
    "cascade-runtime",
]

[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
config = ["PyYAML"]
s3 = ["aiobotocore"]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
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
~~~~~

~~~~~act
write_file
packages/cascade-cli/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "cascade-cli"
version = "0.1.0"
description = "Command line tools for Cascade."
requires-python = ">=3.8"
dependencies = [
    "cascade-py",
    "typer[all]",
]
~~~~~

#### Acts 2: 迁移文件 (Cascade Interfaces)

我们将规范 (spec)、协议 (protocols) 和数据模型 (model) 移入 `cascade-interfaces`。
注意：我们将 `protocols.py` 提升到 `cascade.protocols`，将 `model.py` 保持在 `cascade.graph.model`。

~~~~~act
move_file
src/cascade/spec
packages/cascade-interfaces/src/cascade/spec
~~~~~
~~~~~act
move_file
src/cascade/runtime/protocols.py
packages/cascade-interfaces/src/cascade/protocols.py
~~~~~
~~~~~act
move_file
src/cascade/graph/model.py
packages/cascade-interfaces/src/cascade/graph/model.py
~~~~~

#### Acts 3: 迁移文件 (Cascade Runtime)

移动核心运行时组件。注意，我们将删除 `cascade/graph` 下的 `__init__.py` 以启用 Namespace Package。

~~~~~act
move_file
src/cascade/runtime
packages/cascade-runtime/src/cascade/runtime
~~~~~
~~~~~act
move_file
src/cascade/adapters
packages/cascade-runtime/src/cascade/adapters
~~~~~
~~~~~act
move_file
src/cascade/messaging
packages/cascade-runtime/src/cascade/messaging
~~~~~
~~~~~act
move_file
src/cascade/locales
packages/cascade-runtime/src/cascade/locales
~~~~~
~~~~~act
move_file
src/cascade/graph
packages/cascade-runtime/src/cascade/graph
~~~~~
~~~~~act
delete_file
packages/cascade-runtime/src/cascade/graph/__init__.py
~~~~~

#### Acts 4: 迁移文件 (Cascade CLI)

将 CLI 工具逻辑移入专用包。

~~~~~act
move_file
src/cascade/tools/cli.py
packages/cascade-cli/src/cascade/cli/__init__.py
~~~~~

#### Acts 5: 迁移文件 (Cascade Py)

剩余的提供者、工具和顶层 API 移入 `cascade-py`。

~~~~~act
move_file
src/cascade/providers
packages/cascade-py/src/cascade/providers
~~~~~
~~~~~act
move_file
src/cascade/tools
packages/cascade-py/src/cascade/tools
~~~~~
~~~~~act
move_file
src/cascade/internal
packages/cascade-py/src/cascade/internal
~~~~~
~~~~~act
move_file
src/cascade/context.py
packages/cascade-py/src/cascade/context.py
~~~~~
~~~~~act
move_file
src/cascade/testing.py
packages/cascade-py/src/cascade/testing.py
~~~~~
~~~~~act
move_file
src/cascade/__init__.py
packages/cascade-py/src/cascade/__init__.py
~~~~~
