简要回答
非常抱歉，这是我的失误。我错误地假设 `visualize` 函数在 `preview.py` 中，但实际上它位于独立的 `visualize.py` 模块里。这也是为什么之前空的 `__init__.py` 没有报错，因为那时大家都是直接从子模块导入的。

现在为了提供更整洁的 API（即允许 `from cascade.tools import visualize`），我们需要在 `__init__.py` 中正确地组织这些导入。

## [WIP] fix(sdk): 修正 tools 包的导入路径错误

### 错误分析
`ImportError: cannot import name 'visualize' from 'cascade.tools.preview'`

**原因**:
在 `packages/cascade-sdk/src/cascade/tools/__init__.py` 中，我写了 `from .preview import dry_run, visualize`。
然而，`visualize` 函数实际上定义在 `packages/cascade-sdk/src/cascade/tools/visualize.py` 文件中，而非 `preview.py`。

**解决方案**:
将导入语句拆分，从正确的子模块导入 `visualize`。

### 用户需求
修复 `cascade.tools` 包的导入错误，使其能正确导出 `visualize`、`dry_run` 和新的 `to_lisp`。

### 评论
这是一个简单的路径引用修正，对于确保 SDK 的可用性至关重要。

### 目标
1.  修正 `cascade/tools/__init__.py` 中的导入语句。

### 基本原理
将 `visualize` 的导入源从 `.preview` 改为 `.visualize`。

### 标签
#intent/fix #flow/ready #priority/high #comp/sdk #scope/dx #ai/instruct #task/domain/tooling #task/object/package-structure #task/action/fix-import #task/state/continue

---

### Script

#### Acts 1: 修正导入路径

~~~~~act
write_file
packages/cascade-sdk/src/cascade/tools/__init__.py
~~~~~
~~~~~python
from .cli import create_cli
from .preview import dry_run
from .visualize import visualize
from .lisp import to_lisp

__all__ = ["create_cli", "dry_run", "visualize", "to_lisp"]
~~~~~
