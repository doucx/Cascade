To proceed with Phase 1 of the Dyad Architecture Refactoring, I will enforce the trace tunneling contract by making the `trace` field mandatory in `ComputeRequest`. This ensures that context metadata is explicitly preserved across the compute boundary.

## [WIP] refactor(spec): enforce Trace propagation in ComputeRequest

### 用户需求
实施“二元体架构重构 (Dyad Architecture Refactoring)”的 Phase 1。
核心目标是确保计算协议支持上下文（Trace）的“隧道传输”，使元数据能够跟随数据穿越异步计算边界。

### 评论
这是一个关键的基础设施变更。虽然代码改动很小（仅仅移除一个默认值），但它在协议层面确立了“Trace 必须被传递”的强契约。这消除了开发者（或未来的 IC 实现者）忘记转发 Trace 的可能性，直接支持了后续 Phase 2 中 Launcher 和 Lander 的无状态设计。

### 目标
1.  修改 `cascade-spec` 中的 `ComputeRequest` 契约，将 `trace` 字段从可选（带默认值）改为必须（无默认值）。
2.  确认 `cascade-vm` 中的计算服务实现已经支持 Trace 透传（经代码审查，已支持）。

### 基本原理
在二元体架构中，`Lander` 节点不再拥有独立的 Trace 输入端口，它必须完全依赖从计算结果（`result_token`）中恢复上下文。这意味着 Trace 必须像隧道一样穿过 Compute Service。
通过移除 `ComputeRequest` 中 `trace` 的默认值，我们强制所有发起计算的组件（如即将实现的 `Launcher` 和现有的 `Dispatcher`）必须显式地捕获并传递 Trace。这利用 Python 的类型检查和运行时参数校验来防止上下文丢失。

### 标签
#intent/refine #flow/ready #priority/high
#comp/interfaces #comp/runtime #scope/core
#task/domain/architecture #task/object/trace-tunneling #task/action/protocol-upgrade
#task/state/begin

---

### Script

#### Acts 1: Enforce Trace in ComputeRequest

我们修改 `contracts.py`，移除 `trace` 字段的 `default_factory`，使其成为必填项。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/contracts.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class ComputeRequest:
    code_hash: str
    input_refs: Dict[str, Ref]
    reply_to_nid: str
    trace: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class ComputeRequest:
    code_hash: str
    input_refs: Dict[str, Ref]
    reply_to_nid: str
    trace: Dict[str, Any]
~~~~~

### 下一步建议

协议基础已经夯实。接下来我们进入 Phase 2，开始定义和实现二元体的核心组件。

建议的步骤：
1.  在 `cascade-spec` 中定义 `LauncherSpec` 和 `LanderSpec`。
2.  在 `cascade-std` 中实现对应的 `standard_launcher` 和 `standard_lander` IC。
