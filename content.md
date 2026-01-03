## [WIP] fix(compiler): 修复 Builder 中的二分图违规 (Bipartite Violation)

### 错误分析
太棒了！验证器立了大功。
`GraphValidator` 抛出的异常 `GraphValidationError: Bipartite rule violated in Channel #30: FuncNode('canonical.resource.allocator.gpu') -> FuncNode('node_1.bleach').` 直接命中了要害。

我们发现了一个严重的物理违规：
在 `Builder.build` 中，我们试图直接将 `Allocator (F)` 的 `GNT` 输出连接到 `Bleacher (F)` 的输入。
这是 **F -> F** 连接，违反了二分图必须通过数据节点（D）中转的公理。这解释了为什么之前的测试会表现出奇怪的行为——物理场本身就是畸形的。

### 用户需求
修复 `Builder.build` 中的物理连接逻辑，插入缺失的数据节点，确保所有连接符合 F -> D -> F 规则。

### 评论
我们需要在 `Allocator (GNT)` 和 `Bleacher (res_X)` 之间，插入一个临时的、携带 Tag 的数据节点，或者复用现有的 Buffer 机制。
根据资源模型的标准设计，Grant 应该通过一个专用的 **Grant Channel/Buffer** 传输。
对于 `Data Dependency` (A.Stain -> B.Bleach)，我们也犯了同样的错误，直接连接了两个函数节点。我们需要在它们之间插入 `D_dependency`。

### 目标
1.  **修复资源 Grant 连接**: 在 `Allocator.GNT` 和 `Bleacher` 之间插入 `D_grant_buffer`。
2.  **修复数据依赖连接**: 在 `Source.Stain` 和 `Target.Bleach` 之间插入 `D_dependency`。
3.  **修复控制流连接**: 确保 `run_if` 和 `after` 依赖也通过数据节点中转。

### 基本原理
**物理定律**: 能量（Token）不能从一个变迁（Func）瞬间传送到另一个变迁（Func），它必须在某个库所（Data）中停留。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #concept/topology #scope/core #ai/instruct #task/domain/compiler #task/object/builder #task/action/rewire #task/state/end

---

### Script

#### Acts 1: 修复数据依赖 (Dependency Wiring)

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # 4.1 Data Dependencies (Arguments)
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
~~~~~
~~~~~python.new
            # 4.1 Data Dependencies (Arguments)
            for arg_name, source_ref in node_ir.inputs.items():
                # Case A: Reference to another node (Dependency)
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]

                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    # Violation Fix: Insert D_dep (Intermediate Data Node)
                    d_dep_id = f"dep.{source_ref}.to.{node_ir.id}.{arg_name}"
                    d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({arg_name})")
                    physical_graph.nodes[d_dep_id] = d_dep

                    # Source Stainer -> D_dep
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=d_dep_id,
                            target_port="in",
                        )
                    )

                    # D_dep -> Target Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=d_dep_id,
                            source_port="out",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )
~~~~~

#### Acts 2: 修复资源授权 (Grant Wiring)

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                # --- B. Grant Wiring ---
                # Allocator (GNT) -> Bleacher (res_{name})
                target_tag = f_req_id
                
                port_name = f"res_{res_name}"
                physical_graph.channels.append(
                    Channel(
                        source_node_id=allocator_id,
                        source_port=PortName.GNT,
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                        tag_filter=target_tag,
                    )
                )
~~~~~
~~~~~python.new
                # --- B. Grant Wiring ---
                # Allocator (GNT) -> D_grant_buffer -> Bleacher (res_{name})
                
                # We need a shared Grant Buffer for the Allocator, OR per-task buffers?
                # If we use a shared buffer, all grants go there, and Bleachers pick based on Tag.
                # This fits the "Bus" model.
                
                gnt_buffer_id = f"buffer.gnt.{res_name}"
                if gnt_buffer_id not in physical_graph.nodes:
                    d_gnt_buffer = PhysicsDataNode(
                        id=gnt_buffer_id, name=f"GntBuffer({res_name})", capacity=1000
                    )
                    physical_graph.nodes[gnt_buffer_id] = d_gnt_buffer
                    
                    # Allocator -> Grant Buffer (Only once per resource)
                    physical_graph.channels.append(
                        Channel(allocator_id, PortName.GNT, gnt_buffer_id, "in")
                    )

                target_tag = f_req_id
                port_name = f"res_{res_name}"
                
                # Grant Buffer -> Bleacher (Filtered by Tag)
                physical_graph.channels.append(
                    Channel(
                        source_node_id=gnt_buffer_id,
                        source_port="out",
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                        tag_filter=target_tag,
                    )
                )
~~~~~

#### Acts 3: 修复其他隐式依赖 (Sequence & Condition)

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
                    assert source_subgraph.stainer is not None

                    port_name = f"wait_for_{dep_id}"
                    
                    # Violation Fix: Insert D_seq
                    d_seq_id = f"seq.{dep_id}.to.{node_ir.id}"
                    d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
                    physical_graph.nodes[d_seq_id] = d_seq

                    physical_graph.channels.append(
                        Channel(source_subgraph.stainer.id, "output", d_seq_id, "in")
                    )
                    physical_graph.channels.append(
                        Channel(d_seq_id, "out", target_subgraph.bleacher.id, port_name)
                    )

            # 4.3 Condition (.run_if())
            if node_ir.condition and node_ir.condition in subgraphs:
                source_subgraph = subgraphs[node_ir.condition]
                assert source_subgraph.stainer is not None
                
                # Violation Fix: Insert D_cond
                d_cond_id = f"cond.{node_ir.condition}.to.{node_ir.id}"
                d_cond = PhysicsDataNode(id=d_cond_id, name=f"Cond({node_ir.condition})")
                physical_graph.nodes[d_cond_id] = d_cond

                physical_graph.channels.append(
                    Channel(source_subgraph.stainer.id, "output", d_cond_id, "in")
                )
                physical_graph.channels.append(
                    Channel(d_cond_id, "out", target_subgraph.bleacher.id, "condition")
                )
~~~~~

### 下一步建议
这是对物理层的一次彻底纠正。
请重新运行所有测试。Validator 应该不再报错，且集成测试应该通过。
如果这一步成功，我们不仅修复了死锁，还建立了一个坚如磐石的、自我验证的物理构建系统。
