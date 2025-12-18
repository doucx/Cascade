简要回答
这是一个典型的命名空间包遮蔽（Namespace Package Shadowing）问题。由于 `cascade-py` 包中意外包含了一个空的 `cascade/graph/__init__.py` 文件，导致 Python 将 `cascade.graph` 识别为仅存在于 `cascade-py` 中的普通包，从而无法发现位于 `cascade-runtime` 包中的 `build` 模块。

## [WIP] fix: 修复命名空间包遮蔽导致的 ModuleNotFoundError

### 用户需求
修复 `import cascade as cs` 时出现的 `ModuleNotFoundError: No module named 'cascade.graph.build'` 错误。

### 评论
在多包（Multi-Package）架构中，当一个逻辑子包（如 `cascade.graph`）的内容分散在多个物理分发包（如 `cascade-interfaces` 和 `cascade-runtime`）中时，该子包必须也是一个命名空间包（即不能包含 `__init__.py`）。当前 `cascade-py` 中残留的 `__init__.py` 破坏了这一机制。此外，`cascade-py` 中对 `serialize` 模块的引用路径也是过时的，需要同步修正。

### 目标
1.  删除 `packages/cascade-py/src/cascade/graph/__init__.py` 以恢复 `cascade.graph` 的命名空间特性。
2.  修正 `packages/cascade-py/src/cascade/__init__.py` 中错误的导入路径。

### 基本原理
1.  **删除 `__init__.py`**: 遵循 Python 命名空间包规范（PEP 420），确保 `cascade.graph` 能够跨越包边界聚合模块。
2.  **修正 Import**: 重构后，`serialize.py` 位于 `cascade.graph` 模块下，而非 `cascade.runtime.graph`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/package-structure #scope/core #ai/instruct #task/domain/core #task/object/package-layout #task/action/fix-import-error #task/state/begin

---

### Script

#### Acts 1: 删除阻碍命名空间解析的 `__init__.py`

这个文件是空的，且它的存在导致 Python 解释器在 `cascade-py` 中找到 `cascade.graph` 后就停止搜索其他路径，从而找不到 `cascade-runtime` 中的 `build.py`。

~~~~~act
delete_file
packages/cascade-py/src/cascade/graph/__init__.py
~~~~~

#### Acts 2: 修正 `cascade-py` 入口文件中的导入路径

将错误的 `cascade.runtime.graph.serialize` 更新为正确的 `cascade.graph.serialize`。

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
from .tools.cli import cli
from cascade.runtime.graph.serialize import to_json, from_json


# --- V1.3 Factory Functions ---
~~~~~
~~~~~python
from .tools.cli import cli
from cascade.graph.serialize import to_json, from_json


# --- V1.3 Factory Functions ---
~~~~~

### 下一步建议
修复后，建议运行一个简单的 `import cascade as cs; print(cs.__version__)` 脚本来验证修复是否生效。如果仍有导入错误，可能需要检查其他子包（如 `cascade-interfaces` 或 `cascade-runtime`）中是否也存在类似的意外 `__init__.py` 文件。
