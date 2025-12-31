## [WIP] fix: 修正根目录 Hatch 构建配置

### 摘要
`hatchling` 构建后端因无法确定根目录 (`cascade-monorepo`) 中应包含哪些文件而失败。我们将显式配置 Hatch 以包含空包列表，或者干脆从根目录的 `pyproject.toml` 中移除构建后端的职责，仅将其作为开发环境配置。考虑到我们需要它作为 dev environment，显式设置包含内容是最安全的。

### 错误分析
错误信息 `ValueError: Unable to determine which files to ship inside the wheel` 是因为我们将 `packages = []` 设置为空，而 Hatch 的默认启发式规则期望找到与项目名称匹配的目录 (`src/cascade_monorepo` 或 `cascade_monorepo`)。当它找不到且没有显式配置 `only-include` 时，就会报错。

### 用户需求
1.  修复 `uv pip install -e .` 失败的问题。
2.  保持根目录作为开发环境和工具配置中心的地位。

### 评论
根目录不需要作为 Python 包发布。它只是一个容器。我们可以通过配置 Hatch 忽略所有文件来创建一个空的“虚拟”包，仅用于承载依赖。

### 目标
修改根目录 `pyproject.toml`，显式告知 Hatch 不要包含任何源文件，或者指向一个存在的占位文件。

### 基本原理
Hatch 需要明确的指令。由于根目录没有代码，我们需要配置 `force-include` 或类似的机制来满足构建要求，或者利用 `packages` 配置指向一个确实存在的（即使是空的）目录。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/core #task/domain/core #task/object/pyproject.toml #task/action/configure #task/state/continue

---

### Script

#### Acts 1: 修正 `pyproject.toml` 构建目标
我们将 `packages` 设置回指向 `packages/cascade-python/src/cascade`，但这可能会导致再次冲突。
更好的方法是配置 Hatch 仅包含 `README.md` 或其他非代码文件，并使用 `force-include`。
或者，更简单地，我们可以欺骗它：我们将 packages 设置为 `["."]`, 然后使用 exclude 排除所有。
但最标准的方法是告诉 hatch 这是一个 namespace package 或者手动指定包含。

让我们尝试将 `cascade-monorepo` 作为一个仅包含元数据的包。
Hatch 文档指出：如果无法自动检测，必须定义 `tool.hatch.build.targets.wheel.packages`。
我们之前设置了 `packages = []`，这导致了启发式失败。

我们将尝试使用 `bypass-selection` 选项（如果支持）或显式包含根目录下的某个无害文件。
但 `hatchling` 似乎强制要求 wheel 中有内容。

另一种策略：将 `cascade-monorepo` 视为一个 meta-project，不参与构建 wheel，但 `uv pip install -e .` 会尝试构建它。

让我们尝试指向一个确实存在的目录，例如 `packages`，但排除其中的所有内容，或者更好的是，创建一个空的 `src/cascade_monorepo/__init__.py`？不，这太乱了。

回退方案：将 `tool.hatch.build.targets.wheel` 指向 `packages/cascade-python/src/cascade`，但这次我们修改项目名称为 `cascade-monorepo` 了，所以它不会与 `cascade` 包冲突。这样 `cascade-monorepo` 安装后也会提供 `cascade` 命名空间，但这没关系，因为它们内容是一样的（或者我们指向一个虚拟的空包）。

让我们创建一个虚拟的空目录结构来满足 Hatch。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p src/cascade_monorepo
touch src/cascade_monorepo/__init__.py
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.hatch.build.targets.wheel]
packages = []
~~~~~
~~~~~toml.new
[tool.hatch.build.targets.wheel]
packages = ["src/cascade_monorepo"]
~~~~~

### 下一步建议
再次运行 `uv pip install -e .[dev]`。现在 Hatch 应该能找到 `src/cascade_monorepo` 并成功构建。这个包是空的，不干扰实际逻辑，仅作为安装开发依赖的载体。
