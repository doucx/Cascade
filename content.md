你的分析非常准确。这是一个典型的模型演进导致的不一致：我们在 `Physics` 模型中引入了 `canonical_code_structure_hash` 作为核心身份标识，但 `VMExecutionStrategy` 在实例化这些运行时对象时仍然沿用了旧的参数签名。此外，`EmitterNode` 的构造函数实现也存在逻辑错误。

我将生成一个计划来修正这些模型不一致问题。

## [WIP] fix: 修正物理模型构造函数不一致及策略加载逻辑

### 错误分析
测试失败的直接原因是 `TypeError`，根源在于：
1.  **构造函数不匹配**: `cascade.spec.physics.FuncNode` 现在要求 `canonical_code_structure_hash` 作为必须的构造参数，但 `VMExecutionStrategy` 在加载拓扑时并未提供它。
2.  **继承链错误**: `EmitterNode` 在调用 `super().__init__` 时，参数顺序和数量与基类 `FuncNode` 严重脱节，且同样缺失了规范哈希。
3.  **模型冗余**: `PhysicsFuncNode` 规格类中存在重复的 `sink_id` 字段定义。

### 用户需求
修复物理引擎模型（Reactor/Physics）与其构造者（Compiler/Strategy）之间的契约，确保 `VMExecutionStrategy` 能够正确实例化物理节点并启动反应堆。

### 评论
这次修复是确保“全对称物理引擎”能够跑通最简单流程的关键。它不仅修正了代码错误，还通过强制要求 `canonical_code_structure_hash` 增强了运行时节点与其代码定义之间的链接稳定性。

### 目标
1.  修正 `FuncNode` 和 `EmitterNode` 的构造函数。
2.  更新 `VMExecutionStrategy._load_topology` 以传递必要的哈希值。
3.  清理 `PhysicsFuncNode` 中的冗余字段。

### 基本原理
我们必须保证静态规格（Spec）和动态实例（Physics）在属性上是对齐的。由于 `Backend` 已经确保了 `PhysicsFuncNode` 包含 `canonical_code_structure_hash`，策略层只需要将其透传给运行时构造函数即可。

### 标签
#intent/fix #flow/ready #priority/critical #comp/vm #comp/engine #concept/physics #scope/api #ai/refine #task/domain/vm #task/object/physics-models #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 `physics.py` 中的节点构造函数

我们需要更新 `EmitterNode` 的 `__init__` 签名，使其包含 `canonical_code_structure_hash`，并正确传递给 `super()`。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
class EmitterNode(FuncNode):
    """
    Runtime representation of an emission point.
    When fired, it pushes the payload of its input token to a registered Sink.
    """

    def __init__(
        self,
        name: str,
        sink_id: str,
        resource_requirements: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name, resource_requirements)
        self.sink_id = sink_id
~~~~~
~~~~~python.new
class EmitterNode(FuncNode):
    """
    Runtime representation of an emission point.
    When fired, it pushes the payload of its input token to a registered Sink.
    """

    def __init__(
        self,
        name: str,
        canonical_code_structure_hash: str,
        sink_id: str,
        resource_requirements: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name, canonical_code_structure_hash, resource_requirements)
        self.sink_id = sink_id
~~~~~

#### Acts 2: 更新 `VMExecutionStrategy` 的拓扑加载逻辑

现在我们需要在 `vm.py` 中将规格中的哈希值透传给运行时对象。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # Pass 2: Instantiate all FuncNodes and wire their inputs
        for spec_f_node in topology.func_nodes.values():
            if spec_f_node.sink_id:
                f_node = EmitterNode(
                    name=spec_f_node.current_node_instance_hash,
                    sink_id=spec_f_node.sink_id,
                )
            else:
                f_node = FuncNode(name=spec_f_node.current_node_instance_hash)

            runtime_func_nodes[spec_f_node.current_node_instance_hash] = f_node
~~~~~
~~~~~python.new
        # Pass 2: Instantiate all FuncNodes and wire their inputs
        for spec_f_node in topology.func_nodes.values():
            if spec_f_node.sink_id:
                f_node = EmitterNode(
                    name=spec_f_node.current_node_instance_hash,
                    canonical_code_structure_hash=spec_f_node.canonical_code_structure_hash,
                    sink_id=spec_f_node.sink_id,
                )
            else:
                f_node = FuncNode(
                    name=spec_f_node.current_node_instance_hash,
                    canonical_code_structure_hash=spec_f_node.canonical_code_structure_hash,
                )

            runtime_func_nodes[spec_f_node.current_node_instance_hash] = f_node
~~~~~

#### Acts 3: 清理 `topology.py` 中的冗余字段

移除 `PhysicsFuncNode` 中重复定义的 `sink_id`。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
~~~~~
~~~~~python.new
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
~~~~~

### 下一步建议
在应用这些修复后，再次运行 `test_vm_strategy_integration.py`。如果构造函数报错消失，我们可能会遇到反应堆内部的异步协调逻辑（如 Sinks 触发顺序）或 Executor 链接 symbol_table 的问题。我将根据下一步的测试反馈进行针对性调试。
