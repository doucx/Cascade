## [WIP] fix: Resolve Dataclass Inheritance Order in Ops

### 错误分析
与 `TaskDef` 遇到的问题完全一致，`cascade.foundation.ir.ops.Op` 基类定义了带默认值的字段 (`inputs`, `control_deps`)，而子类 `ComputeOp` 定义了无默认值的字段 (`callable_ref`)。这导致生成的 `__init__` 方法签名非法。

### 用户需求
修复 `Op` 及其子类的 `dataclass` 定义，使其能够正确继承。

### 评论
必须统一使用 `kw_only=True` 策略。这不仅解决了继承问题，也使得构建 Op 时的代码更具可读性（必须写 `Op(id="...", callable_ref="...")`）。

### 目标
为 `packages/cascade-foundation/src/cascade/foundation/ir/ops.py` 中的所有 dataclass 添加 `kw_only=True`。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/foundation #scope/core
#ai/instruct
#task/domain/core #task/object/ir #task/action/fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修正 Ops 定义
批量为所有 Op 类添加 `kw_only=True`。

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/ir/ops.py
~~~~~
~~~~~python.old
@dataclass
class Op:
    """
    Base class for Level 1 IR Operations.
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class Op:
    """
    Base class for Level 1 IR Operations.
~~~~~

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/ir/ops.py
~~~~~
~~~~~python.old
@dataclass
class ComputeOp(Op):
    """
    Represents a computational task (function execution).
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class ComputeOp(Op):
    """
    Represents a computational task (function execution).
~~~~~

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/ir/ops.py
~~~~~
~~~~~python.old
@dataclass
class ConstantOp(Op):
    """
    Represents a static value.
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class ConstantOp(Op):
    """
    Represents a static value.
~~~~~

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/ir/ops.py
~~~~~
~~~~~python.old
@dataclass
class ResourceOp(Op):
    """
    Represents a resource lifecycle action.
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class ResourceOp(Op):
    """
    Represents a resource lifecycle action.
~~~~~

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/ir/ops.py
~~~~~
~~~~~python.old
@dataclass
class MultiplexOp(Op):
    """
    Represents a branching decision (Router).
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class MultiplexOp(Op):
    """
    Represents a branching decision (Router).
~~~~~

#### Acts 2: 修正 Compiler 中的 Op 构造调用
由于我们强制了 `kw_only=True`，之前 Compiler 代码中如果有使用位置参数构造 Op 的地方（虽然之前看起来主要是关键字参数，但为了保险起见，检查一下 `builder.py`），必须确保使用关键字参数。

检查 `packages/cascade-compiler/src/cascade/compiler/builder.py`：
之前的代码是：
```python
op = ComputeOp(
    id=op_id,
    inputs=inputs,
    callable_ref=...,
    config=...
)
```
这已经是关键字参数了，所以不需要修改 `builder.py`。但是，我们需要确保 `test_builder.py` 中的测试代码也是合规的。

检查 `test_builder.py`：
我们在 Acts 5 中生成的 `test_builder.py` 使用了关键字参数 `TaskDef(name="my_task", ...)`。所以测试代码应该也是安全的。

### 下一步建议
再次运行测试。
