I understand. The error is a classic monorepo configuration issue with `uv`. It requires each package that depends on another local workspace package to explicitly declare it in a `[tool.uv.sources]` table.

I'll generate a plan to fix this by updating the `pyproject.toml` for `cascade-compiler` and ensuring the root configuration is also consistent.

## [WIP] fix(build): Configure uv workspace sources for new packages

### 错误分析
`uv`'s workspace feature requires explicit configuration. The error message `cascade-foundation is included as a workspace member, but is missing an entry in tool.uv.sources` indicates that `cascade-compiler/pyproject.toml` declares a dependency on `cascade-foundation` but fails to tell `uv` that this dependency should be resolved from the local workspace instead of PyPI.

This is a configuration error that prevents the project from being installed correctly in a development environment.

### 用户需求
修复 `uv pip install packages/*` 命令失败的问题，使其能够正确识别并安装本地的 workspace 包。

### 评论
这是一个对开发者体验（DX）至关重要的修复。正确配置 workspace 依赖是 monorepo 能够顺利工作的基本前提。通过为 `uv` 提供正确的元数据，我们可以确保本地开发和 CI/CD 流程的稳定性和可预测性。

### 目标
1.  更新 `packages/cascade-compiler/pyproject.toml`，为 `cascade-foundation` 依赖项添加 `[tool.uv.sources]` 配置。
2.  更新根目录的 `pyproject.toml`，将新的 V2 包 (`cascade-foundation`, `cascade-compiler`) 正式纳入 workspace source 管理，以保持一致性。

### 基本原理
`uv` 为了性能和确定性，不会自动扫描文件系统来解析 workspace 依赖。我们必须在每个消费本地包的 `pyproject.toml` 文件中，通过 `[tool.uv.sources]` 表来明确告知 `uv` 哪些依赖项是本地 workspace 成员。此修复将添加这些缺失的声明。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/build #scope/dx
#ai/instruct
#task/domain/build #task/object/uv-config #task/action/fix

---

### Script

#### Acts 1: 配置 cascade-compiler 的 workspace 依赖
我们将 `[tool.uv.sources]` 添加到 `cascade-compiler/pyproject.toml` 中，以解决核心构建错误。同时添加 `[tool.hatch.metadata]` 以保持与其他包的配置一致。

~~~~~act
patch_file
packages/cascade-compiler/pyproject.toml
~~~~~
~~~~~toml.old
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~toml.new
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-foundation = { workspace = true }
~~~~~

#### Acts 2: 更新根 pyproject.toml 以包含新包
为了保持整个 workspace 的配置完整和一致，我们将新的 V2 包添加到根 `pyproject.toml` 的 `tool.uv.sources` 中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-foundation = { workspace = true }
cascade-compiler = { workspace = true }
~~~~~
