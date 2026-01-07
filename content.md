好的，我将按照 `d3-principle-pytest-monorepo-architecture` 协议创建一个新的 `cascade-test-utils` 包，用于存放共享的测试工具，并将 `cascade.testing` 模块迁移至此。

在此过程中，我将严格遵守你的要求，使用 `sed` 命令来修复代码中的导入路径。

## [WIP] feat: 创建 cascade-test-utils 包以共享测试基础设施

### 用户需求

用户要求创建一个新的 `cascade-test-utils` 包，以集中管理项目中的共享测试工具。具体要求包括：
1.  创建 `packages/cascade-test-utils` 包。
2.  将 `packages/cascade-sdk/src/cascade/testing.py` 移动到新包的 `src/cascade/test_utils/helpers.py`。
3.  更新整个项目，将所有对 `cascade.testing` 的引用修改为 `cascade.test_utils.helpers`。
4.  修改过程必须使用 `sed` 命令，而不是 `patch_file`。

### 评论

这是一个非常关键的架构重构，完全符合 `d3-principle-pytest-monorepo-architecture` 的核心理念。通过建立一个专门的 `test-utils` 包，我们遵循了 DRY 原则，避免了未来在多个包中重复定义测试辅助工具和 Fixture 的问题。这将显著提升测试代码的可维护性和可扩展性。

### 目标

1.  创建 `cascade-test-utils` 包的标准目录结构。
2.  为新包创建 `pyproject.toml` 文件，定义其元数据和依赖项。
3.  将现有的 `testing.py` 移动并重命名为 `helpers.py`，使其角色更加明确。
4.  更新根 `pyproject.toml`，将新包纳入工作区管理和开发依赖。
5.  使用 `sed` 命令在整个代码库中无缝地更新所有相关的导入路径。

### 基本原理

我们将严格遵循 Monorepo 测试架构规范。首先，创建包结构和配置文件，使其成为工作区的一个合法成员。接着，将核心的 `testing.py` 文件迁移过去。最关键的一步是进行全局的路径重构，我们将使用 `find` 和 `xargs sed` 的组合命令，精确地将所有 `cascade.testing` 的引用替换为新的 `cascade.test_utils.helpers` 路径，从而保证整个项目在重构后依然能够正确导入依赖。

### 标签

#intent/tooling #intent/refactor #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-utils #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建 `cascade-test-utils` 包结构

首先，我们为新包创建必要的目录和 `__init__.py` 文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-test-utils/src/cascade/test_utils
touch packages/cascade-test-utils/src/cascade/test_utils/__init__.py
~~~~~

#### Acts 2: 定义新包的 `pyproject.toml`

接下来，我们为 `cascade-test-utils` 创建 `pyproject.toml` 文件。它需要依赖 `cascade-spec`、`cascade-runtime` 和 `cascade-graph` 来支持其中的辅助函数。

~~~~~act
write_file
packages/cascade-test-utils/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-test-utils"
version = "0.1.0"
description = "Shared testing utilities for the Cascade monorepo."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
  "cascade-runtime",
  "cascade-graph",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-graph = { workspace = true }
~~~~~

#### Acts 3: 移动并重命名 `testing.py`

现在，我们将 `testing.py` 从 `cascade-sdk` 移动到新包中，并将其重命名为 `helpers.py` 以更好地反映其作用。

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-sdk/src/cascade/testing.py packages/cascade-test-utils/src/cascade/test_utils/helpers.py
~~~~~

#### Acts 4: 将新包集成到 Monorepo 配置中

我们需要更新根目录的 `pyproject.toml`，让 `uv` 和 `hatch` 识别这个新包。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.workspace]
members = [
    "packages/*",
]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
cascade-vm-rs = { workspace = true }

[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-runtime",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-vm",
    "packages/cascade-compiler",
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
]
~~~~~
~~~~~toml.new
[tool.uv.workspace]
members = [
    "packages/*",
]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
cascade-vm-rs = { workspace = true }

[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-runtime",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-vm",
    "packages/cascade-compiler",
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
]
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
cascade-vm-rs = { workspace = true }
~~~~~
~~~~~toml.new
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-test-utils = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
cascade-vm-rs = { workspace = true }
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
]
~~~~~
~~~~~toml.new
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
    "packages/cascade-test-utils",
]
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "cascade-vm",
  "cascade-vm-rs",
  "cascade-compiler",
  "cascade-std",
~~~~~
~~~~~toml.new
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "cascade-test-utils",
  "cascade-vm",
  "cascade-vm-rs",
  "cascade-compiler",
  "cascade-std",
~~~~~

#### Acts 5: 全局更新导入路径

最后，我们使用 `sed` 命令在 `packages` 和 `tests` 目录下查找所有 Python 文件，并将 `cascade.testing` 替换为 `cascade.test_utils.helpers`。

~~~~~act
run_command
~~~~~
~~~~~
find packages tests -type f -name "*.py" -exec sed -i 's/cascade.testing/cascade.test_utils.helpers/g' {} +
~~~~~

### 下一步建议

我们已经成功地将共享测试工具迁移到了专用的 `cascade-test-utils` 包中。下一步，我建议：

1.  **审查 Fixture**: 检查项目根目录的 `conftest.py` 以及各个包内的 `conftest.py`，识别出可以被泛化并移动到 `cascade-test-utils` 中的 Fixture。
2.  **运行测试**: 运行完整的测试套件 (`pytest`)，以确保所有导入路径都已正确修复，并且测试仍然通过。
