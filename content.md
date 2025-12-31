## [WIP] test(engine): 创建真实执行的集成测试 (RED)

### 用户需求
开始 TDD 集成周期的 RED 阶段。目的是暴露新管线中“函数解析”和“参数传递”等核心断点。我们需要创建一个真实的、非 Mock 的集成测试，强制 `Engine` 使用新编译器管线运行一个简单的工作流。

### 评论
这个测试将复用 `test_e2e_linear_workflow` 的逻辑，但通过 `use_vm=True` 强制激活新代码路径。由于之前提到的 `Backend` 中 `func=None` 的问题，我们预期该测试会因 `ValueError: Instruction for task ... has no function to call` 或类似的错误而失败。

### 目标
1.  创建 `packages/cascade-engine/tests/integration/test_real_execution.py`。
2.  实现 `test_linear_workflow_with_vm`，它包含一个真实的 2 节点任务链，并断言其输出。
3.  确保测试失败，且失败原因符合预期（不是因为环境配置错误，而是因为实现缺失）。

### 基本原理
真正的集成测试是验证系统的最终裁判。通过移除 mocks，我们将直接面对新旧系统接口不匹配的现实。这符合“焦土政策”中“建立真理”的原则。

### 标签
#intent/tooling #flow/ready #priority/high #comp/engine #concept/integration #scope/core #ai/instruct #task/domain/refactor #task/object/integration-test #task/action/create #task/state/begin

---

### Script

#### Acts 1: 创建真实执行测试

创建一个新的测试文件，不使用 patch，直接运行 Engine。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_real_execution.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus

@pytest.mark.asyncio
async def test_linear_workflow_with_vm():
    """
    Verifies that the new compiler pipeline can execute a real, 2-step workflow.
    This test is expected to FAIL initially because the Backend/VM does not yet
    handle function resolution or argument passing correctly.
    """
    # 1. Define tasks
    @cs.task
    def get_number() -> int:
        return 41

    @cs.task
    def add_one(x: int) -> int:
        return x + 1

    # 2. Build workflow
    workflow = add_one(get_number())

    # 3. Setup Engine with minimal dependencies
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # 4. Run with VM enabled
    # We expect this to fail, likely inside the VM when it tries to call a function
    # that hasn't been resolved properly.
    result = await engine.run(workflow, use_vm=True)

    # 5. Assert final result
    assert result == 42
~~~~~
