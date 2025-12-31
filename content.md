## [WIP] fix: 解决 Monorepo 包名冲突与依赖缺失

### 摘要
本计划旨在修复 `uv` 构建时因根目录与 `cascade-python` 包同名 (`cascade`) 导致的冲突，并修正 `cascade-python` 缺失对 `cascade-sdk` 依赖的问题。

### 错误分析
1.  **包名冲突**: 根目录 `pyproject.toml` 和 `packages/cascade-python/pyproject.toml` 都将项目名称定义为 `cascade`。在 `uv` 的 workspace 模式下，这是不允许的。
2.  **依赖缺失**: `cascade-python` 旨在作为 SDK 的聚合入口，但其依赖列表中遗漏了包含具体工具实现的 `cascade-sdk` 包。这会导致 `cascade.tools` 等模块无法被导入。

### 用户需求
1.  修改根目录 `pyproject.toml` 的名称以避免冲突（建议改为 `cascade-monorepo`）。
2.  确保 `cascade-python` 正确依赖所有必要的子包（包括 `cascade-sdk`）。
3.  保持 `cascade-vm` 的重构成果。

### 评论
将根目录重命名为 `cascade-monorepo` 是标准的 Monorepo 实践，它明确了根目录作为开发环境容器的角色，而将 `cascade` 这一核心包名的所有权移交给 `cascade-python` 子包。

### 目标
1.  重命名根目录项目为 `cascade-monorepo`。
2.  更新 `cascade-python` 的依赖列表，加入 `cascade-sdk`。
3.  调整 workspace 依赖引用方式。

### 基本原理
-   **Workspace 唯一性**: Workspace 中的每个成员必须有唯一的名称。
-   **聚合包模式**: `cascade-python` 作为一个 Metapackage，通过依赖其他子包来组合出完整的 SDK 功能。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/core #task/domain/core #task/object/pyproject.toml #task/action/rename #task/state/continue

---

### Script

#### Acts 1: 修正根目录 `pyproject.toml`
重命名项目，并将 `cascade` 的源指向 workspace 成员，不再作为本地路径覆盖。同时清空根目录的构建目标，因为它不再包含代码。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[project]
name = "cascade"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
~~~~~
~~~~~toml.new
[project]
name = "cascade-monorepo"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
cascade-vm = { workspace = true }
cascade = { path = "packages/cascade-python", editable = true }

[tool.hatch.workspaces]
~~~~~
~~~~~toml.new
cascade-vm = { workspace = true }
cascade = { workspace = true }

[tool.hatch.workspaces]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.hatch.build.targets.wheel]
packages = ["packages/cascade-python/src/cascade"]
~~~~~
~~~~~toml.new
[tool.hatch.build.targets.wheel]
packages = []
~~~~~

#### Acts 2: 修正 `cascade-python` 依赖
在 `packages/cascade-python/pyproject.toml` 中添加 `cascade-sdk` 依赖，确保完整的 SDK 功能可用。

~~~~~act
patch_file
packages/cascade-python/pyproject.toml
~~~~~
~~~~~toml.old
    "cascade-library",
    # Tools included by default
    "cascade-cli-controller",
    "cascade-cli-observer",
]
~~~~~
~~~~~toml.new
    "cascade-library",
    "cascade-sdk",
    # Tools included by default
    "cascade-cli-controller",
    "cascade-cli-observer",
]
~~~~~

~~~~~act
patch_file
packages/cascade-python/pyproject.toml
~~~~~
~~~~~toml.old
cascade-library = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
~~~~~
~~~~~toml.new
cascade-library = { workspace = true }
cascade-sdk = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
~~~~~

### 下一步建议
配置修正后，建议运行 `uv pip install -e .[dev]` 重新安装环境，然后运行测试套件。这应该能解决 `Two workspace members...` 的错误，并且 `cascade` 模块应该能正确加载。
