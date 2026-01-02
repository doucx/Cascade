好的，我们继续进行架构加固。

这个计划将执行您在战略审查中确定的第二个修正项：统一 `Reactor` 与其调度的物理指令之间的 API 契约。我们将移除 `Reactor` 中的兼容性回退逻辑，并相应地更新所有测试中的 Mock 函数，以消除技术债务并增强系统的健壮性。

## [WIP] refactor(vm): 统一 Reactor 中的指令签名并更新测试

### 错误分析

战略审查发现 `cascade.vm.reactor.Reactor._fire` 方法中存在一个 `try-except TypeError` 块。这个代码块是为了兼容旧的、只接受 `inputs` 参数的 Mock 函数而设计的回退机制。

这造成了几个问题：
1.  **技术债务**: 它是一个临时的权宜之FIX，使核心代码变得复杂。
2.  **API 契约不一致**: 它允许物理指令存在两种不同的签名 (`(inputs)` 和 `(inputs, node)`)，这违反了单一、清晰的接口原则。
3.  **隐藏 Bug**: 它可能会掩盖由于签名不匹配而本应暴露的 `TypeError`，使调试更加困难。

### 用户需求

根据战略审查的结论，执行“统一 Reactor 中的指令签名”的建议。

### 评论

这是一个非常健康的重构步骤。通过移除兼容性逻辑并强制执行统一的 API 契约，我们简化了 `Reactor` 的核心逻辑，使其更加健壮和可预测。这确保了所有在物理引擎中执行的代码单元都遵循相同的规则，降低了未来出错的可能性，并提升了开发者体验（DX）。

### 目标

1.  **重构 Reactor**: 移除 `packages/cascade-vm/src/cascade/vm/reactor.py` 中 `_fire` 方法的 `try-except` 回退逻辑。
2.  **更新测试**: 修改所有测试用例中的 Mock 指令函数，使其完全符合标准的 `(inputs, node)` 签名。

### 基本原理

严格的接口统一性是构建可靠系统的基石。我们将通过移除 `Reactor` 中的“防御性”编程，转而要求其所有协作者（即物理指令）严格遵守其 API 契约。这将系统的正确性保证从运行时的异常处理，前移到了更早的静态定义阶段，是一种更优秀的设计。

### 标签

#intent/refine #flow/ready #priority/high
#comp/vm #comp/tests #scope/dx
#task/domain/architecture #task/object/instruction-signature #task/action/unification
#task/state/continue

---

### Script

#### Acts 1: 重构 Reactor._fire 以强制执行统一签名

我们将修改 `reactor.py`，移除 `_fire` 方法中的 `try-except` 块，只保留标准的双参数调用。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        # We pass the node instance as the second argument to the instruction
        # to allow access to static port definitions (PortDef).
        # Note: Some simple mocks might not accept the second arg, but standard instructions do.
        # Ideally, we should unify the signature. For now, we assume standard signature.
        try:
            result_tokens: Dict[str, Token] = await self.executor.submit(
                func, (input_data, node)
            )
        except TypeError:
            # Fallback for legacy/mock functions that only take (inputs)
            # This is a temporary bridge for tests using simple mocks like 'noop'
            result_tokens: Dict[str, Token] = await self.executor.submit(
                func, (input_data,)
            )
~~~~~
~~~~~python.new
        # We pass the node instance as the second argument to the instruction
        # to allow access to static port definitions (PortDef).
        result_tokens: Dict[str, Token] = await self.executor.submit(
            func, (input_data, node)
        )
~~~~~

#### Acts 2: 更新测试中的 Mock 指令签名

现在，我们将遍历所有测试文件，将那些旧的、单参数的 Mock 函数更新为符合新契约的双参数形式。

首先更新 `test_observability_congestion.py`。
~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
def noop_producer(inputs):
    return {"out": Token(payload="event")}
~~~~~
~~~~~python.new
def noop_producer(inputs, node):
    return {"out": Token(payload="event")}
~~~~~

更新 `test_branching.py`。
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python.old
def switch_logic(inputs: Dict[str, Token]) -> Dict[str, Token]:
    in_token = inputs["in"]
    direction = in_token.payload

    if direction == "path_a":
        return {"out": Token(payload="Data A", tag="A")}
    else:
        return {"out": Token(payload="Data B", tag="B")}
~~~~~
~~~~~python.new
def switch_logic(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    in_token = inputs["in"]
    direction = in_token.payload

    if direction == "path_a":
        return {"out": Token(payload="Data A", tag="A")}
    else:
        return {"out": Token(payload="Data B", tag="B")}
~~~~~

更新 `test_ping_pong.py`。
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
def simple_increment(inputs: Dict[str, Token]) -> Dict[str, Token]:
    # Extract
    in_token = inputs["value"]
    val = in_token.payload
~~~~~
~~~~~python.new
def simple_increment(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    # Extract
    in_token = inputs["value"]
    val = in_token.payload
~~~~~

更新 `test_resource_backpressure.py`。
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
def mock_worker(inputs: Dict[str, Token]) -> Dict[str, Token]:
    # The WorkerNode receives a single token on its 'worker_input' port.
    # The payload of this token is the dictionary of actual arguments.
~~~~~
~~~~~python.new
def mock_worker(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    # The WorkerNode receives a single token on its 'worker_input' port.
    # The payload of this token is the dictionary of actual arguments.
~~~~~

最后，更新 `test_reactor.py`。
~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
# Dummy function for testing
def noop(inputs):
    # Echos back a generic result token on 'out' port
    return {"out": Token(payload="result")}
~~~~~
~~~~~python.new
# Dummy function for testing
def noop(inputs, node):
    # Echos back a generic result token on 'out' port
    return {"out": Token(payload="result")}
~~~~~

### 下一步建议

我们已经成功地加固了 VM 的核心 API 契约。至此，战略审查中发现的两个最关键的底层问题都已解决。

现在，底层的物理引擎和编译器后端已经非常坚实。我建议我们正式将工作重心推进到 **阶段 5: 全系统集成 (System Integration)**。

这主要意味着我们需要开始构建 `cascade-compiler` 的前端，即实现将用户编写的、基于 `LazyResult` 的工作流定义，完整地翻译成 `GraphIR` 的逻辑。这将是打通从用户代码到物理执行的最后一公里。

如果您同意，我们可以开始着手设计并实现这个前端翻译器。
