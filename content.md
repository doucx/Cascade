好的，我们遇到了预料之中的测试失败。由于我们在 Phase 1 和 Phase 2 中移除了 `probe` 组件并修改了编译器，所有依赖旧 `probe` 架构的测试都已失效。

我将执行一个修复计划来清理这些过时的测试，使其与新的、更纯粹的物理架构保持一致。

## [WIP] fix: 移除已废弃的 Probe 组件测试并修复集成测试

### 错误分析
测试失败的根本原因是我们在之前的步骤中彻底删除了 `packages/cascade-std/src/cascade/std/probe` 模块。
1.  **直接原因**: 所有 `import ... from cascade.std.probe` 语句现在都会导致 `ModuleNotFoundError`。
2.  **根本原因**: 测试代码尚未更新，以反映编译器不再生成 `F_probe` 节点，以及 `D_const` 节点现在直接连接到其目标（如 `Bleacher` 或 `Requestor`）的新架构。

### 用户需求
根据 TDD 流程，我们需要修复因架构重构而损坏的测试套件，确保系统在新的架构下行为正确。

### 评论
这是一个健康的、预料之中的失败。它验证了我们的重构确实移除了旧的组件。现在的任务是让测试套件“跟上”架构的演进。这主要是一个清理工作：删除不再相关的测试，并更新集成测试中的 `function_map` 和执行流程模拟，以匹配新的、更精简的物理拓扑。

### 目标
1.  删除所有针对已移除 `probe` 组件的单元测试。
2.  更新所有集成测试，移除对 `const_probe` 的导入和使用。
3.  修正 `test_resource_backpressure` 中对 Reactor `step` 的模拟，以匹配简化的执行流程。

### 基本原理
测试必须反映代码的当前状态。由于 `F_probe` 已从编译器的输出中移除，测试辅助代码（特别是 `function_map` 的构建）和对执行流程的断言也必须相应更新。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #comp/compiler #comp/vm #ai/instruct #task/domain/vm #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 删除过时的 Probe 单元测试

这些测试是针对一个已不存在的模块，因此需要被完全删除。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-std/tests/unit/probe
~~~~~

#### Acts 2: 修复 `test_resource_contention.py`

移除对 `const_probe` 的依赖。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
# Standard IC imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe
from cascade.spec.physical.object import Ref
~~~~~
~~~~~python.new
# Standard IC imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.spec.physical.object import Ref
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
        elif "reclaimer" in node_id:
            func_map[node_id] = debug_wrapper(discrete_reclaimer, node.name)
        elif node_id.startswith("req."):
            func_map[node_id] = debug_wrapper(resource_requestor, node.name)
        elif node_id.startswith("probe.const."):
            func_map[node_id] = debug_wrapper(const_probe, node.name)
        elif "observability" in node_id:
            func_map[node_id] = standard_observer
~~~~~
~~~~~python.new
        elif "reclaimer" in node_id:
            func_map[node_id] = debug_wrapper(discrete_reclaimer, node.name)
        elif node_id.startswith("req."):
            func_map[node_id] = debug_wrapper(resource_requestor, node.name)
        elif "observability" in node_id:
            func_map[node_id] = standard_observer
~~~~~

#### Acts 3: 修复 `test_ref_architecture.py`

移除对 `const_probe` 的依赖。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.probe.const import const_probe
~~~~~
~~~~~python.new
# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
        elif "observer" in node_id:
            func_map[node_id] = standard_observer
        elif node_id.startswith("probe.const."):
            func_map[node_id] = const_probe
        # All user workers are now implemented by the dispatcher
        elif node_id in assembly.symbol_table:
~~~~~
~~~~~python.new
        elif "observer" in node_id:
            func_map[node_id] = standard_observer
        # All user workers are now implemented by the dispatcher
        elif node_id in assembly.symbol_table:
~~~~~

#### Acts 4: 修复 `test_resource_backpressure.py`

移除对 `const_probe` 的依赖，并修正执行流程模拟。由于 `F_req` 现在由已预置 Token 的 `D_const` 直接驱动，它将在第一个 `step` 中就被激发，不再需要之前模拟的两个 `step`。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe
from cascade.spec.physical.object import Ref
~~~~~
~~~~~python.new
# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.spec.physical.object import Ref
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
        elif "reclaimer" in node_id:
            func_map[node_id] = discrete_reclaimer
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
        elif node_id.startswith("probe.const."):
            func_map[node_id] = const_probe
        elif "observability" in node_id:
            func_map[node_id] = noop_observer
~~~~~
~~~~~python.new
        elif "reclaimer" in node_id:
            func_map[node_id] = discrete_reclaimer
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
        elif "observability" in node_id:
            func_map[node_id] = noop_observer
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # --- SIMULATION ---
    # The new graph has many more steps due to Probe -> Req -> Broker -> Bleacher

    # Round 1: Probes fire (providing Amount and X)
    reactor.step()

    # Round 2: Requestors fire (sending Req Tokens to Buffer)
    reactor.step()

    # Check Buffer state
    req_buffer_id = "buffer.req.gpu"
    assert memory.get_count(req_buffer_id) == 2  # Both requests are in buffer
~~~~~
~~~~~python.new
    # --- SIMULATION ---
    # With direct D_const -> F_req wiring, requestors fire on the first step.

    # Step 1: Requestors for both tasks fire, populating the request buffer.
    reactor.step()

    # Check Buffer state
    req_buffer_id = "buffer.req.gpu"
    assert memory.get_count(req_buffer_id) == 2  # Both requests are in buffer
~~~~~

### 下一步建议
测试套件现已与 Phase 1 和 2 的架构变更对齐。我们可以继续执行路线图的 **Phase 3: 策略层重构**，这是将所有新组件粘合在一起形成完整端到端流程的关键一步。
