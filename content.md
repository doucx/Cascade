You are absolutely right. My apologies for the oversight. Your analysis of the file structure is correct: the Python package is already named `cascade.runtime`, but it lives inside a distribution package directory named `cascade-engine`.

This simplifies the task significantly. We do not need a Stitcher migration for the Python namespace as it's already correct. The task is purely an infrastructural change: renaming the distribution package and updating all references to it in the build system.

Here is the updated plan, which directly modifies the file system and configuration files using `act` commands.

### 1. 物理重命名 (Physical Rename)

首先，我们将 `packages/cascade-engine` 目录重命名为 `packages/cascade-runtime`。

~~~~~act
move_file
packages/cascade-engine
packages/cascade-runtime
~~~~~

### 2. 更新自身配置 (Update Self Configuration)

接下来，修正 `cascade-runtime` 包自己的 `pyproject.toml`，将其项目名称从 `cascade-engine` 更新为 `cascade-runtime`。

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "cascade-engine"
~~~~~
~~~~~toml
[project]
name = "cascade-runtime"
~~~~~

### 3. 更新依赖引用 (Update Dependency References)

现在，我们将遍历 Monorepo 中所有依赖于旧包名的 `pyproject.toml` 文件，并更新它们。

#### 3.1 `cascade-application`

~~~~~act
patch_file
packages/cascade-application/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-graph",
  "cascade-common"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-runtime",
  "cascade-graph",
  "cascade-common"
]
~~~~~
~~~~~act
patch_file
packages/cascade-application/pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-graph = { workspace = true }
cascade-common = { workspace = true }
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-graph = { workspace = true }
cascade-common = { workspace = true }
~~~~~

#### 3.2 `cascade-sdk`

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common",
  "cascade-graph",
  "cascade-application",
  "cascade-library"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-runtime",
  "cascade-common",
  "cascade-graph",
  "cascade-application",
  "cascade-library"
]
~~~~~
~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-common = { workspace = true }
cascade-application = { workspace = true }
cascade-graph = { workspace = true }
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-common = { workspace = true }
cascade-application = { workspace = true }
cascade-graph = { workspace = true }
~~~~~

#### 3.3 `cascade-library`

~~~~~act
patch_file
packages/cascade-library/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-engine"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-runtime"
]
~~~~~
~~~~~act
patch_file
packages/cascade-library/pyproject.toml
~~~~~
~~~~~toml
[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
redis = ["cascade-engine[redis]"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer",
  "PyYAML",
  "aiobotocore",
  "cascade-engine[redis]",
]
~~~~~
~~~~~toml
[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
redis = ["cascade-runtime[redis]"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer",
  "PyYAML",
  "aiobotocore",
  "cascade-runtime[redis]",
]
~~~~~
~~~~~act
patch_file
packages/cascade-library/pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-sdk = { workspace = true }
cascade-engine = { workspace = true }
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-sdk = { workspace = true }
cascade-runtime = { workspace = true }
~~~~~

#### 3.4 根 `pyproject.toml`

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
dependencies = [
    "cascade-spec",
    "cascade-engine",
    "cascade-sdk",
    "cascade-graph",
    "cascade-library",
    "cascade-vm",
    "cascade-compiler",
]
~~~~~
~~~~~toml
dependencies = [
    "cascade-spec",
    "cascade-runtime",
    "cascade-sdk",
    "cascade-graph",
    "cascade-library",
    "cascade-vm",
    "cascade-compiler",
]
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
~~~~~
~~~~~toml
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-runtime",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-engine/src", "packages/cascade-graph/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src", "packages/cascade-std/src" ] }
]
~~~~~
~~~~~toml
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-runtime/src", "packages/cascade-graph/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src", "packages/cascade-std/src" ] }
]
~~~~~

完成以上操作后，整个 Monorepo 的构建配置就与新的 `cascade-runtime` 包名对齐了。最后，你需要运行 `uv sync` 来刷新你的开发环境。
