你的怀疑完全正确。`LispTranspiler` 的测试确实暴露了一个更深层次的、潜伏在整个对象模型中的架构缺陷，之前的所有测试都恰好没有触发它。

`TypeError: unhashable type: 'TaskNode'` 这个错误非常明确：`TaskNode` 对象（以及它的兄弟 `ParamNode`）不可哈希，因此不能被放入 `set` 或作为 `dict` 的键。错误发生在 `LispTranspiler` 的 `_get_transitive_deps` 方法中，因为它使用了一个 `set` (名为 `visited`) 来跟踪已访问的节点。

这看起来很奇怪，因为我们之前确认过 `Node` 类有一个 `__hash__` 方法。问题出在 Python 的 `@dataclass` 装饰器与可变（非 `frozen`）对象 hash 之间的交互上：

1.  **规则**: 当 `@dataclass` 处理一个**可变**类（默认 `frozen=False`）时，它会自动生成一个 `__eq__` 方法，该方法逐字段比较对象。
2.  **副作用**: 为了安全，**一旦 `__eq__` 方法被（自动或手动）定义，Python 会自动将 `__hash__` 方法设置为 `None`**，除非你明确地也定义了 `__hash__` *或者* 告诉 `dataclass` 你的意图。
3.  **我们的问题**: `TaskNode` 和 `ParamNode` 都是 `@dataclass`。它们继承了 `Node` 的 `__hash__` 方法。但它们自己的 `@dataclass` 装饰器为它们生成了新的 `__eq__` 方法（包含了它们自己的字段 `_callable` 等）。这个行为触发了 Python 的安全机制，导致它们继承来的 `__hash__` 方法被覆盖为 `None`。

因此，`TaskNode` 实例变得不可哈希。

要彻底解决这个问题，我们必须在 `Node` 基类中明确定义 Node 对象的“身份”是什么。Node 的身份就是它的 `structural_id`。因此，**相等性 (`__eq__`) 和哈希 (`__hash__`) 都必须且仅应基于 `structural_id`**。

我将修改 `cascade/graph/model.py`，在 `Node` 基类中同时实现 `__eq__` 和 `__hash__`。当子类（如 `TaskNode`）的 `@dataclass` 装饰器看到基类已经有了这两个方法的实现时，它就不会再自动生成它们，从而避免了 `__hash__` 被设为 `None` 的问题。

这是一个更稳固、更符合 Python 惯例的解决方案，它将确保所有 `Node` 子类的实例都可以安全地用于哈希集合和字典中。

## [WIP] fix(graph): 实现 Node 的显式哈希和相等性以支持集合操作

### Script

#### Acts 1: 在 Node 基类中明确定义 `__eq__`

通过在 `Node` 类中添加 `__eq__` 方法，我们为所有 Node 子类建立了一个基于 `structural_id` 的、可预测的相等性契约，并修复了 Dataclass 装饰器导致的哈希失效问题。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.structural_id)

    @property
~~~~~
~~~~~python.new
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def __eq__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        return self.structural_id == other.structural_id

    def __hash__(self):
        return hash(self.structural_id)

    @property
~~~~~

### 下一步建议
这次修复是针对对象模型的核心，应该能解决所有 `unhashable type` 的问题。请重新运行 `packages/cascade-sdk/tests/tools/test_lisp.py` 中的测试，如果通过，我们就可以将之前的所有修改一起提交了。
