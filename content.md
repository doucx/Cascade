好的，我们将实施“全局启动脉全新”方案来解决源节点无法启动的战略性缺陷。这需要对 `Builder` 进行结构性增强。

## [WIP] feat(compiler): 实现全局启动脉冲以驱动源节点

### 用户需求
修复 `Reactor` 无法启动无输入源任务（如 `setup_task`）的根本问题。通过在编译器 `Builder` 中引入一个全局启动脉冲 (`global.start.pulse` DataNode)，并自动将其连接到所有无上游依赖的 `Bleacher` 节点，来确保所有源任务都能接收到初始激发能量。

### 评论
这是一个关键的架构修正，它使 Cascade 的物理执行模型更加自洽和完备。我们不再依赖 `Reactor` 的特殊逻辑来处理源节点，而是将“第一推动力”也物化为一个物理实体 (`D_start`) 和物理连接 (Channels)。这完美符合“逻辑即拓扑”的核心哲学。此变更将解锁 E2E 测试，并从根本上解决 `setup_task` 不运行的问题。

### 目标
1.  **增强 `Builder`**: 在 `build` 方法中，首先创建一个 `global.start.pulse` 数据节点，并用一个 Token 对其进行 `prime`。
2.  **自动布线**: `Builder` 在完成所有显式依赖的布线后，必须扫描图中所有的 `Bleacher` 节点。
3.  **识别源节点**: 对于任何没有入边 (incoming channels) 的 `Bleacher` 节点，自动创建一条从 `global.start.pulse` 到该 `Bleacher` 的 `__start__` 信号端口的通道。
4.  **增强 `Expander`**: 确保所有 `Bleacher` 节点都拥有一个 `__start__` 信号输入端口，以便 `Builder` 进行连接。

### 基本原理
在物理场模型中，任何 `FuncNode` 的激发都必须由上游 `DataNode` 的能量（Token）触发。对于没有显式上游依赖的源任务，它们也需要一个初始能量来源来启动。`global.start.pulse` 扮演的就是这个“宇宙大爆炸”的角色，它为所有独立的计算分支提供启动所需的能量。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #scope/core #ai/brainstorm #task/domain/compiler #task/object/source-node-activation #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 Expander 中为 Bleacher 增加 `__start__` 端口

我们需要一个标准化的端口来接收启动脉冲。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {
            arg.name: PortDef(arg.name, PortRole.DATA, "Any")
            for arg in node_ir.task.args
        }
~~~~~
~~~~~python.new
        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {
            # Add a standardized port for the global start pulse
            "__start__": PortDef("__start__", PortRole.SIGNAL, "Pulse"),
            **{
                arg.name: PortDef(arg.name, PortRole.DATA, "Any")
                for arg in node_ir.task.args
            }
        }
~~~~~

#### Acts 2: 在 Builder 中实现全局启动脉冲

这是本次修复的核心。我们将修改 `Builder` 来创建 `D_start` 并自动连接到源节点。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 1. Create Objective Environment (D_res nodes)
        for res_def in environment.resources:
            res_node_id = PhysicalIdGenerator.global_resource(res_def.name)
            d_res = PhysicsDataNode(
                id=res_node_id,
                name=f"Resource({res_def.name})",
                capacity=res_def.capacity,
                initial_tokens=res_def.capacity,
            )
            physical_graph.nodes[res_node_id] = d_res

        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = PhysicalIdGenerator.observability_bus()
~~~~~
~~~~~python.new
        # 1. Create Global Infrastructure
        # 1.1 Objective Environment (D_res nodes)
        for res_def in environment.resources:
            res_node_id = PhysicalIdGenerator.global_resource(res_def.name)
            d_res = PhysicsDataNode(
                id=res_node_id,
                name=f"Resource({res_def.name})",
                capacity=res_def.capacity,
                initial_tokens=res_def.capacity,
            )
            physical_graph.nodes[res_node_id] = d_res

        # 1.2 Global Start Pulse
        start_pulse_id = PhysicalIdGenerator.start_pulse()
        d_start = PhysicsDataNode(
            id=start_pulse_id,
            name="GlobalStartPulse",
            capacity=sys.maxsize, # Can trigger infinite source nodes
            initial_tokens=1,
        )
        physical_graph.nodes[start_pulse_id] = d_start


        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = PhysicalIdGenerator.observability_bus()
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                # Release: F_stain -> D_res
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=res_node_id,
                        target_port="in",
                    )
                )

        return physical_graph
~~~~~
~~~~~python.new
                # Release: F_stain -> D_res
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=res_node_id,
                        target_port="in",
                    )
                )

        # 6. Wire Global Start Pulse to all Source Nodes
        # A source node is a bleacher that has no incoming data, condition, or dependency channels.
        all_target_bleacher_ids = {
            c.target_node_id for c in physical_graph.channels if c.target_node_id.endswith(".bleach")
        }

        for subgraph in subgraphs.values():
            bleacher = subgraph.bleacher
            if bleacher and bleacher.id not in all_target_bleacher_ids:
                # This bleacher is a source node, connect it to the start pulse
                physical_graph.channels.append(
                    Channel(
                        source_node_id=start_pulse_id,
                        source_port="out",
                        target_node_id=bleacher.id,
                        target_port="__start__",
                    )
                )


        return physical_graph
~~~~~

#### Acts 3: 更新 PhysicalIdGenerator

我们需要为启动脉冲节点添加一个 ID 生成方法。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def observability_observer() -> str:
        return "global.observability.observer"
~~~~~
~~~~~python.new
    @staticmethod
    def observability_observer() -> str:
        return "global.observability.observer"

    @staticmethod
    def start_pulse() -> str:
        return "global.start.pulse"
~~~~~

### 下一步建议
这次修改从根本上解决了源节点的激发问题。请再次运行 `test_e2e_vm_run.py`。我预计 `setup_task` 和 `should_run_task` 现在将会被正确执行，从而允许整个工作流继续进行。如果测试仍然失败，我们将能从新的 DEBUG 日志中获得更精确的线索。
