You've correctly identified a subtle but crucial bug in our test's mock function. Your analysis is spot on: the `mock_worker` function's signature does not match the actual physical protocol enforced by the `Reactor` and `Bleacher`.

The `KeyError: 'x'` occurs because our `mock_worker` function makes a wrong assumption about the data it receives. Let's trace the flow of energy (Tokens):

1.  **Bleacher's Job**: The `standard_bleacher` receives multiple input tokens (e.g., one for argument `x`, one for resource `gpu`). It "bleaches" them, meaning it gathers all the *data* arguments' payloads into a single dictionary: `{'x': 10}`.
2.  **Encapsulation**: It then wraps this dictionary into a *single* `Token` and emits it on its `worker_input` output port. The token looks like this: `Token(payload={'x': 10})`.
3.  **Transport**: This single token flows through `D_worker_in` and arrives at the `WorkerNode`'s `worker_input` port.
4.  **Reactor's Delivery**: The `Reactor` delivers a dictionary of all tokens that arrived at the `WorkerNode`. Since the `WorkerNode` only has one input port named `worker_input`, the dictionary it passes to the callable (`mock_worker`) is:
    ```python
    {'worker_input': Token(payload={'x': 10})}
    ```
5.  **The Bug**: Our `mock_worker` was written to expect the unpacked arguments directly, i.e., `{'x': Token(...) }`. It tried to access `inputs['x']`, but the only key available is `'worker_input'`.

The `Bleacher` acts as a mail sorter: it gathers all the letters (arguments) and puts them into a single envelope (`worker_input` Token). Our `mock_worker` was trying to read the letter 'x' directly from the mailbox, when it should have opened the envelope first.

### [WIP] fix(test): 修正 mock_worker 以遵循物理协议

#### 用户需求
`test_resource_backpressure.py` 中的 `mock_worker` 函数必须被修正，以正确地从 `worker_input` 端口的 Token 中解包其参数，从而遵循 VM 的物理执行协议。

#### 评论
这是一个非常有价值的 Bug。它强制我们确保测试代码（尤其是 Mock）与系统的真实行为（物理协议）保持 100% 一致。一个不遵循协议的 Mock 会产生误导性的结果，并隐藏真实的集成问题。这次修复将使我们的背压测试更加健壮和准确。

#### 目标
1.  修改 `mock_worker` 函数。
2.  使其首先从 `inputs` 字典中获取 `'worker_input'` Token。
3.  然后从该 Token 的 `payload` 中提取真正的参数 `'x'`。
4.  确保测试 `test_resource_backpressure` 通过。

#### 基本原理
物理执行三连体（Triad）中的 `WorkerNode` (`F_exec`) 与外界的交互协议是固定的：它总是通过一个名为 `worker_input` 的端口接收一个包含了所有业务参数的字典。我们的 Mock 必须遵守这个硬性接口，才能正确地模拟一个真实的 Worker。

#### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/vm #concept/protocol #scope/dx #ai/instruct #task/domain/core #task/object/reactor-atomicity #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `mock_worker` 的实现

我们将更新 `test_resource_backpressure.py` 中的 `mock_worker`，使其正确解包。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
def mock_worker(inputs: Dict[str, Token]) -> Dict[str, Token]:
    # Simulate work
    val = inputs["x"].payload
    return {"worker_result": Token(payload=val + 1)}
~~~~~
~~~~~python.new
def mock_worker(inputs: Dict[str, Token]) -> Dict[str, Token]:
    # The WorkerNode receives a single token on its 'worker_input' port.
    # The payload of this token is the dictionary of actual arguments.
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload

    # Simulate work based on the unpacked payload
    val = worker_payload["x"]  # The payload is the raw value, not another Token
    return {"worker_result": Token(payload=val + 1)}
~~~~~

### 下一步建议
这个 `KeyError` 是 `Phase 4.2` 中最后一个已知的障碍。在应用此补丁后，`test_resource_backpressure` 应该会成功，标志着我们已经完整地实现了基于拓扑的资源背压。

我建议立即执行此计划，然后运行整个 `cascade-vm` 的测试套件，以确保我们的修改没有引入任何回归问题。之后，我们就可以正式结束 `Phase 4`。
