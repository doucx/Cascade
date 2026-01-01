你完全正确，我的上一个计划是错误的，并且没有解决根本问题。在没有确凿证据的情况下，我不能再进行猜测。我为之前的失败道歉，也感谢你提供的清晰反馈。

诊断脚本的结果，尤其是循环导入的错误，是解决问题的关键。

## [WIP] fix: 修复 cascade-library 和 cascade-sdk 之间的包级循环依赖

### 错误分析
诊断脚本虽然在最后报告成功，但它在第 3 步捕获到了一个至关重要的、稍纵即逝的错误：`partially initialized module 'cascade' ... has no attribute 'task' (most likely due to a circular import)`。这个错误在加载 `ipfs` 插件时出现，揭示了问题的真正根源：**包级别的循环依赖**。

循环路径如下：
1.  `cascade-sdk` 是顶层 API 包，它依赖 `cascade-library` 来获取 Providers。
2.  `cascade-library` 的 `pyproject.toml` 文件错误地声明了它依赖 `cascade-sdk`。
3.  当测试代码 `import cascade as cs` 时，Python 尝试加载 `cascade-sdk`。
4.  当代码访问 `cs.ipfs` 时，`cascade.sdk` 尝试加载 `cascade.providers.registry`（它现在位于 `cascade-library` 中）。
5.  为了加载 `cascade-library`，Python 的包管理器发现它需要 `cascade-sdk`。
6.  此时，`cascade-sdk` 正在被加载（回到第 3 步），但尚未完成。Python 陷入了一个循环，导致 `cascade` 模块处于“部分初始化”状态。当 `ipfs` 插件尝试从这个不完整的模块中导入 `@task` 时，就失败了。

**解决方案**: `cascade-library` 作为一个提供基础功能的库，**绝对不能**依赖于顶层的 `cascade-sdk` 包。它应该只依赖于它实际需要的底层包，比如 `cascade-spec` (用于 `@task` 等) 和 `cascade-engine` (因为 `subflow` 提供者需要它)。

### 用户需求
彻底解决由包循环依赖引起的 `AttributeError`，让 Provider 加载机制稳定可靠。

### 评论
这是一个比之前预想的更深层次的架构问题。修复 `pyproject.toml` 中的依赖关系将打破这个导入循环，并从根本上解决问题。这种清晰的依赖关系（SDK -> Library -> Engine/Spec）是维持大型项目健康的关键。

### 目标
1.  修改 `packages/cascade-library/pyproject.toml`，移除对 `cascade-sdk` 的依赖。
2.  在 `packages/cascade-library/pyproject.toml` 中添加对 `cascade-spec` 和 `cascade-engine` 的直接依赖，以准确反映其代码的实际 `import`。

### 基本原理
通过在包定义文件（`pyproject.toml`）中建立一个单向的、无环的依赖图 (DAG)，我们消除了 Python 导入器在解析模块时可能遇到的歧义和循环，确保了模块可以被完整、正确地初始化。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/dependency-graph #scope/core #ai/brainstorm #task/domain/build #task/object/circular-dependency #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 cascade-library 的包依赖
这是解决循环导入问题的核心。我们将 `cascade-sdk` 替换为 `cascade-spec` 和 `cascade-engine`。

~~~~~act
patch_file
packages/cascade-library/pyproject.toml
~~~~~
~~~~~toml.old
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-library"
version = "0.1.0"
description = "Standard library of providers for the Cascade ecosystem."
requires-python = ">=3.8"
dependencies = [
  "cascade-sdk"
]

[project.optional-dependencies]
template = ["jinja2"]
~~~~~
~~~~~toml.new
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-library"
version = "0.1.0"
description = "Standard library of providers for the Cascade ecosystem."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
  "cascade-engine"
]

[project.optional-dependencies]
template = ["jinja2"]
~~~~~
