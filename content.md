# [WIP] fix: 修复 PIDL 实现中的 Optional 类型访问和协议覆盖错误

### 错误分析

1.  **Optional 成员访问错误 (`reportOptionalMemberAccess`)**:
    *   在 Kernel 实现中（如 `discrete_allocator`），我们直接访问了输入 Token 的属性（如 `.payload`）。
    *   但在 Spec 的 `IO` 协议中，输入端口被定义为 `Optional[Token]`（反映了运行时可能为空的事实）。
    *   Pyright 正确地指出，在访问属性前必须处理 `None` 的情况。

2.  **协议覆盖错误 (`reportIncompatibleVariableOverride`)**:
    *   `PhysicsSpec` 基类定义了一个空的 `IO` 协议。
    *   子类 Spec 重新定义了同名的 `IO` 协议。
    *   Pyright 认为这是不兼容的类属性覆盖。鉴于基类的 `IO` 仅用于文档目的，可以直接移除以消除冲突。

### 用户需求

消除所有剩余的 Pyright 类型检查错误，确保 Kernel 代码在类型安全的前提下运行。

### 评论

通过在 Kernel 代码中显式添加 `assert token is not None`，我们将运行时的隐式假设（“核心输入必须存在”）转化为了显式的代码契约。这不仅修复了类型错误，也增强了系统的故障诊断能力——如果输入意外丢失，系统将立即抛出断言错误，而不是后续的空指针异常。

### 目标

1.  移除 `PhysicsSpec` 中的 `IO` 定义，解决继承冲突。
2.  在 `discrete.py` 和 `requestor.py` 中添加断言，确保所有必需的输入 Token 在使用前都经过非空检查。

### 基本原理

*   **移除基类定义**: 基类的 `IO` 协议没有实际逻辑作用，移除它能最干净地解决 Override 冲突。
*   **运行时断言**: 对于必须存在的输入（如 Allocator 的 Ledger），使用 `assert` 是声明前提条件的标准 Python 方式，它同时也能作为类型守卫（Type Guard）告知静态分析器后续变量不为 `None`。

### 标签

#intent/fix #flow/ready #priority/high #comp/std #comp/spec #concept/typing #scope/core #ai/instruct #task/domain/typing #task/object/pyright-errors #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 移除基类 `PhysicsSpec` 中的 `IO` 定义

解决 `reportIncompatibleVariableOverride` 错误。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics/spec.py
~~~~~
~~~~~python.old
class PhysicsSpec(metaclass=PhysicsSpecMeta):
    input_ports: ClassVar[Dict[str, PortDef]]
    output_ports: ClassVar[Dict[str, PortDef]]

    class IO(Protocol):
        """
        Protocol stub for Kernel function type hinting.

        In the future, `@implements(Spec)` will use this Protocol to enforce
        that the kernel function accepts an 'io' object with attributes matching
        the Spec's ports.
        """

        pass
~~~~~
~~~~~python.new
class PhysicsSpec(metaclass=PhysicsSpecMeta):
    input_ports: ClassVar[Dict[str, PortDef]]
    output_ports: ClassVar[Dict[str, PortDef]]
~~~~~

#### Acts 2: 修复 `discrete.py` 中的 Optional 访问

在访问 `payload` 或 `trace` 之前，断言 Token 存在。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
@implements(DiscreteAllocatorSpec)
def discrete_allocator(
    io: DiscreteAllocatorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    ledger_data = ledger_token.payload

    # Extract Ledger (Handle Ref if ledger itself is ref-based in future, currently payload is obj)
    # For now ledger payload is passed as-is (PhysicsDataNode initial_payload)
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = io.req_in
    req_amount = int(_extract_scalar(req_token.payload))

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount

        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            # Use dynamic output map
            io.grants[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing
            io.gnt_out = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Park
        io.req_parked = req_token

    io.ledger_out = Token(payload=ledger)


@implements(DiscreteReclaimerSpec)
def discrete_reclaimer(
    io: DiscreteReclaimerSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = io.rel_in
    release_amount = int(_extract_scalar(rel_token.payload))

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    io.ledger_out = Token(payload=ledger)
    # Emit wake-up signal
    io.signal_out = Token(payload=None, trace=rel_token.trace)
~~~~~
~~~~~python.new
@implements(DiscreteAllocatorSpec)
def discrete_allocator(
    io: DiscreteAllocatorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    assert ledger_token is not None, "Ledger token missing"
    ledger_data = ledger_token.payload

    # Extract Ledger (Handle Ref if ledger itself is ref-based in future, currently payload is obj)
    # For now ledger payload is passed as-is (PhysicsDataNode initial_payload)
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = io.req_in
    assert req_token is not None, "Request token missing"
    req_amount = int(_extract_scalar(req_token.payload))

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount

        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            # Use dynamic output map
            io.grants[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing
            io.gnt_out = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Park
        io.req_parked = req_token

    io.ledger_out = Token(payload=ledger)


@implements(DiscreteReclaimerSpec)
def discrete_reclaimer(
    io: DiscreteReclaimerSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    assert ledger_token is not None, "Ledger token missing"
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = io.rel_in
    assert rel_token is not None, "Release token missing"
    release_amount = int(_extract_scalar(rel_token.payload))

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    io.ledger_out = Token(payload=ledger)
    # Emit wake-up signal
    io.signal_out = Token(payload=None, trace=rel_token.trace)
~~~~~

#### Acts 3: 修复 `requestor.py` 中的 Optional 访问

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/requestor.py
~~~~~
~~~~~python.old
@implements(ResourceRequestorSpec)
def resource_requestor(
    io: ResourceRequestorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    amount_token = io.amount

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    io.req_out = Token(payload=amount_token.payload, trace=trace)
~~~~~
~~~~~python.new
@implements(ResourceRequestorSpec)
def resource_requestor(
    io: ResourceRequestorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    amount_token = io.amount
    assert amount_token is not None, "Amount token missing"

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    io.req_out = Token(payload=amount_token.payload, trace=trace)
~~~~~

### 下一步建议

再次运行 `pyright`，应该可以看到所有错误都已清零。

```bash
pyright packages/cascade-spec/ packages/cascade-reflection/ packages/cascade-compiler/ packages/cascade-std/
```

如果验证通过，我们就可以提交代码了。这将标志着 Cascade PIDL 重构的圆满完成。
