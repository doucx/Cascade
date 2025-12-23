太棒了。测试的全面通过标志着我们成功跨越了架构重构中最困难的一个关口：**从“基于实例的图”演进为“基于模板的图”**。

这不仅是性能上的优化（通过 Interning 减少了内存占用），更是语义上的飞跃。现在，Cascade 终于拥有了稳定的、能够跨越不同任务调用甚至不同运行周期而保持一致的“结构身份”。这是实现 Hashlife 模型和全局计算缓存的绝对前提。

我将生成一个 `[COMMIT]` 计划，将这些具有里程碑意义的改动永久记录下来。

## [COMMIT] feat(graph): Implement node interning and stable structural identifiers

### 用户需求
完成路线图第二阶段 2.1 节，实现全局/会话级的节点注册表（Node Interning），并确保计算图的每个节点都由一个稳定的结构化 ID（哈希）唯一标识。

### 评论
这是一次深度的架构演进。我们不仅实现了一个用于节点复用的 `NodeRegistry`，还通过引入 `ShallowHasher` 和 `instance_map` 机制，彻底解决了节点“结构身份”与“调用实例”的分离。虽然过程中面临了 ID 语义转换带来的巨大集成挑战，但目前的实现非常稳固，且为后续的“骨架-血肉分离（Skeleton-Flesh Split）”铺平了道路。

### 目标
1.  提交 `NodeRegistry`、`ShallowHasher` 以及重构后的 `GraphBuilder` 核心代码。
2.  提交所有为适配新的 ID 模型而进行的运行时组件（`FlowManager`, `Resolvers`, `Engine`）的更新。
3.  提交已同步更新的 SDK 工具（`visualize`, `preview`）及其测试套件。

### 基本原理
通过将 `Node.id` 锁定为节点的浅层结构哈希，我们使计算图在逻辑上变得可复用。引入 `instance_map` 是本次重构的点睛之笔，它充当了临时实例与持久模板之间的翻译层，使得现有的、基于实例构建的复杂逻辑（如路由剪枝）在不破坏向后兼容性的前提下，依然能在新的规范化模型中正确运行。

### 标签
#intent/architect #intent/refine #flow/ready #priority/high 
#comp/graph #comp/engine #comp/sdk #comp/tests
#concept/interning #concept/hashing #concept/state
#task/domain/graph #task/object/node-interning #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交节点复用与稳定标识符架构

我们将所有核心模块、运行时组件、SDK 工具以及对应的测试文件添加到暂存区。这是一个涵盖了模型层、逻辑层和展示层的内聚提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/engine.py
packages/cascade-engine/src/cascade/runtime/flow.py
packages/cascade-engine/src/cascade/runtime/processor.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
packages/cascade-engine/src/cascade/runtime/strategies.py
packages/cascade-graph/src/cascade/graph/__init__.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/hashing.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/registry.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-sdk/src/cascade/tools/preview.py
packages/cascade-sdk/src/cascade/tools/visualize.py
tests/engine/adapters/solvers/test_csp.py
tests/engine/adapters/solvers/test_native.py
tests/engine/graph/test_build.py
tests/engine/graph/test_build_tco.py
tests/engine/graph/test_serialize.py
tests/engine/runtime/test_engine_core.py
tests/engine/runtime/test_flow_manager.py
tests/engine/runtime/test_router_pruning.py
tests/sdk/integration/test_state_backends.py
tests/sdk/tools/test_preview.py
tests/sdk/tools/test_visualize.py
tests/spec/spec/test_constraint.py
tests/spec/spec/test_routing.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(graph): Implement node interning and stable structural identifiers

This milestone marks the full implementation of Node Interning, shifting Cascade's execution model from transient instance-based graphs to reusable template-based graphs.

Key Innovations:
1. **NodeRegistry & ShallowHasher**: Introduced a session-level registry that uses structural hashing to ensure any structurally identical node (same task, policies, and literal inputs) is represented by a single, unique Node object.
2. **Skeleton-Flesh Separation**: Decoupled the Node's stable identity (structural ID) from its runtime invocation (LazyResult UUID).
3. **Instance Mapping**: Implemented 'instance_map' to bridge the gap between instance-aware logic (like Router pruning) and the new canonical graph model, ensuring full consistency across resolvers and state backends.
4. **Resilient Runtime**: Updated FlowManager, ArgumentResolver, and ConstraintResolver to correctly handle ID translation, resolving complex integration issues with dynamic routing and resource scheduling.

This refactor provides the mandatory foundation for the upcoming "Universal Graph Cache" and Hashlife-inspired performance optimizations.
~~~~~

### 下一步建议

随着 2.1 节（节点复用）的正式闭环，我们下一步将进入 **2.2 分离的数据提取流程 (Separated Data Extraction)**。

虽然我们在 `GraphBuilder` 中已经初步引入了 `_data_buffer`，但当前的提取逻辑仍然分散在节点创建过程中。下一阶段的目标是：
- **纯化提取逻辑**：实现一个独立的 `DataExtractor` 类或优化 `Builder`，使其能以更系统、更高效的方式从复杂的嵌套结构中剥离“血肉（字面量数据）”。
- **增强水合（Hydration）**：优化 `ArgumentResolver` 的性能，使其在利用 `SlotRef` 从 `DataTuple` 还原参数时达到零开销级别。

如果你准备好了，我们可以开始 2.2 节的详细方案设计。
