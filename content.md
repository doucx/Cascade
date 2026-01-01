好的，我来分析这个问题。

这是一个典型的**构造函数签名不匹配**错误，源于我们在上一步中对 `FuncNode` 的基类进行了修改，但忘记将这个修改同步到其所有子类 (`EmitterNode` 和 `TerminatorNode`)。

**错误分析**:
1.  **直接原因**: 我们在 `cascade.spec.physics.FuncNode` 的 `__init__` 方法中添加了 `code_structure_hash` 参数。
2.  **遗漏之处**: Python 中，如果子类没有定义自己的 `__init__`，它会继承父类的。但如果子类**有**自己的 `__init__`（就像 `EmitterNode` 那样），它就**不会**自动继承父类 `__init__` 的新参数。我们为 `EmitterNode` 定义了 `__init__(self, name, sink_id, ...)`，这个签名现在与父类 `FuncNode.__init__(self, name, code_structure_hash, ...)` 不兼容。
3.  **连锁反应**: `TerminatorNode` 没有自定义 `__init__`，所以它隐式地继承了新的签名，因此没有报错。但 `EmitterNode` 报错了。

**解决方案**:
我们需要标准化所有 `FuncNode` 及其子类的构造函数，确保它们都接受 `code_structure_hash`，即使对于像 `EmitterNode` 这样没有用户代码的内在节点也是如此。

我们将执行以下操作：
1.  修改 `cascade.spec.physics.EmitterNode` 的 `__init__` 方法，使其接受 `code_structure_hash` 并将其传递给父类的构造函数。
2.  为保持一致性，也为 `TerminatorNode` 添加一个显式的 `__init__`，遵循同样的模式。这能让代码更清晰，并防止未来对基类的修改再次悄悄地破坏它。

## [WIP] fix(spec): Align FuncNode subclass signatures

### 用户需求
修复因 `FuncNode` 基类构造函数变更而导致的 `EmitterNode` 初始化 `TypeError`。

### 评论
这是一个常见的面向对象编程中的维护问题。通过显式地更新所有子类的构造函数以匹配父类的新契约，并使用 `super().__init__()` 来传递参数，我们确保了继承链的健壮性和一致性。这使得未来对基类的修改更容易被发现和同步。

### 目标
1.  更新 `cascade.spec.physics.EmitterNode` 的 `__init__` 签名。
2.  为 `cascade.spec.physics.TerminatorNode` 添加一个显式的 `__init__` 签名以保持一致性。
3.  确保 `cascade-engine` 测试能够通过。

### 基本原理
我们将修改 `EmitterNode` 和 `TerminatorNode` 的构造函数，使其能够接收 `code_structure_hash` 并通过 `super()` 调用将其传递给 `FuncNode` 基类。对于这些没有实际用户代码的内在节点，`code_structure_hash` 可以是一个空字符串或 `None`。

### 标签
#intent/fix #flow/ready #priority/high #comp/spec #concept/inheritance #task/domain/runtime #task/object/physics-model #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 EmitterNode 和 TerminatorNode 的构造函数

我们将更新 `packages/cascade-spec/src/cascade/spec/physics.py` 文件，使子类与 `FuncNode` 的新构造函数签名保持一致。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
class TerminatorNode(FuncNode):
    """
    Runtime representation of a termination point.
    When fired, it signals the Reactor to stop.
    """
    pass


class EmitterNode(FuncNode):
    """
    Runtime representation of an emission point.
    When fired, it pushes the payload of its input token to a registered Sink.
    """
    def __init__(
        self, 
        name: str, 
        sink_id: str,
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        super().__init__(name, resource_requirements)
        self.sink_id = sink_id
~~~~~
~~~~~python.new
class TerminatorNode(FuncNode):
    """
    Runtime representation of a termination point.
    When fired, it signals the Reactor to stop.
    """
    def __init__(
        self, 
        name: str, 
        code_structure_hash: str = "",
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        super().__init__(name, code_structure_hash, resource_requirements)


class EmitterNode(FuncNode):
    """
    Runtime representation of an emission point.
    When fired, it pushes the payload of its input token to a registered Sink.
    """
    def __init__(
        self, 
        name: str, 
        sink_id: str,
        code_structure_hash: str = "",
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        super().__init__(name, code_structure_hash, resource_requirements)
        self.sink_id = sink_id
~~~~~

### 下一步建议
我们已经修复了 `FuncNode` 子类的构造函数签名。现在整个编译和运行时加载流程在类型上应该是对齐的。

下一步是重新运行测试。如果所有测试都通过了，那我们就完成了阶段 5.3 的核心重构，可以进入最后的验证阶段了。
