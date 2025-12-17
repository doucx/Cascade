简要回答
当前的 `Engine` 实现理论上已经支持将 `.map()` 的结果直接传递给下游任务。为了确认这一点并决定是否需要调整路线图，我将先创建一个针对性的测试用例。如果测试通过，说明现有的递归执行模型已经满足需求，该路线图步骤可能是不必要的优化或基于过时假设。

## [WIP] test(runtime): 验证 map 结果直接传递给下游任务

### 用户需求
验证 Cascade 当前是否支持将 `.map()` 操作生成的 `MappedLazyResult` 直接作为参数传递给下游聚合任务（如 `sum`），并正确解析为结果列表。

### 评论
路线图的第二部分假设此操作目前会失败。我需要通过“实地考察”来验证这个假设。如果测试通过，我们将节省大量重构时间；如果失败，我们将获得明确的调试线索来实现该修复。

### 目标
编写并运行一个测试，该测试构建一个 `Source -> Map -> Reduce` 的工作流，验证端到端的执行正确性。

### 基本原理
实践是检验真理的唯一标准。在着手修改核心图构建逻辑之前，先通过测试确立基线行为是明智的工程实践。

### 标签
#intent/tooling #flow/draft #priority/high #comp/tests #concept/map-reduce #scope/core #ai/instruct #task/domain/testing #task/object/map-integration #task/action/verification #task/state/continue

---

### Script

#### Acts 1: 创建验证测试
创建一个新的测试文件 `tests/runtime/test_map_reduce_integration.py`。

~~~~~act
write_file
tests/runtime/test_map_reduce_integration.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

@cs.task
def generate_range(n: int) -> list[int]:
    return list(range(n))

@cs.task
def double(x: int) -> int:
    return x * 2

@cs.task
def sum_all(numbers: list[int]) -> int:
    return sum(numbers)

@pytest.mark.asyncio
async def test_map_reduce_pipeline():
    """
    Test the flow: generate -> map(double) -> sum_all.
    This verifies if a MappedLazyResult can be passed directly to a downstream task
    and is correctly resolved as a list of values.
    """
    # 1. Generate dynamic input: [0, 1, 2, 3, 4]
    nums = generate_range(5)
    
    # 2. Map: [0, 2, 4, 6, 8]
    doubled_nums = double.map(x=nums)
    
    # 3. Reduce: 20
    # Here doubled_nums is a MappedLazyResult. 
    # The engine must resolve this to [0, 2, 4, 6, 8] before calling sum_all.
    total = sum_all(numbers=doubled_nums)
    
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(total)
    
    assert result == 20
~~~~~

### 下一步建议
根据测试结果：
1.  **如果通过**: 说明现有的 Engine 逻辑（递归执行并返回列表）已经能够处理这种情况。我们可以跳过“隐式 Gather 节点”的开发，直接进入路线图的下一部分（第二部分：统一 Provider API）。
2.  **如果失败**: 分析错误原因，如果是类型错误（传入了 `MappedLazyResult` 对象而不是列表），则按照原计划实施 `GraphBuilder` 的修改。
