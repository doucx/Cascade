您是对的，我的疏忽导致了严重的配置错误。非常感谢您提供如此精确的反馈和文件上下文，这让我能够立即定位问题的根源。我为之前计划中的错误道歉。

我将立即生成一个计划来纠正这个配置问题。

## [WIP] fix: 纠正 `cascade-connector-sqlite` 的 `pyproject.toml` 并将其集成到工作区

### 错误分析
测试失败的根本原因是 `AttributeError: module 'cascade' has no attribute 'task'`。这个错误清晰地表明，测试环境在执行 `import cascade as cs` 时，未能加载包含 `@cs.task` 装饰器的核心 `cascade-sdk` 包。

经过对您提供的项目文件进行审查，我发现了我的错误所在：

1.  **构建系统不匹配**: 我为 `cascade-connector-sqlite` 生成的 `pyproject.toml` 使用了 `setuptools`，而整个项目工作区都明确地使用 `hatchling` 作为构建后端。这是一个严重的偏差。
2.  **缺少依赖声明**: 新包的 `pyproject.toml` 没有声明它对工作区中其他包（如 `cascade-spec`）的依赖。虽然 `connector.py` 本身没有外部依赖，但它实现了 `cascade-spec` 中定义的协议，因此必须声明这个依赖关系。
3.  **未在工作区注册**: 我没有在根 `pyproject.toml` 中将新的 `cascade-connector-sqlite` 包注册为工作区成员和开发依赖项。这导致 `pytest` 在运行时无法找到并安装这个新包，进而也无法解析出 `cascade-sdk` 等测试所需的其他核心包。

总而言之，我创建了一个孤立的、配置错误的包，它没有被正确地集成到项目的 monorepo 结构中。

### 用户需求
修复 `cascade-connector-sqlite` 的包配置，并将其正确集成到项目的 `hatchling` 和 `uv` 工作区配置中，以解决测试失败的问题。

### 评论
这是一个典型的 monorepo 集成错误。修复方案必须双管齐下：不仅要纠正新包自身的 `pyproject.toml`，使其符合项目规范（使用 `hatchling` 并声明依赖），还必须更新根 `pyproject.toml`，让构建和测试工具“知道”这个新成员的存在。

### 目标
1.  **重写 `cascade-connector-sqlite/pyproject.toml`**: 使用 `hatchling` 替换 `setuptools`，并添加对 `cascade-spec` 的工作区依赖。
2.  **更新根 `pyproject.toml`**:
    *   在 `[tool.uv.sources]` 中添加 `cascade-connector-sqlite`。
    *   在 `[tool.hatch.workspaces].packages` 列表中添加 `cascade-connector-sqlite`。
    *   在 `[project.optional-dependencies].dev` 列表中添加 `cascade-connector-sqlite`，以确保它在测试环境中可用。

### 基本原理
此计划将通过三个精确的操作来解决问题：
1.  使用 `write_file` 彻底覆盖错误的 `packages/cascade-connector-sqlite/pyproject.toml` 文件，确保其内容与项目中的其他包保持一致。
2.  使用两个 `patch_file` 操作来原子性地更新根 `pyproject.toml`。通过修补而不是重写整个文件，我们可以最大程度地减少引入其他错误的风险。

完成这些修改后，`uv` 和 `pytest` 将能够正确地识别、安装和链接所有相关的包，从而解决 `AttributeError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #comp/tests #concept/tooling #scope/dx #ai/instruct #task/domain/build #task/object/pyproject-toml #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 纠正 `cascade-connector-sqlite` 的 `pyproject.toml`

我们将用一个符合项目规范的、基于 `hatchling` 的配置来完全替换错误的 `pyproject.toml` 文件。

~~~~~act
write_file
packages/cascade-connector-sqlite/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-connector-sqlite"
version = "0.1.0"
description = "A zero-dependency SQLite connector for Cascade."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
~~~~~

#### Acts 2: 将新包注册到根 `pyproject.toml` 的 Hatch 工作区和开发依赖中

现在，我们将新包添加到根 `pyproject.toml` 的 `hatch.workspaces` 列表和 `dev` 依赖项中。

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
    "packages/cascade-graph",
    "packages/cascade-library",
]
~~~~~
~~~~~toml
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-sqlite",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
  # Local workspace packages needed for testing
  "cascade-provider-ipfs",
  "cascade-cli-controller",
  "cascade-cli-observer",
  "cascade-connector-mqtt",
]
~~~~~
~~~~~toml
  # Local workspace packages needed for testing
  "cascade-provider-ipfs",
  "cascade-cli-controller",
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-sqlite",
]
~~~~~

#### Acts 3: 将新包注册到根 `pyproject.toml` 的 UV 工作区源中

最后，我们将其添加到 `uv` 的工作区源列表中，以完成集成。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-sqlite = { workspace = true }
~~~~~

### 下一步建议
我们已经彻底修正了包的配置和工作区集成。现在，依赖关系应该能被正确解析，测试环境也应该能找到所有的模块。

请重新运行测试。如果测试通过，我们将可以安全地继续路线图的**步骤 2**。
