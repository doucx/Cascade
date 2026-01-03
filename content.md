好的，我来分析这个错误。

这是一个非常典型的异步测试问题，表面上是 `TimeoutError`，但根源在于一个被“吞噬”的同步异常。你的诊断是正确的，我们必须深入分析日志。

## [WIP] fix(std): 修正 `standard_observer` 的函数签名以匹配 Reactor 协议

### 错误分析

**根本原因**: 测试 `test_event_driven_ping_pong` 超时的直接原因是 `runner.wait_for_event` 永远没有从 `self.event_queue` 中等到任何事件。而队列为空的根本原因，在捕获的日志中清晰可见：

```
ERROR    cascade.vm.reactor:reactor.py:174 Error executing task global.observability.observer: standard_observer() got multiple values for argument 'queue'
```

`Reactor` 在后台的循环中尝试执行 `standard_observer` 节点时，程序崩溃了。由于这个崩溃发生在 `asyncio.create_task` 创建的后台任务中，它没有直接让测试失败，而是“静默”地阻止了事件的产生，最终导致了主流程的超时。

**技术细节**:
1.  **Reactor 的调用协议**: `Reactor` 执行任何函数节点时，都严格使用 `func(input_data, node)` 的签名。
2.  **`EventDrivenRunner` 的注入**: 我们的 `Runner` 使用 `functools.partial(standard_observer, queue=self.event_queue)` 来创建一个新的可调用对象，意图注入 `queue`。
3.  **`standard_observer` 的旧签名**: 它被定义为 `async def standard_observer(inputs: Dict[str, Token], queue: Queue) -> None:`。它只有两个参数。
4.  **调用冲突**: 当 `Reactor` 调用 `partial` 对象时，Python 尝试将 `Reactor` 提供的参数 `(input_data, node)` 和 `partial` 预设的关键字参数 `queue=...` 映射到 `standard_observer` 的签名上。
    *   `inputs` (位置 1) 接收了 `input_data`。
    *   `queue` (位置 2) 接收了 `node`。
    *   然后 Python 发现还有一个关键字参数 `queue=...` 也要赋值给 `queue` 参数。
    *   因此，`queue` 参数被赋值了两次，导致了 `TypeError: got multiple values for argument 'queue'`。

**解决方案**:
所有由 `Reactor` 调度的函数都**必须**遵守 `(inputs, node)` 的基本签名。为了注入额外的上下文（如 `queue`），我们应该使用关键字专用参数 (`keyword-only argument`)。

我们将修改 `standard_observer` 的签名，使其符合 Reactor 协议，同时允许通过 `partial` 安全地注入 `queue`。

### 用户需求
修复 `standard_observer` 函数，使其能够在 `EventDrivenRunner` 中被正确调用，从而解除测试的死锁问题。

### 评论
这个 Bug 暴露了 `cascade-std` 中一个组件与 `cascade-vm` 物理执行协议之间的不一致性。修复它不仅能让测试通过，更重要的是保证了标准库（`std`）的所有组件都严格遵守了虚拟机的物理定律，这对于系统的稳定性和可预测性至关重要。

### 目标
1.  修改 `cascade-std/src/cascade/std/triad/observer.py` 中 `standard_observer` 的函数签名。
2.  重新运行测试，确认 `EventTimeoutError` 已解决。

### 基本原理
通过将 `queue` 参数变为关键字专用参数，我们使得函数签名在位置上与 `Reactor` 的 `(inputs, node)` 调用兼容，同时保留了一个专用的“通道”用于通过 `functools.partial` 进行依赖注入。

### 标签
#intent/fix #flow/ready #priority/high #comp/std #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/harness #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `standard_observer` 的函数签名

我们将修改 `observer.py` 文件，为 `standard_observer` 函数添加 `node` 参数，并将 `queue` 变为关键字专用参数。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/observer.py
~~~~~
~~~~~python.old
async def standard_observer(inputs: Dict[str, Token], queue: Queue) -> None:
    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    await queue.put(event)
~~~~~
~~~~~python.new
from cascade.spec.physics import Token, PhysicsNode


async def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, *, queue: Queue
) -> None:
    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    await queue.put(event)
~~~~~

#### Acts 2: 修正 `observer.stitcher.yaml` 文档

文档也需要更新以反映新的签名。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/observer.stitcher.yaml
~~~~~
~~~~~yaml.old
"standard_observer": |-
  The standard implementation for an Observability Node (F_obs).

  It consumes a Token from a lifecycle data node (D_life), converts its
  trace information into a structured ObservedEvent, and puts it onto an
  external queue for telemetry systems.

  This function does not return anything; its purpose is to create a side-effect.

  Args:
      inputs: A dictionary mapping input port names to their corresponding Tokens.
              Expected port: 'event_token'.
      queue: The external queue to which the ObservedEvent will be sent.
~~~~~
~~~~~yaml.new
"standard_observer": |-
  The standard implementation for an Observability Node (F_obs).

  It consumes a Token from a lifecycle data node (D_life), converts its
  trace information into a structured ObservedEvent, and puts it onto an
  external queue for telemetry systems.

  This function does not return anything; its purpose is to create a side-effect.

  Args:
      inputs: A dictionary mapping input port names to their corresponding Tokens.
              Expected port: 'event_token'.
      node: The PhysicsNode instance being executed.
      queue: (Keyword-only) The external queue to which the ObservedEvent will be sent.
             This is typically injected by a test harness like EventDrivenRunner.
~~~~~

### 下一步建议
我们已经修复了 `standard_observer` 的签名问题。现在，`EventDrivenRunner` 应该能够正常工作。请重新运行测试。

如果测试通过，我们就可以自信地使用这个新的测试工具来重构更多现有的、基于 `step()` 的脆弱测试，并最终用它来验证 `cascade-compiler` 生成的完整物理图的行为。
