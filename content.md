## [WIP] fix(compiler): 修复 Builder 中的资源饿死问题 (Reclaimer Priority)

### 用户需求
`test_broker_starvation.py` 的通过证实了我们的假设：如果 `Allocator` 在图遍历顺序中先于 `Reclaimer`，并且持续有请求，它会一直抢占 Ledger，导致 `Reclaimer` 无法归还资源，造成系统死锁。
我们需要在 Compiler 的 Builder 中强制实施 **Reclaimer 优先 (Reclaimer Priority)** 的构建顺序。

### 评论
虽然 `test_resource_backpressure.py` 仍然失败，但这正是因为当前的 Builder 实现中 `Allocator` 是先创建并连接的。
解决此问题的“物理学方法”不是引入复杂的调度器逻辑，而是调整物理场的构建拓扑顺序。只要我们在构建阶段保证 `Reclaimer` 在节点列表中排在 `Allocator` 之前，Reactors 的线性扫描特性就会自然地优先执行回收操作。

### 目标
1.  修改 `cascade-compiler/backend/builder.py`。
2.  调整 Broker 组件的创建和注册顺序，确保 `reclaimer_id` 先于 `allocator_id` 被加入 `physical_graph.nodes`。
3.  这应该能自动解决 `test_resource_backpressure.py` 中的死锁问题。

### 基本原理
Reactor 扫描顺序 = 插入 `graph.nodes` 的顺序（Python 3.7+ 字典保证）。
通过先插入 `F_reclaimer`，我们赋予了它对 Ledger 的隐式高优先级访问权。
这是一个零成本的架构修复。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/builder #task/action/reorder #task/state/end

---

### Script

#### Acts 1: 调整 Builder 中的注册顺序

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # F_allocator
            f_allocator = PhysicsFuncNode(
                id=allocator_id,
                name=f"Allocator({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                    PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
                },
            )
            physical_graph.nodes[allocator_id] = f_allocator

            # F_reclaimer
            f_reclaimer = PhysicsFuncNode(
                id=reclaimer_id,
                name=f"Reclaimer({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REL: PortDef(PortName.REL, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                },
            )
            physical_graph.nodes[reclaimer_id] = f_reclaimer
~~~~~
~~~~~python.new
            # F_reclaimer (Priority High: Must release before allocate to avoid starvation)
            f_reclaimer = PhysicsFuncNode(
                id=reclaimer_id,
                name=f"Reclaimer({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REL: PortDef(PortName.REL, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                },
            )
            physical_graph.nodes[reclaimer_id] = f_reclaimer

            # F_allocator (Priority Low)
            f_allocator = PhysicsFuncNode(
                id=allocator_id,
                name=f"Allocator({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                    PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
                },
            )
            physical_graph.nodes[allocator_id] = f_allocator
~~~~~

### 下一步建议
这是修复死锁的最后一步。请重新运行 `test_resource_backpressure.py`。
如果通过，说明我们已经成功构建了一个抗饿死、支持并发竞争的物理资源协商系统。
