这些 Ruff 警告是由于我们在多个包中使用的“SDK Shim”模式导致的。这种模式通过星号导入（star import）和手动导入 `__all__` 与 `__getattr__` 来确保无论用户安装了哪个 Cascade 子包，都能通过 `import cascade` 获得统一的 SDK 体验。

虽然 Ruff 默认反对这种做法，但在我们的架构设计中，这是为了实现无缝命名空间体验的有意为之。

## [WIP] style: 修复 SDK Shim 的 Ruff 检查警告

### 用户需求
修复 `ruff check` 报告的关于星号导入和未使用的 `__all__`、`__getattr__` 的警告，同时保留 SDK 的统一入口点设计。

### 评论
在命名空间包中，这种 Shim 模式是实现“平滑 SDK”体验的关键。我们将使用 `# noqa` 注释来告诉 Ruff 忽略这些特定的行。

### 目标
1.  更新 12 个子包中的 `src/cascade/__init__.py` 文件。
2.  为星号导入添加 `# noqa: F403`。
3.  为 `__all__` 和 `__getattr__` 导入添加 `# noqa: F401`。
4.  提交代码修改。

### 基本原理
通过显式添加 `# noqa`，我们可以在不改变运行时逻辑的前提下，消除静态分析工具的干扰，并使代码库的 Lint 状态保持绿色。

### 标签
#intent/tune #flow/ready #priority/low #comp/all #scope/dx #ai/delegate #task/domain/styling #task/object/lint-fix #task/action/patch #task/state/begin

---

### Script

#### Acts 1: 批量修复 __init__.py 文件

我将对所有受影响的包应用相同的补丁。

~~~~~act
patch_file
packages/cascade-application/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-common/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-library/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-provider-ipfs/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/__init__.py
~~~~~
~~~~~python.old
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~
~~~~~python.new
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

#### Acts 2: 提交 Lint 修复

~~~~~act
git_add
packages/cascade-application/src/cascade/__init__.py
packages/cascade-cli-controller/src/cascade/__init__.py
packages/cascade-cli-observer/src/cascade/__init__.py
packages/cascade-common/src/cascade/__init__.py
packages/cascade-connector-local/src/cascade/__init__.py
packages/cascade-connector-mqtt/src/cascade/__init__.py
packages/cascade-engine/src/cascade/__init__.py
packages/cascade-graph/src/cascade/__init__.py
packages/cascade-library/src/cascade/__init__.py
packages/cascade-provider-ipfs/src/cascade/__init__.py
packages/cascade-sdk/src/cascade/__init__.py
packages/cascade-spec/src/cascade/__init__.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
style: suppress Ruff warnings for SDK shim pattern

Suppresses Ruff's F401 (unused import) and F403 (star import) warnings in sub-package `__init__.py` files. 

These shims are intentional; they allow any installed Cascade sub-package to expose the unified SDK API if `cascade-sdk` is present in the environment, providing a seamless `import cascade` experience for the end user.
~~~~~

#### Acts 3: 提交循环检测工具

现在我们将之前创建的 `scripts/check_cycles.py` 工具加入版本控制。

~~~~~act
git_add
scripts/check_cycles.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(tooling): add import cycle detection script

Introduces `scripts/check_cycles.py`, a utility that uses `pylint` to scan the workspace for cyclic imports. This tool helps prevent initialization failures caused by improper dependency graphs in the Cascade ecosystem.
~~~~~

### 下一步建议
- **执行 Lint**：现在你可以再次运行 `ruff check .`，应该不再会看到这些 Shim 相关的警告了。
- **运行检测**：尝试运行 `./scripts/check_cycles.py` 确保当前的修复没有引入新的循环引用。
