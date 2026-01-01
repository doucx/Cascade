## [WIP] feat(compiler): 实现构建器字面量支持与 Reactor 预加载机制

### 用户需求
1.  **构建器支持字面量**: 编译器后端需要能够识别 `NodeIR.inputs` 中的字面量值，并自动在物理图中创建对应的常量节点 (`DataNode`) 和连线，而不是忽略它们。
2.  **Reactor 支持初始载荷**: 物理引擎的 `prime()` 方法需要升级，以支持将具体的 Payload 注入到初始 Token 中，而不仅仅是空的占位符。这对于常量和配置注入至关重要。
3.  **移除测试 Hack**: 清理 `test_resource_backpressure.py` 中为了绕过构建器缺陷而编写的手动构图代码。

### 评论
这是迈向“全功能编译器”的重要一步。目前 `Builder` 只能处理节点间的依赖，无法处理静态参数，这导致生成的图在逻辑上是不完整的。通过引入 `initial_payload` 概念，我们将“常量”这一概念物理化为“预填充了信息的存储槽”，完美契合全对称物理场的哲学。

### 目标
1.  修改 `PhysicsDataNode` 定义，增加 `initial_payload` 字段。
2.  更新 `Reactor.prime` 逻辑，使其在生成初始 Token 时携带 `initial_payload`。
3.  升级 `Builder.build` 逻辑，为每个字面量输入创建一个专属的 `DataNode` 并连接到对应的 `Bleacher`。
4.  重构 `test_resource_backpressure.py`，验证端到端的字面量传递能力。

### 基本原理
在 Cascade 的物理场中，常量不是代码中的魔法值，而是**持久存在的、带有特定信息的势能**。
*   **Spec 变更**: `PhysicsDataNode` 需要知道它持有的初始能量的“质” (`initial_payload`)，而不仅仅是“量” (`initial_tokens`)。
*   **Compiler 变更**: 对于每一个静态输入 `x=10`，编译器会在物理空间中实体化一个名为 `const_..._x` 的存储槽，放入一个值为 `10` 的令牌，并将其管道连接到任务的预处理器。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #comp/vm #concept/data-flow #scope/core #ai/instruct #task/domain/compiler #task/object/literal-values #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修改 Spec 定义

在 `PhysicsDataNode` 中添加 `initial_payload` 字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
@dataclass
class PhysicsDataNode(PhysicsNode):
    capacity: int = 1
    """Maximum number of tokens this node can hold simultaneously."""

    initial_tokens: int = 0
    """Number of tokens to pre-fill at reactor startup (Potential Energy)."""
~~~~~
~~~~~python.new
@dataclass
class PhysicsDataNode(PhysicsNode):
    capacity: int = 1
    """Maximum number of tokens this node can hold simultaneously."""

    initial_tokens: int = 0
    """Number of tokens to pre-fill at reactor startup (Potential Energy)."""

    initial_payload: Any = None
    """The payload to use for pre-filled tokens."""
~~~~~

#### Acts 2: 升级 Reactor 启动逻辑

修改 `Reactor.prime()`，使其使用 `initial_payload` 创建 Token。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    def prime(self) -> None:
        """
        Injects initial potential energy (tokens) into the system
        based on PhysicsDataNode.initial_tokens.
        """
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens are pure potential; no payload, no trace.
                    self.memory.put(node, Token(payload=None))

    async def step(self) -> int:
~~~~~
~~~~~python.new
    def prime(self) -> None:
        """
        Injects initial potential energy (tokens) into the system
        based on PhysicsDataNode.initial_tokens.
        """
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    self.memory.put(node, Token(payload=node.initial_payload))

    async def step(self) -> int:
~~~~~

#### Acts 3: 实现 Builder 的字面量支持

修改 `builder.py`，在构建数据依赖时处理字面量。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
            
            # Help static analysis
            assert target_subgraph.bleacher is not None

            for arg_name, source_ref in node_ir.inputs.items():
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
                    
                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )

        # 5. Wire Global Resources (The Loop)
~~~~~
~~~~~python.new
        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
            
            # Help static analysis
            assert target_subgraph.bleacher is not None

            for arg_name, source_ref in node_ir.inputs.items():
                # Case A: Reference to another node (Dependency)
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
                    
                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )
                # Case B: Literal Value (Constant)
                else:
                    # Create a dedicated DataNode for this constant
                    # Naming convention: const_[target_node]_[arg_name]
                    const_node_id = f"const_{node_ir.id}_{arg_name}"
                    const_node = PhysicsDataNode(
                        id=const_node_id,
                        name=f"Const({arg_name})",
                        capacity=1,
                        initial_tokens=1,
                        initial_payload=source_ref,
                    )
                    physical_graph.nodes[const_node_id] = const_node

                    # Wire Const -> Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=const_node_id,
                            source_port="out",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )

        # 5. Wire Global Resources (The Loop)
~~~~~

#### Acts 4: 重构测试用例

重构 `test_resource_backpressure.py`，移除手动的节点注入，使用 `inputs` 传递参数。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # We need to handle the global D_life observability sidecar if we want full correctness.
    # Builder created 'global_d_life'.
    # But Builder did NOT create an F_obs node attached to it in the current implementation?
    # Let's check builder.py...
    # Builder creates 'd_life' DataNode. But it does NOT seem to create the F_obs node consuming it.
    # It just wires output ports TO d_life.
    # This means d_life will fill up with events. This is fine for this test.

    # 4. FIX for Test: Manually create DataNodes for literal inputs 'x'.
    # This is a temporary measure because the Builder doesn't yet support literals.
    for node_prefix, val in [("node_1", 10), ("node_2", 20)]:
        d_literal = PhysicsDataNode(id=f"{node_prefix}_in_x", name="Literal X")
        physical_graph.nodes[d_literal.id] = d_literal
        physical_graph.channels.append(
            Channel(d_literal.id, "out", f"{node_prefix}_bleach", target_port="x")
        )
        memory.put(d_literal, Token(payload=val))

    # 5. Re-initialize Reactor AFTER all graph modifications are complete.
    reactor = Reactor(physical_graph, memory, executor, func_map)

    # 6. Prime the reactor ONCE to fill D_res.
    reactor.prime()
    assert memory.get_count("global_res_gpu") == 1
~~~~~
~~~~~python.new
    # We need to handle the global D_life observability sidecar if we want full correctness.
    # Builder created 'global_d_life'.
    
    # 4. (Deleted) Manual DataNode creation is no longer needed.
    # The Builder now automatically creates 'const_node_1_x' and 'const_node_2_x'
    # based on the literals in NodeIR.inputs.
    
    # 5. Initialize Reactor
    reactor = Reactor(physical_graph, memory, executor, func_map)

    # 6. Prime the reactor.
    # This should fill:
    # - global_res_gpu (1 token, payload=None)
    # - const_node_1_x (1 token, payload=10)
    # - const_node_2_x (1 token, payload=20)
    reactor.prime()
    
    assert memory.get_count("global_res_gpu") == 1
    assert memory.get_count("const_node_1_x") == 1
    assert memory.get_count("const_node_2_x") == 1
    
    # Verify payloads
    t1 = memory.take("const_node_1_x")
    assert t1.payload == 10
    memory.put(physical_graph.nodes["const_node_1_x"], t1) # Put it back for execution

    t2 = memory.take("const_node_2_x")
    assert t2.payload == 20
    memory.put(physical_graph.nodes["const_node_2_x"], t2) # Put it back
~~~~~

### 下一步建议
我们已经完成了构建器的字面量支持。现在我们应该关注之前战略分析中提到的“命名规范”问题，特别是资源节点的命名 (`global_res_gpu`) 和内部节点 (`_bleach`, `_stain`) 的命名。这些硬编码字符串是技术债务。建议下一步进行 **规范化命名 (Canonical Naming)** 的重构。
