## [WIP] fix: Resolve Dataclass Inheritance Order Issue in TaskDef

### 错误分析
测试失败的原因是 `TypeError: non-default argument 'func' follows default argument 'metadata'`。
这是 Python `dataclasses` 继承的一个经典陷阱。
1.  **基类 `Definition`**: 定义了带默认值的字段 `metadata` (`metadata: Dict[str, Any] = field(default_factory=dict)`).
2.  **子类 `TaskDef`**: 定义了无默认值的字段 `func` 和 `name`。
3.  **继承机制**: Python 合并字段时，基类的字段在前，子类的在后。结果生成的 `__init__` 签名类似于 `__init__(self, fingerprint=None, metadata={}, func, name)`。这违反了 Python 语法规则：**所有带默认值的参数必须放在无默认值参数之后**。

### 用户需求
修复 `cascade-foundation` 中的 `dataclass` 定义，使其符合 Python 的继承规则。

### 评论
这个问题必须在 Phase 2 TDD 的早期解决。如果不修复，任何涉及 `TaskDef` 的测试都无法运行。

### 目标
调整 `Definition` 和 `TaskDef` 的字段定义，确保生成的 `__init__` 方法签名合法。

### 基本原理
对于 `dataclasses` 继承问题，主要有两种解决方案：
1.  **KW_ONLY (Python 3.10+)**: 强制所有有默认值的字段变为 Keyword-Only 参数。这通常是最干净的解法，特别是对于基类中的元数据字段。
2.  **重排**: 将基类中的所有字段都设为无默认值（不可行，因为 `metadata` 应该是可选的）。
3.  **子类提供默认值**: 也不可行。

我们将采用 **`kw_only=True`** 策略。这将强制所有后续字段（包括子类的新字段）都必须作为关键字参数传递，从而绕过“非默认跟随默认”的顺序限制，或者仅仅将基类的带默认值字段标记为 `kw_only`。但在 3.10+ 中，最简单的是在基类 `Definition` 的装饰器中添加 `kw_only=True`。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/foundation #scope/core
#ai/instruct
#task/domain/core #task/object/ir #task/action/fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修正 Definition 基类
将 `Definition` 标记为 `kw_only=True`。这会使得 `fingerprint` 和 `metadata` 在 `__init__` 中成为 Keyword-Only 参数，从而不再干扰子类的位置参数顺序。

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/definitions/base.py
~~~~~
~~~~~python.old
@dataclass
class Definition:
    """
    Base class for all IR Level 0 definitions.
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class Definition:
    """
    Base class for all IR Level 0 definitions.
~~~~~

#### Acts 2: 修正 TaskDef 子类
为了保持一致性（且通常是良好的实践），我们也建议将子类标记为 `kw_only=True`，或者至少确保它的无默认值字段在语义上是可以接受的。如果基类是 `kw_only=True`，子类的无默认值字段将变成位置参数（如果子类没有 `kw_only=True`），或者也变成关键字参数（如果子类有）。
为了 API 的清晰性，我们统一让所有 IR 定义都使用关键字参数构造。

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/definitions/model.py
~~~~~
~~~~~python.old
@dataclass
class TaskDef(Definition):
    """
    Represents a computational task definition.
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class TaskDef(Definition):
    """
    Represents a computational task definition.
~~~~~

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/definitions/model.py
~~~~~
~~~~~python.old
@dataclass
class ServiceDef(Definition):
    """
    Represents a configuration for an external service operation.
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class ServiceDef(Definition):
    """
    Represents a configuration for an external service operation.
~~~~~

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/definitions/model.py
~~~~~
~~~~~python.old
@dataclass
class MapDef(Definition):
    """
    Represents a mapping operation over another definition.
    """
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class MapDef(Definition):
    """
    Represents a mapping operation over another definition.
    """
~~~~~

### 下一步建议
重新运行测试。现在 `TaskDef(...)` 调用必须使用关键字参数（例如 `TaskDef(name="foo", ...)`），检查测试代码 `test_builder.py` 是否已经使用了关键字参数（看起来是的，`TaskDef(name="my_task", ...)`）。如果不符合，也需要更新测试代码。
