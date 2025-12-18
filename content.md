好的，遵照指示，我将为你创建第一阶段“创建新的包结构和配置文件”的 `Plan.md` 文件。

这个计划是自包含的，并且严格遵循了我们共同制定的重构路线图中的第一阶段步骤。

***

没问题，这是执行重构第一阶段的计划。

该计划的目标是为我们的多包（Monorepo）架构搭建骨架。我们将创建所有必需的目录和基础的 `pyproject.toml` 配置文件，为第二阶段的代码迁移做好准备。

## [WIP] refactor(build): Establish monorepo package structure and configs

### 用户需求
根据已制定的重构路线图，执行第一阶段任务：创建 `packages` 目录，为 `cascade-interfaces`、`cascade-runtime`、`cascade-py` 和 `cascade-cli` 四个新包建立标准的目录结构，并为每个包生成基础的 `pyproject.toml` 配置文件。

### 评论
这是整个重构工作的基石。一个清晰、一致的目录结构和预先定义的包元数据，能极大地降低后续代码迁移的复杂性。通过这个步骤，我们为每个组件划分了明确的“领地”，使关注点分离的原则在物理层面得到体现。

### 目标
1.  在项目根目录下创建 `packages` 目录。
2.  在 `packages` 目录内，为四个目标包（`cascade-interfaces`, `cascade-runtime`, `cascade-py`, `cascade-cli`）创建符合 Python `src` 布局的目录结构。
3.  为每个新包分别创建一个 `pyproject.toml` 文件，并填入其核心的项目元数据，如名称、版本和描述。

### 基本原理
我们将采用原子化的步骤来执行此阶段任务。首先，使用一个 `run_command` 指令结合 `mkdir -p` 来一次性、幂等地创建所有必需的目录结构。这比多个单独的创建指令更高效、更可靠。随后，使用四个独立的 `write_file` 指令来精确地生成每个包的配置文件。这种方法确保了结构创建和配置写入是两个独立的、可验证的步骤，完全符合路线图的设计。

### 标签
#intent/architect #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/monorepo-structure #task/action/setup #task/state/begin

---

### Script

#### Acts 1: 创建目录骨架

此操作将创建所有新包所需的目录结构，为后续的文件迁移和配置写入做准备。

~~~~~act
run_command
~~~~~
~~~~~bash
# 创建顶层 packages 目录
mkdir packages

# 为每个包创建标准目录结构
PACKAGE_NAMES="cascade-interfaces cascade-runtime cascade-py cascade-cli"
for pkg in $PACKAGE_NAMES; do
    mkdir -p "packages/$pkg/src/cascade"
done

# 为 cascade-cli 创建其特定的子目录
mkdir -p "packages/cascade-cli/src/cascade/cli"

# 为 cascade-interfaces 创建其特定的子目录
mkdir -p "packages/cascade-interfaces/src/cascade/graph"
mkdir -p "packages/cascade-interfaces/src/cascade/interfaces"

# 为 cascade-runtime 创建其特定的子目录
mkdir -p "packages/cascade-runtime/src/cascade/graph"
~~~~~

#### Acts 2: 写入各包的配置文件

现在，我们将为每个新包创建其 `pyproject.toml` 文件，正式定义它们的身份和元数据。

首先是 `cascade-interfaces`，它将是生态系统的契约中心。
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
description = "Interfaces, specifications, and data models for the Cascade ecosystem."
requires-python = ">=3.8"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

接下来是 `cascade-runtime`，作为我们新的执行核心。
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
description = "The core runtime engine for Cascade workflows."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces @ file:///${PROJECT_ROOT}/packages/cascade-interfaces"
]

[project.optional-dependencies]
csp_solver = ["python-constraint"]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

然后是 `cascade-py`，面向用户的主要库。
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
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces @ file:///${PROJECT_ROOT}/packages/cascade-interfaces",
  "cascade-runtime @ file:///${PROJECT_ROOT}/packages/cascade-runtime"
]

[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer[all]"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
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

最后是 `cascade-cli`，我们的命令行界面入口。
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
description = "Command-line tools for the Cascade workflow engine."
requires-python = ">=3.8"
dependencies = [
  "cascade-py @ file:///${PROJECT_ROOT}/packages/cascade-py",
  "typer[all]"
]

[project.scripts]
cascade = "cascade.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade/cli"]
~~~~~

### 下一步建议
我们已经成功创建了新架构的骨架。接下来的 **第二阶段** 将是整个重构的核心：将现有 `src/cascade` 目录中的所有代码和测试文件，逐一迁移到它们在 `packages/*` 和 `tests/*` 中对应的新家。

如果你同意，我将为你生成执行第二阶段（文件迁移）的计划。
