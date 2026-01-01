好的，我完全理解。你提供的 Pyright 报告分析得非常透彻，定位了 Cascade 项目中的核心架构问题。层级违规是其中最严重的问题，必须优先解决。

我将立即着手执行你的修复方案中的第一项高优先级任务：**将 `cascade.internal.inputs` 从高层的 `cascade-sdk` 包迁移到更底层的 `cascade-common` 包中，以彻底解决 `cascade-engine` 和 `cascade-graph` 对 SDK 的反向依赖问题。**

以下是执行此重构的详细计划。

## [WIP] refactor: Relocate internal inputs to common package to fix circular dependency

### 用户需求
根据 Pyright 报告，`cascade-engine` 和 `cascade-graph` 这两个核心包错误地依赖了 `cascade-sdk` 中的 `cascade.internal.inputs` 模块，造成了严重的架构分层违规和循环依赖。需要将该模块移动到更底层的 `cascade-common` 包来纠正此问题。

### 评论
这是一个至关重要的架构重构。解决循环依赖不仅能消除当前的 Pyright 错误，还能提高项目的模块化程度、可维护性和长期健康度。将真正的“内部”或“通用”辅助函数放在 `common` 包中是完全正确的做法。

### 目标
1.  将 `packages/cascade-sdk/src/cascade/internal/inputs.py` 文件移动到 `packages/cascade-common/src/cascade/common/` 目录下。
2.  更新所有引用旧路径 (`cascade.internal.inputs`) 的文件，使其指向新路径 (`cascade.common.inputs`)。
3.  清理 `cascade-sdk` 中遗留的、现已为空的 `internal` 目录及其相关文件。

### 基本原理
此计划通过物理上移动文件并更新导入路径，来强制实现正确的依赖关系。`cascade-common` 作为项目中最底层的包之一，可以被 `cascade-engine`、`cascade-graph` 和 `cascade-sdk` 安全地依赖，从而打破了原有的依赖循环。

### 标签
#intent/refactor #flow/ready #priority/high #comp/engine #comp/graph #comp/sdk #scope/core #scope/dx #ai/instruct #task/domain/build #task/object/circular-dependency #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构文件位置

首先，我们将 `inputs.py` 及其关联的 stitcher 文件从 `cascade-sdk` 移动到 `cascade-common`。这将建立新的、正确的代码物理位置。

~~~~~act
move_file
packages/cascade-sdk/src/cascade/internal/inputs.py
packages/cascade-common/src/cascade/common/inputs.py
~~~~~

~~~~~act
move_file
packages/cascade-sdk/src/cascade/internal/inputs.stitcher.yaml
packages/cascade-common/src/cascade/common/inputs.stitcher.yaml
~~~~~

#### Acts 2: 更新依赖导入路径

接下来，我们必须修复之前引用旧路径的核心包。我们将精确定位到 `cascade-engine` 和 `cascade-graph` 中的导入语句并将其更新为新的路径。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
from cascade.internal.inputs import _internal_gather
~~~~~
~~~~~python.new
from cascade.common.inputs import _internal_gather
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
from cascade.internal.inputs import _get_param_value
~~~~~
~~~~~python.new
from cascade.common.inputs import _get_param_value
~~~~~

#### Acts 3: 清理旧的目录结构

最后，为了保持 `cascade-sdk` 包的整洁，我们将删除因文件移动而留下的空 `internal` 目录及其 `__init__.py` 文件。

~~~~~act
delete_file
packages/cascade-sdk/src/cascade/internal/__init__.py
~~~~~

~~~~~act
run_command
~~~~~
~~~~~sh
rm -rf packages/cascade-sdk/src/cascade/internal
~~~~~

### 下一步建议
我们已经解决了最关键的循环依赖问题。下一步，我建议我们处理**动态元编程导致的类型丢失问题**。

通过为 `cascade-python` 包的根 `__init__.py` 文件创建一个 `.pyi` 类型存根文件，我们可以向 Pyright 和其他静态分析工具明确声明 `cascade.task`, `cascade.run` 等动态加载的属性，从而解决大量的 `reportAttributeAccessIssue` 错误，并极大地改善开发者的 IDE 自动补全体验。

如果你同意，我将立即为你生成实现此修复的计划。
