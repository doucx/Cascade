好的，已经完成了 Cascade 3.0 创世纪阶段（Stage 0）的所有物理原语定义，并搭建好了 `cascade-vm` 和 `cascade-compiler` 的包结构。现在我们将这些变更作为一个完整的逻辑单元进行提交。

## [COMMIT] feat(core): 实现 Cascade 3.0 物理原语与 Monorepo 包结构

### 用户需求
根据 Cascade 3.0 重构路线图，完成创世纪阶段（Stage 0）的实施，包括确立物理世界基本粒子的 Spec 定义，以及在 Monorepo 中创建并集成 `cascade-vm` 和 `cascade-compiler` 包。

### 评论
这是一个具有里程碑意义的提交。它标志着 Cascade 3.0 从理论设计正式进入代码实现阶段。通过在 `cascade-spec` 中确立的“令牌物理学”原语，我们为后续的编译器和物理引擎建立了一套统一、全对称的通信契约。

### 目标
1.  提交 `cascade-vm` 和 `cascade-compiler` 的包结构与配置文件。
2.  提交根目录 `pyproject.toml` 的集成配置。
3.  提交 `cascade-spec` 中关于物理节点、令牌、三连体、拓扑和资源的规范定义。

### 基本原理
我们严格遵循路线图中的“真理之源”原则。所有的物理原语都是纯粹的数据类，确保了系统底层定义的稳定性。包结构的建立遵循 PEP 561 规范，确保了在 Monorepo 环境下的类型安全和开发效率。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/vm #comp/compiler #concept/physics #scope/core #ai/instruct #task/domain/core #task/object/genesis #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交创世纪阶段的全部变更

我们将所有涉及到的新包文件、Spec 定义以及根目录配置添加到暂存区并执行提交。

~~~~~act
git_add
pyproject.toml
packages/cascade-vm/pyproject.toml
packages/cascade-vm/src/cascade/__init__.py
packages/cascade-vm/src/cascade/py.typed
packages/cascade-vm/src/cascade/vm/__init__.py
packages/cascade-compiler/pyproject.toml
packages/cascade-compiler/src/cascade/__init__.py
packages/cascade-compiler/src/cascade/py.typed
packages/cascade-compiler/src/cascade/compiler/__init__.py
packages/cascade-spec/src/cascade/spec/physics.py
packages/cascade-spec/src/cascade/spec/triad.py
packages/cascade-spec/src/cascade/spec/topology.py
packages/cascade-spec/src/cascade/spec/resources.py
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): implement Cascade 3.0 physics primitives and package structure

This commit establishes the foundation for the Cascade 3.0 "Fully Symmetric
Computational Physics Field" as outlined in the roadmap.

Core Changes:
1.  **Monorepo Integration**: Created `cascade-vm` (physics engine) and
    `cascade-compiler` (graph expander) packages, integrating them into the
    root workspace (uv, hatch, pyright).
2.  **Physics Primitives**: Defined the fundamental entities in `cascade-spec`:
    - `Token`: Added payload, tagging, and trace metadata for observability.
    - `Nodes`: Implemented `PhysicsDataNode` and `PhysicsFuncNode` as base types.
    - `Triad Structure`: Defined `BleachNode`, `WorkerNode`, and `StainNode`
      to decouple business logic from context.
    - `Topology`: Implemented `Channel` with spectral tag filtering and the
      `BipartiteGraph` container.
    - `Resources`: Added `ResourceSlot` for topological back-pressure.

This marks the successful completion of Stage 0 (Genesis).
~~~~~

### 下一步建议

我们已经确立了物理世界的“宪法”。接下来的重点是赋予这个世界以动力。

我建议我们进入 **阶段 1：反应堆点火 (Reactor Ignition)**：
1.  **任务 1.1：内存模型实现**：在 `cascade-vm` 中实现 `VolatileMemory`，负责管理 `DataNode` 中令牌的 `put/take` 行为。
2.  **任务 1.2：反应堆核心循环**：实现 `Reactor.step()`，让物理引擎能够根据“全准入激发”定律自动运转。

如果您准备好了，我们可以开始任务 1.1 的 TDD 过程。
