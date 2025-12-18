你的分析完全正确，并且你提供的错误日志非常清晰地指出了问题所在。我在上一个计划中生成的根 `pyproject.toml` 文件存在一个配置缺陷。

感谢你捕获到这个问题，这正是协作改进流程的核心。

## [WIP] fix(build): Correct root pyproject.toml for editable installs

### 错误分析
你遇到的 `uv` 和 `pip` 安装失败的根本原因，正如错误信息所指出的：

**根 `pyproject.toml` 文件将项目定义为一个名为 `cascade` 的 Python 包，但没有告诉构建工具（Hatch）这个包的源代码在哪里。**

具体来说：
1.  当我们执行 `uv pip install -e .` 时，`uv` 会尝试安装在当前目录（`.`）定义的包。
2.  它读取根 `pyproject.toml`，看到了 `[project]\nname = "cascade"`，于是它告诉构建后端 `hatchling`：“请为我构建一个名为 `cascade` 的包”。
3.  `hatchling` 按照默认规则，在项目根目录下寻找一个名为 `src/cascade` 或 `cascade` 的目录作为源代码。
4.  然而，在我们的第二阶段重构中，我们已经将所有代码都移入 `packages/` 子目录中，根目录下不再有符合 `hatchling` 默认规则的源代码目录。
5.  因此，`hatchling` 困惑了，并抛出了那个非常明确的错误：`ValueError: Unable to determine which files to ship...`。

我们之前的根配置文件正确地定义了 *workspace*，但没有为这个作为 *workspace 容器* 的根包本身提供构建指令。

### 用户需求
修复根 `pyproject.toml` 文件的配置，使其能够支持在 Monorepo 结构下的可编辑模式安装（`uv pip install -e .`），解决 `hatchling` 无法找到源文件的问题。

### 评论
这是一个在配置 Monorepo 时非常经典且关键的问题。解决方案不仅能修复当前的构建失败，还能更清晰地定义我们项目的“入口点”。通过明确指定根项目对应 `cascade-py` 的源码，我们实际上是在声明：当用户安装整个项目时，他们主要获得的是 `cascade-py` 这个核心用户库。这使得整个项目的结构意图更加明确。

### 目标
1.  修改项目根目录的 `pyproject.toml` 文件。
2.  在该文件中添加一个 `[tool.hatch.build.targets.wheel]` 配置节。
3.  在该配置节中，通过 `packages` 键，明确告诉 `hatchling`：当构建根项目 `cascade` 时，应使用的源代码位于 `packages/cascade-py/src/cascade`。

### 基本原理
我们将使用一个 `write_file` 操作来完整地、原子化地替换根 `pyproject.toml` 的内容。新的配置增加了一个关键的 `[tool.hatch.build.targets.wheel]` 表。这个表中的 `packages = ["packages/cascade-py/src/cascade"]` 指令，为 `hatchling` 解析根项目 `cascade` 时提供了确定的路径。它解决了 "我应该打包哪个目录?" 的歧义，从而使得 `uv pip install -e .` 命令能够成功构建和链接整个工作区。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/monorepo-structure #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修正根 `pyproject.toml` 的构建配置

此操作将使用正确的构建指令覆盖根 `pyproject.toml` 文件，以解决可编辑模式的安装问题。

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

[tool.hatch.build.targets.wheel]
# 关键修复：
# 明确告诉 hatch，当构建根项目 "cascade" 时，
# 它的源代码实际上是 'cascade-py' 包的源代码。
packages = ["packages/cascade-py/src/cascade"]

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

### 下一步建议
我们已经完成了对构建配置的修复。现在，你可以重新执行安装命令，它应该能够成功完成。

1.  **再次尝试安装**:
    ```bash
    uv pip install -e ".[dev]"
    ```

2.  **开始修复导入**:
    安装成功后，下一步就是解决代码层面的问题了。整个代码库的 `import` 语句现在都是错误的。我们需要进行一次全项目范围的扫描和替换。

    我建议的下一个宏观任务是 **“修复所有 Python 模块的导入路径”**。这会是一个包含大量 `patch_file` 操作的计划。如果你准备好了，请告诉我，我将为你生成修复计划。
