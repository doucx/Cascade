## [WIP] fix(tests): Adapt `mock_worker` in contention test to Ref Protocol

### 错误分析

**错误**: `TypeError: 'Ref' object cannot be interpreted as an integer`
**位置**: `packages/cascade-compiler/tests/integration/test_resource_contention.py` 中的 `mock_worker` 函数。
**原因**: 
1.  在 `test_resource_scarcity_topology_and_execution` 中，任务的 `duration` 参数通过 `const_probe` 被转换为一个 `Ref` 对象。
2.  `standard_bleacher` 将这个 `Ref` 包装在 `worker_input` 的 payload 字典中。
3.  `mock_worker` 直接从 payload 中取出 `duration` 并传递给 `time.sleep()`。
4.  由于 `duration` 是一个 `Ref` 而不是 `float/int`，`time.sleep` 崩溃。

**修复方案**: 
在 `mock_worker` 中添加对 `Ref` 的解包逻辑，优先读取 `meta['scalar_value']`。

### 用户需求
修复集成测试中的类型错误，确保资源竞争压力测试能正常运行。

### 评论
这再次验证了架构迁移中“数据主权”变更的影响。Mock 代码必须与物理层的真实数据契约保持同步。虽然手动修复这些 Mock 很繁琐，但它揭示了我们在 `Ref` 协议设计上的正确性：标量提升确实为 Kernel 级别的操作提供了必要的数据，而无需触发昂贵的 I/O。

### 目标
修改 `packages/cascade-compiler/tests/integration/test_resource_contention.py` 中的 `mock_worker`，使其能够识别并解包 `duration` 引用。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/contention-test #task/action/fix-mock-payload #task/state/continue

---

### Script

#### Acts 1: 适配 `test_resource_contention.py` 中的 `mock_worker`

我们将添加一个通用的 `_extract_val` 逻辑，以便 Mock 能够透明地处理 `Ref`。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


@task
def resource_heavy_task(duration: float = 0.01):
    # Simulate work
    import time

    time.sleep(duration)
    return "Done"


# Mock Worker
def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    trace = worker_input_token.trace

    # Simulate execution duration
    payload = worker_input_token.payload
    duration = payload.get("duration", 0.0)

    # We cheat a bit and sleep async here to allow reactor to switch contexts
~~~~~
~~~~~python.new
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe
from cascade.spec.physical.object import Ref


@task
def resource_heavy_task(duration: float = 0.01):
    # Simulate work
    import time

    time.sleep(duration)
    return "Done"


# Mock Worker
def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    trace = worker_input_token.trace

    # Simulate execution duration
    payload = worker_input_token.payload
    duration = payload.get("duration", 0.0)
    
    # Adapt to Ref-Based Architecture
    if isinstance(duration, Ref):
        duration = duration.meta.get("scalar_value", 0.0)

    # We cheat a bit and sleep async here to allow reactor to switch contexts
~~~~~

### 下一步建议

1.  **全面回归测试**: 在修复了这两个关键的 Mock 错误后，请再次运行 `pytest`。
2.  **性能观测**: 如果测试通过，你可以观察 `test_resource_scarcity_topology_and_execution` 的运行时间。由于我们激活了同步内核，它应该比之前稍快。
3.  **正式进入 Phase 4**: 随着执行层的基本稳固，我们可以开始考虑 `Reactor` 的进一步进化，特别是如何更优雅地处理 `Ref` 的生命周期和垃圾回收。
