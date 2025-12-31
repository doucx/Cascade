好的，我已经定位到目标测试文件。根据 Phase 5.1 的规划，我们将通过取消跳过该测试来建立 TDD 的 **RED** 状态，从而驱动 `VMExecutionStrategy` 向基于 `Reactor` 的事件驱动架构演进。

## [WIP] test: 取消跳过 VMStrategy TCO 集成测试以进入 RED 状态

### 用户需求
取消 `packages/cascade-engine/tests/integration/test_vm_strategy_tco.py` 文件的跳过标记，使 TCO 相关的集成测试参与运行。

### 评论
这是 Phase 5 “策略层对齐”的第一步。目前该测试被跳过，是因为在之前的“焦土式重构”中，我们尚未将 `Engine` 的执行策略与新的 `Reactor`（物理引擎）对接。取消跳过将暴露当前策略无法处理递归 `Jump` 的缺陷。

### 目标
移除文件中的 `pytestmark = pytest.mark.skip(...)` 语句。

### 基本原理
遵循 TDD（测试驱动开发）流程，在实现功能前必须先有一个失败的测试（RED）。该测试验证了系统在处理 `cs.Jump` 信号时的正确性，目前的 `VMExecutionStrategy` 实现（如果仍然基于旧的线性 VM）将无法通过此测试。

### 标签
#intent/tooling #flow/ready #priority/high #comp/engine #comp/tests #concept/navigation #scope/dx #ai/instruct #task/domain/engine #task/object/vm-strategy-tco #task/action/unskip #task/state/begin

---

### Script

#### Acts 1: 取消跳过测试文件

我们将修改 `test_vm_strategy_tco.py`，移除顶层的跳过标记。

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_vm_strategy_tco.py
~~~~~
~~~~~python.old
from cascade.adapters.solvers.native import NativeSolver
from cascade.spec.jump import Jump

pytestmark = pytest.mark.skip("Primitives not yet aligned with scorched earth refactor")

@pytest.mark.asyncio
~~~~~
~~~~~python.new
from cascade.adapters.solvers.native import NativeSolver
from cascade.spec.jump import Jump


@pytest.mark.asyncio
~~~~~

### 下一步建议
1.  **运行测试**: 执行 `pytest packages/cascade-engine/tests/integration/test_vm_strategy_tco.py`，确认测试如期失败。
2.  **实现 Green 阶段**: 按照重构计划，彻底重写 `cascade.runtime.strategies.vm.VMExecutionStrategy`，使其采用 “编译 -> 加载到 Reactor -> 注入令牌 -> 运行 Reactor” 的新范式。
