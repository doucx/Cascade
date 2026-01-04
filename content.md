好的，底层的全息投影协议基础设施已经搭建完毕，我们可以将其作为一个完整的逻辑单元提交。

这标志着 Cascade 3.0 正式告别了非结构化的 trace 数据，转向了标准化的、工业级的遥测协议。

## [COMMIT] feat(obs): Implement EventIR protocol and Holographic Telemetry infrastructure

### 用户需求
完成 [Cascade 3.0 实施路线图] 的前三个阶段：
1.  **立法**: 定义 `EventIR` 核心 Schema。
2.  **翻译**: 实现逻辑层对 IR 的水合 (Hydration) 能力。
3.  **发射**: 改造物理原语使其能够产生和中转 IR。

### 评论
这个提交确立了物理层（VM）与逻辑层（Engine）之间的解耦契约。通过 `EventIR`，我们实现了“全息投影”愿景的第一步：让物理世界的事件以标准的、扁平的格式流向逻辑世界。这不仅解决了之前的测试失败问题，还为未来的分布式可观测性铺平了道路。

### 目标
1.  提交 `cascade-spec` 中关于 `EventIR`, `EventType`, `EventState` 的定义。
2.  提交 `cascade-engine` 中 `Event.from_ir` 的水合逻辑及其总线增强。
3.  提交 `cascade-std` 中 `Bleacher`, `Stainer`, `Observer` 的发射源改造。
4.  提交 `cascade-vm` 中 `EventDrivenRunner` 对新事件流架构的适配。

### 基本原理
我们通过在 `spec` 层定义数据契约，在 `engine` 层定义适配器，在 `std` 层应用契约，建立了一套完整的数据流链路。特别是 `EventDrivenRunner` 的改造，证明了这套架构不仅能满足生产环境，还能完美兼容并增强现有的 TDD 测试套件。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/engine #comp/std #comp/vm #concept/observability #scope/core #ai/instruct #task/domain/observability #task/object/holographic-telemetry #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交全息投影协议基础设施

我们将所有相关的修改添加到暂存区并创建一个详尽的提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/observability.py
packages/cascade-spec/src/cascade/spec/__init__.py
packages/cascade-spec/tests/unit/test_observability.py
packages/cascade-engine/src/cascade/runtime/events.py
packages/cascade-engine/src/cascade/runtime/event_bus.py
packages/cascade-engine/tests/unit/test_event_translation.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-std/src/cascade/std/triad/observer.py
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(obs): implement EventIR protocol and holographic telemetry

This commit establishes the "Holographic Projection" protocol for Cascade 3.0,
decoupling the physical VM from the logical Engine through a standardized
Intermediate Representation (EventIR).

Key architectural changes:
1.  **Specification (cascade-spec)**: Introduced `EventIR` (JSON-serializable 
    telemetry schema), `EventType`, and `EventState` as the system's 
    observability axioms.
2.  **Hydration (cascade-engine)**: Implemented `Event.from_ir` and 
    `EventBus.publish_ir` to translate raw physical signals into rich, 
    semantically aware Event objects.
3.  **Physical Emitters (cascade-std)**: Refactored `Bleacher` and `Stainer` 
    to emit structured IR packets. The `Observer` is now a "Dumb Relay" that 
    blindly forwards IR payloads to the global event bus.
4.  **Harness Update (cascade-vm)**: Upgraded `EventDrivenRunner` to use 
    the system `EventBus` as its primary observability source, ensuring 
    testing infrastructure eats its own dogfood.

This infrastructure roots observability in the physical Locality Principle, 
where events carry their own context as tokens flow through the graph.
~~~~~

### 下一步建议
我们已经锁定了基础设施。下一步我们将启动 **Phase 4: 上下文注入 (The Context Injection)**，按照我们之前的战略分析，通过“创世注入”和“迹流传播”机制，让 `run_id` 自动在物理场中流动，从而填充 `EventIR.ctx` 字段。
