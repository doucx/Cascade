好的，我来修复这个 `NameError`。

测试框架在收集测试文件时就报错了，根本原因是 `src/cascade/runtime/engine.py` 文件中存在一个 `NameError`。新添加的 `_resolve_inputs` 方法在其签名中使用了 `Graph` 作为类型提示，但是我忘记了从 `cascade.graph.model` 中导入 `Graph` 类，只导入了 `Node`。

这是一个简单的导入遗漏，我会立即修正。

## [WIP] fix: 修复 Engine 中 Graph 未定义的 NameError

### 用户需求
修复 `src/cascade/runtime/engine.py` 中的 `NameError: name 'Graph' is not defined` 错误，以便测试可以正常运行。

### 评论
这是一个简单的疏忽，在添加 `_resolve_inputs` 方法时忘记了同步更新文件的导入语句。修复这个问题将解除测试阻塞。

### 目标
1.  在 `src/cascade/runtime/engine.py` 中，将 `Graph` 添加到 `from cascade.graph.model` 的导入列表中。

### 基本原理
补全缺失的类型定义导入，以解决 Python 解释器在解析 `_resolve_inputs` 方法签名时遇到的 `NameError`。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/runtime #scope/core
#task/domain/core #task/object/async-support #task/action/bug-fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Fix Missing Import

在 `engine.py` 中添加对 `Graph` 的导入。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node
from cascade.spec.task import LazyResult
from cascade.spec.resource import ResourceDefinition, Inject
~~~~~
~~~~~python
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.spec.task import LazyResult
from cascade.spec.resource import ResourceDefinition, Inject
~~~~~

### 下一步建议
请再次运行测试。这个修复应该能解决所有的 `NameError`，让测试流程可以继续。
