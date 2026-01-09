好的，这是清理工作的计划。

由于我们在前面的步骤中使用了 `write_file` 完全重写了策略文件，代码层面的“废弃导入”已经随之被清理掉了。因此，本次清理工作的重心将放在**文档的一致性**上。我们需要更新 `.stitcher.yaml` 文件，以反映 `SubGraph`、`Builder` 和 `ResourcePrism` 的架构变更，并为新引入的 `ExpansionPolicy` 添加文档。

## [WIP] docs(compiler): 更新 Stitcher YAML 文档以反映架构变更

### 用户需求

根据架构路线图 4.2，进行代码清理和文档同步。主要任务是更新 `stitcher.yaml` 文件，使其与最新的代码结构（两阶段编译、新 `SubGraph` 结构、新 `ResourcePrism` 协议）保持一致。

### 评论

代码是事实，但文档是地图。现在的地图（YAML 文档）仍然描绘着旧的单阶段编译大陆，而代码已经迁移到了新的两阶段群岛。如果不更新这些元数据，未来的开发者（或 AI 代理）在查阅 Stitcher 文档时将会产生严重的认知偏差。这是一次必要的“制图学”更新。

### 目标

1.  更新 `backend/expander.stitcher.yaml`：详细描述 `SubGraph` 中新增的 `constants`, `resources`, `controls` 容器字段。
2.  更新 `backend/builder.stitcher.yaml`：反映 `Builder` 的两阶段编译流程（Materialization -> Wiring）。
3.  更新 `backend/wiring/prism.stitcher.yaml`：废除 `connect_task` 描述，新增 `expand_task` 和 `wire_task` 的描述。
4.  创建 `backend/expansion/protocol.stitcher.yaml`：为新的 `ExpansionPolicy` 协议添加文档。

### 基本原理

Stitcher YAML 文件是 Cascade 项目中用于生成 API 文档和辅助 AI 理解代码结构的单一事实来源。保持其与代码库的同步是维护项目长期可读性的关键。

### 标签

#intent/tune #flow/ready #priority/medium #task/domain/compiler #task/object/documentation #task/action/update #task/state/end #scope/docs #ai/instruct

---

### Script

#### Acts 1: 更新 `expander.stitcher.yaml`

更新 `SubGraph` 的描述，解释其作为完整组件容器的新角色。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.stitcher.yaml
~~~~~
~~~~~yaml
"Expander": "The 'Big Bang' engine. \nIt expands a single logical NodeIR into a physical\
  \ Triad SubGraph.\n\nTriad Structure:\n    F_pre (Bleacher) --> D_worker_in -->\
  \ F_worker --> D_worker_out --> F_post (Stainer)\n           |                 \
  \                                             ^\n           +--------------------->\
  \ D_trace -------------------------------+"
"Expander.expand_node": |-
  Expands a NodeIR into a physical Triad.
"SubGraph": |-
  A comprehensive container for all physical nodes representing a single logical task.
  
  It acts as the "inventory" for the task's physical manifestation, containing:
  1. The Core Triad (Bleacher, Worker, Stainer) created by the Expander.
  2. Auxiliary Components (Constants, Requestors, Glue Logic) created by ExpansionPolicies.
  
  WiringPolicies use this container to look up nodes and establish connections.
"SubGraph.constants": |-
  Registry of parameter constant nodes (D_const), indexed by argument name.
"SubGraph.controls": |-
  Registry of control flow nodes (D_seq, D_cond, D_egress, D_pulse), indexed by role.
"SubGraph.resources": |-
  Registry of resource-related nodes (List[D_amt, F_req, D_gnt]), indexed by resource name.
~~~~~

#### Acts 2: 更新 `builder.stitcher.yaml`

描述新的两阶段构建过程。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.stitcher.yaml
~~~~~
~~~~~yaml
"Builder": |-
  The master assembler for the physical graph.
  
  It orchestrates the compilation process in two distinct phases:
  
  1. **Phase 1: Materialization (Expansion)**
     - The `Expander` creates the core Triad for each task.
     - `ExpansionPolicies` create all auxiliary nodes (constants, resource requestors, etc.).
     - No connections are allowed between subgraphs in this phase.
  
  2. **Phase 2: Wiring**
     - The `WiringHarness` is locked to prevent new node creation.
     - `WiringPolicies` connect the pre-existing nodes within and between subgraphs.
"Builder.build": |-
  Executes the compilation pipeline: Setup -> Materialization -> Wiring -> Validation -> Manifest Generation.
~~~~~

#### Acts 3: 更新 `wiring/prism.stitcher.yaml`

反映 `ResourcePrism` 协议的拆分。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.stitcher.yaml
~~~~~
~~~~~yaml
"ResourcePrism": |-
  A Prism refracts a high-level Resource Definition into a complex physical topology.
  It encapsulates the knowledge of how to wire a specific type of resource.
  
  It follows the two-phase compilation model:
  - expand_task: Creates the physical components.
  - wire_task: Connects the components to the grid.
"ResourcePrism.ensure_globals": |-
  Create the global infrastructure for this resource (e.g., Allocator, Ledger).
  This may be called multiple times for different resources of the same type.
"ResourcePrism.expand_task": |-
  Phase 1: Materialization.
  Creates the physical nodes required for a task to consume this resource
  (e.g., Requestor, Amount Constant).
  MUST NOT create any connections.
"ResourcePrism.wire_task": |-
  Phase 2: Wiring.
  Connects the nodes created in Phase 1 to the task's triad and the
  global resource infrastructure.
  MUST NOT create any new nodes.
~~~~~

#### Acts 4: 创建 `expansion/protocol.stitcher.yaml`

为新的 `ExpansionPolicy` 添加文档。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/protocol.stitcher.yaml
~~~~~
~~~~~yaml
"ExpansionPolicy": |-
  Protocol for a Materialization strategy.
  
  Each policy is responsible for creating a specific category of auxiliary physical nodes
  (e.g., constants, control flow gates) and registering them into the SubGraph.
"ExpansionPolicy.expand": |-
  Executes the expansion logic for a single logical node.
  
  Args:
      ctx: The expansion context.
      node_ir: The logical node definition.
      subgraph: The container to populate with new nodes.
      
  Constraints:
      - MUST create nodes using `ctx.wire.add_node()`.
      - MUST register created nodes into `subgraph.nodes` and specialized buckets (e.g. `subgraph.constants`).
      - MUST NOT create any channels/connections.
~~~~~

### 下一步建议

清理工作已完成。文档现在准确反映了代码库的最新架构状态。
我们已经完成了从方案二（扩展流水线）的全部实施工作。

至此，`Expander` 与 `WiringPolicy` 的架构重构任务圆满结束。编译器后端现在拥有了一个职责清晰、扩展性强、且具有运行时防腐保障的架构。您可以安心地在此基础上继续开发新的特性或进行其他重构了。
