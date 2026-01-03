## [WIP] fix(compiler): 修复 Builder 违反二分图原则导致的依赖失效

### 用户需求
修复 `Builder` 在处理 `dependencies` (`.after()`) 和 `condition` (`.run_if()`) 时直接连接两个 `FuncNode` 的错误。这种连接违反了二分图原则，导致 `Reactor` 忽略了这些依赖，从而引发下游任务提前执行（偷跑）。

### 评论
这是一个涉及物理场基本定律的修正。在我们的模型中，能量（Token）必须在“库所（DataNode）”中停留，不能直接从一个“变迁（FuncNode）”跳到另一个。通过引入中间的 `Signal` 数据节点，我们不仅修复了二分图结构，还利用 `Reactor` 的扇出机制天然实现了信号的广播，确保了依赖关系的物理真实性。

### 目标
修改 `packages/cascade-compiler/src/cascade/compiler/backend/builder.py`，在连接控制流依赖时，动态创建中间的 `PhysicsDataNode`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/signal-channel #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 在 Builder 中引入信号中继节点

我们将修改 `Builder` 的连接逻辑，为 `wait_for` 和 `condition` 连接插入中间数据节点。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # 4.2 Sequence Dependencies (.after())
            for dep_id in node_ir.dependencies:
                if dep_id in subgraphs:
                    source_subgraph = subgraphs[dep_id]
                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    port_name = f"wait_for_{dep_id}"
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=port_name,
                        )
                    )

            # 4.3 Condition (.run_if())
            if node_ir.condition and node_ir.condition in subgraphs:
                source_subgraph = subgraphs[node_ir.condition]
                # Help static analysis
                assert source_subgraph.stainer is not None

                physical_graph.channels.append(
                    Channel(
                        source_node_id=source_subgraph.stainer.id,
                        source_port="output",
                        target_node_id=target_subgraph.bleacher.id,
                        target_port="condition",
                    )
                )
~~~~~
~~~~~python.new
            # 4.2 Sequence Dependencies (.after())
            for dep_id in node_ir.dependencies:
                if dep_id in subgraphs:
                    source_subgraph = subgraphs[dep_id]
                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    port_name = f"wait_for_{dep_id}"
                    
                    # Create intermediate DataNode for the signal
                    signal_node_id = f"signal.{dep_id}.to.{node_ir.id}"
                    signal_node = PhysicsDataNode(
                        id=signal_node_id,
                        name=f"Signal({dep_id}->{node_ir.name})",
                        capacity=1
                    )
                    physical_graph.nodes[signal_node_id] = signal_node

                    # Wire Stainer -> Signal
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=signal_node_id,
                            target_port="in",
                        )
                    )
                    
                    # Wire Signal -> Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=signal_node_id,
                            source_port="out",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=port_name,
                        )
                    )
            
            # 4.3 Condition (.run_if())
            if node_ir.condition and node_ir.condition in subgraphs:
                source_subgraph = subgraphs[node_ir.condition]
                # Help static analysis
                assert source_subgraph.stainer is not None

                # Create intermediate DataNode for the condition signal
                cond_node_id = f"cond.{node_ir.condition}.to.{node_ir.id}"
                cond_node = PhysicsDataNode(
                    id=cond_node_id,
                    name=f"Cond({node_ir.condition}->{node_ir.name})",
                    capacity=1
                )
                physical_graph.nodes[cond_node_id] = cond_node

                # Wire Stainer -> CondNode
                physical_graph.channels.append(
                    Channel(
                        source_node_id=source_subgraph.stainer.id,
                        source_port="output",
                        target_node_id=cond_node_id,
                        target_port="in",
                    )
                )

                # Wire CondNode -> Bleacher
                physical_graph.channels.append(
                    Channel(
                        source_node_id=cond_node_id,
                        source_port="out",
                        target_node_id=target_subgraph.bleacher.id,
                        target_port="condition",
                    )
                )
~~~~~

#### Acts 2: 同样修复 Data Dependencies 的连接

虽然数据依赖在之前的测试中看似工作正常，但那是 `Stainer` -> `Bleacher` 吗？
不，数据依赖通常是 `Stainer` -> `Bleacher`。
`Stainer` 的 `output` 端口。
`Builder`:
```python
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )
```
**这也是错的！** 数据依赖也违反了二分图原则。
我们需要为每一个数据传输也创建一个 DataNode。
或者，我们可以利用上游已有的 `D_worker_out`？
不，`D_worker_out` 在 `Stainer` 之前。
`Stainer` 的作用是染色。
所以下游确实需要 `Stainer` 的输出。

我们需要为每一个数据依赖连接也插入一个 DataNode。或者复用一个广播用的 DataNode？
不，为了简单和隔离，我们为每条边创建一个 DataNode 是最安全的。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
                # Case A: Reference to another node (Dependency)
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]

                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    # Create intermediate DataNode for data transfer
                    data_node_id = f"data.{source_ref}.to.{node_ir.id}.{arg_name}"
                    data_node = PhysicsDataNode(
                        id=data_node_id,
                        name=f"Data({source_ref}->{node_ir.name}.{arg_name})",
                        capacity=1
                    )
                    physical_graph.nodes[data_node_id] = data_node

                    # Wire Stainer -> DataNode
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=data_node_id,
                            target_port="in",
                        )
                    )

                    # Wire DataNode -> Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=data_node_id,
                            source_port="out",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )
~~~~~

### 下一步建议
这次修复是全面且彻底的。我们不仅修复了信号依赖，也顺带修正了数据依赖的潜在问题。请运行测试。我非常有信心 `setup_task` 这次会正确运行，且 `main_task` 会乖乖等待。
