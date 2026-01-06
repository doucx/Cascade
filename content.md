好的，我来分析并解决这个新的测试失败。

## [WIP] fix: 在测试工具中实现标量提升以对齐物理内核公理

### 错误分析
1.  **核心错误**: `ValueError: Ref mem://... missing 'scalar_value' metadata for Kernel access.`
2.  **位置**: 该错误发生在 `discrete_allocator` 内核函数中，这是一个**物理层**组件。
3.  **根本原因**: 根据“物理层无数据公理”，物理内核中的函数（如 `allocator`）**绝对禁止**执行 I/O 操作，包括对 `ObjectStore` 的 `get()` 调用。为了读取资源请求的数量（例如 `gpu=1`），它依赖于一种名为“**标量提升 (Scalar Hoisting)**”的机制：在创建 `Ref` 时，将小的标量值直接复制到 `Ref.meta` 字典中。这样，内核函数就可以无 I/O地读取该值。
4.  **漏洞所在**: 我们在上一步修复 `EventDrivenRunner.prime()` 时，正确地实现了“常量物质化”（将 `1` 转换为 `Ref`），但**遗漏了“标量提升”**这一关键步骤。`object_store.put(payload)` 创建了一个 `meta` 为空的 `Ref` 对象。当这个 `Ref` 到达 `discrete_allocator` 时，后者无法从中读取请求数量，从而导致断言失败并抛出异常。Reactor 捕获异常并中止，导致测试流程死锁并最终超时。

### 用户需求
修复测试基础设施，使其完全符合“引用即实体”和“物理内核无 I/O”的架构公理，从而让资源约束测试能够通过。

### 评论
这是一个非常好的、深度的架构验证失败。它证明了我们的物理层组件（`discrete_allocator`）正在正确地强制执行核心公理。失败点不在于业务逻辑，而在于我们的测试工具 (`EventDrivenRunner`) 尚未完全模拟最终 `Strategy` 层所需的所有行为。通过修复这个问题，我们的测试将变得更加高保真。

### 目标
1.  **更新 `ObjectStore` 协议**: 修改其 `put` 方法以接受可选的 `metadata` 参数。
2.  **更新 `InMemoryObjectStore` 实现**: 使其能够将传入的 `metadata` 附加到创建的 `Ref` 对象上。
3.  **更新 `EventDrivenRunner`**: 在其 `prime` 方法中实现标量提升逻辑。

### 基本原理
为了维护物理内核的纯粹性，所有内核函数操作所需的小型、关键数据都必须通过“标量提升”在进入物理图之前嵌入到 `Ref` 的元数据中。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #comp/vm #concept/physics #scope/core #ai/instruct
#task/domain/vm #task-object/scalar-hoisting #task-action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 `ObjectStore` 协议

首先，我们更新位于 `cascade-spec` 中的核心协议，以正式支持在创建引用时注入元数据。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/storage.py
~~~~~
~~~~~python.old
class ObjectStore(Protocol):
    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref: ...

    def get(self, ref: Ref) -> Any: ...
~~~~~
~~~~~python.new
class ObjectStore(Protocol):
    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref: ...

    def get(self, ref: Ref) -> Any: ...
~~~~~

#### Acts 2: 更新 `EventDrivenRunner` 以实现标量提升

现在，我们在测试工具的 `prime` 方法中添加标量提升逻辑。

> **注意**: 我将直接修改 `packages/cascade-vm/src/cascade/vm/harness.py` 文件，因为它在之前的步骤中已经存在。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    def prime(self):
        # Phase 3.2 - Constant Materialization
        # The runner, acting as the Strategy, scans the graph for any initial payloads
        # and converts them to Refs before priming the reactor.
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                payload = node.initial_payload
                if payload is not None and not isinstance(payload, Ref):
                    # Materialize the raw value into the object store
                    node.initial_payload = self.object_store.put(payload)

        self.reactor.prime(genesis_trace={"rid": self.run_id})
~~~~~
~~~~~python.new
    def prime(self):
        # Phase 3.2 - Constant Materialization & Scalar Hoisting
        # The runner, acting as the Strategy, scans the graph for any initial payloads
        # and converts them to Refs before priming the reactor.
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                payload = node.initial_payload
                if payload is not None and not isinstance(payload, Ref):
                    meta = {}
                    # Perform Scalar Hoisting for kernel-readable values
                    if isinstance(payload, (int, float, bool, str)) and len(str(payload)) < 256:
                        meta["scalar_value"] = payload
                    
                    # Materialize the raw value into the object store with metadata
                    node.initial_payload = self.object_store.put(payload, metadata=meta)

        self.reactor.prime(genesis_trace={"rid": self.run_id})
~~~~~

### 下一步建议
我们已经修复了测试工具链中的最后一个已知架构偏差。现在，所有的集成测试都应该能够正确地在新的、基于引用的、无 I/O 内核的架构下运行。

在测试通过后，我们可以自信地宣布 Phase 1 和 Phase 2 已经完成并得到验证。下一步，我们将正式开始 **Phase 3: 策略层重构**，构建生产环境下的 `CascadeVMStrategy`。
