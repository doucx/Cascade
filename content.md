非常抱歉，我的疏忽导致了 `pyright` 检查失败。

你在静态分析中发现的问题是完全正确的。在我前一步删除 `.../wiring/prism.py` 文件的过程中，遗漏了更新 `.../expansion/policies/resource.py` 文件中对它的引用，从而导致了导入错误。

我将立即生成一个计划来修复这个疏漏。

## [WIP] fix: 修正 ResourceExpansionPolicy 中悬空的导入路径

### 错误分析

**错误**: `pyright` 报告在 `packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py` 文件中存在一个无法解析的导入：`...wiring.prism`。

**根本原因**: 在上一个重构步骤中，文件 `packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.py` 被正确地删除了，因为它的内容（`ResourcePrism` 协议）已经被移至 `cascade-spec`。然而，我未能更新 `ResourceExpansionPolicy` 中对这个旧文件的导入语句，导致该引用悬空，从而引发了静态分析错误。

### 用户需求

代码库必须通过静态分析检查，确保在重构后没有引入新的构建或类型错误。

### 评论

这是一个典型的重构后清理疏漏。它强调了在每次修改后运行静态分析和测试套件的重要性，以捕捉此类问题。这是一个小但至关重要的修复，以确保架构重构的完整性。

### 目标

1.  修改 `packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py`。
2.  将其中错误的导入语句 `from ...wiring.prism import ResourcePrism` 替换为正确的 `from cascade.spec.compiler.interfaces import ResourcePrism`。

### 基本原理

通过将悬空的导入路径指向 `cascade-spec` 中权威的协议定义，我们恢复了代码的类型安全性和可构建性，使之与我们新的架构规范保持一致。

### 标签

#intent/fix #flow/ready #priority/critical #comp/compiler #scope/dx #task/domain/architecture #task/object/decoupling #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正悬空的导入

我们将直接修补 `resource.py` 文件，使其从 `cascade-spec` 导入 `ResourcePrism` 协议。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py
~~~~~
~~~~~python.old
from ...expander import SubGraph
from ..context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
from ...wiring.prism import ResourcePrism
from ...wiring.prisms.discrete import DiscreteResourcePrism


class ResourceExpansionPolicy(ExpansionPolicy):
~~~~~
~~~~~python.new
from ...expander import SubGraph
from ..context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy, ResourcePrism
from ...wiring.prisms.discrete import DiscreteResourcePrism


class ResourceExpansionPolicy(ExpansionPolicy):
~~~~~

### 下一步建议

这个补丁应该已经解决了 `pyright` 报告的错误。我建议你重新运行静态分析来确认问题已经解决。

一旦确认通过，我们就可以继续之前的计划：生成一个 `[COMMIT]` 计划，将这次成功的、跨越多个步骤的架构重构工作作为一个完整的单元进行提交。
