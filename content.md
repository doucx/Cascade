简要回答
好吧，Python 的 `dataclass` 行为比我预期的还要顽固。即使在基类中手动定义了 `__eq__`，`dataclass` (默认 `eq=True`) 依然会在子类上覆盖（override）它，并随即将 `__hash__` 设为 `None`。

## [WIP] fix(graph): 强制 dataclasses 不覆盖 Node 的相等性逻辑

### 错误分析
简单地在基类添加 `__eq__` 不足以阻止 Python 的 `dataclass` 机制在子类上生成默认的 `__eq__` 方法。当 `@dataclass` 装饰器应用到子类（如 `TaskNode`）时，默认参数是 `eq=True`，这意味着它会为子类生成一个新的 `__eq__` 方法（比较所有字段），这再次触发了 Python 将 `__hash__` 设为 `None` 的机制。

### 解决方案
必须显式告诉 `dataclasses` 模块：虽然你是数据类，但你不应该管相等性，因为我已经基于 ID 定义好了唯一的对象身份。
我们需要修改 `cascade/graph/model.py` 中 `TaskNode`, `MapNode`, `ParamNode` 的 `@dataclass` 装饰器，添加参数 `eq=False`。这会强制保留基类 `Node` 中手动定义的基于 `structural_id` 的 `__eq__` 和 `__hash__` 方法。

### Script

#### Acts 1: 对所有 Node 子类禁用自动生成 eq

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class TaskNode(Node):
    """Represents a standard executable task."""
~~~~~
~~~~~python.new
@dataclass(eq=False)
class TaskNode(Node):
    """Represents a standard executable task."""
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class MapNode(Node):
    """Represents a mapped task execution."""
~~~~~
~~~~~python.new
@dataclass(eq=False)
class MapNode(Node):
    """Represents a mapped task execution."""
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class ParamNode(TaskNode):
    """Represents an external parameter injection."""
~~~~~
~~~~~python.new
@dataclass(eq=False)
class ParamNode(TaskNode):
    """Represents an external parameter injection."""
~~~~~

### 下一步建议
再次运行测试。这次变更显式地接管了对象身份的定义权，应该能彻底解决哈希问题。
