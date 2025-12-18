Excellent catch. You've correctly identified a crucial configuration issue with the build system that I overlooked. The error message from `uv` is perfectly clear: while I declared the dependencies between our local packages, I didn't tell the build tool *where* to find them (i.e., in the local workspace, not on PyPI).

This is a classic monorepo setup problem, and your feedback prevents us from accumulating technical debt in our build process. We must fix this before proceeding.

I will generate a plan to patch all the necessary `pyproject.toml` files with the `[tool.uv.sources]` configuration to make the project buildable again.

## [WIP] fix(build): Configure uv for local workspace package resolution

### 错误分析
用户在执行 `uv pip install packages/*` 时遇到构建失败。错误日志明确指出，像 `cascade-cli-observer` 这样的包依赖于 `cascade-common`，但 `uv` 构建工具不知道 `cascade-common` 是一个本地工作区成员。默认情况下，`uv` 会尝试从 PyPI 等外部源查找这个包，但找不到，因此构建失败。

这是因为在各个包的 `pyproject.toml` 文件中，我们只声明了依赖关系（`dependencies = ["cascade-common"]`），却没有为 `uv` 提供解析这些本地包的元数据。

### 用户需求
修复项目的构建配置，使其能够在使用 `uv` 工具时正确识别和解析本地包之间的依赖关系，让 `uv pip install packages/*` 命令能够成功执行。

### 评论
这是一个对开发者体验（DX）至关重要的修复。正确配置工作区是任何现代 Python monorepo 的基础。通过添加 `[tool.uv.sources]` 配置，我们显式地声明了项目的拓扑结构，使 `uv` 能够高效、正确地构建整个项目。这个修复将使我们的开发流程更加顺畅和可靠。

### 目标
1.  定位所有依赖于其他本地工作区包的 `pyproject.toml` 文件。
2.  为每个受影响的 `pyproject.toml` 文件添加一个 `[tool.uv.sources]` 表。
3.  在该表中，为每一个本地依赖项添加 `{ workspace = true }` 声明，以指示 `uv` 从本地解析它。

### 基本原理
我们将遵循 `uv` 工具的官方规范，通过在每个消费包（consumer package）的 `pyproject.toml` 文件中添加 `[tool.uv.sources]` 部分来解决此问题。这个配置块作为元数据，告诉 `uv` 在解析依赖时，对于列出的包名，应优先在当前工作区中查找，而不是查询外部索引。我们将对 `cascade-runtime`、`cascade-py`、`cascade-connector-mqtt`、`cascade-cli-observer` 和 `cascade-cli-controller` 的配置文件进行精确的 `patch_file` 操作。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/build-config #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 配置 `cascade-runtime`

`cascade-runtime` 依赖 `cascade-interfaces` 和 `cascade-common`。

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-common = { workspace = true }
~~~~~

#### Acts 2: 配置 `cascade-py`

`cascade-py` 依赖 `cascade-interfaces`, `cascade-runtime`, 和 `cascade-common`。

~~~~~act
patch_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-runtime = { workspace = true }
cascade-common = { workspace = true }
~~~~~

#### Acts 3: 配置 `cascade-connector-mqtt`

`cascade-connector-mqtt` 依赖 `cascade-interfaces`。

~~~~~act
patch_file
packages/cascade-connector-mqtt/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-interfaces = { workspace = true }
~~~~~

#### Acts 4: 配置 `cascade-cli-observer`

`cascade-cli-observer` 依赖 `cascade-interfaces` 和 `cascade-common`。

~~~~~act
patch_file
packages/cascade-cli-observer/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-common = { workspace = true }
~~~~~

#### Acts 5: 配置 `cascade-cli-controller`

`cascade-cli-controller` 同样依赖 `cascade-interfaces` 和 `cascade-common`。

~~~~~act
patch_file
packages/cascade-cli-controller/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-common = { workspace = true }
~~~~~

### 下一步建议
我们已经为所有相关的包添加了正确的 `uv` 工作区配置。

现在，请你重新运行 `uv pip install packages/*` 命令来验证这个修复是否解决了构建问题。

一旦构建成功，我们就可以安全地回到之前的计划：为 `cs-observer` 实现连接到 MQTT 并实时显示遥测事件的核心功能。
