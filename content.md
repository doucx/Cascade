我们已经完成了 Cascade v3.1 Ref-Based 架构最核心的基础设施建设。现在，我们将这些变更作为一个完整的逻辑单元进行提交，锁定当前的架构基线。

## [COMMIT] feat: 实现 Ref-Based 架构 v3.1 核心协议与基础组件

### 用户需求
完成 Cascade v3.1 架构演进的第一阶段至第三阶段核心组件，确立“控制流（物理引用）”与“数据流（对象实体）”的解耦模型。

### 评论
这是 Cascade 历史上的一次重大架构跃迁。通过引入 `Ref` 和 `ObjectStore`，我们从根本上消除了 Reactor 对业务数据的依赖，解决了由于搬运大数据载荷导致的性能瓶颈，并为未来的分布式执行铺平了道路。

### 目标
1.  提交 `Ref`, `ObjectStore`, `ComputeDelegate` 等核心协议定义。
2.  提交 `InMemoryObjectStore` 实现，确立 `mem://` 存储规范。
3.  提交 `PhysicsKernel`（同步内核）和 `LocalComputeDelegate`（异步执行器）实现。
4.  确保所有新组件均配备完备的单元测试。

### 基本原理
本提交通过物化“引用（Ref）”这一概念，实现了物理执行层与用户计算层的完全隔离。`PhysicsKernel` 专注于处理拓扑演化（同步、无 IO），而 `LocalComputeDelegate` 负责繁重的计算任务（异步、数据感知）。这种“两极分化”的设计在保证极致正确性的同时，预留了最大的性能优化空间。

### 标签
#intent/architect #flow/ready #priority/critical #comp/interfaces #comp/runtime #comp/vm #concept/storage #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/ref-architecture #task/action/foundation-commit #task/state/end

---

### Script

#### Acts 1: 提交 v3.1 核心定义与组件

我们将所有的接口定义、存储实现、执行器实现以及配套测试添加到 Git 暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/physical/object.py
packages/cascade-spec/src/cascade/spec/runtime/storage.py
packages/cascade-spec/src/cascade/spec/runtime/compute.py
packages/cascade-spec/src/cascade/spec/__init__.py
packages/cascade-spec/src/cascade/spec/runtime/__init__.py
packages/cascade-runtime/src/cascade/runtime/storage/memory.py
packages/cascade-runtime/src/cascade/runtime/storage/__init__.py
packages/cascade-vm/src/cascade/vm/compute/local.py
packages/cascade-vm/src/cascade/vm/compute/__init__.py
packages/cascade-vm/src/cascade/vm/kernel/core.py
packages/cascade-vm/src/cascade/vm/kernel/__init__.py
packages/cascade-vm/tests/unit/test_compute_delegate.py
packages/cascade-vm/tests/unit/test_physics_kernel.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat: Implement Ref-Based Architecture v3.1 core protocols and components

This commit establishes the foundational infrastructure for the 'Reference-Based'
architecture, strictly decoupling the Physics Layer (Control Plane) from the 
Object Plane (Data Plane).

Key additions:
1. Physical References (Ref): Defined in cascade-spec as lightweight pointers 
   carrying URI and hoisted metadata.
2. ObjectStore Protocol: Defined the standard for data persistence and 
   dereferencing, including 'peek' for IO-free metadata access.
3. InMemoryObjectStore: A reference implementation of ObjectStore in runtime.
4. PhysicsKernel: A high-performance synchronous execution unit for kernel ICs 
   that operates exclusively on Refs.
5. LocalComputeDelegate: An asynchronous worker bridge that handles data 
   dereferencing, code execution, and result materialization.

This structure allows the Reactor to drive graph evolution at nanosecond speeds 
without being blocked by user payload weights or IO latency.
~~~~~

### 下一步建议
我们已经锁定了 v3.1 的地基。接下来的任务是：
1.  **Phase 4: StdLib Synchronization**: 重写 `cascade-std` 中的 `Bleacher` 和 `Stainer`，使其适配同步的 `PhysicsKernel` 和 `Ref` 模型。
2.  **Phase 5: Reactor Evolution**: 改造 `Reactor` 以支持“断连式异步桥接”和双循环机制。

建议从 **Phase 4** 开始，先准备好内核所需的“零件”。
