好的，既然 TCO 快速通道已经通过了深度递归和相互递归的测试验证，这意味着我们本次重构的最核心逻辑已经稳固。

我将生成一个 `[COMMIT]` 计划，将这次涉及“模板-实例分离”架构重构的所有核心变更作为一个逻辑单元提交。

## [COMMIT] refactor(core): Implement Template-Instance Separation for Hashlife-ready model

### 用户需求
完成 Cascade 架构重构路线图的第二、三、四步。将计算图的“骨架”（拓扑）与“血肉”（数据）彻底分离，并在引擎层实现零开销 TCO 优化。

### 评论
这是 Cascade 演进史上的一个里程碑。通过引入 `SlotRef` 绑定和规范化构建器，我们实现了“一次编译，多次执行”的模式。这不仅消除了递归任务的内存增长隐患，还为未来实现 Hashlife 风格的全局图结构缓存奠定了坚实的底层协议基础。

### 目标
1.  提交 `cascade-spec` 中新增的 `binding.py`（定义了 `SlotRef` 和 `Constant`）。
2.  提交 `cascade-graph` 中重构的 `Node` 模型、`GraphBuilder`、`StructuralHasher` 和序列化逻辑。
3.  提交 `cascade-engine` 中重构的 `ArgumentResolver`（实现数据注入）和 `GraphExecutionStrategy`（实现 TCO 快速通道）。
4.  确保所有 217 个测试用例（包括新增的 TCO 测试）全部通过。

### 基本原理
本次重构的核心是建立了“骨架”与“血肉”的分离契约：
*   **骨架**: 由 `GraphBuilder` 生成，包含通过 `NodeRegistry` 规范化的 `Node` 实例，节点仅持有指向数据槽的 `SlotRef`。
*   **血肉**: 由 `GraphBuilder` 提取出的扁平化 `data_tuple`。
*   **连接**: 引擎在执行阶段，通过 `ArgumentResolver` 动态地将 `SlotRef` 指向的索引与 `data_tuple` 中的值结合，完成“水合（Hydration）”。

这一分离使得引擎可以安全地缓存 `ExecutionPlan`，并在识别到 TCO 循环时跳过昂贵的求解过程，仅执行轻量级的数据提取。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/engine #comp/graph #comp/spec #concept/state #scope/core 
#ai/instruct 
#task/domain/core #task/object/template-instance-separation #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交架构重构核心代码

我们将所有涉及本次“结构与数据分离”重构的文件添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/binding.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-graph/src/cascade/graph/hashing.py
packages/cascade-engine/src/cascade/runtime/strategies.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Implement Template-Instance Separation for Hashlife-ready model

This commit implements the "The Great Split" across the core packages, decoupling graph topology (Skeleton) from runtime data (Flesh).

Key Structural Changes:
- Spec: Introduced `SlotRef` and `Constant` bindings as the standard for node inputs.
- Graph: Refactored `Node` to store `input_bindings` instead of literal values.
- Builder: `GraphBuilder` now extracts literal data into a linear `data_tuple` and returns canonical nodes via `NodeRegistry` interning.
- Serialization: Updated `serialize.py` to handle binding-based graph representations.

Engine & Runtime Improvements:
- Resolvers: `ArgumentResolver` now performs dynamic "Hydration" by combining bindings with the `data_tuple` at runtime.
- TCO Optimization: Implemented Zero-Overhead fast path in `GraphExecutionStrategy`. The engine now reuses cached `ExecutionPlan` for recognized recursive cycles, achieving O(1) scheduling overhead for long-running Agent loops.

This architecture enables future global structure caching and provides a robust foundation for high-performance distributed execution.
~~~~~

### 下一步建议

恭喜！我们已经完成了这一宏大路线图中最具挑战性的部分。Cascade 现在运行在一个全新的、极具扩展性的引擎核心之上。

接下来的建议：
1.  **性能基准测试**: 我们可以针对深层递归任务进行一次性能对比测试，以量化 TCO 快速通道带来的提升。
2.  **文档更新**: 需要更新 `指导原则：计算图的 Hashlife 模型.md` 及其相关文档，记录这一阶段的正式实现细节。
3.  **探索阶段四**: 既然底层已经支持“模板+数据”，我们可以开始考虑如何将其应用到分布式执行场景中，实现真正的“算力网格”。
