生成 Quipu 计划以执行 Step 3.1。

## [WIP] feat: 定义 Dyad 架构所需的物理常量与命名规则

### 用户需求
实施 Dyad 架构重构的 Phase 3.1。需要更新 `cascade-spec` 和 `cascade-reflection` 包，定义新的物理节点前缀（Launcher, Lander, Result）以及相应的 ID 生成逻辑，为后续编译器重构奠定基础。

### 评论
这是重构的基础设施层。通过明确定义 `LAUNCH`, `LAND` 等常量和 ID 生成规则，我们正式确立了二元体架构的物理实体命名规范。这也标志着物理层从三联体向二元体的正式迁移开始。

### 目标
1.  在 `cascade-spec` 中更新 `NodePrefix` 常量，添加 `LAUNCH`, `LAND`, `RESULT`。
2.  在 `cascade-reflection` 中更新 `PhysicalIdGenerator`，添加 `launcher_node`, `lander_node`, `result_data` 的生成方法。

### 基本原理
为了支持 Dyad 架构，我们需要一套新的物理节点标识符。
*   `Launcher` (发射器) 替代 `Bleacher` + `Worker` (前半部分)。
*   `Lander` (着陆器) 替代 `Stainer`。
*   `Result` (结果数据节点) 替代 `D_worker_out`，作为异步计算结果的存放地。
使用统一的常量和生成器可以确保编译器、链接器和运行时之间契约的一致性。

### 标签
#intent/architect #flow/ready #priority/high #comp/interfaces #comp/build #task/domain/compiler #task/object/dyad-infrastructure #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新物理节点常量

在 `NodePrefix` 中添加 Dyad 所需的新常量。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/constants.py
~~~~~
~~~~~python.old
    INGRESS = "ingress"  # Entry point (reserved)

    # Function Nodes (Transitions)
    BLEACH = "bleach"  # Triad: Pre-process
    WORKER = "worker"  # Triad: Execution
    STAIN = "stain"  # Triad: Post-process
    REQ = "req"  # Resource Requestor
~~~~~
~~~~~python.new
    INGRESS = "ingress"  # Entry point (reserved)
    RESULT = "result"  # Async result holder (DataNode)

    # Function Nodes (Transitions)
    LAUNCH = "launch"  # Dyad: Launcher (Prepare & Dispatch)
    LAND = "land"  # Dyad: Lander (Receive & Finalize)
    BLEACH = "bleach"  # Triad: Pre-process (Deprecated)
    WORKER = "worker"  # Triad: Execution (Deprecated)
    STAIN = "stain"  # Triad: Post-process (Deprecated)
    REQ = "req"  # Resource Requestor
~~~~~

#### Acts 2: 更新 ID 生成器

在 `PhysicalIdGenerator` 中添加生成 Launcher, Lander 和 Result 节点 ID 的方法。我们采用 `{logical_id}.{prefix}` 的命名模式，比旧的 `{logical_id}.data.out` 更简洁。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def bleach_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.BLEACH}"

    @staticmethod
    def worker_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.WORKER}"

    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.STAIN}"
~~~~~
~~~~~python.new
    @staticmethod
    def launcher_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.LAUNCH}"

    @staticmethod
    def lander_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.LAND}"

    @staticmethod
    def result_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.RESULT}"

    @staticmethod
    def bleach_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.BLEACH}"

    @staticmethod
    def worker_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.WORKER}"

    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.STAIN}"
~~~~~

### 下一步建议
完成基础定义后，我们可以进入 Step 3.2 和 3.3，开始修改编译器模型 `SubGraph` 并重写 `Expander` 逻辑，正式将拓扑生成逻辑切换到 Dyad 模式。建议先更新 `SubGraph` 模型，因为它是 `Expander` 的返回类型。
