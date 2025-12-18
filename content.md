简要回答：
这是一个 Hatchling 构建后端的安全限制。默认情况下，Hatchling 禁止在 `project.dependencies` 中使用直接文件引用（Direct References, 如 `pkg @ file://...`）。我们需要显式地在 `pyproject.toml` 中通过 `[tool.hatch.metadata] allow-direct-references = true` 解除此限制。

## [WIP] fix(build): 允许 Hatchling 使用直接文件引用以解决构建错误

### 错误分析
构建失败的直接原因是 `cascade-cli` 的 `pyproject.toml` 中声明了对 `cascade-py` 的本地文件依赖 (`cascade-py @ file:../cascade-py`)。

Hatchling 抛出了 `ValueError: Dependency #1 ... cannot be a direct reference unless field tool.hatch.metadata.allow-direct-references is set to true`。这是 Hatch 为了防止意外发布包含本地路径的包而设置的默认保护机制。

由于我们要构建一个包含相互依赖的本地包的 Monorepo，我们需要在所有涉及本地路径依赖的 `pyproject.toml` 文件中显式启用此选项。

### 用户需求
修复 `uv pip install -e ".[dev]"` 时的构建错误。

### 评论
这是一个非常典型的 Monorepo配置问题。虽然 `uv` 能够处理工作区，但在底层调用构建后端（这里是 `hatchling`）生成元数据时，必须遵守构建后端的规则。

### 目标
修改根目录及所有子包的 `pyproject.toml`，添加允许直接引用的配置。

### 基本原理
我们在所有 `pyproject.toml` 文件中添加 `[tool.hatch.metadata]` 配置块，设置 `allow-direct-references = true`。这将允许 Hatchling 处理我们在多包布局中定义的 `file:` 依赖。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/config #scope/dx #ai/instruct #task/domain/devops #task/object/monorepo-config #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 配置 `cascade-cli` (报错源头)
首先修复报错的 `cascade-cli` 包。

~~~~~act
patch_file
packages/cascade-cli/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade/cli"]
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade/cli"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~

#### Acts 2: 配置 `cascade-py`
`cascade-py` 也依赖于其他本地包 (`cascade-interfaces`, `cascade-runtime`)，同样需要修复。

~~~~~act
patch_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~

#### Acts 3: 配置 `cascade-runtime`
`cascade-runtime` 依赖于 `cascade-interfaces`。

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~

#### Acts 4: 配置根目录 `pyproject.toml`
根目录作为开发环境入口，也定义了对所有子包的本地依赖，因此也需要此配置以支持 `pip install -e .`。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "moto[s3]",
  # 关键修复 1: 移除 "[all]"
  "typer",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
]
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "moto[s3]",
  # 关键修复 1: 移除 "[all]"
  "typer",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~

### 下一步建议
执行完上述补丁后，请再次尝试运行 `uv pip install -e ".[dev]"`。如果安装成功，我们可以继续进行第四阶段的验证工作（运行测试）。
