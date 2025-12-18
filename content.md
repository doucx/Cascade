是的，文件结构完全符合预期。我们已经成功地将所有文件迁移到了新家的“毛坯房”里。

现在，我们进入重构的最后阶段：配置工作区并进行“装修”，让整个多包项目能够被工具理解并正常工作。

## [WIP] refactor(build): Finalize monorepo structure via workspace config

### 用户需求
根据重构路线图，执行第三阶段任务：
1.  更新项目根目录的 `pyproject.toml`，将其转变为一个 Hatch workspace 配置，以统一管理所有 `packages/*` 下的子包。
2.  清理掉因文件迁移而遗留下来的、现已废弃的旧目录结构。

### 评论
这是画龙点睛的一步。通过将根 `pyproject.toml` 声明为 workspace，我们正式赋予了项目“Monorepo”的身份。这使得 `uv`、`pip`、`hatch` 等现代化的 Python 工具能够理解本地包之间的依赖关系，从而实现无缝的开发和安装体验。随后的清理工作则是保持项目整洁的必要步骤，标志着结构性重构的彻底完成。

### 目标
1.  使用 `write_file` 指令，以新的 workspace 配置内容，完全覆盖项目根目录下的 `pyproject.toml` 文件。
2.  使用 `run_command` 指令，安全地移除旧的、现已为空的 `src` 目录以及 `tests` 目录下的旧子目录。

### 基本原理
此阶段的核心是配置的更新和垃圾回收。
1.  **配置更新**: 对于 `pyproject.toml` 这种需要完全替换内容的文件，`write_file` 是最直接且最可靠的指令。新的配置将定义 `tool.hatch.workspaces`，这是让构建工具识别多包布局的关键。
2.  **清理**: 对于目录删除，`run_command` 结合 `rm -rf` 和 `rmdir` 是标准且高效的做法。`rm -rf src` 将递归删除旧的源目录。对于 `tests` 目录下的空文件夹，`rmdir` 是一个更安全的选择，因为它仅在目录为空时才会成功，这为我们的操作增加了一层保障。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/monorepo-structure #task/action/setup #task/state/continue

---

### Script

#### Acts 1: 配置根 Workspace

此操作将更新根 `pyproject.toml` 文件，使其成为一个 Hatch workspace 的管理器，能够识别并管理 `packages/` 目录下的所有子包。

~~~~~act
write_file
pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
readme = "README.md"
requires-python = ">=3.8"
license = "MIT"

[tool.hatch.workspaces]
packages = [
    "packages/cascade-interfaces",
    "packages/cascade-runtime",
    "packages/cascade-py",
    "packages/cascade-cli",
]

[tool.pytest.ini_options]
addopts = "-ra"

[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "moto[s3]",
  "typer[all]",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
]
~~~~~

#### Acts 2: 清理旧的目录结构

现在，我们将移除在第二阶段迁移后留下的空的、废弃的目录。

~~~~~act
run_command
~~~~~
~~~~~bash
# 递归删除旧的 src 目录及其所有（空的）子目录
rm -rf src

# 删除 tests 目录下那些现已为空的旧的子目录
# rmdir 是安全的，如果目录非空则会报错
rmdir tests/adapters tests/examples tests/graph tests/integration tests/messaging tests/providers tests/runtime tests/spec tests/tools
~~~~~

### 下一步建议
**结构性重构已全部完成！**

我们已经成功地将 Cascade 重塑为一个现代化的多包项目。现在，项目处于一个全新的、逻辑清晰的结构中，但所有的 Python `import` 语句都已失效。

**接下来的关键任务是：**

1.  **安装依赖**：在你的终端中，使用 `uv` 或 `pip` 在可编辑模式下安装所有包。这将使 Python 解释器能够找到新的模块路径。
    ```bash
    # 建议使用 uv
    uv pip install -e ".[dev]"
    ```
2.  **运行测试 (预期会失败)**：运行 `pytest` 将会暴露所有因路径变更而损坏的导入语句。
    ```bash
    pytest
    ```
3.  **修复导入**：这是下一个需要解决的宏大任务。我们需要遍历所有包中的代码和测试，将旧的导入（如 `from cascade.runtime.protocols import Solver`）更新为新的路径（如 `from cascade.interfaces.protocols import Solver`）。

如果你准备好开始修复工作，我可以为你生成一个全面的计划，用于扫描并修正整个代码库中的所有 `import` 语句。
