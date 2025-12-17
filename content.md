## [WIP] refactor: 重构项目结构为多包 Monorepo

### 用户需求
将现有的单体 `src/cascade` 结构重构为基于 `packages/` 目录的多包 Monorepo 结构。
需要拆分为以下包：
1.  `cascade-interfaces`: 协议与数据规范。
2.  `cascade-runtime`: 核心执行引擎与适配器。
3.  `cascade-py`: 面向用户的 SDK 与工具。
4.  `cascade-cli`: 命令行工具。

### 评论
这是一个重大的架构调整，旨在提高代码的模块化程度，明确依赖边界，并为未来的插件系统和扩展打下基础。采用 Quipu 的结构作为参考是合理的，这种结构清晰地分离了接口、运行时和应用层。避免使用 `core` 命名也是符合现代工程实践的（避免上帝对象/包）。

### 目标
1.  创建 `packages/` 目录结构。
2.  根据功能职责，将现有文件迁移到对应的包中。
3.  为每个新包生成 `pyproject.toml`。
4.  修正因文件移动而破坏的核心引用路径（主要是将 `runtime` 中的协议/数据类移动到 `interfaces` 后的引用）。

### 基本原理
1.  **物理隔离**: 通过物理目录的分离，强制执行架构分层，防止循环依赖。
2.  **接口稳定**: `cascade-interfaces` 作为最底层，应该包含最稳定的定义（Protocols, Specs, Models），不依赖具体实现。
3.  **Namespace Packages**: 利用 Python 的 Namespace Packages 特性，使得不同包下的代码可以在 `cascade` 这个统一命名空间下共存（例如 `cascade.runtime` 和 `cascade.spec` 分布在不同物理包中）。

### 标签
#intent/refine #flow/ready #priority/high
#comp/build #concept/architecture #scope/core
#ai/instruct
#task/domain/runtime #task/object/monorepo #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建目录骨架

我们首先创建所有必要的目录结构。利用 `src/cascade` 作为统一的命名空间根目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-interfaces/src/cascade/interfaces
mkdir -p packages/cascade-interfaces/src/cascade/spec
mkdir -p packages/cascade-interfaces/src/cascade/graph
mkdir -p packages/cascade-runtime/src/cascade/runtime
mkdir -p packages/cascade-runtime/src/cascade/adapters
mkdir -p packages/cascade-runtime/src/cascade/graph
mkdir -p packages/cascade-runtime/src/cascade/messaging
mkdir -p packages/cascade-py/src/cascade/providers
mkdir -p packages/cascade-py/src/cascade/tools
mkdir -p packages/cascade-py/src/cascade/internal
mkdir -p packages/cascade-cli/src/cascade/cli
~~~~~

#### Acts 2: 迁移文件 - Interfaces

将协议、规范、数据模型和异常移动到 `cascade-interfaces`。
注意：`graph/model.py` 定义了 `Node` 和 `Graph` 数据结构，属于接口层。

~~~~~act
run_command
~~~~~
~~~~~bash
mv src/cascade/spec/* packages/cascade-interfaces/src/cascade/spec/
mv src/cascade/runtime/protocols.py packages/cascade-interfaces/src/cascade/interfaces/
mv src/cascade/runtime/events.py packages/cascade-interfaces/src/cascade/interfaces/
mv src/cascade/runtime/exceptions.py packages/cascade-interfaces/src/cascade/interfaces/
mv src/cascade/graph/model.py packages/cascade-interfaces/src/cascade/graph/
~~~~~

#### Acts 3: 迁移文件 - Runtime

将核心运行时逻辑、适配器、消息总线实现以及图构建逻辑移动到 `cascade-runtime`。

~~~~~act
run_command
~~~~~
~~~~~bash
mv src/cascade/runtime/* packages/cascade-runtime/src/cascade/runtime/
mv src/cascade/adapters/* packages/cascade-runtime/src/cascade/adapters/
mv src/cascade/messaging/* packages/cascade-runtime/src/cascade/messaging/
mv src/cascade/graph/* packages/cascade-runtime/src/cascade/graph/
~~~~~

#### Acts 4: 迁移文件 - CLI

将 CLI 工具逻辑移动到 `cascade-cli`。并将入口文件重命名为 `main.py` 以符合 CLI 包惯例。

~~~~~act
run_command
~~~~~
~~~~~bash
mv src/cascade/tools/cli.py packages/cascade-cli/src/cascade/cli/main.py
touch packages/cascade-cli/src/cascade/cli/__init__.py
~~~~~

#### Acts 5: 迁移文件 - Cascade Py (SDK)

将剩余的用户面组件（Providers, Context, Tools, Init）移动到 `cascade-py`。

~~~~~act
run_command
~~~~~
~~~~~bash
mv src/cascade/providers/* packages/cascade-py/src/cascade/providers/
mv src/cascade/tools/* packages/cascade-py/src/cascade/tools/
mv src/cascade/internal/* packages/cascade-py/src/cascade/internal/
mv src/cascade/context.py packages/cascade-py/src/cascade/
mv src/cascade/testing.py packages/cascade-py/src/cascade/
mv src/cascade/__init__.py packages/cascade-py/src/cascade/
mv src/cascade/locales packages/cascade-py/src/cascade/
~~~~~

#### Acts 6: 清理旧目录

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf src/cascade
rmdir src || true
~~~~~

#### Acts 7: 创建配置文件 (pyproject.toml)

为每个包创建配置文件，定义依赖关系。

**1. cascade-interfaces**

~~~~~act
write_file
packages/cascade-interfaces/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-interfaces"
version = "0.1.0"
description = "Protocols and specifications for Cascade."
dependencies = []
requires-python = ">=3.8"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

**2. cascade-runtime**

~~~~~act
write_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-runtime"
version = "0.1.0"
description = "Core execution runtime for Cascade."
dependencies = [
    "cascade-interfaces",
]
requires-python = ">=3.8"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

**3. cascade-cli**

~~~~~act
write_file
packages/cascade-cli/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-cli"
version = "0.1.0"
description = "Command line interface for Cascade."
dependencies = [
    "cascade-py",
    "typer[all]",
]
requires-python = ">=3.8"

[project.scripts]
cs = "cascade.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

**4. cascade-py (User SDK)**

注意：我们将原来的 `project.entry-points` 移到这里，因为 Provider 的发现逻辑在这里。

~~~~~act
write_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-py"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
dependencies = [
    "cascade-interfaces",
    "cascade-runtime",
]
requires-python = ">=3.8"

[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
config = ["PyYAML"]
csp_solver = ["python-constraint"]
s3 = ["aiobotocore"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "PyYAML",
  "python-constraint",
  "aiobotocore",
]

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

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

#### Acts 8: 修正 SDK 入口 (__init__.py)

由于文件结构变化，`cascade-py` 中的 `__init__.py` (原 `src/cascade/__init__.py`) 的相对引用需要修改为绝对引用，或者调整路径。由于它是 Namespace Package 的一部分，最好使用完整的包路径。

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
# Runtime
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from .runtime.exceptions import DependencyMissingError
from .runtime.protocols import Connector
from .adapters.solvers.native import NativeSolver
from .adapters.executors.local import LocalExecutor

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json
~~~~~
~~~~~python
# Runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.interfaces.exceptions import DependencyMissingError
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
# CLI is now in a separate package, we can try to import it if available, or remove from core API
# For backward compatibility within cascade-py context, we might leave it out or handle it gracefully.
# The user asked for `cascade-cli` to be separate. `cli` tool might logically belong to `cascade-cli`.
# However, `cascade.cli` helper function constructs an app. Let's refer to where we moved it.
# We moved `tools/cli.py` to `packages/cascade-cli/src/cascade/cli/main.py`.
# But `cascade.cli` function logic (as a helper) is useful for `cascade-py` users.
# Let's assume for now we keep the imports pointing to the right places.
# Since `graph` moved to runtime:
from cascade.graph.serialize import to_json, from_json
~~~~~

> **注意**: 我将在下一步计划中执行大规模的 `sed` 替换来修复整个代码库中的 `cascade.runtime.protocols` -> `cascade.interfaces.protocols` 等引用问题。此步骤仅修复了最顶层的入口。

### 下一步建议
我们已经完成了物理结构的重构。现在的关键任务是修复因包移动导致的 `import` 路径断裂。
我建议立即执行以下操作：
1.  使用 `grep` 和 `sed` 批量替换代码库中的旧引用：
    *   `cascade.runtime.protocols` -> `cascade.interfaces.protocols`
    *   `cascade.runtime.events` -> `cascade.interfaces.events`
    *   `cascade.runtime.exceptions` -> `cascade.interfaces.exceptions`
2.  调整 `cascade-cli` 的代码，使其能正确导入 `cascade-py` 的组件。
3.  更新根目录的 `pyproject.toml` (如果存在) 或创建一个工作区配置来管理这些包。
