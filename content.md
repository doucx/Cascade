好的，第一阶段“奠定基础”的所有重构工作已经顺利完成，并且所有相关的单元测试与集成测试都已经通过，确保了系统在新的“主权端口”模型下的稳定性。

我将生成一个 `[COMMIT]` 计划，将这些涉及 Spec、VM、Compiler 和 Std 的重大架构变更作为一个完整的逻辑单元提交。

## [COMMIT] refactor(core): 废弃 Tag 路由，实现主权端口模型 (Phase 1)

### 用户需求
完成“Cascade 3.1 架构演进路线图”第一阶段：
- 从协议层彻底移除 `tag` 和 `tag_filter`。
- 简化 Reactor 发射逻辑。
- 重构编译器资源分配布线，采用专用物理通道。
- 更新标准库 IC 和测试，适配多端口输出与 Trace 路由。

### 评论
这是一次具有里程碑意义的重构。通过移除隐式的 Tag 机制，我们消除了计算图中长期存在的语义歧义。现在的拓扑结构是“诚实”的：任何连接都代表了确定的能量流动路径。特别是在资源系统中，从“广播+过滤”到“点对点专用通道”的转变，不仅提高了性能，更极大增强了系统在极端负载下的可观测性和鲁棒性。

### 目标
- 创建一个包含协议变更、编译器重构、VM 简化及标准库适配的 Git 提交。

### 基本原理
**主权端口原则**：将路由决策权从“智能通道”收回到“主权节点”。这不仅净化了物理层法律（Reactor 不再需要进行光谱过滤），也为未来的 JIT 优化提供了更清晰的拓扑信息。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/vm #comp/compiler #comp/std #concept/topology #scope/core #ai/instruct #task/domain/core #task/object/topology #task/action/sovereignty #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交 Phase 1 的所有架构变更

我们将把所有包中的相关变更添加到暂存区并创建提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/topology.py
packages/cascade-spec/src/cascade/spec/physics.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring.py
packages/cascade-compiler/src/cascade/compiler/utils/visualizer.py
packages/cascade-compiler/tests/integration/test_branching.py
packages/cascade-compiler/tests/unit/utils/test_visualizer.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-std/src/cascade/std/resource/discrete.py
packages/cascade-std/src/cascade/std/resource/continuous.py
packages/cascade-std/src/cascade/std/resource/requestor.py
packages/cascade-std/tests/unit/triad/test_bleacher.py
packages/cascade-std/tests/unit/triad/test_observer.py
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Deprecate tag-based routing in favor of Sovereign Ports (Phase 1)

This major architectural refactoring implements the first phase of the Cascade 3.1 
"Sovereignty Edition" roadmap, moving from implicit metadata filtering to explicit 
topological routing.

Key Changes:
1. **Spec & Physics**: Removed 'tag' field from Token and 'tag_filter' from Channel. 
   Physics is now strictly based on connectivity and port names.
2. **Reactor**: Simplified emission logic. The Reactor no longer performs spectral 
   filtering, making the core loop more efficient and purely deterministic.
3. **Compiler (Manifold Routing)**: Enhanced the Builder to support dynamic port 
   generation. Resource grants are now routed via dedicated, point-to-point physical 
   channels instead of a shared tagged buffer.
4. **Standard ICs (Sovereign Agents)**: 
   - Updated 'discrete_allocator' and 'resource_requestor' to use Trace-based ID 
     injection and dynamic port routing.
   - Updated 'standard_bleacher' to establish canonical Trace identity for every task.
5. **Testing**: Refactored the test suite to align with the manifold routing model, 
   ensuring high-fidelity validation of the new topological axioms.

This commit establishes 'Topological Honesty': the visual graph representation now 
perfectly matches the execution logic, fulfilling the vision of 'Logic as Topology'.
~~~~~

### 下一步建议
我们已经稳固了基础，现在可以进入 **第二阶段：控制流重构 (Control Flow)**。
接下来的核心任务是：
1.  **[Compiler] Expander 扩展 Stainer 端口**: 修改 `Expander`，使其根据 `NodeIR` 的分支信息（如 success/error）动态生成 `StainNode` 的输出端口。
2.  **[Compiler] Builder 实现 Stainer 布线**: 更新 `Builder`，将 `Stainer` 的不同端口（`output_default`, `output_error`）物理连接到不同的下游节点。
3.  **[Std] 重构 `standard_stainer`**: 实现 `Stainer` 内部的路由逻辑，使其根据结果类型将 Token 投射到正确的端口。

如果你准备好了，我们可以开始 Phase 2。
